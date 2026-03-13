# Production Deployment Checklist - Property Asset Management

## Deployment Information

- **Feature**: Property Asset Management
- **Deployment Date**: _____________
- **Deployment Lead**: _____________
- **Database Administrator**: _____________
- **Maintenance Window**: _____________ to _____________

## Pre-Deployment Phase

### 1. Code and Testing Verification

- [ ] All Phase A-E tasks marked complete in tasks.md
- [ ] All unit tests passing (`pytest backend/tests/`)
- [ ] All property-based tests passing (`pytest backend/tests/ -k properties`)
- [ ] All integration tests passing
- [ ] Frontend tests passing (`npm run test`)
- [ ] E2E tests passing
- [ ] Code review completed and approved
- [ ] Security review completed
- [ ] Performance testing completed

### 2. Documentation Review

- [ ] API documentation updated (`backend/docs/API_PROPERTY_ENDPOINTS.md`)
- [ ] Developer guide reviewed (`backend/docs/DEVELOPER_GUIDE_PROPERTY_MANAGEMENT.md`)
- [ ] User guide prepared
- [ ] Migration deployment guide reviewed
- [ ] Rollback procedures reviewed
- [ ] Austrian tax law references verified

### 3. Staging Validation

- [ ] Deployed to staging environment
- [ ] All migrations tested on staging
- [ ] Rollback tested on staging
- [ ] Manual QA completed on staging
- [ ] Performance benchmarks met on staging
- [ ] Monitoring verified on staging
- [ ] Celery tasks tested on staging
- [ ] Sign-off received from QA team
- [ ] Sign-off received from Product team

### 4. Environment Preparation

- [ ] Production database backup verified (< 24 hours old)
- [ ] Disk space checked (minimum 20% free)
- [ ] Database performance baseline recorded
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified (48 hours advance)
- [ ] User notification email prepared
- [ ] Emergency contacts confirmed
- [ ] Rollback team briefed

### 5. Infrastructure Readiness

- [ ] Redis cache available and tested
- [ ] MinIO/S3 storage available
- [ ] Celery workers configured
- [ ] Celery beat scheduler configured
- [ ] Prometheus monitoring configured
- [ ] Grafana dashboard imported
- [ ] Alert rules configured
- [ ] Log aggregation configured

## Deployment Phase

### 6. Pre-Deployment Backup

**Time**: ___:___ (Start of maintenance window)

- [ ] Application servers stopped
- [ ] Active database connections verified (should be 0)
- [ ] Full database backup created
  ```bash
  pg_dump -h production-db-host -U taxja_user -d taxja_production \
    -F c -f /backup/production/$(date +%Y%m%d)/taxja_production_pre_property_$(date +%Y%m%d_%H%M%S).dump
  ```
- [ ] Backup verified with `pg_restore --list`
- [ ] Backup size checked and reasonable
- [ ] Backup copied to secure location
- [ ] Backup copied to S3/cloud storage
- [ ] Current migration version recorded
- [ ] Table row counts recorded
- [ ] Database size recorded

**Backup File**: _________________________________
**Backup Size**: _________________________________
**Backup Location**: _________________________________

### 7. Database Migration

**Time**: ___:___ 

- [ ] Environment variables verified
- [ ] Database connection tested
- [ ] Current migration version confirmed
- [ ] Migration execution started
  ```bash
  cd backend
  alembic upgrade head
  ```
- [ ] Migration completed successfully
- [ ] Migration duration recorded: _______ seconds
- [ ] Final migration version verified
- [ ] Verification script executed
  ```bash
  python backend/alembic/verify_property_migration.py --database taxja_production
  ```
- [ ] Verification passed (exit code 0)
- [ ] Table structure verified
- [ ] Indexes created successfully
- [ ] Data integrity verified

**Migration Start Time**: ___:___
**Migration End Time**: ___:___
**Migration Duration**: _______ seconds
**Final Version**: _________________________________

### 8. Application Deployment

**Time**: ___:___

- [ ] New application code deployed to all servers
- [ ] Docker images built (if using Docker)
- [ ] Environment variables updated
- [ ] Application servers started
- [ ] Health checks passing on all servers
- [ ] Application logs checked for errors
- [ ] Database connection pool verified

**Servers Deployed**:
- [ ] app-server-1: http://_______________:8000/health
- [ ] app-server-2: http://_______________:8000/health
- [ ] app-server-3: http://_______________:8000/health

### 9. Celery Services Deployment

**Time**: ___:___

- [ ] Celery worker configuration verified
- [ ] Celery beat schedule verified
- [ ] Celery workers started
- [ ] Celery beat scheduler started
- [ ] Flower monitoring dashboard accessible
- [ ] Worker status verified
- [ ] Beat schedule verified
- [ ] Test task executed successfully

**Celery Services**:
- [ ] Worker 1: Status _____________
- [ ] Worker 2: Status _____________
- [ ] Beat Scheduler: Status _____________
- [ ] Flower Dashboard: http://_______________:5555

### 10. Feature Verification

**Time**: ___:___

- [ ] Property endpoints responding
  ```bash
  curl -X GET http://production-app-server:8000/api/v1/properties \
    -H "Authorization: Bearer $TOKEN"
  ```
- [ ] Property creation tested
- [ ] Property listing tested
- [ ] Property detail view tested
- [ ] Property update tested
- [ ] Transaction linking tested
- [ ] Historical depreciation tested
- [ ] Metrics endpoint verified
- [ ] Frontend property pages loading

