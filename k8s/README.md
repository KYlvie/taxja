# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying Taxja to a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured
- NGINX Ingress Controller
- cert-manager (for TLS certificates)
- Metrics Server (for HPA)
- Persistent Volume provisioner

## Directory Structure

```
k8s/
├── namespace.yaml                    # Namespace definition
├── secrets.example.yaml              # Secret template
├── configmap.yaml                    # Application configuration
├── postgres-deployment.yaml          # PostgreSQL database
├── redis-deployment.yaml             # Redis cache
├── minio-deployment.yaml             # MinIO object storage
├── backend-deployment.yaml           # FastAPI backend
├── celery-worker-deployment.yaml     # Celery workers
├── frontend-deployment.yaml          # React frontend
├── ingress.yaml                      # Ingress configuration
├── hpa.yaml                          # Horizontal Pod Autoscaling
├── monitoring/                       # Monitoring stack
│   ├── prometheus-config.yaml        # Prometheus metrics
│   ├── grafana-deployment.yaml       # Grafana dashboards
│   ├── loki-deployment.yaml          # Loki log aggregation
│   └── alertmanager-config.yaml      # Alert configuration
└── backup/                           # Backup and recovery
    ├── postgres-backup-cronjob.yaml  # Database backups
    ├── minio-backup-cronjob.yaml     # Document backups
    ├── restore-job.yaml              # Restore procedures
    └── README.md                     # Backup documentation
```

## Quick Start

### 1. Create Namespace
```bash
kubectl apply -f namespace.yaml
```

### 2. Configure Secrets
```bash
# Copy and edit the secrets file
cp secrets.example.yaml secrets.yaml

# Generate secure random keys
SECRET_KEY=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 24)
MINIO_ACCESS_KEY=$(openssl rand -base64 16)
MINIO_SECRET_KEY=$(openssl rand -base64 32)

# Edit secrets.yaml with your actual values
# Then apply
kubectl apply -f secrets.yaml
```

### 3. Deploy ConfigMap
```bash
kubectl apply -f configmap.yaml
```

### 4. Deploy Infrastructure Services
```bash
# PostgreSQL
kubectl apply -f postgres-deployment.yaml

# Redis
kubectl apply -f redis-deployment.yaml

# MinIO
kubectl apply -f minio-deployment.yaml

# Wait for services to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n taxja --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n taxja --timeout=300s
kubectl wait --for=condition=ready pod -l app=minio -n taxja --timeout=300s
```

### 5. Deploy Application Services
```bash
# Backend API
kubectl apply -f backend-deployment.yaml

# Celery Workers
kubectl apply -f celery-worker-deployment.yaml

# Frontend
kubectl apply -f frontend-deployment.yaml

# Wait for services to be ready
kubectl wait --for=condition=ready pod -l app=backend -n taxja --timeout=300s
kubectl wait --for=condition=ready pod -l app=celery-worker -n taxja --timeout=300s
kubectl wait --for=condition=ready pod -l app=frontend -n taxja --timeout=300s
```

### 6. Configure Ingress and TLS
```bash
# Install cert-manager (if not already installed)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create Let's Encrypt ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@taxja.at
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Deploy ingress
kubectl apply -f ingress.yaml
```

### 7. Enable Horizontal Pod Autoscaling
```bash
kubectl apply -f hpa.yaml
```

### 8. Deploy Monitoring Stack (Optional but Recommended)
```bash
# Prometheus
kubectl apply -f monitoring/prometheus-config.yaml

# Grafana
kubectl apply -f monitoring/grafana-deployment.yaml

# Loki and Promtail
kubectl apply -f monitoring/loki-deployment.yaml

# Alertmanager
kubectl apply -f monitoring/alertmanager-config.yaml
```

### 9. Configure Automated Backups
```bash
# PostgreSQL backups
kubectl apply -f backup/postgres-backup-cronjob.yaml

# MinIO backups
kubectl apply -f backup/minio-backup-cronjob.yaml
```

## Verify Deployment

### Check Pod Status
```bash
kubectl get pods -n taxja
```

Expected output:
```
NAME                              READY   STATUS    RESTARTS   AGE
backend-xxxxx                     1/1     Running   0          5m
celery-worker-xxxxx               1/1     Running   0          5m
celery-beat-xxxxx                 1/1     Running   0          5m
frontend-xxxxx                    1/1     Running   0          5m
postgres-xxxxx                    1/1     Running   0          10m
redis-xxxxx                       1/1     Running   0          10m
minio-xxxxx                       1/1     Running   0          10m
```

### Check Services
```bash
kubectl get services -n taxja
```

### Check Ingress
```bash
kubectl get ingress -n taxja
kubectl describe ingress taxja-ingress -n taxja
```

### Test Application
```bash
# Test backend health
curl https://taxja.at/api/health

# Test frontend
curl https://taxja.at/
```

## Scaling

