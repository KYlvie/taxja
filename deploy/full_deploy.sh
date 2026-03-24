#!/bin/bash
# =============================================================================
# Taxja Full Deployment Script
# =============================================================================
# Usage: Run from the project root on the SERVER after files are uploaded.
#
# This script:
#   1. Stops the backend container
#   2. Drops and recreates the database (clean slate)
#   3. Imports schema + seed data
#   4. Rebuilds and restarts all containers
#   5. Flushes Redis cache
#
# Prerequisites:
#   - docker/init-db/init.sql must exist (schema + seed data)
#   - docker-compose.server.yml must exist
#   - .env.prod must exist
# =============================================================================

set -e

COMPOSE_FILE="docker-compose.server.yml"
DB_CONTAINER="taxja-postgres"
REDIS_CONTAINER="taxja-redis"
BACKEND_CONTAINER="taxja-backend"
DB_USER="taxja"
DB_NAME="taxja"

echo "============================================"
echo "  Taxja Full Deployment"
echo "============================================"

# 1. Stop backend to release DB connections
echo ""
echo "[1/6] Stopping backend..."
docker compose -f $COMPOSE_FILE stop backend || true

# 2. Drop and recreate database
echo ""
echo "[2/6] Dropping and recreating database..."
docker exec $DB_CONTAINER psql -U $DB_USER -d postgres -c "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
"
docker exec $DB_CONTAINER psql -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec $DB_CONTAINER psql -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo "  Database recreated."

# 3. Import schema + seed data (single init.sql)
echo ""
echo "[3/6] Importing schema and seed data..."
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < docker/init-db/init.sql
echo "  Schema and seed data imported."

# 4. Flush Redis
echo ""
echo "[4/6] Flushing Redis cache..."
docker exec $REDIS_CONTAINER redis-cli FLUSHALL
echo "  Redis flushed."

# 5. Rebuild and restart
echo ""
echo "[5/6] Rebuilding and restarting all services..."
docker compose -f $COMPOSE_FILE up -d --build backend
docker compose -f $COMPOSE_FILE restart nginx

echo ""
echo "============================================"
echo "  Deployment complete!"
echo "============================================"
echo ""

# Verify
echo "Checking services..."
sleep 3
docker compose -f $COMPOSE_FILE ps

echo ""
echo "Checking database tables..."
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT count(*) as tables FROM information_schema.tables WHERE table_schema = 'public';"

echo ""
echo "Checking seed data..."
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT plan_type, name, monthly_credits FROM plans ORDER BY id;"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT operation, credit_cost FROM credit_cost_configs ORDER BY id;"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT count(*) as tax_years FROM tax_configurations;"
