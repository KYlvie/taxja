# Backup and Disaster Recovery

This directory contains Kubernetes manifests for automated backups and disaster recovery.

## Backup Strategy

### PostgreSQL Database Backups
- **Schedule**: Daily at 2 AM UTC
- **Retention**: 30 days
- **Location**: MinIO bucket `taxja-backups/postgres/`
- **Format**: Compressed SQL dump (`.sql.gz`)

### MinIO Document Storage Backups
- **Schedule**: Daily at 3 AM UTC
- **Retention**: 30 days
- **Location**: MinIO bucket `taxja-backups/documents-YYYYMMDD-HHMMSS/`
- **Method**: Mirror/sync

## Setup

1. Deploy backup CronJobs:
```bash
kubectl apply -f postgres-backup-cronjob.yaml
kubectl apply -f minio-backup-cronjob.yaml
```

2. Verify CronJobs are scheduled:
```bash
kubectl get cronjobs -n taxja
```

3. Check backup job history:
```bash
kubectl get jobs -n taxja | grep backup
```

## Manual Backup

### PostgreSQL
```bash
# Trigger manual backup
kubectl create job --from=cronjob/postgres-backup postgres-backup-manual -n taxja

# Check job status
kubectl logs job/postgres-backup-manual -n taxja
```

### MinIO
```bash
# Trigger manual backup
kubectl create job --from=cronjob/minio-backup minio-backup-manual -n taxja

# Check job status
kubectl logs job/minio-backup-manual -n taxja
```

## Restore Procedures

### PostgreSQL Restore

1. List available backups:
```bash
kubectl exec -it deployment/postgres -n taxja -- ls -lh /backups/
```

2. Edit restore job with backup filename:
```bash
# Edit restore-job.yaml and set BACKUP_FILE environment variable
# Example: BACKUP_FILE: "taxja-20260304-020000.sql.gz"
```

3. Run restore job:
```bash
kubectl apply -f restore-job.yaml
```

4. Monitor restore progress:
```bash
kubectl logs job/postgres-restore -n taxja -f
```

5. Verify database after restore:
```bash
kubectl exec -it deployment/postgres -n taxja -- psql -U taxja -d taxja -c "\dt"
```

### MinIO Document Restore

1. List available backups:
```bash
kubectl exec -it deployment/minio -n taxja -- mc ls minio/taxja-backups/
```

2. Restore from specific backup:
```bash
# Connect to MinIO pod
kubectl exec -it deployment/minio -n taxja -- sh

# Inside the pod
mc alias set minio http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
mc mirror minio/taxja-backups/documents-20260304-030000/ minio/taxja-documents/
```

## Disaster Recovery Testing

### Test Restore Procedure (Recommended Monthly)

1. Create test namespace:
```bash
kubectl create namespace taxja-dr-test
```

2. Deploy test database:
```bash
kubectl apply -f ../postgres-deployment.yaml -n taxja-dr-test
```

3. Restore latest backup to test database:
```bash
# Modify restore-job.yaml to use taxja-dr-test namespace
kubectl apply -f restore-job.yaml
```

4. Verify data integrity:
```bash
kubectl exec -it deployment/postgres -n taxja-dr-test -- psql -U taxja -d taxja -c "SELECT COUNT(*) FROM users;"
kubectl exec -it deployment/postgres -n taxja-dr-test -- psql -U taxja -d taxja -c "SELECT COUNT(*) FROM transactions;"
```

5. Cleanup test environment:
```bash
kubectl delete namespace taxja-dr-test
```

## Backup Monitoring

### Check Backup Job Status
```bash
# View recent backup jobs
kubectl get jobs -n taxja --sort-by=.metadata.creationTimestamp

# Check for failed backups
kubectl get jobs -n taxja --field-selector status.successful=0
```

### Backup Alerts

Prometheus alerts are configured for:
- Backup job failures
- Backup storage space low
- Backup age exceeding threshold

View alerts in Grafana dashboard or Alertmanager.

## Off-site Backup (Production)

For production environments, configure additional off-site backups:

1. **AWS S3**: Use `mc mirror` to sync to S3
2. **Google Cloud Storage**: Use `gsutil rsync`
3. **Azure Blob Storage**: Use `azcopy sync`

Example S3 sync:
```bash
mc alias set s3 https://s3.amazonaws.com AWS_ACCESS_KEY AWS_SECRET_KEY
mc mirror minio/taxja-backups/ s3/taxja-backups-offsite/
```

## Recovery Time Objective (RTO) and Recovery Point Objective (RPO)

- **RPO**: 24 hours (daily backups)
- **RTO**: 2 hours (estimated time to restore from backup)

For critical production systems, consider:
- Increasing backup frequency (e.g., every 6 hours)
- Implementing continuous replication
- Setting up hot standby database

## Backup Encryption

All backups are encrypted at rest using:
- MinIO server-side encryption (AES-256)
- PostgreSQL backup files stored in encrypted MinIO buckets

For additional security, consider encrypting backup files before upload using GPG.
