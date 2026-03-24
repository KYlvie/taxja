#!/usr/bin/env python3
"""Deploy Taxja to new Hetzner CX33 server via SFTP + SSH."""
import paramiko
import os
import sys
import stat
import time

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"
REMOTE_BASE = "/opt/taxja"

# Directories/files to skip during upload
SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.hypothesis', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'dist', '.next', '.claude', '.codex-runtime',
    '.kiro', 'output', 'tmp', '.codex-eval', '.codex-run', 'models',
    '.hypothesis', 'k8s', '.github', 'docs', 'src'
}
SKIP_FILES = {'.env', '.env.prod', '.env.example'}

# What to upload (relative to workspace root)
UPLOAD_DIRS = ['backend', 'frontend', 'docker']
UPLOAD_FILES = ['docker-compose.yml', 'docker-compose.prod.yml', 'Makefile']


def run_cmd(client, cmd, timeout=300):
    """Run SSH command and return results."""
    print(f"  >>> {cmd[:100]}{'...' if len(cmd) > 100 else ''}")
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            lines = out.split('\n')
            for line in lines[-5:]:
                print(f"      {line}")
        if err and exit_code != 0:
            for line in err.split('\n')[-3:]:
                print(f"      ERR: {line}")
        return exit_code, out, err
    except Exception as e:
        print(f"      TIMEOUT/ERROR: {e}")
        return -1, "", str(e)


def should_skip(name, is_dir=False):
    """Check if file/dir should be skipped."""
    if is_dir and name in SKIP_DIRS:
        return True
    if not is_dir and name in SKIP_FILES:
        return True
    # Skip compiled/cache files
    if name.endswith(('.pyc', '.pyo', '.egg-info')):
        return True
    return False


def sftp_mkdir_p(sftp, remote_dir):
    """Recursively create remote directories."""
    dirs_to_create = []
    current = remote_dir
    while current and current != '/':
        try:
            sftp.stat(current)
            break
        except FileNotFoundError:
            dirs_to_create.append(current)
            current = os.path.dirname(current)
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except Exception:
            pass


def upload_directory(sftp, local_dir, remote_dir, file_count=[0]):
    """Recursively upload a directory via SFTP."""
    sftp_mkdir_p(sftp, remote_dir)
    
    for item in sorted(os.listdir(local_dir)):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        
        if os.path.isdir(local_path):
            if should_skip(item, is_dir=True):
                continue
            upload_directory(sftp, local_path, remote_path, file_count)
        else:
            if should_skip(item, is_dir=False):
                continue
            try:
                sftp.put(local_path, remote_path)
                file_count[0] += 1
                if file_count[0] % 50 == 0:
                    print(f"      ... uploaded {file_count[0]} files")
            except Exception as e:
                print(f"      WARN: Failed to upload {remote_path}: {e}")


# Connect
print(f"Connecting to {HOST}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
sftp = client.open_sftp()
print("Connected!\n")

# Step 1: Clean and prepare
print("=" * 60)
print("STEP 1: Prepare remote directory")
print("=" * 60)
run_cmd(client, f"rm -rf {REMOTE_BASE}")
run_cmd(client, f"mkdir -p {REMOTE_BASE}")

# Step 2: Upload files
print("\n" + "=" * 60)
print("STEP 2: Upload project files via SFTP")
print("=" * 60)

workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"  Workspace: {workspace_root}")

file_count = [0]
for dirname in UPLOAD_DIRS:
    local = os.path.join(workspace_root, dirname)
    remote = f"{REMOTE_BASE}/{dirname}"
    if os.path.exists(local):
        print(f"\n  Uploading {dirname}/...")
        upload_directory(sftp, local, remote, file_count)
        print(f"    {dirname}/ done")
    else:
        print(f"  SKIP: {local} not found")

for fname in UPLOAD_FILES:
    local = os.path.join(workspace_root, fname)
    remote = f"{REMOTE_BASE}/{fname}"
    if os.path.exists(local):
        sftp.put(local, remote)
        file_count[0] += 1
        print(f"  Uploaded {fname}")

print(f"\n  Total files uploaded: {file_count[0]}")

sftp.close()


# Step 3: Create .env.prod
print("\n" + "=" * 60)
print("STEP 3: Create .env.prod")
print("=" * 60)

