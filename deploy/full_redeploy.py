"""
全量重新部署 Taxja 到 Hetzner VPS
- 停止所有容器
- 删除 postgres volume（全新数据库）
- 上传最新代码
- 重建所有容器
- init.sql 自动建库 + seed data
- seed tax configs
- 创建测试账号
- 健康检查
"""
import paramiko
import os
import time
import sys

SERVER_IP = '46.62.227.62'
SSH_KEY = r'C:\Users\yk1e25\taxja-server-nopass'
REMOTE_BASE = '/opt/taxja'

def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_IP, username='root', key_filename=SSH_KEY, timeout=30)
    return client

def run(client, cmd, timeout=120):
    print(f'  $ {cmd[:120]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[-10:]:
            print(f'    {line}')
    if err and 'warning' not in err.lower() and 'CSRF' not in err:
        for line in err.split('\n')[-5:]:
            print(f'    ERR: {line}')
    return out

def upload_dir(sftp, local_dir, remote_dir, run_fn=None, client=None):
    """Recursively upload a directory."""
    count = 0
    for root, dirs, files in os.walk(local_dir):
        rel = os.path.relpath(root, local_dir).replace('\\', '/')
        remote_root = remote_dir if rel == '.' else f'{remote_dir}/{rel}'
        try:
            sftp.mkdir(remote_root)
        except:
            pass
        for f in files:
            local_path = os.path.join(root, f)
            remote_path = f'{remote_root}/{f}'
            sftp.put(local_path, remote_path)
            count += 1
    return count


def main():
    print(f'=== 全量重新部署 Taxja ===')
    print(f'服务器: {SERVER_IP}')
    print()

    client = ssh_connect()
    print('已连接\n')

    # ── Step 1: 停止所有容器 ──
    print('=' * 60)
    print('STEP 1: 停止所有容器并删除数据库')
    print('=' * 60)
    run(client, f'cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml down -v 2>&1 || true')
    run(client, 'docker stop $(docker ps -aq) 2>/dev/null; docker rm $(docker ps -aq) 2>/dev/null || true')
    # 删除 postgres volume
    run(client, 'docker volume rm taxja_postgres_data 2>/dev/null || docker volume rm opt_taxja_postgres_data 2>/dev/null || true')
    print('  容器已停止，数据库 volume 已删除\n')

    # ── Step 2: 上传后端代码 ──
    print('=' * 60)
    print('STEP 2: 上传后端代码')
    print('=' * 60)
    run(client, f'rm -rf {REMOTE_BASE}/backend/app {REMOTE_BASE}/backend/alembic')
    run(client, f'mkdir -p {REMOTE_BASE}/backend')

    sftp = client.open_sftp()

    # Upload backend essentials
    for f in ['requirements.txt', 'Dockerfile', 'pyproject.toml', 'alembic.ini', '.dockerignore']:
        local = f'backend/{f}'
        if os.path.exists(local):
            sftp.put(local, f'{REMOTE_BASE}/backend/{f}')

    n = upload_dir(sftp, 'backend/app', f'{REMOTE_BASE}/backend/app')
    print(f'  backend/app: {n} files')
    n = upload_dir(sftp, 'backend/alembic', f'{REMOTE_BASE}/backend/alembic')
    print(f'  backend/alembic: {n} files')
    n = upload_dir(sftp, 'backend/scripts', f'{REMOTE_BASE}/backend/scripts')
    print(f'  backend/scripts: {n} files')

    # ── Step 3: 上传前端 dist + nginx.conf ──
    print('\n' + '=' * 60)
    print('STEP 3: 上传前端')
    print('=' * 60)
    run(client, f'rm -rf {REMOTE_BASE}/frontend/dist')
    run(client, f'mkdir -p {REMOTE_BASE}/frontend')
    n = upload_dir(sftp, 'frontend/dist', f'{REMOTE_BASE}/frontend/dist')
    print(f'  frontend/dist: {n} files')
    sftp.put('frontend/nginx.conf', f'{REMOTE_BASE}/frontend/nginx.conf')
    print('  nginx.conf uploaded')

    # ── Step 4: 上传 init.sql ──
    print('\n' + '=' * 60)
    print('STEP 4: 上传 init.sql')
    print('=' * 60)
    run(client, f'mkdir -p {REMOTE_BASE}/docker/init-db')
    sftp.put('docker/init-db/init.sql', f'{REMOTE_BASE}/docker/init-db/init.sql')
    print('  init.sql uploaded')

    # ── Step 5: 写 docker-compose.server.yml ──
    print('\n' + '=' * 60)
    print('STEP 5: 写 docker-compose.server.yml')
    print('=' * 60)

    compose = """services:
  postgres:
    image: postgres:15-alpine
    container_name: taxja-postgres
    restart: always
    environment:
      POSTGRES_USER: taxja
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: taxja
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init-db/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U taxja"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: taxja-redis
    restart: always
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    container_name: taxja-minio
    restart: always
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: taxja-backend
    restart: always
    env_file: .env.prod
    environment:
      POSTGRES_SERVER: postgres
      REDIS_HOST: redis
      MINIO_ENDPOINT: minio:9000
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: taxja-celery-worker
    restart: always
    env_file: .env.prod
    environment:
      POSTGRES_SERVER: postgres
      REDIS_HOST: redis
      MINIO_ENDPOINT: minio:9000
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2 --max-tasks-per-child=50 -Q default,ocr,ml

  nginx:
    image: nginx:alpine
    container_name: taxja-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
      - ./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend

volumes:
  postgres_data:
  redis_data:
  minio_data:
"""
    with sftp.open(f'{REMOTE_BASE}/docker-compose.server.yml', 'w') as f:
        f.write(compose)
    print('  docker-compose.server.yml written')

    sftp.close()

    # ── Step 6: 构建并启动所有容器 ──
    print('\n' + '=' * 60)
    print('STEP 6: 构建并启动容器 (需要几分钟)')
    print('=' * 60)
    run(client,
        f'cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build 2>&1 | tail -20',
        timeout=600)

    print('  等待 30 秒让服务启动...')
    time.sleep(30)
    run(client, f'cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml ps')

    # ── Step 7: Seed tax configs ──
    print('\n' + '=' * 60)
    print('STEP 7: Seed tax configs')
    print('=' * 60)
    run(client,
        'docker exec taxja-backend python3 -c "'
        'import sys; sys.path.insert(0, \\\"/app\\\"); '
        'from app.db.seed_tax_config import seed_tax_configs; '
        'seed_tax_configs()'
        '" 2>&1 | tail -5')

    # ── Step 8: 创建测试账号 ──
    print('\n' + '=' * 60)
    print('STEP 8: 创建测试账号 admin@taxja.at')
    print('=' * 60)

    create_user_script = r'''
import sys
sys.path.insert(0, "/app")
from app.db.base import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.credit_balance import CreditBalance
from app.services.trial_service import TrialService
from datetime import datetime, timedelta

db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == "admin@taxja.at").first()
    if existing:
        print(f"User already exists: id={existing.id}")
    else:
        user = User(
            email="admin@taxja.at",
            name="Admin",
            hashed_password=get_password_hash("Admin123!"),
            user_type="employee",
            language="de",
            is_admin=True,
            email_verified=True,
            trial_used=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"User created: id={user.id}")

        # Activate trial
        try:
            trial_svc = TrialService(db)
            sub = trial_svc.activate_trial(user.id)
            print(f"Trial activated, expires: {sub.current_period_end}")
        except Exception as e:
            print(f"Trial activation failed: {e}")

        # Create credit balance
        pro_plan = db.query(Plan).filter(Plan.plan_type == PlanType.PRO).first()
        credits = pro_plan.monthly_credits if pro_plan else 200
        cb = CreditBalance(
            user_id=user.id,
            plan_balance=credits,
            topup_balance=0,
            overage_enabled=False,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
        db.add(cb)
        db.commit()
        print(f"Credit balance created: {credits} credits")

    # Show final state
    for u in db.query(User).all():
        sub = db.query(Subscription).filter(Subscription.user_id == u.id).first()
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == u.id).first()
        credits = (cb.plan_balance + cb.topup_balance) if cb else 0
        status = sub.status.value if sub else "none"
        print(f"  {u.email}: sub={status}, credits={credits}")
finally:
    db.close()
'''

    sftp2 = client.open_sftp()
    with sftp2.open('/tmp/create_admin.py', 'w') as f:
        f.write(create_user_script)
    sftp2.close()

    run(client, 'docker cp /tmp/create_admin.py taxja-backend:/tmp/create_admin.py')
    run(client, 'docker exec taxja-backend python3 /tmp/create_admin.py 2>&1')

    # ── Step 9: 健康检查 ──
    print('\n' + '=' * 60)
    print('STEP 9: 健康检查')
    print('=' * 60)
    run(client, 'curl -s http://localhost:8000/api/v1/health | head -3')
    run(client, 'curl -s -o /dev/null -w "nginx: HTTP %{http_code}" http://localhost:80/')
    run(client, 'curl -s -o /dev/null -w "api via nginx: HTTP %{http_code}" http://localhost:80/api/v1/health')

    # Check plans
    run(client, 'docker exec taxja-backend python3 -c "'
        'import sys; sys.path.insert(0, \\\"/app\\\"); '
        'from app.db.base import SessionLocal; '
        'from app.models.plan import Plan; '
        'db = SessionLocal(); '
        '[print(f\\\"  id={p.id} {p.plan_type.value} {p.name} credits={p.monthly_credits}\\\") for p in db.query(Plan).all()]; '
        'db.close()'
        '" 2>&1')

    client.close()
    print('\n' + '=' * 60)
    print('部署完成！访问 https://taxja.at 验证')
    print('测试账号: admin@taxja.at / Admin123!')
    print('=' * 60)


if __name__ == '__main__':
    main()