**Test Results**:
- Property Creation: [ ] Pass [ ] Fail
- Property Listing: [ ] Pass [ ] Fail
- Transaction Linking: [ ] Pass [ ] Fail
- Historical Backfill: [ ] Pass [ ] Fail

### 11. Monitoring Verification

**Time**: ___:___

- [ ] Prometheus metrics endpoint accessible
- [ ] Property metrics visible in Prometheus
- [ ] Grafana dashboard accessible
- [ ] Grafana dashboard showing data
- [ ] Alert rules active
- [ ] Log aggregation working
- [ ] Application logs flowing
- [ ] Database logs flowing

**Monitoring URLs**:
- Prometheus: http://_______________:9090
- Grafana: http://_______________:3000
- Flower: http://_______________:5555

### 12. Maintenance Mode Disabled

**Time**: ___:___

- [ ] Maintenance mode disabled
- [ ] Load balancer health checks restored
- [ ] User traffic flowing
- [ ] Response times normal
- [ ] Error rate normal
- [ ] User notification email sent

## Post-Deployment Phase

### 13. Initial Monitoring (First 15 Minutes)

**Time**: ___:___ to ___:___

- [ ] Application logs monitored (no critical errors)
- [ ] Database performance monitored
- [ ] Response times within SLA (p95 < 500ms)
- [ ] Error rate within acceptable limits (< 1%)
- [ ] CPU usage normal
- [ ] Memory usage normal
- [ ] Database connection pool healthy
- [ ] No user-reported issues

**Metrics Snapshot**:
- Response Time (p95): _______ ms
- Error Rate: _______ %
- CPU Usage: _______ %
- Memory Usage: _______ %
- Active Users: _______

### 14. Extended Monitoring (First Hour)

**Time**: ___:___ to ___:___

- [ ] Continued log monitoring
- [ ] Database query performance checked
- [ ] Slow query log reviewed
- [ ] Cache hit rate verified
- [ ] Celery task queue length normal
- [ ] No memory leaks detected
- [ ] No database connection leaks
- [ ] User feedback monitored

### 15. Smoke Testing

**Time**: ___:___

- [ ] User authentication tested
- [ ] Transaction listing tested
- [ ] Document upload tested
- [ ] Property creation tested (new feature)
- [ ] Property listing tested (new feature)
- [ ] E1 import tested
- [ ] Tax calculation tested
- [ ] Report generation tested

### 16. Performance Validation

**Time**: ___:___

- [ ] Property list query < 100ms
- [ ] Property detail query < 50ms
- [ ] Transaction linking < 500ms
- [ ] Historical backfill < 5s per property
- [ ] Database indexes being used
- [ ] Cache hit rate > 80%
- [ ] No N+1 query issues

**Performance Metrics**:
- Property List: _______ ms
- Property Detail: _______ ms
- Transaction Linking: _______ ms
- Backfill Duration: _______ s

### 17. User Acceptance

**Time**: ___:___ (First 24 hours)

- [ ] Beta users notified
- [ ] User feedback channels monitored
- [ ] Support tickets reviewed
- [ ] Feature adoption tracked
- [ ] No critical user issues reported
- [ ] User satisfaction positive

**User Metrics**:
- Properties Created: _______
- Users Adopting Feature: _______
- Support Tickets: _______
- Critical Issues: _______

## Post-Deployment Communication

### 18. Stakeholder Notification

- [ ] Deployment completion email sent
- [ ] Success metrics shared
- [ ] Known issues documented (if any)
- [ ] Next steps communicated

### 19. Documentation Updates

- [ ] Changelog updated
- [ ] Release notes published
- [ ] User guide published
- [ ] API documentation published
- [ ] Internal wiki updated

## Rollback Decision

**If critical issues are discovered:**

### Rollback Criteria

Initiate rollback if ANY of the following occur:

- [ ] Application crashes or becomes unresponsive
- [ ] Data corruption detected
- [ ] Critical security vulnerability discovered
- [ ] Error rate > 5% for > 5 minutes
- [ ] Response time p95 > 2 seconds for > 5 minutes
- [ ] Database performance degradation > 50%
- [ ] User-reported critical issues > 10

### Rollback Execution

**Time**: ___:___

- [ ] Rollback decision made by: _____________
- [ ] Rollback procedure initiated
- [ ] Application servers stopped
- [ ] Database rolled back to version 001
  ```bash
  alembic downgrade 001
  ```
- [ ] Previous application version deployed
- [ ] Application servers restarted
- [ ] Rollback verification completed
- [ ] Stakeholders notified
- [ ] Post-mortem scheduled

**Rollback Reason**: _________________________________
**Rollback Duration**: _______ minutes

## Sign-Off

### Deployment Team

- [ ] **Deployment Lead**: _____________ Date: _______
- [ ] **Database Administrator**: _____________ Date: _______
- [ ] **Backend Lead**: _____________ Date: _______
- [ ] **Frontend Lead**: _____________ Date: _______
- [ ] **DevOps Lead**: _____________ Date: _______
- [ ] **QA Lead**: _____________ Date: _______

### Management

- [ ] **Product Manager**: _____________ Date: _______
- [ ] **Engineering Manager**: _____________ Date: _______
- [ ] **CTO**: _____________ Date: _______

## Deployment Status

**Final Status**: [ ] SUCCESS [ ] PARTIAL SUCCESS [ ] FAILED [ ] ROLLED BACK

**Deployment Duration**: _______ minutes

**Issues Encountered**: 
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**Lessons Learned**:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**Follow-Up Actions**:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

**Document Version**: 1.0
**Last Updated**: 2026-03-08
**Next Review**: After deployment completion
