# Production Deployment Guide - Property Asset Management

## Overview

This guide provides comprehensive instructions for deploying the Property Asset Management feature to production. The deployment supports both Docker Compose (single-server) and Kubernetes (multi-server) environments.

## Feature Summary

The Property Asset Management feature enables:
- Property registration and tracking for landlords
- Automatic depreciation (AfA) calculation per Austrian tax law
- Property-transaction linking
- Historical depreciation backfill
- Property reports and analytics
- E1/Bescheid integration
- Multi-property portfolio management

## Prerequisites

### Required Tools
- Docker and Docker Compose (for Docker deployment)
- kubectl and Kubernetes cluster access (for K8s deployment)
- Git
- Python 3.11+
- PostgreSQL client tools
- curl or similar HTTP client

### Access Requirements
- Production environment access
- Database credentials
- Git repository access
- SSL/TLS certificates
- Sufficient disk space (>30% free)
- Backup storage access

### Pre-Deployment Requirements
- [ ] Staging deployment completed successfully
- [ ] Staging monitored for 24-48 hours with no critical issues
- [ ] User acceptance testing completed
- [ ] All stakeholders notified
- [ ] Maintenance window scheduled
- [ ] Rollback plan approved
- [ ] Backup procedures tested

## Deployment Architecture

### Docker Compose (Single Server)
Suitable for small to medium deployments (< 1000 users)

### Kubernetes (Multi-Server)
Recommended for production deployments (> 1000 users)
- High availability
- Auto-scaling
- Load balancing
- Zero-downtime deployments

## Pre-Deployment Checklist

### 1. Code Readiness
- [x] All Phase A-E tasks completed
- [x] All tests passing (unit, integration, property-based)
- [x] Code reviewed and approved
- [x] Documentation complete
- [x] Staging deployment successful

### 2. Database Migrations
- [x] 8 property migrations created (002-009)
- [x] Migration test guide reviewed
- [x] Rollback procedures documented
- [x] Migrations tested on staging

### 3. Environment Preparation
- [ ] Production environment accessible
- [ ] Production database backup created
- [ ] Disk space verified (>30% free)
- [ ] SSL/TLS certificates valid
- [ ] Environment variables configured
- [ ] Monitoring configured
- [ ] Alerting configured

### 4. Stakeholder Communication
- [ ] Deployment scheduled
- [ ] Team notified
- [ ] Users notified (if maintenance window)
- [ ] Rollback plan approved
- [ ] On-call engineer assigned

---

## Deployment Method 1: Docker Compose (Single Server)

### Phase 1: Pre-Deployment (30 minutes)

#### 1.1 Verify Environment

```bash
# Check Docker
docker --version
docker-compose --version

# Check disk space (should be >30% free)
df -h

# Check services are running
docker-compose ps

# Check system resources
free -h
top -bn1 | head -20
```

**Status**: [ ] Complete

#### 1.2 Create Backup

```bash
# Create backup directory
mkdir -p backup/production/$(date +%Y%m%d)

# Backup database
docker-compose exec postgres pg_dump -U taxja -d taxja | gzip > \
  backup/production/$(date +%Y%m%d)/taxja_production_pre_property_$(date +%Y%m%d_%H%M%S).sql.gz

# Backup MinIO documents
docker-compose exec minio mc mirror /data/taxja backup/production/$(date +%Y%m%d)/minio/

# Verify backups
ls -lh backup/production/$(date +%Y%m%d)/
```

**CRITICAL**: Verify backup was created successfully and test restore on a separate system before proceeding!

**Status**: [ ] Complete  
**Backup Location**: ___________________________  
**Backup Size**: ___________________________

#### 1.3 Check Current State

```bash
# Check migration version
cd backend
alembic current

# Check database size and statistics
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT
    pg_size_pretty(pg_database_size('taxja')) as database_size,
    pg_size_pretty(pg_total_relation_size('transactions')) as transactions_size,
    pg_size_pretty(pg_total_relation_size('users')) as users_size,
    pg_size_pretty(pg_total_relation_size('documents')) as documents_size;
"

# Check table counts
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT 'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL SELECT 'documents', COUNT(*) FROM documents;
"

cd ..
```

**Status**: [ ] Complete  
**Current Migration**: ___________________________  
**Database Size**: ___________________________  
**User Count**: ___________________________  
**Transaction Count**: ___________________________

### Phase 2: Build and Deploy (30 minutes)

#### 2.1 Pull Latest Code

