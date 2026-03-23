import paramiko
import time

def run(client, cmd, timeout=120, ignore_err=False):
    print(f'\n$ {cmd[:100]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out[-2000:])
    if err and not ignore_err:
        print('ERR:', err[-800:])
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass',
               timeout=20)
print('Connected!')

# 1. 写 .env.prod 到服务器
env_content = """FRONTEND_URL=https://taxja.at
SECRET_KEY=iXnv9jutfWE4ELYFr2r5jYVIPz-msIr1IUnIpFbJB7s-PROD-CHANGE
ENCRYPTION_KEY=iXnv9jutfWE4ELYFr2r5jYVIPz/msIr1IUnIpFbJB7s=
POSTGRES_SERVER=postgres
POSTGRES_USER=taxja
POSTGRES_PASSWORD=taxja_prod_2026
POSTGRES_DB=taxja
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin_prod_2026
MINIO_BUCKET=taxja-documents
MINIO_SECURE=false
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
GROQ_ENABLED=true
GROQ_API_KEY=your-groq-api-key-here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1
OLLAMA_ENABLED=false
BACKEND_CORS_ORIGINS=["https://taxja.at","https://www.taxja.at","http://localhost:5173"]
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
STRIPE_SECRET_KEY=your-stripe-secret-key-here
STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key-here
STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret-here
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

# 写 env 文件
sftp = client.open_sftp()
with sftp.open('/opt/taxja/.env.prod', 'w') as f:
    f.write(env_content)
print('env.prod written')

# 2. 写轻量版 docker-compose
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
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
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

with sftp.open('/opt/taxja/docker-compose.server.yml', 'w') as f:
    f.write(compose_content)
print('docker-compose.server.yml written')

# 3. 更新 nginx.conf 指向 backend 容器
nginx_conf = """server {
    listen 80;
    server_name taxja.at www.taxja.at;

    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
"""

with sftp.open('/opt/taxja/frontend/nginx.conf', 'w') as f:
    f.write(nginx_conf)
print('nginx.conf updated (proxy to backend container)')

sftp.close()

# 4. 检查 frontend/dist 是否存在
out = run(client, 'ls /opt/taxja/frontend/dist 2>/dev/null | head -5 || echo NO_DIST')
if 'NO_DIST' in out or not out:
    print('\nNeed to build frontend on server...')
    run(client, 'apt-get install -y nodejs npm', timeout=120)
    run(client, 'node --version && npm --version')
    run(client, 'npm ci --prefix /opt/taxja/frontend', timeout=300)
    run(client, 'npm run build --prefix /opt/taxja/frontend', timeout=300)
    run(client, 'ls /opt/taxja/frontend/dist')
else:
    print('frontend/dist exists, skipping build')

client.close()
print('\nAll config files ready!')
