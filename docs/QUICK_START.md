# Taxja Quick Start Guide

Get Taxja up and running in 5 minutes.

## Local Development (Docker Compose)

### 1. Prerequisites
- Docker 24+
- Docker Compose 2.20+
- Git

### 2. Clone and Start

```bash
# Clone repository
git clone https://github.com/taxja/taxja.git
cd taxja

# Start all services
make up

# Wait for services to start (about 30 seconds)
```

### 3. Access Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

### 4. Initialize Database

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Create test user (optional)
docker-compose exec backend python -m app.db.init_db
```

### 5. Test the Application

1. Open http://localhost:5173
2. Register a new account
3. Upload a test receipt
4. Create a transaction
5. View dashboard

## Production Deployment (Kubernetes)

### 1. Prerequisites
- Kubernetes cluster 1.25+
- kubectl configured
- Domain name with DNS configured

### 2. Quick Deploy

```bash
cd k8s

# Create namespace
kubectl apply -f namespace.yaml

# Create secrets (edit with your values first!)
cp secrets.example.yaml secrets.yaml
# Edit secrets.yaml
kubectl apply -f secrets.yaml

# Deploy everything
kubectl apply -f configmap.yaml
kubectl apply -f postgres-deployment.yaml
kubectl apply -f redis-deployment.yaml
kubectl apply -f minio-deployment.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f celery-worker-deployment.yaml
kubectl apply -f frontend-deployment.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n taxja --timeout=300s

# Run migrations
kubectl exec -it deployment/backend -n taxja -- alembic upgrade head
```

### 3. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n taxja

# Test backend
curl https://your-domain.com/api/health

# Test frontend
curl https://your-domain.com/
```

## Common Commands

### Docker Compose

```bash
# Start services
make up

# Start only infrastructure (for local dev)
make dev

# View logs
make logs

# Run tests
make test

# Stop services
make down

# Clean up (removes volumes)
make clean
```

### Kubernetes

```bash
# View all resources
kubectl get all -n taxja

# View logs
kubectl logs -f deployment/backend -n taxja

# Scale services
kubectl scale deployment backend -n taxja --replicas=5

# Update image
kubectl set image deployment/backend backend=taxja/backend:v1.1.0 -n taxja

# Rollback
kubectl rollout undo deployment/backend -n taxja
```

## Next Steps

- Read the [Deployment Guide](DEPLOYMENT.md) for detailed instructions
- Configure [Monitoring](../k8s/monitoring/) for production
- Set up [Automated Backups](../k8s/backup/)
- Review [Security Best Practices](DEPLOYMENT.md#security-hardening)

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend

# Restart services
docker-compose restart
```

### Database connection errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U taxja -d taxja -c "SELECT 1;"
```

### Port already in use

```bash
# Stop conflicting services
docker-compose down

# Or change ports in docker-compose.yml
```

## Getting Help

- **Documentation**: https://docs.taxja.at
- **GitHub Issues**: https://github.com/taxja/taxja/issues
- **Email**: support@taxja.at