```bash
# Ensure on production branch/tag
git fetch --all --tags
git checkout tags/v1.x.0  # Replace with actual version

# Verify commit
git log -1 --oneline
```

**Status**: [ ] Complete  
**Version**: ___________________________  
**Commit Hash**: ___________________________

#### 2.2 Build Docker Images

```bash
# Build backend image
docker-compose build --no-cache backend

# Build frontend image
docker-compose build --no-cache frontend

# Tag images with version
docker tag taxja/backend:latest taxja/backend:v1.x.0
docker tag taxja/frontend:latest taxja/frontend:v1.x.0

# Verify images
docker images | grep taxja
```

**Status**: [ ] Complete  
**Backend Image**: ___________________________  
**Frontend Image**: ___________________________

#### 2.3 Enable Maintenance Mode (Optional)

```bash
# Create maintenance page
cat > maintenance.html <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Taxja - Wartung</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Wartungsarbeiten</h1>
    <p>Taxja wird gerade aktualisiert. Wir sind in wenigen Minuten wieder für Sie da.</p>
    <p>Maintenance in progress. We'll be back shortly.</p>
</body>
</html>
EOF

# Configure nginx to serve maintenance page
# (Implementation depends on your nginx setup)
```

**Status**: [ ] Complete (if applicable)

#### 2.4 Stop Application Services

```bash
# Stop only application services (keep data services running)
docker-compose stop backend frontend celery-worker celery-beat

# Verify stopped
docker-compose ps
```

**Status**: [ ] Complete  
**Stopped At**: ___________________________

### Phase 3: Database Migration (20 minutes)

#### 3.1 Apply Migrations

```bash
cd backend

# Set environment
export DATABASE_URL="postgresql://taxja:${POSTGRES_PASSWORD}@localhost:5432/taxja"

# Apply migrations one at a time with verification
echo "Applying migration 002: Add properties table"
alembic upgrade 002
docker-compose exec postgres psql -U taxja -d taxja -c "\d properties"

echo "Applying migration 003: Add property_id to transactions"
alembic upgrade 003
docker-compose exec postgres psql -U taxja -d taxja -c "\d transactions" | grep property_id

echo "Applying migration 004: Add property_loans table"
alembic upgrade 004

echo "Applying migration 005: Add historical_import tables"
alembic upgrade 005

echo "Applying migration 006: Add performance indexes"
alembic upgrade 006

echo "Applying migration 007: Increase column sizes for encryption"
alembic upgrade 007

echo "Applying migration 008: Encrypt existing property addresses"
alembic upgrade 008

echo "Applying migration 009: Add audit_logs table"
alembic upgrade 009

# Verify final state
alembic current

cd ..
```

**Status**: [ ] Complete  
**Final Migration**: ___________________________  
**Migration Duration**: ___________________________  
**Any Errors**: ___________________________

#### 3.2 Verify Migration

```bash
# Check tables exist
docker-compose exec postgres psql -U taxja -d taxja -c "\dt" | grep -E "properties|property_loans|audit_logs"

# Check indexes
docker-compose exec postgres psql -U taxja -d taxja -c "\di" | grep -E "idx_properties|idx_transactions"

# Verify constraints
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT conname, contype, convalidated
FROM pg_constraint
WHERE conrelid IN ('properties'::regclass, 'transactions'::regclass)
ORDER BY conrelid, conname;
"

# Check data integrity
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT COUNT(*) as total_transactions,
       COUNT(property_id) as transactions_with_property
FROM transactions;
"
```

**Status**: [ ] Complete  
**Tables Created**: ___________________________  
**Indexes Created**: ___________________________

### Phase 4: Application Deployment (20 minutes)

#### 4.1 Start Services

```bash
# Start all services
docker-compose up -d

# Wait for services to be ready
sleep 60

# Check service status
docker-compose ps
```

**Status**: [ ] Complete  
**All Services Running**: [ ] Yes [ ] No

#### 4.2 Verify Application Health

```bash
# Check backend health
curl https://taxja.at/api/health

# Expected: {"status":"healthy"} or similar

# Check API docs
curl https://taxja.at/api/docs

# Check frontend
curl https://taxja.at/

# Check SSL certificate
openssl s_client -connect taxja.at:443 -servername taxja.at < /dev/null 2>/dev/null | openssl x509 -noout -dates
```

**Status**: [ ] Complete  
**Backend Health**: ___________________________  
**Frontend Accessible**: [ ] Yes [ ] No  
**SSL Valid**: [ ] Yes [ ] No

#### 4.3 Disable Maintenance Mode

