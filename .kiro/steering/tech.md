# Tech Stack

## Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL 15+ with SQLAlchemy 2.0 ORM
- **Cache**: Redis 7+
- **Storage**: MinIO (S3-compatible)
- **Migrations**: Alembic
- **Task Queue**: Celery
- **OCR**: Tesseract + OpenCV
- **ML**: scikit-learn for transaction classification

## Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **State**: Zustand
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod validation
- **i18n**: i18next
- **PWA**: Vite PWA Plugin

## Infrastructure
- **Containerization**: Docker + Docker Compose
- **Orchestration**: Kubernetes (k8s configs available)
- **CI/CD**: GitHub Actions

## Common Commands

### Development
```bash
# Start all services
make up
docker-compose up -d

# Start only infrastructure (for local dev)
make dev
docker-compose up -d postgres redis minio

# View logs
make logs
docker-compose logs -f
```

### Backend
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload

# Run tests
pytest
pytest --cov=app

# Code quality
black .
ruff check .
mypy .
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Run tests
npm run test

# Lint
npm run lint
```

### Testing
```bash
# Run all tests
make test

# Backend tests only
cd backend && pytest

# Frontend tests only
cd frontend && npm run test
```

## Code Quality Standards
- **Python**: Black formatter (line length 100), Ruff linter, MyPy type checking
- **TypeScript**: ESLint with React hooks plugin
- **Testing**: pytest for backend, vitest for frontend
- **Property-Based Testing**: Hypothesis library used for correctness validation
