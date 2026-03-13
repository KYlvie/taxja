# Project Structure

## Root Layout
```
taxja/
├── backend/          # FastAPI backend application
├── frontend/         # React frontend application
├── docs/             # Documentation (Austrian tax guides)
├── k8s/              # Kubernetes deployment configs
├── models/           # Pre-trained ML models (pkl files)
├── src/              # Legacy/shared source (calculators, services)
├── docker-compose.yml
├── Makefile
└── README.md
```

## Backend Structure
```
backend/
├── app/
│   ├── api/          # API endpoints (v1 versioning)
│   ├── core/         # Config, security, encryption
│   ├── db/           # Database setup and seeding
│   ├── models/       # SQLAlchemy ORM models
│   ├── schemas/      # Pydantic schemas for validation
│   ├── services/     # Business logic layer
│   ├── tasks/        # Celery async tasks (OCR)
│   └── main.py       # FastAPI app entry point
├── alembic/          # Database migrations
├── tests/            # pytest tests (including property-based)
├── examples/         # Usage examples
├── docs/             # Backend-specific docs
├── requirements.txt
└── pyproject.toml    # Poetry config
```

## Frontend Structure
```
frontend/
├── src/
│   ├── components/   # Reusable React components
│   ├── pages/        # Page-level components
│   ├── services/     # API client services
│   ├── stores/       # Zustand state stores
│   ├── i18n/         # Translation files (de, en, zh)
│   ├── App.tsx       # Root component
│   └── main.tsx      # Entry point
├── public/           # Static assets
└── package.json
```

## Key Service Modules (backend/app/services/)
- `transaction_classifier.py` - Main classification orchestrator
- `ml_classifier.py` - Machine learning classifier
- `rule_based_classifier.py` - Rule-based fallback classifier
- `classification_learning.py` - Learning from corrections
- `deductibility_checker.py` - Tax deduction validation
- `deduction_calculator.py` - Deduction amount calculation
- `income_tax_calculator.py` - Income tax computation
- `vat_calculator.py` - VAT calculations
- `svs_calculator.py` - Social insurance calculations
- `tax_calculation_engine.py` - Main tax engine
- `duplicate_detector.py` - Transaction deduplication
- `loss_carryforward_service.py` - Loss carryforward tracking

## Database Models (backend/app/models/)
- `user.py` - User accounts
- `transaction.py` - Income/expense transactions
- `document.py` - Uploaded documents (OCR)
- `tax_configuration.py` - Tax rules and rates
- `tax_report.py` - Generated tax reports
- `classification_correction.py` - ML training data
- `loss_carryforward.py` - Multi-year loss tracking

## Testing Conventions
- Property-based tests use Hypothesis library
- Test files: `test_*_properties.py` for property tests
- Regular unit tests: `test_*.py`
- Tests validate Austrian tax law requirements
- Coverage reports via pytest-cov

## Configuration Files
- `.env` - Environment variables (never commit)
- `.env.example` - Template for environment setup
- `alembic.ini` - Database migration config
- `docker-compose.yml` - Local development services
- `k8s/*.yaml` - Production deployment manifests

## Architecture Patterns
- **Backend**: Layered architecture (API → Services → Models)
- **Frontend**: Component-based with centralized state (Zustand)
- **API**: RESTful with versioning (/api/v1/)
- **Database**: SQLAlchemy ORM with Alembic migrations
- **Async**: Celery for background tasks (OCR processing)
- **Caching**: Redis for session and computation caching
- **Storage**: MinIO for document storage (S3-compatible)
