# Taxja Deployment Guide

Complete guide for deploying Taxja Austrian Tax Management System to production.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development](#local-development)
4. [Staging Deployment](#staging-deployment)
5. [Production Deployment](#production-deployment)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
9. [Security Hardening](#security-hardening)
10. [Troubleshooting](#troubleshooting)

## Overview

Taxja uses a containerized microservices architecture deployed on Kubernetes. The system consists of:

- **Frontend**: React 18 + TypeScript (Nginx)
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Storage**: MinIO (S3-compatible)
- **Task Queue**: Celery workers
- **Monitoring**: Prometheus + Grafana + Loki

## Prerequisites

### Required Tools

- Docker 24+
- Docker Compose 2.20+
- kubectl 1.28+
- Kubernetes cluster 1.25+
- Helm 3.12+ (optional)
- Git

### Required Services

- Domain name (e.g., taxja.at)
- SSL/TLS certificate (Let's Encrypt recommended)
- SMTP server for email notifications
- Container registry (Docker Hub, AWS ECR, or GCR)

### Infrastructure Requirements

**Minimum (Development/Staging)**:
- 3 nodes
- 4 CPU cores per node
- 8 GB RAM per node
- 100 GB storage

**Recommended (Production)**:
- 5+ nodes
- 8 CPU cores per node
- 16 GB RAM per node
- 500 GB storage (with auto-scaling)

## Local Development

### Using Docker Compose

1. Clone the repository:
```bash
git clone https://github.com/taxja/taxja.git
cd taxja
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start all services:
```bash
make up
# or
docker-compose up -d
```

4. Access the application:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

5. Run database migrations:
```bash
docker-compose exec backend alembic upgrade head
```

6. Create initial admin user:
```bash
docker-compose exec backend python -m app.db.init_db
```

### Development Workflow

```bash
# Start only infrastructure (for local backend/frontend development)
make dev

# View logs
make logs

# Run tests
make test

# Stop all services
make down

# Clean up (removes volumes)
make clean
```

## Staging Deployment

### 1. Prepare Kubernetes Cluster

```bash
# Verify cluster access
kubectl cluster-info
kubectl get nodes

# Create namespace
kubectl create namespace taxja-staging
```

### 2. Configure Secrets

```bash
cd k8s

# Generate secure keys
SECRET_KEY=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 24)
MINIO_ACCESS_KEY=$(openssl rand -base64 16)
MINIO_SECRET_KEY=$(openssl rand -base64 32)

# Create secrets
kubectl create secret generic taxja-secrets \
  --from-literal=secret-key=$SECRET_KEY \
  --from-literal=encryption-key=$ENCRYPTION_KEY \
  --from-literal=postgres-user=taxja \
  --from-literal=postgres-password=$POSTGRES_PASSWORD \
  --from-literal=minio-access-key=$MINIO_ACCESS_KEY \
  --from-literal=minio-secret-key=$MINIO_SECRET_KEY \
  --from-literal=grafana-admin-user=admin \
  --from-literal=grafana-admin-password=$(openssl rand -base64 16) \
  -n taxja-staging
```

### 3. Deploy Infrastructure

```bash
# ConfigMap
kubectl apply -f configmap.yaml -n taxja-staging

# PostgreSQL
kubectl apply -f postgres-deployment.yaml -n taxja-staging

# Redis
kubectl apply -f redis-deployment.yaml -n taxja-staging

# MinIO
kubectl apply -f minio-deployment.yaml -n taxja-staging

# Wait for services
kubectl wait --for=condition=ready pod -l app=postgres -n taxja-staging --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n taxja-staging --timeout=300s
kubectl wait --for=condition=ready pod -l app=minio -n taxja-staging --timeout=300s
```

### 4. Deploy Application

```bash
# Backend
kubectl apply -f backend-deployment.yaml -n taxja-staging

# Celery Workers
kubectl apply -f celery-worker-deployment.yaml -n taxja-staging

# Frontend
kubectl apply -f frontend-deployment.yaml -n taxja-staging

# Wait for services
kubectl wait --for=condition=ready pod -l app=backend -n taxja-staging --timeout=300s
```

### 5. Configure Ingress

```bash
# Update ingress.yaml with staging domain (e.g., staging.taxja.at)
kubectl apply -f ingress.yaml -n taxja-staging
```

### 6. Run Database Migrations

```bash
kubectl exec -it deployment/backend -n taxja-staging -- alembic upgrade head
```

### 7. Verify Deployment

```bash
# Check all pods
kubectl get pods -n taxja-staging

# Test backend
curl https://staging.taxja.at/api/health

# Test frontend
curl https://staging.taxja.at/
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] All tests passing in CI/CD
- [ ] Staging deployment verified
- [ ] Database backup completed
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured
- [ ] On-call team notified
- [ ] Maintenance window scheduled (if needed)

### 1. Prepare Production Namespace

```bash
kubectl create namespace taxja
```

### 2. Configure Production Secrets

```bash
# Use strong, unique values for production
kubectl create secret generic taxja-secrets \
  --from-literal=secret-key=$PROD_SECRET_KEY \
  --from-literal=encryption-key=$PROD_ENCRYPTION_KEY \
  --from-literal=postgres-user=taxja \
  --from-literal=postgres-password=$PROD_POSTGRES_PASSWORD \
  --from-literal=minio-access-key=$PROD_MINIO_ACCESS_KEY \
  --from-literal=minio-secret-key=$PROD_MINIO_SECRET_KEY \
  --from-literal=grafana-admin-user=admin \
  --from-literal=grafana-admin-password=$PROD_GRAFANA_PASSWORD \
  -n taxja
```

### 3. Deploy Infrastructure

```bash
# Apply all infrastructure manifests
kubectl apply -f configmap.yaml -n taxja
kubectl apply -f postgres-deployment.yaml -n taxja
kubectl apply -f redis-deployment.yaml -n taxja
kubectl apply -f minio-deployment.yaml -n taxja
```

### 4. Deploy Application

```bash
# Deploy application services
kubectl apply -f backend-deployment.yaml -n taxja
kubectl apply -f celery-worker-deployment.yaml -n taxja
kubectl apply -f frontend-deployment.yaml -n taxja

# Enable autoscaling
kubectl apply -f hpa.yaml -n taxja
```

### 5. Configure Ingress and TLS

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
kubectl apply -f ingress.yaml -n taxja
```

### 6. Deploy Monitoring Stack

```bash
kubectl apply -f monitoring/prometheus-config.yaml -n taxja
kubectl apply -f monitoring/grafana-deployment.yaml -n taxja
kubectl apply -f monitoring/loki-deployment.yaml -n taxja
kubectl apply -f monitoring/alertmanager-config.yaml -n taxja
```

### 7. Configure Automated Backups

```bash
kubectl apply -f backup/postgres-backup-cronjob.yaml -n taxja
kubectl apply -f backup/minio-backup-cronjob.yaml -n taxja
```

### 8. Run Database Migrations

```bash
kubectl exec -it deployment/backend -n taxja -- alembic upgrade head
```

### 9. Smoke Tests

```bash
# Test backend health
curl https://taxja.at/api/health

# Test frontend
curl https://taxja.at/

# Test authentication
curl -X POST https://taxja.at/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
```

### 10. Post-Deployment Verification

- [ ] All pods running
- [ ] Health checks passing
- [ ] Ingress routing correctly
- [ ] TLS certificates valid
- [ ] Monitoring dashboards showing data
- [ ] Logs being collected
- [ ] Backups scheduled
- [ ] Alerts configured

## CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline is configured in `.github/workflows/ci-cd.yml`:

1. **Backend Tests**: Run pytest with coverage
2. **Frontend Tests**: Run vitest and linting
3. **Build Images**: Build and push Docker images
4. **Deploy Staging**: Automatic deployment to staging
5. **Deploy Production**: Manual approval required

### Setting Up CI/CD

1. Configure GitHub Secrets:
```
DOCKER_USERNAME: Your Docker Hub username
DOCKER_PASSWORD: Your Docker Hub password
KUBE_CONFIG_STAGING: Base64-encoded kubeconfig for staging
KUBE_CONFIG_PRODUCTION: Base64-encoded kubeconfig for production
```

2. Encode kubeconfig:
```bash
cat ~/.kube/config | base64 -w 0
```

3. Configure GitHub Environments:
- Create "staging" environment (auto-deploy)
- Create "production" environment (require approval)

### Manual Deployment

```bash
# Build images
docker build -t taxja/backend:v1.0.0 ./backend
docker build -t taxja/frontend:v1.0.0 ./frontend

# Push images
docker push taxja/backend:v1.0.0
docker push taxja/frontend:v1.0.0

# Update Kubernetes
kubectl set image deployment/backend backend=taxja/backend:v1.0.0 -n taxja
kubectl set image deployment/frontend frontend=taxja/frontend:v1.0.0 -n taxja

# Check rollout
kubectl rollout status deployment/backend -n taxja
kubectl rollout status deployment/frontend -n taxja
```

## Monitoring and Alerting

### Access Grafana

```bash
# Port forward
kubectl port-forward svc/grafana 3000:3000 -n taxja

# Open http://localhost:3000
# Login with credentials from secrets
```

### Key Metrics to Monitor

1. **Application Metrics**:
   - Request rate and latency
   - Error rate (5xx responses)
   - Active users
   - OCR processing queue length

2. **Infrastructure Metrics**:
   - CPU and memory usage
   - Disk space
   - Network I/O
   - Pod restart count

3. **Business Metrics**:
   - User registrations
   - Tax calculations performed
   - Documents processed
   - Reports generated

### Alert Configuration

Alerts are configured in `monitoring/alertmanager-config.yaml`:

- **Critical**: High error rate, database down, disk space low
- **Warning**: High response time, high memory usage, OCR queue backup

Configure notification channels:
- Email: alerts@taxja.at
- PagerDuty: For critical alerts
- Slack: For team notifications

## Backup and Disaster Recovery

### Automated Backups

- **PostgreSQL**: Daily at 2 AM UTC (30-day retention)
- **MinIO**: Daily at 3 AM UTC (30-day retention)

### Manual Backup

```bash
# PostgreSQL
kubectl create job --from=cronjob/postgres-backup postgres-backup-manual -n taxja

# MinIO
kubectl create job --from=cronjob/minio-backup minio-backup-manual -n taxja
```

### Restore Procedures

See [k8s/backup/README.md](../k8s/backup/README.md) for detailed restore procedures.

### Disaster Recovery Plan

1. **RTO (Recovery Time Objective)**: 2 hours
2. **RPO (Recovery Point Objective)**: 24 hours

**Recovery Steps**:
1. Provision new Kubernetes cluster
2. Deploy infrastructure services
3. Restore database from latest backup
4. Restore MinIO documents from latest backup
5. Deploy application services
6. Verify data integrity
7. Update DNS to point to new cluster

## Security Hardening

### 1. Network Security

```bash
# Apply network policies
kubectl apply -f network-policies.yaml -n taxja
```

### 2. Pod Security

```bash
# Enable Pod Security Standards
kubectl label namespace taxja pod-security.kubernetes.io/enforce=restricted
```

### 3. RBAC Configuration

```bash
# Create service account with minimal permissions
kubectl create serviceaccount taxja-app -n taxja

# Apply RBAC rules
kubectl apply -f rbac.yaml -n taxja
```

### 4. Image Security

- Scan images for vulnerabilities (Trivy, Snyk)
- Use minimal base images (Alpine)
- Don't run as root
- Use read-only root filesystem where possible

### 5. Secrets Management

Consider using external secret managers:
- HashiCorp Vault
- AWS Secrets Manager
- Azure Key Vault
- Google Secret Manager

### 6. Security Headers

Configured in `frontend/nginx.conf`:
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (HSTS)

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status
kubectl get pods -n taxja

# Describe pod
kubectl describe pod <pod-name> -n taxja

# Check logs
kubectl logs <pod-name> -n taxja
```

#### 2. Database Connection Errors

```bash
# Test database connection
kubectl exec -it deployment/postgres -n taxja -- psql -U taxja -d taxja -c "SELECT 1;"

# Check database logs
kubectl logs deployment/postgres -n taxja
```

#### 3. High Memory Usage

```bash
# Check resource usage
kubectl top pods -n taxja

# Check HPA status
kubectl get hpa -n taxja

# Increase resource limits if needed
kubectl edit deployment backend -n taxja
```

#### 4. TLS Certificate Issues

```bash
# Check certificate status
kubectl get certificate -n taxja
kubectl describe certificate taxja-tls -n taxja

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager
```

#### 5. Ingress Not Working

```bash
# Check ingress status
kubectl describe ingress taxja-ingress -n taxja

# Check NGINX ingress controller
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

### Performance Optimization

1. **Database**:
   - Add indexes for frequently queried columns
   - Enable connection pooling
   - Tune PostgreSQL configuration

2. **Caching**:
   - Enable Redis caching for tax calculations
   - Cache static assets with long TTL
   - Use CDN for frontend assets

3. **Application**:
   - Enable gzip compression
   - Optimize database queries
   - Use async processing for heavy tasks

4. **Kubernetes**:
   - Configure resource requests and limits
   - Enable HPA for auto-scaling
   - Use node affinity for optimal placement

## Support and Maintenance

### Regular Maintenance Tasks

**Daily**:
- Check monitoring dashboards
- Review error logs
- Verify backups completed

**Weekly**:
- Review resource usage trends
- Check for security updates
- Test backup restoration

**Monthly**:
- Update dependencies
- Review and optimize costs
- Conduct disaster recovery drill
- Review and update documentation

### Getting Help

- **Documentation**: https://docs.taxja.at
- **GitHub Issues**: https://github.com/taxja/taxja/issues
- **Email Support**: support@taxja.at
- **Emergency**: emergency@taxja.at

## Appendix

### Environment Variables

See `.env.example` for complete list of environment variables.

### Resource Requirements

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Backend | 500m | 2000m | 512Mi | 2Gi |
| Celery Worker | 500m | 2000m | 512Mi | 2Gi |
| Frontend | 100m | 500m | 128Mi | 512Mi |
| PostgreSQL | 1000m | 2000m | 1Gi | 4Gi |
| Redis | 100m | 500m | 256Mi | 1Gi |
| MinIO | 500m | 1000m | 512Mi | 2Gi |

### Useful Commands

```bash
# Get all resources in namespace
kubectl get all -n taxja

# Watch pod status
kubectl get pods -n taxja -w

# Execute command in pod
kubectl exec -it <pod-name> -n taxja -- /bin/sh

# Copy files from pod
kubectl cp taxja/<pod-name>:/path/to/file ./local-file

# Port forward to service
kubectl port-forward svc/<service-name> <local-port>:<service-port> -n taxja

# View resource usage
kubectl top nodes
kubectl top pods -n taxja

# Drain node for maintenance
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Uncordon node after maintenance
kubectl uncordon <node-name>
```
