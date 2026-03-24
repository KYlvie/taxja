#!/bin/bash
# =============================================================================
# Taxja Server Redeployment Script
# Run from local machine: bash redeploy_server.sh
# =============================================================================

SERVER="root@178.104.73.139"
REMOTE_DIR="/opt/taxja"

echo "=== Step 1: Connecting to server and stopping all services ==="
ssh $SERVER << 'EOF'
  set -e
  cd /opt/taxja

  echo "--- Stopping all containers ---"
  docker compose -f docker-compose.server.yml down || true

  echo "--- Pulling latest code ---"
  git fetch origin main
  git reset --hard origin/main

  echo "--- Current files check ---"
  ls -la backend/requirements*.txt
  head -20 backend/Dockerfile

  echo "--- Rebuilding backend image ---"
  docker compose -f docker-compose.server.yml build --no-cache backend

  echo "--- Starting infrastructure (postgres, redis, minio) ---"
  docker compose -f docker-compose.server.yml up -d postgres redis minio
  echo "Waiting for postgres to be ready..."
  sleep 10

  # Wait for postgres health check
  for i in {1..30}; do
    if docker compose -f docker-compose.server.yml exec -T postgres pg_isready -U taxja 2>/dev/null; then
      echo "PostgreSQL is ready!"
      break
    fi
    echo "Waiting for PostgreSQL... ($i/30)"
    sleep 2
  done

  echo "--- Starting backend ---"
  docker compose -f docker-compose.server.yml up -d backend
  sleep 10

  echo "--- Checking current migration version ---"
  docker compose -f docker-compose.server.yml exec -T backend alembic current || echo "No migration history found"

  echo "--- Running ALL migrations ---"
  docker compose -f docker-compose.server.yml exec -T backend alembic upgrade head

  echo "--- Verifying migration ---"
  docker compose -f docker-compose.server.yml exec -T backend alembic current

  echo "--- Starting remaining services (nginx, celery) ---"
  docker compose -f docker-compose.server.yml up -d

  echo "--- Health check ---"
  sleep 5
  curl -sf http://localhost:8000/api/v1/health && echo "" && echo "Backend OK!" || echo "Backend health check failed"

  echo "--- All containers status ---"
  docker compose -f docker-compose.server.yml ps

  echo "=== Redeployment complete ==="
EOF

echo ""
echo "Done! Check https://taxja.at to verify."