env_prod = r"""# Taxja Production Environment
FRONTEND_URL=https://taxja.at
GOOGLE_CLIENT_ID=663869101551-c2s3tka97lb9o2ml108s8ues9bm4gp40.apps.googleusercontent.com

# Security
SECRET_KEY=prod-secret-key-hetzner-cx33-2026
ENCRYPTION_KEY=iXnv9jutfWE4ELYFr2r5jYVIPz/msIr1IUnIpFbJB7s=

# Database
POSTGRES_SERVER=postgres
POSTGRES_USER=taxja
POSTGRES_PASSWORD=TaxjaDB2026!Prod
POSTGRES_DB=taxja
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# MinIO/S3
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=taxja-minio-prod
MINIO_SECRET_KEY=TaxjaMinio2026!Prod
MINIO_BUCKET=taxja-documents
MINIO_SECURE=false

# LLM
OPENAI_API_KEY=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
OPENAI_MODEL=gpt-4o
ANTHROPIC_API_KEY=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
ANTHROPIC_MODEL=claude-opus-4-1-20250805
ANTHROPIC_VISION_MODEL=claude-opus-4-1-20250805
CONTRACT_ROLE_MODE=shadow

# Groq
GROQ_ENABLED=true
GROQ_API_KEY=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
GROQ_MODEL=openai/gpt-oss-120b

# GPT-OSS
GPT_OSS_ENABLED=false
GPT_OSS_BASE_URL=
GPT_OSS_MODEL=
GPT_OSS_API_KEY=

# Ollama
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=
OLLAMA_MODEL=
OLLAMA_VISION_MODEL=

# CORS
BACKEND_CORS_ORIGINS=["https://taxja.at","https://www.taxja.at","http://localhost"]

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Stripe
STRIPE_SECRET_KEY=sk_test_51T9EqEIHe2PMXpl39hkfi29RVUWqmTyovqicJEHr30JyTlSHWQycgvXFP0vcEOnSBSvtm3Gob8kUlyZSfVBvWnx3002e0j5jzz
STRIPE_PUBLISHABLE_KEY=pk_test_51T9EqEIHe2PMXpl3LCNqrxo0fAqVyL1WJwymwy3mj4p6SN9rBZjk2SgR8FCkNARtAbVEJ57rFDGbgEQrs7yV5gEA00kxLlf8NV
STRIPE_WEBHOOK_SECRET=whsec_3a781c83463a4ebea65f9136fe22f4247d09caf277086e0db2b7fd4d8ae349e8
STRIPE_PLUS_MONTHLY_PRICE_ID=price_1TBGZdIHe2PMXpl3RlUcjIBq
STRIPE_PLUS_YEARLY_PRICE_ID=price_1TBGXVIHe2PMXpl3e9SMugWg
STRIPE_PRO_MONTHLY_PRICE_ID=price_1TBGbkIHe2PMXpl3tnxAVJm3
STRIPE_PRO_YEARLY_PRICE_ID=price_1TBGgUIHe2PMXpl38HHGCYxK
STRIPE_OVERAGE_PRODUCT_ID=prod_UApZwABQQOY9SW

# Email
ENABLE_EMAIL_NOTIFICATIONS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ylvie.khoo@gmail.com
SMTP_PASSWORD=dzobcjugezwzyrxb
SMTP_FROM_EMAIL=ylvie.khoo@gmail.com
SMTP_FROM_NAME=Taxja
SMTP_USE_TLS=true
"""

# Write .env.prod via SSH heredoc
sftp2 = client.open_sftp()
with sftp2.open(f"{REMOTE_BASE}/.env.prod", 'w') as f:
    f.write(env_prod)
sftp2.close()
run_cmd(client, f"wc -l {REMOTE_BASE}/.env.prod")
print("  .env.prod created")

# Step 4: Create docker-compose.server.yml
print("\n" + "=" * 60)
print("STEP 4: Create docker-compose.server.yml")
print("=" * 60)

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
    f.write(compose)
sftp3.close()
run_cmd(client, f"wc -l {REMOTE_BASE}/docker-compose.server.yml")
print("  docker-compose.server.yml created")

# Step 5: Build frontend on server
print("\n" + "=" * 60)
print("STEP 5: Build frontend")
print("=" * 60)
print("  Installing npm dependencies (this takes a few minutes)...")
code, out, err = run_cmd(client, 
    f"cd {REMOTE_BASE} && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine sh -c 'npm install 2>&1 | tail -5'",
    timeout=600)
if code != 0:
    print(f"  npm install failed! Trying with --legacy-peer-deps...")
    run_cmd(client,
        f"cd {REMOTE_BASE} && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine sh -c 'npm install --legacy-peer-deps 2>&1 | tail -5'",
        timeout=600)

print("  Building frontend...")
code, out, err = run_cmd(client,
    f"cd {REMOTE_BASE} && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine sh -c 'npm run build 2>&1 | tail -10'",
    timeout=300)
run_cmd(client, f"ls -la {REMOTE_BASE}/frontend/dist/index.html 2>/dev/null && echo 'Frontend build OK' || echo 'Frontend build FAILED'")

# Step 6: Start all services
print("\n" + "=" * 60)
print("STEP 6: Start all services")
print("=" * 60)
print("  Building and starting containers (this takes several minutes)...")
run_cmd(client,
    f"cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build 2>&1 | tail -15",
    timeout=900)

print("  Waiting 20s for services to start...")
time.sleep(20)

run_cmd(client, f"cd {REMOTE_BASE} && docker compose -f docker-compose.server.yml ps")

# Step 7: Init database
print("\n" + "=" * 60)
print("STEP 7: Initialize database")
print("=" * 60)
run_cmd(client, f"docker cp {REMOTE_BASE}/docker/init-db/init.sql taxja-postgres:/tmp/init.sql")
run_cmd(client, 'docker exec taxja-postgres psql -U taxja -d taxja -f /tmp/init.sql 2>&1 | tail -10', timeout=120)
run_cmd(client, 'docker exec taxja-postgres psql -U taxja -d taxja -c "SELECT count(*) as tables FROM information_schema.tables WHERE table_schema = \'public\';"')
run_cmd(client, "docker exec taxja-redis redis-cli FLUSHALL")

# Step 8: Health check
print("\n" + "=" * 60)
print("STEP 8: Health check")
print("=" * 60)
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost:8000/api/v1/health || echo 'Backend not responding'")
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost/ || echo 'Nginx not responding'")
run_cmd(client, "docker logs taxja-backend --tail 5 2>&1")
run_cmd(client, "docker logs taxja-nginx --tail 5 2>&1")

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE!")
print(f"Server: http://{HOST}")
print("Next: SSL cert + DNS update")
print("=" * 60)

client.close()