### Manual Scaling
```bash
# Scale backend
kubectl scale deployment backend -n taxja --replicas=5

# Scale Celery workers
kubectl scale deployment celery-worker -n taxja --replicas=4

# Scale frontend
kubectl scale deployment frontend -n taxja --replicas=3
```

### Horizontal Pod Autoscaling (HPA)
HPA is configured in `hpa.yaml` and will automatically scale based on CPU/memory usage:

- **Backend**: 3-10 replicas (70% CPU, 80% memory)
- **Celery Workers**: 2-8 replicas (75% CPU, 85% memory)
- **Frontend**: 2-5 replicas (60% CPU)

Check HPA status:
```bash
kubectl get hpa -n taxja
```

## Monitoring and Logging

### View Logs
```bash
# Backend logs
kubectl logs -f deployment/backend -n taxja

# Celery worker logs
kubectl logs -f deployment/celery-worker -n taxja

# Frontend logs
kubectl logs -f deployment/frontend -n taxja

# All logs from a specific pod
kubectl logs -f <pod-name> -n taxja
```

### Access Grafana Dashboard
```bash
# Port forward to access locally
kubectl port-forward svc/grafana 3000:3000 -n taxja

# Open http://localhost:3000
# Default credentials: admin / (from secrets)
```

### Access Prometheus
```bash
kubectl port-forward svc/prometheus 9090:9090 -n taxja
# Open http://localhost:9090
```

## Backup and Disaster Recovery

See [backup/README.md](backup/README.md) for detailed backup and restore procedures.

### Quick Backup Commands
```bash
# Trigger manual PostgreSQL backup
kubectl create job --from=cronjob/postgres-backup postgres-backup-manual -n taxja

# Trigger manual MinIO backup
kubectl create job --from=cronjob/minio-backup minio-backup-manual -n taxja
```

## Troubleshooting

### Pod Not Starting
```bash
# Describe pod to see events
kubectl describe pod <pod-name> -n taxja

# Check logs
kubectl logs <pod-name> -n taxja

# Check previous logs if pod restarted
kubectl logs <pod-name> -n taxja --previous
```

### Database Connection Issues
```bash
# Check PostgreSQL pod
kubectl get pod -l app=postgres -n taxja

# Test database connection
kubectl exec -it deployment/postgres -n taxja -- psql -U taxja -d taxja -c "SELECT 1;"
```

### Ingress Not Working
```bash
# Check ingress status
kubectl describe ingress taxja-ingress -n taxja

# Check cert-manager certificate
kubectl get certificate -n taxja
kubectl describe certificate taxja-tls -n taxja

# Check NGINX ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

### High Memory/CPU Usage
```bash
# Check resource usage
kubectl top pods -n taxja
kubectl top nodes

# Check HPA status
kubectl get hpa -n taxja
kubectl describe hpa backend-hpa -n taxja
```

## Updating Deployment

### Update Image Version
```bash
# Update backend
kubectl set image deployment/backend backend=taxja/backend:v1.2.0 -n taxja

# Update frontend
kubectl set image deployment/frontend frontend=taxja/frontend:v1.2.0 -n taxja

# Check rollout status
kubectl rollout status deployment/backend -n taxja
```

### Rollback Deployment
```bash
# Rollback to previous version
kubectl rollout undo deployment/backend -n taxja

# Rollback to specific revision
kubectl rollout undo deployment/backend --to-revision=2 -n taxja

# Check rollout history
kubectl rollout history deployment/backend -n taxja
```

## Cleanup

### Delete All Resources
```bash
kubectl delete namespace taxja
```

### Delete Specific Resources
```bash
# Delete application only (keep data)
kubectl delete deployment backend frontend celery-worker celery-beat -n taxja

# Delete monitoring stack
kubectl delete -f monitoring/
```

## Production Checklist

Before deploying to production, ensure:

- [ ] Secrets are properly configured with strong random values
- [ ] TLS certificates are configured and valid
- [ ] Backup CronJobs are scheduled and tested
- [ ] Monitoring and alerting are configured
- [ ] Resource limits are set appropriately
- [ ] HPA is configured and tested
- [ ] Ingress is configured with proper domain
- [ ] Database is using persistent storage
- [ ] MinIO is using persistent storage
- [ ] Security headers are configured in nginx.conf
- [ ] CORS origins are properly configured
- [ ] Log aggregation is working
- [ ] Disaster recovery procedures are documented and tested

## Security Considerations

1. **Secrets Management**: Use Kubernetes secrets or external secret managers (e.g., HashiCorp Vault)
2. **Network Policies**: Implement network policies to restrict pod-to-pod communication
3. **RBAC**: Configure Role-Based Access Control for kubectl access
4. **Pod Security**: Use Pod Security Standards (restricted profile)
5. **Image Scanning**: Scan Docker images for vulnerabilities before deployment
6. **TLS**: Ensure all external traffic uses TLS 1.3
7. **Backup Encryption**: Encrypt backups at rest and in transit

## Support

For issues or questions:
- GitHub Issues: https://github.com/taxja/taxja/issues
- Email: support@taxja.at
- Documentation: https://docs.taxja.at
