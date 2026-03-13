#!/bin/bash

# Staging Deployment Script - Property Asset Management
# This script automates the staging deployment process
# Usage: ./scripts/staging_deployment.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="backup/staging/$(date +%Y%m%d)"
DEPLOYMENT_LOG="deployment_$(date +%Y%m%d_%H%M%S).log"

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

confirm() {
    read -p "$1 (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Deployment cancelled by user"
        exit 1
    fi
}

# Banner
echo "=========================================="
echo "  Property Asset Management"
echo "  Staging Deployment"
echo "  $(date +'%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# Pre-flight checks
log "Running pre-flight checks..."

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed"
    exit 1
fi

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    warning "Some services are not running"
    confirm "Do you want to continue?"
fi

log "✓ Pre-flight checks passed"

# Phase 1: Backup
log "Phase 1: Creating backup..."

mkdir -p "$BACKUP_DIR"

log "Backing up database..."
docker-compose exec -T postgres pg_dump -U taxja -d taxja > \
    "$BACKUP_DIR/taxja_staging_pre_property_$(date +%Y%m%d_%H%M%S).sql"

BACKUP_SIZE=$(du -h "$BACKUP_DIR"/*.sql | cut -f1)
log "✓ Backup created: $BACKUP_SIZE"

# Phase 2: Check current state
log "Phase 2: Checking current state..."

log "Current migration version:"
cd backend
CURRENT_MIGRATION=$(alembic current 2>&1 | grep -oP '(?<=\(head\) )[a-f0-9]+' || echo "unknown")
log "  Migration: $CURRENT_MIGRATION"

log "Database statistics:"
docker-compose exec -T postgres psql -U taxja -d taxja -c "
SELECT
    'users' as table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('users')) as size
FROM users
UNION ALL
SELECT 'transactions', COUNT(*), pg_size_pretty(pg_total_relation_size('transactions'))
FROM transactions
UNION ALL
SELECT 'documents', COUNT(*), pg_size_pretty(pg_total_relation_size('documents'))
FROM documents;
" | tee -a "$DEPLOYMENT_LOG"

cd ..

# Phase 3: Build images
log "Phase 3: Building Docker images..."

confirm "Ready to build new Docker images?"

log "Building backend image..."
docker-compose build backend

log "Building frontend image..."
docker-compose build frontend

log "✓ Docker images built successfully"

# Phase 4: Stop services
log "Phase 4: Stopping application services..."

confirm "Ready to stop application services?"

docker-compose stop backend frontend celery-worker

log "✓ Application services stopped"

# Phase 5: Apply migrations
log "Phase 5: Applying database migrations..."

confirm "Ready to apply database migrations?"

cd backend

log "Applying migration 002: Add properties table"
alembic upgrade 002

log "Applying migration 003: Add property_id to transactions"
alembic upgrade 003

log "Applying migration 004: Add property_loans table"
alembic upgrade 004

log "Applying migration 005: Add historical_import tables"
alembic upgrade 005

log "Applying migration 006: Add performance indexes"
alembic upgrade 006

log "Applying migration 007: Increase column sizes for encryption"
alembic upgrade 007

log "Applying migration 008: Encrypt existing property addresses"
alembic upgrade 008

log "Applying migration 009: Add audit_logs table"
alembic upgrade 009

FINAL_MIGRATION=$(alembic current 2>&1 | grep -oP '(?<=\(head\) )[a-f0-9]+' || echo "unknown")
log "✓ Migrations applied successfully. Current: $FINAL_MIGRATION"

cd ..

# Phase 6: Verify migration
log "Phase 6: Verifying migration..."

log "Checking tables exist:"
docker-compose exec -T postgres psql -U taxja -d taxja -c "\dt" | grep -E "properties|audit_logs" | tee -a "$DEPLOYMENT_LOG"

log "Checking indexes:"
docker-compose exec -T postgres psql -U taxja -d taxja -c "\di" | grep -E "idx_properties|idx_transactions" | tee -a "$DEPLOYMENT_LOG"

log "✓ Migration verification passed"

# Phase 7: Start services
log "Phase 7: Starting services..."

docker-compose up -d

log "Waiting for services to be ready..."
sleep 30

# Check service health
if docker-compose ps | grep -q "Exit"; then
    error "Some services failed to start"
    docker-compose ps
    exit 1
fi

log "✓ All services started successfully"

# Phase 8: Health checks
log "Phase 8: Running health checks..."

log "Checking backend health..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health || echo "FAILED")
if [[ "$HEALTH_RESPONSE" == *"ok"* ]] || [[ "$HEALTH_RESPONSE" == *"healthy"* ]]; then
    log "✓ Backend health check passed"
else
    error "Backend health check failed: $HEALTH_RESPONSE"
    exit 1
fi

log "Checking frontend..."
FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 || echo "000")
if [[ "$FRONTEND_RESPONSE" == "200" ]]; then
    log "✓ Frontend accessible"
else
    warning "Frontend returned status: $FRONTEND_RESPONSE"
fi

# Phase 9: Test property endpoints
log "Phase 9: Testing property endpoints..."

log "Note: Manual testing required for authenticated endpoints"
log "  1. Login to get auth token"
log "  2. Test GET /api/v1/properties"
log "  3. Test POST /api/v1/properties"
log "  4. Test property-transaction linking"

# Phase 10: Summary
log "=========================================="
log "Deployment Summary"
log "=========================================="
log "Backup Location: $BACKUP_DIR"
log "Backup Size: $BACKUP_SIZE"
log "Previous Migration: $CURRENT_MIGRATION"
log "Current Migration: $FINAL_MIGRATION"
log "Deployment Log: $DEPLOYMENT_LOG"
log "=========================================="
log ""
log "✓ Staging deployment completed successfully!"
log ""
log "Next Steps:"
log "  1. Review deployment log: cat $DEPLOYMENT_LOG"
log "  2. Run manual tests (see STAGING_DEPLOYMENT_CHECKLIST.md)"
log "  3. Monitor logs: docker-compose logs -f backend"
log "  4. Monitor for 24-48 hours before production deployment"
log ""
log "Rollback command (if needed):"
log "  cd backend && alembic downgrade 001"
log "  docker-compose exec -T postgres psql -U taxja -d taxja < $BACKUP_DIR/*.sql"
log ""

exit 0
