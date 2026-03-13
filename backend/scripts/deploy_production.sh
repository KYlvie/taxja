#!/bin/bash
# Production Deployment Script - Property Asset Management
# Version: 1.0
# Date: 2026-03-08

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="/backup/production/$(date +%Y%m%d)"
LOG_FILE="/var/log/taxja/deployment_$(date +%Y%m%d_%H%M%S).log"

# Database configuration (override with environment variables)
DB_HOST="${DB_HOST:-production-db-host}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-taxja_production}"
DB_USER="${DB_USER:-taxja_user}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Application configuration
APP_SERVERS="${APP_SERVERS:-app-server-1 app-server-2 app-server-3}"
MAINTENANCE_MODE_FILE="/opt/taxja/MAINTENANCE_MODE"

# Deployment options
DRY_RUN="${DRY_RUN:-false}"
SKIP_BACKUP="${SKIP_BACKUP:-false}"
SKIP_TESTS="${SKIP_TESTS:-false}"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

confirm() {
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would prompt: $1"
        return 0
    fi
    
    read -p "$1 (yes/no): " response
    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check required commands
    local required_commands=("psql" "pg_dump" "alembic" "curl" "docker")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done
    
    # Check database connectivity
    if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
        log_error "Cannot connect to database"
        exit 1
    fi
    
    # Check disk space
    local available_space=$(df -h "$BACKUP_DIR" 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ -z "$available_space" ]; then
        mkdir -p "$BACKUP_DIR"
        available_space=$(df -h "$BACKUP_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    fi
    
    if [ "$available_space" -gt 80 ]; then
        log_error "Insufficient disk space (${available_space}% used)"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

create_backup() {
    if [ "$SKIP_BACKUP" = "true" ]; then
        log_warning "Skipping backup (SKIP_BACKUP=true)"
        return 0
    fi
    
    log "Creating database backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    local backup_file="$BACKUP_DIR/taxja_production_pre_property_$(date +%Y%m%d_%H%M%S).dump"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would create backup at $backup_file"
        return 0
    fi
    
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -F c \
        -f "$backup_file"
    
    if [ $? -ne 0 ]; then
        log_error "Backup failed"
        exit 1
    fi
    
    # Verify backup
    if ! pg_restore --list "$backup_file" &> /dev/null; then
        log_error "Backup verification failed"
        exit 1
    fi
    
    local backup_size=$(du -h "$backup_file" | cut -f1)
    log_success "Backup created: $backup_file ($backup_size)"
    
    # Copy to secure location
    if [ -d "/backup/critical" ]; then
        cp "$backup_file" "/backup/critical/"
        log_success "Backup copied to /backup/critical/"
    fi
    
    # Export to S3 (if configured)
    if command -v aws &> /dev/null && [ -n "${AWS_S3_BACKUP_BUCKET:-}" ]; then
        aws s3 cp "$backup_file" "s3://$AWS_S3_BACKUP_BUCKET/production/$(date +%Y%m%d)/"
        log_success "Backup uploaded to S3"
    fi
    
    echo "$backup_file" > "$BACKUP_DIR/latest_backup.txt"
}

record_pre_migration_state() {
    log "Recording pre-migration state..."
    
    local state_file="$BACKUP_DIR/pre_migration_state.txt"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would record state to $state_file"
        return 0
    fi
    
    # Record migration version
    cd "$PROJECT_ROOT/backend"
    alembic current > "$BACKUP_DIR/pre_migration_version.txt"
    
    # Record table counts
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
    " > "$state_file"
    
    log_success "Pre-migration state recorded"
}

enable_maintenance_mode() {
    log "Enabling maintenance mode..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would enable maintenance mode"
        return 0
    fi
    
    for server in $APP_SERVERS; do
        ssh "$server" "touch $MAINTENANCE_MODE_FILE" || log_warning "Could not enable maintenance mode on $server"
    done
    
    log_success "Maintenance mode enabled"
}

stop_application_servers() {
    log "Stopping application servers..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would stop application servers"
        return 0
    fi
    
    for server in $APP_SERVERS; do
        log "Stopping $server..."
        ssh "$server" "cd /opt/taxja && docker-compose stop backend" || \
        ssh "$server" "systemctl stop taxja-backend" || \
        log_warning "Could not stop $server"
    done
    
    # Wait for connections to close
    sleep 5
    
    # Verify no active connections
    local active_connections=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*)
    FROM pg_stat_activity
    WHERE datname = '$DB_NAME'
    AND application_name != 'psql'
    AND state = 'active';
    " | tr -d ' ')
    
    if [ "$active_connections" -gt 0 ]; then
        log_warning "$active_connections active database connections remaining"
        
        if confirm "Terminate active connections?"; then
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '$DB_NAME'
            AND pid <> pg_backend_pid()
            AND application_name != 'psql';
            "
        fi
    fi
    
    log_success "Application servers stopped"
}

run_migrations() {
    log "Running database migrations..."
    
    cd "$PROJECT_ROOT/backend"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would run migrations"
        alembic upgrade head --sql
        return 0
    fi
    
    local start_time=$(date +%s)
    
    # Run migrations
    if ! alembic upgrade head; then
        log_error "Migration failed"
        return 1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "Migrations completed in $duration seconds"
    
    # Verify migration
    log "Verifying migration..."
    if ! python alembic/verify_property_migration.py --database "$DB_NAME"; then
        log_error "Migration verification failed"
        return 1
    fi
    
    log_success "Migration verification passed"
    
    return 0
}

deploy_application() {
    log "Deploying application..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would deploy application"
        return 0
    fi
    
    for server in $APP_SERVERS; do
        log "Deploying to $server..."
        
        # Pull latest code
        ssh "$server" "cd /opt/taxja && git pull origin main" || {
            log_error "Failed to pull code on $server"
            continue
        }
        
        # Build Docker image
        ssh "$server" "cd /opt/taxja && docker-compose build backend" || {
            log_error "Failed to build on $server"
            continue
        }
        
        # Start application
        ssh "$server" "cd /opt/taxja && docker-compose up -d backend" || {
            log_error "Failed to start on $server"
            continue
        }
        
        log_success "Deployed to $server"
    done
    
    # Wait for applications to start
    log "Waiting for applications to start..."
    sleep 30
}

verify_application() {
    log "Verifying application health..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would verify application"
        return 0
    fi
    
    local all_healthy=true
    
    for server in $APP_SERVERS; do
        log "Checking $server..."
        
        if curl -f "http://$server:8000/health" &> /dev/null; then
            log_success "$server is healthy"
        else
            log_error "$server health check failed"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = false ]; then
        log_error "Some servers failed health check"
        return 1
    fi
    
    log_success "All servers healthy"
    return 0
}