```bash
# Remove maintenance page configuration
# (Implementation depends on your nginx setup)
```

**Status**: [ ] Complete

### Phase 5: Verification (45 minutes)

#### 5.1 Smoke Tests

```bash
# Test authentication
curl -X POST https://taxja.at/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'

# Test property endpoints (should return empty array for new users)
TOKEN="<token-from-login>"
curl -X GET https://taxja.at/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"

# Test property creation
curl -X POST https://taxja.at/api/v1/properties \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_type": "rental",
    "street": "Teststraße 1",
    "city": "Wien",
    "postal_code": "1010",
    "purchase_date": "2020-01-01",
    "purchase_price": 300000.00,
    "building_value": 240000.00,
    "construction_year": 1990
  }'
```

**Status**: [ ] Complete  
**All Smoke Tests Passed**: [ ] Yes [ ] No

#### 5.2 Monitor Logs

```bash
# Monitor backend logs for errors (15 minutes)
docker-compose logs -f backend | grep -i "error\|exception\|property"

# Monitor Celery logs
docker-compose logs -f celery-worker | grep -i "error\|exception"

# Check for any critical errors
docker-compose logs backend | grep -i "critical\|fatal" | tail -20
```

**Status**: [ ] Complete  
**Errors Found**: [ ] Yes [ ] No  
**Error Details**: ___________________________

#### 5.3 Performance Testing

```bash
# Test API response times
time curl -X GET https://taxja.at/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"

# Expected: < 500ms

# Test database query performance
docker-compose exec postgres psql -U taxja -d taxja -c "
EXPLAIN ANALYZE
SELECT * FROM properties WHERE user_id = 1;
"

# Check index usage
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename IN ('properties', 'transactions')
ORDER BY idx_scan DESC;
"
```

**Status**: [ ] Complete  
**Response Times Acceptable**: [ ] Yes [ ] No

---

## Deployment Method 2: Kubernetes (Multi-Server)

### Phase 1: Pre-Deployment (30 minutes)

#### 1.1 Verify Kubernetes Cluster

```bash
# Check kubectl access
kubectl cluster-info
kubectl get nodes

# Check namespace
kubectl get namespace taxja || kubectl create namespace taxja

# Check resource availability
kubectl top nodes
kubectl describe nodes | grep -A 5 "Allocated resources"
```

**Status**: [ ] Complete  
**Cluster Version**: ___________________________  
**Node Count**: ___________________________

#### 1.2 Create Backup

```bash
# Backup PostgreSQL
kubectl exec -n taxja deployment/postgres -- pg_dump -U taxja -d taxja | gzip > \
  backup/production/$(date +%Y%m%d)/taxja_k8s_pre_property_$(date +%Y%m%d_%H%M%S).sql.gz

# Backup MinIO
kubectl exec -n taxja deployment/minio -- mc mirror /data/taxja /backup/

# Backup Kubernetes resources
kubectl get all -n taxja -o yaml > backup/production/$(date +%Y%m%d)/k8s_resources_backup.yaml

# Verify backups
ls -lh backup/production/$(date +%Y%m%d)/
```

**Status**: [ ] Complete  
**Backup Location**: ___________________________

#### 1.3 Check Current State

```bash
# Check current deployments
kubectl get deployments -n taxja

# Check pod status
kubectl get pods -n taxja

# Check database state
kubectl exec -n taxja deployment/postgres -- psql -U taxja -d taxja -c "
SELECT
    'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions;
"

# Check current migration
kubectl exec -n taxja deployment/backend -- alembic current
```

**Status**: [ ] Complete  
**Current Migration**: ___________________________

### Phase 2: Build and Push Images (30 minutes)

#### 2.1 Build Docker Images

```bash
# Build images with version tag
docker build -t taxja/backend:v1.x.0 -f backend/Dockerfile backend/
docker build -t taxja/frontend:v1.x.0 -f frontend/Dockerfile frontend/

# Tag as latest
docker tag taxja/backend:v1.x.0 taxja/backend:latest
docker tag taxja/frontend:v1.x.0 taxja/frontend:latest
```

**Status**: [ ] Complete

#### 2.2 Push to Container Registry

```bash
# Login to registry (adjust for your registry)
docker login registry.taxja.at

# Push images
docker push taxja/backend:v1.x.0
docker push taxja/backend:latest
docker push taxja/frontend:v1.x.0
docker push taxja/frontend:latest

# Verify images
docker pull taxja/backend:v1.x.0
docker pull taxja/frontend:v1.x.0
```

**Status**: [ ] Complete  
**Registry**: ___________________________

