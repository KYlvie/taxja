# Taxja - Austrian Tax Management System

Taxja is an automated tax management platform designed for Austrian taxpayers, including employees, landlords, self-employed individuals, and small business owners.

## Features

- 🧾 **Transaction Management**: Record and categorize income and expenses
- 🤖 **Automatic Classification**: AI-powered transaction categorization
- 📊 **Tax Calculation**: Accurate Austrian tax calculations (2026 USP rates)
- 📄 **OCR Document Recognition**: Extract data from receipts and invoices
- 💰 **VAT & Social Insurance**: Complete VAT and SVS calculations
- 📈 **Dashboard & Analytics**: Real-time tax overview and savings suggestions
- 🌍 **Multi-language**: German, English, and Chinese support
- 📱 **PWA Support**: Mobile-first responsive design

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Storage**: MinIO (S3-compatible)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Task Queue**: Celery
- **OCR**: Tesseract + OpenCV

### Frontend
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **State Management**: Zustand
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod
- **i18n**: i18next
- **PWA**: Vite PWA Plugin

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Local Development with Docker Compose

1. Clone the repository:
```bash
git clone https://github.com/taxja/taxja.git
cd taxja
```

2. Start all services:
```bash
docker-compose up -d
```

3. Access the application:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

### Local Development without Docker

#### Backend

1. Create virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy environment file:
```bash
cp .env.example .env
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Start the server:
```bash
uvicorn app.main:app --reload
```

#### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start development server:
```bash
npm run dev
```

## Project Structure

```
taxja/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Core configuration
│   │   ├── db/           # Database setup
│   │   ├── models/       # SQLAlchemy models
│   │   ├── services/     # Business logic
│   │   └── main.py       # FastAPI app
│   ├── alembic/          # Database migrations
│   ├── tests/            # Backend tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── services/     # API services
│   │   ├── stores/       # Zustand stores
│   │   ├── i18n/         # Translations
│   │   └── main.tsx      # Entry point
│   ├── public/           # Static assets
│   └── package.json
├── docker-compose.yml
└── README.md
```

## Environment Variables

### Backend (.env)

```env
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key
POSTGRES_SERVER=localhost
POSTGRES_USER=taxja
POSTGRES_PASSWORD=taxja_password
POSTGRES_DB=taxja
REDIS_HOST=localhost
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## Documentation

### User Guides
- [Quick Start Guide](docs/QUICK_START.md)
- [User Guide (German)](docs/USER_GUIDE_DE.md)
- [User Guide (English)](docs/USER_GUIDE_EN.md)
- [User Guide (Chinese)](docs/USER_GUIDE_ZH.md)

### Developer Documentation
- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Property Management Developer Guide](backend/docs/DEVELOPER_GUIDE_PROPERTY_MANAGEMENT.md)
- [Property API Endpoints](backend/docs/API_PROPERTY_ENDPOINTS.md)

### Austrian Tax Law References
- [Austrian Tax Guide](docs/AUSTRIAN_TAX_GUIDE.md) - Overview of Austrian tax regulations
- [Property Tax Law Reference](docs/AUSTRIAN_TAX_LAW_PROPERTY_REFERENCE.md) - Detailed guide for rental property taxation, AfA calculations, and expense categories

### Deployment & Operations
- [Deployment Guide](docs/DEPLOYMENT.md)
- [UAT Guide](docs/UAT_GUIDE.md)
- [Performance & Security](docs/PERFORMANCE_AND_SECURITY.md)

## Testing

### Backend Tests
```bash
cd backend
pytest --cov=app
```

### Frontend Tests
```bash
cd frontend
npm run test
```

## Deployment

The project includes GitHub Actions CI/CD pipeline that:
1. Runs tests on every push
2. Builds Docker images
3. Deploys to staging/production

See `.github/workflows/ci-cd.yml` for details.

## Security

- **Encryption**: AES-256 for data at rest, TLS 1.3 for data in transit
- **Authentication**: JWT tokens with 2FA support
- **GDPR Compliant**: User data export and deletion features

## License

Copyright © 2024 Taxja GmbH. All rights reserved.

## Disclaimer

⚠️ This system is for reference only and does not constitute tax advice. Final tax filing should be done through FinanzOnline. For complex situations, consult a Steuerberater. The developers assume no tax liability.