test_property_endpoints() {
    log "Testing property endpoints..."
    
    if [ "$SKIP_TESTS" = "true" ]; then
        log_warning "Skipping tests (SKIP_TESTS=true)"
        return 0
    fi
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would test property endpoints"
        return 0
    fi
    
    # Get authentication token
    local token=$(curl -s -X POST "http://${APP_SERVERS%% *}:8000/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${TEST_USER_EMAIL:-admin@taxja.com}\",\"password\":\"${TEST_USER_PASSWORD}\"}" \
        | jq -r '.access_token')
    
    if [ -z "$token" ] || [ "$token" = "null" ]; then
        log_error "Failed to get authentication token"
        return 1
    fi
    
    # Test property listing
    if curl -f -X GET "http://${APP_SERVERS%% *}:8000/api/v1/properties" \
        -H "Authorization: Bearer $token" &> /dev/null; then
        log_success "Property listing endpoint working"
    else
        log_error "Property listing endpoint failed"
        return 1
    fi
    
    log_success "Property endpoints verified"
    return 0
}

disable_maintenance_mode() {
    log "Disabling maintenance mode..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would disable maintenance mode"
        return 0
    fi
    
    for server in $APP_SERVERS; do
        ssh "$server" "rm -f $MAINTENANCE_MODE_FILE" || log_warning "Could not disable maintenance mode on $server"
    done
    
    log_success "Maintenance mode disabled"
}