### Phase 3: Database Migration (20 minutes)

#### 3.1 Scale Down Application Pods

```bash
# Scale down to prevent concurrent access during migration
kubectl scale deployment backend -n taxja --replicas=0
kubectl scale deployment celery-worker -n taxja --replicas=0

# Wait for pods to terminate
kubectl wait --for=delete pod -l app=backend -n taxja --timeout=120s
kubectl wait --for=delete pod -l app=celery-worker -n taxja --timeout=120s
```

**Status**: [ ] Complete

#### 3.2 Run Migration Job

```bash
# Create migration job
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: property-migration
  namespace: taxja
spec:
  template:
    spec:
      containers:
      - name: migration
        image: taxja/backend:v1.x.0
        command: ["alembic", "upgrade", "head"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: taxja-secrets
              key: database-url
      restartPolicy: Never
  backoffLimit: 3
EOF

# Wait for migration to complete
kubectl wait --for=condition=complete job/property-migration -n taxja --timeout=600s

# Check migration logs
kubectl logs job/property-migration -n taxja

# Verify migration
kubectl exec -n taxja deployment/postgres -- psql -U taxja -d taxja -c "\dt" | grep properties
```

**Status**: [ ] Complete  
**Migration Duration**: ___________________________

### Phase 4: Deploy Updated Application (20 minutes)

#### 4.1 Update Deployments

```bash
# Update backend deployment
kubectl set image deployment/backend backend=taxja/backend:v1.x.0 -n taxja

# Update frontend deployment
kubectl set image deployment/frontend frontend=taxja/frontend:v1.x.0 -n taxja

# Scale back up
kubectl scale deployment backend -n taxja --replicas=3
kubectl scale deployment celery-worker -n taxja --replicas=2

# Wait for rollout
kubectl rollout status deployment/backend -n taxja
kubectl rollout status deployment/frontend -n taxja

# Check pod status
kubectl get pods -n taxja
```

**Status**: [ ] Complete  
**All Pods Running**: [ ] Yes [ ] No

#### 4.2 Verify Application Health

```bash
# Check pod health
kubectl get pods -n taxja -o wide

# Check service endpoints
kubectl get endpoints -n taxja

# Test backend health
kubectl exec -n taxja deployment/backend -- curl http://localhost:8000/health

# Test from outside cluster
curl https://taxja.at/api/health
```

**Status**: [ ] Complete  
**Health Checks Passing**: [ ] Yes [ ] No

### Phase 5: Verification (45 minutes)

#### 5.1 Smoke Tests

```bash
# Test property endpoints
curl -X GET https://taxja.at/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"

# Test property creation
curl -X POST https://taxja.at/api/v1/properties \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_type": "rental",
    "street": "Teststraße 1",
    "city": "Wien",
    "postal_code": "1010",
    "purchase_date": "2020-01-01",
    "purchase_price": 300000.00,
    "building_value": 240000.00,
    "construction_year": 1990
  }'
```

**Status**: [ ] Complete

#### 5.2 Monitor Logs

```bash
# Monitor backend logs
kubectl logs -f deployment/backend -n taxja | grep -i "error\|property"

# Monitor all pods
kubectl logs -f -l app=backend -n taxja --all-containers=true
```

**Status**: [ ] Complete

#### 5.3 Check Metrics

```bash
# Check pod resource usage
kubectl top pods -n taxja

# Check HPA status
kubectl get hpa -n taxja

# Check Prometheus metrics (if configured)
curl http://prometheus.taxja.at/api/v1/query?query=up{namespace="taxja"}
```

**Status**: [ ] Complete

---

## Post-Deployment Checklist

### Success Criteria
- [ ] All migrations applied successfully
- [ ] Application health checks pass
- [ ] No errors in application logs (30 min monitoring)
- [ ] Database performance within acceptable limits
- [ ] Property endpoints respond correctly
- [ ] No increase in error rate
- [ ] Response times within SLA (p95 < 500ms)
- [ ] Frontend UI works correctly
- [ ] All smoke tests pass
- [ ] Monitoring and alerting functional

### Monitoring (First 24 Hours)

```bash
# Monitor error rates
# Check application logs every 2 hours
# Monitor database performance
# Track API response times
# Monitor user feedback channels
```

**Monitoring Schedule**:
- Hour 0-2: Continuous monitoring
- Hour 2-8: Check every 30 minutes
- Hour 8-24: Check every 2 hours
- Day 2-7: Check daily

