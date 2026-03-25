"""
全量重新部署 Taxja - v2 (tar打包上传，速度快)
"""
import paramiko
import os
import time
import tarfile
import tempfile

SERVER_IP = '46.62.227.62'
SSH_KEY = r'C:\Users\yk1e25\taxja-server-nopass'
REMOTE_BASE = '/opt/taxja'

def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_IP, username='root', key_filename=SSH_KEY, timeout=30)
    return client

def run(client, cmd, timeout=120):
    print(f'  $ {cmd[:140]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[-15:]:
            print(f'    {line}')
    if err and 'warning' not in err.lower() and 'CSRF' not in err and 'DEPRECATION' not in err:
        for line in err.split('\n')[-5:]:
            print(f'    ERR: {line}')
    return out

def create_backend_tar():
    """Create tar of backend code (app + alembic + scripts + config files)."""
    tar_path = os.path.join(tempfile.gettempdir(), 'taxja_backend.tar.gz')
    with tarfile.open(tar_path, 'w:gz') as tar:
        for item in ['app', 'alembic', 'scripts']:
            path = os.path.join('backend', item)
            if os.path.exists(path):
                tar.add(path, arcname=item)
        for f in ['requirements.txt', 'Dockerfile', 'pyproject.toml', 'alembic.ini']:
            path = os.path.join('backend', f)
            if os.path.exists(path):
                tar.add(path, arcname=f)
        # .dockerignore
        di = os.path.join('backend', '.dockerignore')
        if os.path.exists(di):
            tar.add(di, arcname='.dockerignore')
    size = os.path.getsize(tar_path)
    print(f'  backend tar: {size/1024/1024:.1f} MB')
    return tar_path

def create_frontend_tar():
    """Create tar of frontend dist."""
    tar_path = os.path.join(tempfile.gettempdir(), 'taxja_frontend.tar.gz')
    with tarfile.open(tar_path, 'w:gz') as tar:
        tar.add('frontend/dist', arcname='dist')
        tar.add('frontend/nginx.conf', arcname='nginx.conf')
    size = os.path.getsize(tar_path)
    print(f'  frontend tar: {size/1024/1024:.1f} MB')
    return tar_path


COMPOSE = """services:
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

def main():
    print('=== 全量重新部署 Taxja (v2 tar) ===')
    print(f'服务器: {SERVER_IP}\n')

    # Step 0: 本地打包
    print('STEP 0: 本地打包')
    print('=' * 60)
    backend_tar = create_backend_tar()
    frontend_tar = create_frontend_tar()

    client = ssh_connect()
    print('已连接\n')

    # Step 1: 停止容器 + 删除 postgres volume
    print('STEP 1: 停止容器 + 删除数据库')
    print('=' * 60)
    run(client, f'cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml down -v 2>&1 || true')
    run(client, 'docker stop $(docker ps -aq) 2>/dev/null; docker rm $(docker ps -aq) 2>/dev/null || true')
    run(client, 'docker volume ls -q | grep postgres | xargs -r docker volume rm 2>/dev/null || true')
    print()

    # Step 2: 上传并解压后端
    print('STEP 2: 上传后端代码')
    print('=' * 60)
    run(client, f'rm -rf {REMOTE_BASE}/backend/app {REMOTE_BASE}/backend/alembic {REMOTE_BASE}/backend/scripts')
    run(client, f'mkdir -p {REMOTE_BASE}/backend')
    sftp = client.open_sftp()
    sftp.put(backend_tar, '/tmp/taxja_backend.tar.gz')
    print('  tar 已上传')
    run(client, f'tar xzf /tmp/taxja_backend.tar.gz -C {REMOTE_BASE}/backend/')
    run(client, f'ls {REMOTE_BASE}/backend/ | head -10')
    print()

    # Step 3: 上传并解压前端
    print('STEP 3: 上传前端')
    print('=' * 60)
    run(client, f'rm -rf {REMOTE_BASE}/frontend/dist')
    run(client, f'mkdir -p {REMOTE_BASE}/frontend')
    sftp.put(frontend_tar, '/tmp/taxja_frontend.tar.gz')
    print('  tar 已上传')
    run(client, f'tar xzf /tmp/taxja_frontend.tar.gz -C {REMOTE_BASE}/frontend/')
    run(client, f'ls {REMOTE_BASE}/frontend/dist/ | head -5')
    print()

    # Step 4: 上传 init.sql + docker-compose
    print('STEP 4: 上传配置文件')
    print('=' * 60)
    run(client, f'mkdir -p {REMOTE_BASE}/docker/init-db')
    sftp.put('docker/init-db/init.sql', f'{REMOTE_BASE}/docker/init-db/init.sql')
    with sftp.open(f'{REMOTE_BASE}/docker-compose.server.yml', 'w') as f:
        f.write(COMPOSE)
    sftp.close()
    print('  init.sql + docker-compose.server.yml 已上传\n')

    # Step 5: 构建并启动
    print('STEP 5: 构建并启动容器')
    print('=' * 60)
    run(client,
        f'cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build 2>&1 | tail -25',
        timeout=600)
    print('  等待 30 秒...')
    time.sleep(30)
    run(client, f'cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml ps')
    print()

    # Step 6: Seed tax configs
    print('STEP 6: Seed tax configs')
    print('=' * 60)
    run(client, 'docker exec taxja-backend python3 -c "import sys; sys.path.insert(0, \\\"/app\\\"); from app.db.seed_tax_config import seed_tax_configs; seed_tax_configs()" 2>&1 | tail -5')
    print()

    # Step 7: 创建测试账号
    print('STEP 7: 创建测试账号')
    print('=' * 60)
    script = '''import sys
sys.path.insert(0, "/app")
from app.db.base import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.models.plan import Plan, PlanType
from app.models.credit_balance import CreditBalance
from app.services.trial_service import TrialService
db = SessionLocal()
try:
    u = User(email="admin@taxja.at", name="Admin", hashed_password=get_password_hash("Admin123!"),
             user_type="employee", language="de", is_admin=True, email_verified=True, trial_used=False)
    db.add(u); db.commit(); db.refresh(u)
    print(f"User created: id={u.id}")
    try:
        sub = TrialService(db).activate_trial(u.id)
        print(f"Trial: expires {sub.current_period_end}")
    except Exception as e: print(f"Trial err: {e}")
    pro = db.query(Plan).filter(Plan.plan_type == PlanType.PRO).first()
    cr = pro.monthly_credits if pro else 2000
    cb = CreditBalance(user_id=u.id, plan_balance=cr, topup_balance=0, overage_enabled=False,
                       overage_credits_used=0, has_unpaid_overage=False, unpaid_overage_periods=0)
    db.add(cb); db.commit()
    print(f"Credits: {cr}")
finally: db.close()
'''
    sftp2 = client.open_sftp()
    with sftp2.open('/tmp/create_admin.py', 'w') as f:
        f.write(script)
    sftp2.close()
    run(client, 'docker cp /tmp/create_admin.py taxja-backend:/tmp/create_admin.py')
    run(client, 'docker exec taxja-backend python3 /tmp/create_admin.py 2>&1')
    print()

    # Step 8: 健康检查
    print('STEP 8: 健康检查')
    print('=' * 60)
    run(client, 'curl -s http://localhost:8000/api/v1/health | head -3')
    out = run(client, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:80/')
    print(f'  nginx: HTTP {out}')
    out = run(client, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:80/api/v1/health')
    print(f'  api via nginx: HTTP {out}')

    client.close()
    print('\n' + '=' * 60)
    print('部署完成！')
    print('  URL: https://taxja.at')
    print('  账号: admin@taxja.at / Admin123!')
    print('=' * 60)

if __name__ == '__main__':
    main()
