#!/bin/bash
# Server-side deployment script for taxja
# Run from /opt/taxja on the server
set -e

echo "=== Taxja Cloud Deployment ==="
echo ""

# 1. Kill DB connections and drop/recreate
echo "[1/6] Dropping and recreating database..."
docker exec taxja-postgres psql -U taxja -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'taxja' AND pid <> pg_backend_pid();"
docker exec taxja-postgres psql -U taxja -d postgres -c "DROP DATABASE IF EXISTS taxja;"
docker exec taxja-postgres psql -U taxja -d postgres -c "CREATE DATABASE taxja OWNER taxja;"
echo "  Done."

# 2. Import init.sql
echo ""
echo "[2/6] Importing schema and seed data from init.sql..."
docker cp docker/init-db/init.sql taxja-postgres:/tmp/init.sql
docker exec taxja-postgres psql -U taxja -d taxja -f /tmp/init.sql > /dev/null 2>&1
echo "  Done."

# 3. Verify DB
echo ""
echo "[3/6] Verifying database..."
docker exec taxja-postgres psql -U taxja -d taxja -c "SELECT count(*) as table_count FROM information_schema.tables WHERE table_schema = 'public';"
docker exec taxja-postgres psql -U taxja -d taxja -c "SELECT plan_type, name, monthly_credits FROM plans ORDER BY id;"
docker exec taxja-postgres psql -U taxja -d taxja -c "SELECT operation, credit_cost FROM credit_cost_configs ORDER BY id;"

# 4. Flush Redis
echo ""
echo "[4/6] Flushing Redis..."
docker exec taxja-redis redis-cli FLUSHALL
echo "  Done."

# 5. Build frontend
echo ""
echo "[5/6] Building frontend..."
if [ -d "frontend" ]; then
  # Check if node_modules exists, if not install
  if [ ! -d "frontend/node_modules" ]; then
    echo "  Installing frontend dependencies..."
    docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm install
  fi
  echo "  Building frontend dist..."
  docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build
  echo "  Frontend built."
else
  echo "  No frontend directory, skipping."
fi

# 6. Rebuild and restart backend
echo ""
echo "[6/6] Rebuilding and restarting backend..."
docker compose -f docker-compose.server.yml up -d --build backend
docker compose -f docker-compose.server.yml restart nginx

echo ""
echo "=== Deployment complete! ==="
echo ""

# Final status
sleep 3
docker compose -f docker-compose.server.yml ps