### Sign-Off
- [ ] Development Team Lead: ___________________________
- [ ] QA Team Lead: ___________________________
- [ ] Product Manager: ___________________________
- [ ] DevOps Lead: ___________________________
- [ ] Security Team: ___________________________

**Deployment Completed**: [ ] Yes [ ] No  
**Deployment Date/Time**: ___________________________  
**Deployed By**: ___________________________

---

## Rollback Procedures

### Docker Compose Rollback

```bash
# 1. Stop services
docker-compose stop backend frontend celery-worker celery-beat

# 2. Rollback database migrations
cd backend
alembic downgrade 001

# 3. Restore database from backup
gunzip < backup/production/YYYYMMDD/taxja_production_pre_property_*.sql.gz | \
  docker-compose exec -T postgres psql -U taxja -d taxja

# 4. Restore previous version
git checkout <previous-version-tag>
docker-compose build backend frontend
docker-compose up -d

# 5. Verify rollback
alembic current
curl https://taxja.at/api/health
```

### Kubernetes Rollback

```bash
# 1. Rollback deployments
kubectl rollout undo deployment/backend -n taxja
kubectl rollout undo deployment/frontend -n taxja

# 2. Scale down for database rollback
kubectl scale deployment backend -n taxja --replicas=0
kubectl scale deployment celery-worker -n taxja --replicas=0

# 3. Rollback database
kubectl exec -n taxja deployment/backend -- alembic downgrade 001

# Or restore from backup
gunzip < backup/production/YYYYMMDD/taxja_k8s_pre_property_*.sql.gz | \
  kubectl exec -i -n taxja deployment/postgres -- psql -U taxja -d taxja

# 4. Scale back up
kubectl scale deployment backend -n taxja --replicas=3
kubectl scale deployment celery-worker -n taxja --replicas=2

# 5. Verify rollback
kubectl exec -n taxja deployment/backend -- alembic current
curl https://taxja.at/api/health
```

**Rollback Executed**: [ ] Yes [ ] No  
**Rollback Reason**: ___________________________  
**Rollback Completed At**: ___________________________

---

## Troubleshooting

### Issue: Migration Fails

**Symptom**: Alembic upgrade command fails

**Solution**:
```bash
# Check current migration state
alembic current

# Check migration history
alembic history

# Try upgrading one migration at a time
alembic upgrade +1

# Check database logs
docker-compose logs postgres
# or
kubectl logs deployment/postgres -n taxja
```

### Issue: Service Won't Start

**Symptom**: Container/pod exits immediately

**Solution**:
```bash
# Docker Compose
docker-compose logs backend
docker-compose restart backend

# Kubernetes
kubectl describe pod <pod-name> -n taxja
kubectl logs <pod-name> -n taxja --previous
kubectl delete pod <pod-name> -n taxja
```

### Issue: High Error Rate

**Symptom**: Increased 500 errors after deployment

**Solution**:
```bash
# Check application logs
docker-compose logs backend | grep -i "error\|exception"
# or
kubectl logs -l app=backend -n taxja | grep -i "error\|exception"

# Check database connectivity
docker-compose exec backend python -c "from app.db.session import engine; engine.connect()"

# Consider rollback if errors persist
```

### Issue: Performance Degradation

**Symptom**: Slow response times

**Solution**:
```bash
# Check database query performance
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"

# Check index usage
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT * FROM pg_stat_user_indexes
WHERE tablename IN ('properties', 'transactions')
ORDER BY idx_scan DESC;
"

# Scale up resources (Kubernetes)
kubectl scale deployment backend -n taxja --replicas=5
```

---

## Success Metrics

Track these metrics for 7 days post-deployment:

- **Uptime**: > 99.9%
- **Error Rate**: < 0.1%
- **API Response Time (p95)**: < 500ms
- **Database Query Time (p95)**: < 100ms
- **User Complaints**: 0 critical issues

---

## Next Steps

After successful production deployment:

1. **Monitor for 7 days**
   - Check logs daily
   - Monitor error rates
   - Track performance metrics
   - Review user feedback

2. **Optimize if Needed**
   - Tune database queries
   - Adjust resource limits
   - Optimize caching

3. **Documentation**
   - Update runbooks
   - Document lessons learned
   - Update deployment procedures

4. **Team Retrospective**
   - Review deployment process
   - Identify improvements
   - Update procedures

---

## Support Contacts

- **On-Call Engineer**: ___________________________
- **Database Admin**: ___________________________
- **DevOps Lead**: ___________________________
- **Development Lead**: ___________________________

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-08  
**Status**: Ready for Production Deployment
