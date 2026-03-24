#!/usr/bin/env python3
"""Setup new Hetzner server for Taxja deployment."""
import paramiko
import time
import sys

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"

def run_cmd(client, cmd, timeout=300):
    """Run command and print output."""
    print(f"\n>>> {cmd[:80]}{'...' if len(cmd) > 80 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        # Print last 5 lines to keep output manageable
        lines = out.split('\n')
        if len(lines) > 5:
            print(f"  ...({len(lines)} lines, showing last 5)")
        for line in lines[-5:]:
            print(f"  {line}")
    if err and exit_code != 0:
        for line in err.split('\n')[-3:]:
            print(f"  ERR: {line}")
    if exit_code != 0:
        print(f"  EXIT CODE: {exit_code}")
    return exit_code, out, err

print(f"Connecting to {HOST}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
print("Connected!\n")

# Step 1: Install Docker
print("=" * 50)
print("STEP 1: Install Docker")
print("=" * 50)

run_cmd(client, "install -m 0755 -d /etc/apt/keyrings")
run_cmd(client, "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && chmod a+r /etc/apt/keyrings/docker.asc")
run_cmd(client, 'CODENAME=$(lsb_release -cs) && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list')
run_cmd(client, "apt-get update -qq 2>&1 | tail -1")

code, _, _ = run_cmd(client, "DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>&1 | tail -3", timeout=300)
if code != 0:
    print("Docker install failed!")
    sys.exit(1)

run_cmd(client, "systemctl enable docker && systemctl start docker")
run_cmd(client, "docker --version && docker compose version")

# Step 2: Clone repo
print("\n" + "=" * 50)
print("STEP 2: Clone repository")
print("=" * 50)

run_cmd(client, "mkdir -p /opt")
code, out, _ = run_cmd(client, "ls -d /opt/taxja 2>/dev/null && echo EXISTS || echo MISSING")
if "EXISTS" in out:
    run_cmd(client, "cd /opt/taxja && git pull")
else:
    run_cmd(client, "cd /opt && git clone https://github.com/yk1e25/taxja.git", timeout=120)

run_cmd(client, "ls /opt/taxja/docker-compose.yml && echo 'Repo OK'")

# Step 3: Build frontend
print("\n" + "=" * 50)
print("STEP 3: Build frontend")
print("=" * 50)

run_cmd(client, "cd /opt/taxja && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm install 2>&1 | tail -3", timeout=300)
run_cmd(client, "cd /opt/taxja && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build 2>&1 | tail -5", timeout=120)
run_cmd(client, "ls -la /opt/taxja/frontend/dist/index.html && echo 'Frontend built OK'")

print("\n" + "=" * 50)
print("STEP 4: Create .env.prod and docker-compose.server.yml")
print("=" * 50)

# Write .env.prod
env_prod = """# Taxja Production Environment
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

# Escape for shell
env_escaped = env_prod.replace("'", "'\\''")
run_cmd(client, f"cat > /opt/taxja/.env.prod << 'ENVEOF'\n{env_prod}\nENVEOF")
run_cmd(client, "wc -l /opt/taxja/.env.prod")

# Write docker-compose.server.yml
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

run_cmd(client, f"cat > /opt/taxja/docker-compose.server.yml << 'COMPEOF'\n{compose}\nCOMPOEF")
run_cmd(client, "wc -l /opt/taxja/docker-compose.server.yml")

# Step 5: Start services
print("\n" + "=" * 50)
print("STEP 5: Start all services")
print("=" * 50)

run_cmd(client, "cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build 2>&1 | tail -10", timeout=600)

print("\nWaiting 15s for services to start...")
time.sleep(15)

run_cmd(client, "cd /opt/taxja && docker compose -f docker-compose.server.yml ps")

# Step 6: Init database
print("\n" + "=" * 50)
print("STEP 6: Initialize database")
print("=" * 50)

run_cmd(client, "cd /opt/taxja && docker cp docker/init-db/init.sql taxja-postgres:/tmp/init.sql && docker exec taxja-postgres psql -U taxja -d taxja -f /tmp/init.sql 2>&1 | tail -5", timeout=120)
run_cmd(client, "docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT count(*) as tables FROM information_schema.tables WHERE table_schema = 'public';\"")
run_cmd(client, "docker exec taxja-redis redis-cli FLUSHALL")

# Step 7: Health check
print("\n" + "=" * 50)
print("STEP 7: Health check")
print("=" * 50)

run_cmd(client, "curl -s http://localhost/api/v1/health || curl -s http://localhost:8000/api/v1/health || echo 'Health check endpoint not responding yet'")
run_cmd(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost/ || echo 'Frontend not responding'")

print("\n" + "=" * 50)
print("DEPLOYMENT COMPLETE!")
print(f"Server: {HOST}")
print(f"HTTP: http://{HOST}")
print("=" * 50)

client.close()
