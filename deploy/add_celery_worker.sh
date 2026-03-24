#!/bin/bash
set -e
cd /opt/taxja

# Backup current compose file
cp docker-compose.server.yml docker-compose.server.yml.bak

# Write the new compose file with celery-worker added
cat > docker-compose.server.yml << 'COMPOSE_EOF'
services:
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
    command: celery -A app.celery_app worker --loglevel=info --concurrency=1 --max-tasks-per-child=50 -Q default,ocr,ml

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
COMPOSE_EOF

echo "docker-compose.server.yml updated with celery-worker"

# Start celery-worker (reuses the already-built backend image)
docker compose -f docker-compose.server.yml --env-file .env.prod up -d celery-worker

echo "Waiting 10s for celery-worker to start..."
sleep 10

# Check if it's running
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "celery|backend|redis"

echo "Checking celery worker logs..."
docker logs taxja-celery-worker --tail 20 2>&1
