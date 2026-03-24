#!/usr/bin/env python3
"""Deploy Taxja to new server - tar with Python tarfile + paramiko SFTP."""
import paramiko
import os
import sys
import time
import tarfile
import io

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"
REMOTE_BASE = "/opt/taxja"

SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.hypothesis', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'dist', '.claude', '.codex-runtime',
    '.kiro', 'output', 'tmp', 'models', 'k8s', '.github', 'docs', 'src',
    'deploy', '.codex-eval', '.codex-run', 'examples', '.egg-info',
    'htmlcov', '.tox', 'venv', '.venv', 'env',
}

def run_cmd(client, cmd, timeout=300):
    print(f"  >>> {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            lines = out.split('\n')
            if len(lines) > 8:
                print(f"      ...({len(lines)} lines, last 5)")
            for line in lines[-5:]:
                print(f"      {line}")
        if err and exit_code != 0:
            for line in err.split('\n')[-3:]:
                print(f"      ERR: {line}")
        return exit_code, out, err
    except Exception as e:
        print(f"      TIMEOUT/ERROR: {e}")
        return -1, "", str(e)

workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tar_path = os.path.join(workspace, "deploy", "taxja-deploy.tar.gz")

# Step 1: Create tar
print("=" * 60)
print("STEP 1: Create tar archive")
print("=" * 60)

file_count = 0
def tar_filter(tarinfo):
    global file_count
    parts = tarinfo.name.replace('\\', '/').split('/')
    for p in parts:
        if p in SKIP_DIRS:
            return None
    if tarinfo.name.endswith(('.pyc', '.pyo', '.pkl', '.pickle')):
        return None
    # Skip large test fixtures
    if tarinfo.size > 10 * 1024 * 1024:  # Skip files > 10MB
        print(f"    SKIP large: {tarinfo.name} ({tarinfo.size // 1024 // 1024}MB)")
        return None
    file_count += 1
    if file_count % 100 == 0:
        print(f"    ... {file_count} files added")
    return tarinfo

print(f"  Workspace: {workspace}")
with tarfile.open(tar_path, 'w:gz', compresslevel=6) as tar:
    for item in ['backend', 'frontend', 'docker']:
        full = os.path.join(workspace, item)
        if os.path.exists(full):
            print(f"  Adding {item}/...")
            tar.add(full, arcname=item, filter=tar_filter)
        else:
            print(f"  MISSING: {item}/")
    for item in ['docker-compose.yml', 'docker-compose.prod.yml', 'Makefile']:
        full = os.path.join(workspace, item)
        if os.path.exists(full):
            tar.add(full, arcname=item)
            file_count += 1

tar_size = os.path.getsize(tar_path) / (1024 * 1024)
print(f"  Archive: {tar_size:.1f} MB, {file_count} files")

# Step 2: Upload
print("\n" + "=" * 60)
print("STEP 2: Connect and upload")
print("=" * 60)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
print(f"  Connected to {HOST}")

run_cmd(client, f"rm -rf {REMOTE_BASE} && mkdir -p {REMOTE_BASE}")

sftp = client.open_sftp()
remote_tar = f"{REMOTE_BASE}/taxja-deploy.tar.gz"
print(f"  Uploading {tar_size:.1f} MB...")
t0 = time.time()
sftp.put(tar_path, remote_tar)
print(f"  Upload done in {time.time()-t0:.0f}s")
sftp.close()

run_cmd(client, f"cd {REMOTE_BASE} && tar xzf taxja-deploy.tar.gz && rm taxja-deploy.tar.gz")
run_cmd(client, f"ls -la {REMOTE_BASE}/")

os.remove(tar_path)
print("  Cleaned up local tar")

# Step 3: .env.prod
print("\n" + "=" * 60)
print("STEP 3: Create .env.prod")
print("=" * 60)

env_content = """FRONTEND_URL=https://taxja.at
GOOGLE_CLIENT_ID=663869101551-c2s3tka97lb9o2ml108s8ues9bm4gp40.apps.googleusercontent.com
SECRET_KEY=prod-secret-key-hetzner-cx33-2026
ENCRYPTION_KEY=iXnv9jutfWE4ELYFr2r5jYVIPz/msIr1IUnIpFbJB7s=
POSTGRES_SERVER=postgres
POSTGRES_USER=taxja
POSTGRES_PASSWORD=TaxjaDB2026!Prod
POSTGRES_DB=taxja
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=taxja-minio-prod
MINIO_SECRET_KEY=TaxjaMinio2026!Prod
MINIO_BUCKET=taxja-documents
MINIO_SECURE=false
OPENAI_API_KEY=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
OPENAI_MODEL=gpt-4o
ANTHROPIC_API_KEY=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
ANTHROPIC_MODEL=claude-opus-4-1-20250805
ANTHROPIC_VISION_MODEL=claude-opus-4-1-20250805
CONTRACT_ROLE_MODE=shadow
GROQ_ENABLED=true
GROQ_API_KEY=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
GROQ_MODEL=openai/gpt-oss-120b
GPT_OSS_ENABLED=false
GPT_OSS_BASE_URL=
GPT_OSS_MODEL=
GPT_OSS_API_KEY=
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=
OLLAMA_MODEL=
OLLAMA_VISION_MODEL=
BACKEND_CORS_ORIGINS=["https://taxja.at","https://www.taxja.at","http://localhost"]
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
STRIPE_SECRET_KEY=sk_test_51T9EqEIHe2PMXpl39hkfi29RVUWqmTyovqicJEHr30JyTlSHWQycgvXFP0vcEOnSBSvtm3Gob8kUlyZSfVBvWnx3002e0j5jzz
STRIPE_PUBLISHABLE_KEY=pk_test_51T9EqEIHe2PMXpl3LCNqrxo0fAqVyL1WJwymwy3mj4p6SN9rBZjk2SgR8FCkNARtAbVEJ57rFDGbgEQrs7yV5gEA00kxLlf8NV
STRIPE_WEBHOOK_SECRET=whsec_3a781c83463a4ebea65f9136fe22f4247d09caf277086e0db2b7fd4d8ae349e8
STRIPE_PLUS_MONTHLY_PRICE_ID=price_1TBGZdIHe2PMXpl3RlUcjIBq
STRIPE_PLUS_YEARLY_PRICE_ID=price_1TBGXVIHe2PMXpl3e9SMugWg
STRIPE_PRO_MONTHLY_PRICE_ID=price_1TBGbkIHe2PMXpl3tnxAVJm3
STRIPE_PRO_YEARLY_PRICE_ID=price_1TBGgUIHe2PMXpl38HHGCYxK
STRIPE_OVERAGE_PRODUCT_ID=prod_UApZwABQQOY9SW
ENABLE_EMAIL_NOTIFICATIONS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ylvie.khoo@gmail.com
SMTP_PASSWORD=dzobcjugezwzyrxb
SMTP_FROM_EMAIL=ylvie.khoo@gmail.com
SMTP_FROM_NAME=Taxja
SMTP_USE_TLS=true
"""

sftp2 = client.open_sftp()
with sftp2.open(f"{REMOTE_BASE}/.env.prod", 'w') as f:
    f.write(env_content)
sftp2.close()
print("  .env.prod created")

# Step 4: docker-compose.server.yml
print("\n" + "=" * 60)
print("STEP 4: Create docker-compose.server.yml")
print("=" * 60)

compose_content = """services:
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

sftp3 = client.open_sftp()
with sftp3.open(f"{REMOTE_BASE}/docker-compose.server.yml", 'w') as f:
    f.write(compose_content)
sftp3.close()
print("  docker-compose.server.yml created")

# Step 5: Build frontend
print("\n" + "=" * 60)
print("STEP 5: Build frontend")
print("=" * 60)
print("  npm install...")
run_cmd(client,
    f"cd {REMOTE_BASE} && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine sh -c 'npm install --legacy-peer-deps 2>&1 | tail -5'",
    timeout=600)
print("  npm run build...")
run_cmd(client,
    f"cd {REMOTE_BASE} && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine sh -c 'npm run build 2>&1 | tail -10'",
    timeout=300)
run_cmd(client, f"ls {REMOTE_BASE}/frontend/dist/index.html 2>/dev/null && echo 'OK' || echo 'FAILED'")

# Step 6: Start services
print("\n" + "=" * 60)
print("STEP 6: Start services")
print("=" * 60)
print("  docker compose up --build...")
run_cmd(client,
    f"cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build 2>&1 | tail -15",
    timeout=900)
print("  Waiting 25s...")
time.sleep(25)
run_cmd(client, f"cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml ps")

# Step 7: Init DB
print("\n" + "=" * 60)
print("STEP 7: Init database")
print("=" * 60)
run_cmd(client, f"docker cp {REMOTE_BASE}/docker/init-db/init.sql taxja-postgres:/tmp/init.sql")
run_cmd(client, 'docker exec taxja-postgres psql -U taxja -d taxja -f /tmp/init.sql 2>&1 | tail -10', timeout=120)
run_cmd(client, "docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT count(*) as tables FROM information_schema.tables WHERE table_schema = 'public';\"")
run_cmd(client, "docker exec taxja-redis redis-cli FLUSHALL")

# Step 8: Health check
print("\n" + "=" * 60)
print("STEP 8: Health check")
print("=" * 60)
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost:8000/api/v1/health || echo 'Backend down'")
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost/ || echo 'Nginx down'")
run_cmd(client, "docker logs taxja-backend --tail 3 2>&1")

print("\n" + "=" * 60)
print(f"DONE! http://{HOST}")
print("Next: SSL + DNS")
print("=" * 60)

client.close()