monitor_deployment() {
    log "Monitoring deployment (15 minutes)..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN: Would monitor deployment"
        return 0
    fi
    
    local end_time=$(($(date +%s) + 900))  # 15 minutes
    local error_count=0
    
    while [ $(date +%s) -lt $end_time ]; do
        # Check error logs
        for server in $APP_SERVERS; do
            local errors=$(ssh "$server" "tail -100 /var/log/taxja/app.log | grep -i error | wc -l")
            if [ "$errors" -gt 10 ]; then
                log_warning "$server has $errors errors in last 100 log lines"
                error_count=$((error_count + 1))
            fi
        done
        
        if [ $error_count -gt 5 ]; then
            log_error "High error rate detected"
            return 1
        fi
        
        sleep 60
    done
    
    log_success "Monitoring completed - no critical issues"
    return 0
}

rollback() {
    log_error "Initiating rollback..."
    
    # Stop application servers
    stop_application_servers
    
    # Rollback database
    cd "$PROJECT_ROOT/backend"
    if ! alembic downgrade 001; then
        log_error "Database rollback failed"
        exit 1
    fi
    
    log_success "Database rolled back"
    
    # Deploy previous version
    for server in $APP_SERVERS; do
        ssh "$server" "cd /opt/taxja && git checkout HEAD~1"
        ssh "$server" "cd /opt/taxja && docker-compose up -d backend"
    done
    
    log_success "Previous application version deployed"
    
    # Disable maintenance mode
    disable_maintenance_mode
    
    log_error "Rollback completed"
}

# Main deployment flow
main() {
    log "========================================="
    log "Property Asset Management - Production Deployment"
    log "========================================="
    log "Start Time: $(date)"
    log "Dry Run: $DRY_RUN"
    log ""
    
    # Confirm deployment
    if ! confirm "Start production deployment?"; then
        log "Deployment cancelled"
        exit 0
    fi
    
    # Phase 1: Pre-deployment
    check_prerequisites
    create_backup
    record_pre_migration_state
    
    # Phase 2: Deployment
    enable_maintenance_mode
    stop_application_servers
    
    if ! run_migrations; then
        log_error "Migration failed - initiating rollback"
        rollback
        exit 1
    fi
    
    deploy_application
    
    if ! verify_application; then
        log_error "Application verification failed"
        if confirm "Rollback deployment?"; then
            rollback
            exit 1
        fi
    fi
    
    if ! test_property_endpoints; then
        log_error "Property endpoint tests failed"
        if confirm "Rollback deployment?"; then
            rollback
            exit 1
        fi
    fi
    
    disable_maintenance_mode
    
    # Phase 3: Post-deployment
    if ! monitor_deployment; then
        log_error "Monitoring detected issues"
        if confirm "Rollback deployment?"; then
            rollback
            exit 1
        fi
    fi
    
    log ""
    log "========================================="
    log_success "Deployment completed successfully!"
    log "========================================="
    log "End Time: $(date)"
    log ""
    log "Next steps:"
    log "1. Monitor application logs for 24 hours"
    log "2. Track user adoption metrics"
    log "3. Review support tickets"
    log "4. Update documentation"
    log ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run       Simulate deployment without making changes"
            echo "  --skip-backup   Skip database backup (not recommended)"
            echo "  --skip-tests    Skip endpoint tests"
            echo "  --help          Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  DB_HOST         Database host (default: production-db-host)"
            echo "  DB_PORT         Database port (default: 5432)"
            echo "  DB_NAME         Database name (default: taxja_production)"
            echo "  DB_USER         Database user (default: taxja_user)"
            echo "  DB_PASSWORD     Database password (required)"
            echo "  APP_SERVERS     Space-separated list of app servers"
            echo ""
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main deployment
main
