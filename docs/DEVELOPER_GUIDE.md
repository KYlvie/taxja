# Taxja Developer Guide

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Backend Development](#backend-development)
5. [Frontend Development](#frontend-development)
6. [Testing Strategy](#testing-strategy)
7. [Deployment](#deployment)
8. [Contributing Guidelines](#contributing-guidelines)

## Architecture Overview

### System Architecture

Taxja follows a modern three-tier architecture with microservices principles:

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │   Web Browser    │         │   Mobile PWA     │         │
│  │  (React + TS)    │         │  (React + TS)    │         │
│  └──────────────────┘         └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              FastAPI Gateway                          │  │
│  │  (Authentication, Rate Limiting, CORS)               │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────┬───────────┬──────────┬──────────┬─────────┐ │
│  │   Auth    │Transaction│   OCR    │   Tax    │   AI    │ │
│  │  Service  │  Service  │ Service  │ Service  │Assistant│ │
│  └───────────┴───────────┴──────────┴──────────┴─────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  PostgreSQL  │  │  Redis   │  │  MinIO (S3)          │ │
│  │  (Primary)   │  │  (Cache) │  │  (Documents)         │ │
│  └──────────────┘  └──────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Clear boundaries between API, business logic, and data layers
2. **Dependency Injection**: Services are injected via FastAPI dependencies
3. **Type Safety**: Full type hints in Python, TypeScript in frontend
4. **Testability**: All components designed for unit and integration testing
5. **Security First**: Encryption at rest and in transit, GDPR compliance
6. **Performance**: Caching, async operations, optimized queries

### Key Technologies

**Backend:**
- FastAPI: High-performance async web framework
- SQLAlchemy 2.0: Modern ORM with async support
- Pydantic v2: Data validation and serialization
- Celery: Distributed task queue for OCR processing
- Tesseract: OCR engine with German language support

**Frontend:**
- React 18: Component-based UI library
- TypeScript: Type-safe JavaScript
- Zustand: Lightweight state management
- React Hook Form + Zod: Form handling and validation
- i18next: Internationalization (de, en, zh)

**Infrastructure:**
- Docker: Containerization
- Kubernetes: Orchestration
- PostgreSQL 15: Relational database
- Redis 7: Caching and session storage
- MinIO: S3-compatible object storage

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Initial Setup

1. **Clone the repository:**
```bash
git clone https://github.com/taxja/taxja.git
cd taxja
```

2. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start infrastructure services:**
```bash
make dev
# or
docker-compose up -d postgres redis minio
```

4. **Backend setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed  # Seed initial data
```

5. **Frontend setup:**
```bash
cd frontend
npm install
```

6. **Start development servers:**
```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Celery worker (for OCR)
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
```

### Development URLs

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- API Docs (ReDoc): http://localhost:8000/redoc

## Project Structure

### Backend Structure

```
backend/
├── app/
│   ├── api/                    # API layer
│   │   ├── v1/
│   │   │   ├── endpoints/      # API endpoints
│   │   │   │   ├── transactions.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── tax.py
│   │   │   │   └── ...
│   │   │   └── router.py       # Main router
│   │   ├── dependencies.py     # Dependency injection
│   │   └── deps.py
│   ├── core/                   # Core configuration
│   │   ├── config.py           # Settings
│   │   ├── security.py         # Auth & encryption
│   │   ├── cache.py            # Redis caching
│   │   └── rate_limiter.py     # Rate limiting
│   ├── db/                     # Database
│   │   ├── session.py          # DB session
│   │   ├── base.py             # Base model
│   │   └── seed.py             # Seed data
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py
│   │   ├── transaction.py
│   │   ├── document.py
│   │   └── ...
│   ├── schemas/                # Pydantic schemas
│   │   ├── user.py
│   │   ├── transaction.py
│   │   └── ...
│   ├── services/               # Business logic
│   │   ├── tax_calculation_engine.py
│   │   ├── income_tax_calculator.py
│   │   ├── vat_calculator.py
│   │   ├── svs_calculator.py
│   │   ├── transaction_classifier.py
│   │   ├── ocr_engine.py
│   │   └── ...
│   ├── tasks/                  # Celery tasks
│   │   ├── celery_app.py
│   │   └── ocr_tasks.py
│   └── main.py                 # FastAPI app
├── alembic/                    # Database migrations
│   └── versions/
├── tests/                      # Tests
│   ├── unit/
│   ├── integration/
│   ├── properties/             # Property-based tests
│   └── conftest.py
├── requirements.txt
└── pyproject.toml
```

### Frontend Structure

```
frontend/
├── src/
│   ├── components/             # Reusable components
│   │   ├── common/             # Generic components
│   │   ├── transactions/       # Transaction components
│   │   ├── documents/          # Document components
│   │   └── ...
│   ├── pages/                  # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Transactions.tsx
│   │   ├── Documents.tsx
│   │   └── ...
│   ├── services/               # API clients
│   │   ├── api.ts              # Axios instance
│   │   ├── authService.ts
│   │   ├── transactionService.ts
│   │   └── ...
│   ├── stores/                 # Zustand stores
│   │   ├── authStore.ts
│   │   ├── transactionStore.ts
│   │   └── ...
│   ├── i18n/                   # Translations
│   │   ├── de.json
│   │   ├── en.json
│   │   └── zh.json
│   ├── types/                  # TypeScript types
│   ├── utils/                  # Utility functions
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
└── vite.config.ts
```

## Backend Development

### Adding a New API Endpoint

1. **Define the Pydantic schema** (`backend/app/schemas/`):
```python
# schemas/example.py
from pydantic import BaseModel, Field
from datetime import datetime

class ExampleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    value: float = Field(..., gt=0)

class ExampleResponse(BaseModel):
    id: int
    name: str
    value: float
    created_at: datetime

    class Config:
        from_attributes = True
```

2. **Create the database model** (`backend/app/models/`):
```python
# models/example.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class Example(Base):
    __tablename__ = "examples"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

3. **Create a database migration**:
```bash
cd backend
alembic revision --autogenerate -m "Add example table"
alembic upgrade head
```

4. **Implement the service** (`backend/app/services/`):
```python
# services/example_service.py
from sqlalchemy.orm import Session
from app.models.example import Example
from app.schemas.example import ExampleCreate

class ExampleService:
    def create_example(self, db: Session, data: ExampleCreate) -> Example:
        example = Example(**data.dict())
        db.add(example)
        db.commit()
        db.refresh(example)
        return example

    def get_example(self, db: Session, example_id: int) -> Example:
        return db.query(Example).filter(Example.id == example_id).first()
```

5. **Create the API endpoint** (`backend/app/api/v1/endpoints/`):
```python
# api/v1/endpoints/example.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.schemas.example import ExampleCreate, ExampleResponse
from app.services.example_service import ExampleService

router = APIRouter()
service = ExampleService()

@router.post("/", response_model=ExampleResponse, status_code=201)
def create_example(
    data: ExampleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return service.create_example(db, data)

@router.get("/{example_id}", response_model=ExampleResponse)
def get_example(
    example_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    example = service.get_example(db, example_id)
    if not example:
        raise HTTPException(status_code=404, detail="Example not found")
    return example
```

6. **Register the router** (`backend/app/api/v1/router.py`):
```python
from app.api.v1.endpoints import example

api_router.include_router(example.router, prefix="/examples", tags=["examples"])
```

7. **Write tests** (`backend/tests/`):
```python
# tests/test_example.py
def test_create_example(client, auth_headers):
    response = client.post(
        "/api/v1/examples/",
        json={"name": "Test", "value": 123.45},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Test"
```

### Tax Calculation Services

The tax calculation engine is modular:

```python
# Example: Using the tax calculation engine
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.income_tax_calculator import IncomeTaxCalculator
from app.services.vat_calculator import VATCalculator
from app.services.svs_calculator import SVSCalculator

engine = TaxCalculationEngine(
    income_tax_calculator=IncomeTaxCalculator(),
    vat_calculator=VATCalculator(),
    svs_calculator=SVSCalculator()
)

result = engine.calculate_total_tax(
    user=user,
    transactions=transactions,
    tax_year=2026
)
```

### OCR Processing

OCR is handled asynchronously via Celery:

```python
# Trigger OCR processing
from app.tasks.ocr_tasks import process_document_ocr

task = process_document_ocr.delay(document_id=123)
task_id = task.id

# Check task status
from celery.result import AsyncResult
result = AsyncResult(task_id)
if result.ready():
    ocr_data = result.get()
```

### Caching Strategy

Use Redis caching for expensive operations:

```python
from app.core.cache import cache_result

@cache_result(ttl=3600)  # Cache for 1 hour
def calculate_tax(user_id: int, tax_year: int):
    # Expensive calculation
    return result
```

## Frontend Development

### Adding a New Page

1. **Create the page component** (`frontend/src/pages/`):
```typescript
// pages/ExamplePage.tsx
import React from 'react';
import { useTranslation } from 'react-i18next';

export const ExamplePage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('example.title')}</h1>
      {/* Page content */}
    </div>
  );
};
```

2. **Add translations** (`frontend/src/i18n/`):
```json
// i18n/de.json
{
  "example": {
    "title": "Beispielseite"
  }
}

// i18n/en.json
{
  "example": {
    "title": "Example Page"
  }
}
```

3. **Create API service** (`frontend/src/services/`):
```typescript
// services/exampleService.ts
import api from './api';

export interface Example {
  id: number;
  name: string;
  value: number;
}

export const exampleService = {
  async getExample(id: number): Promise<Example> {
    const response = await api.get(`/examples/${id}`);
    return response.data;
  },

  async createExample(data: Omit<Example, 'id'>): Promise<Example> {
    const response = await api.post('/examples/', data);
    return response.data;
  }
};
```

4. **Create Zustand store** (if needed):
```typescript
// stores/exampleStore.ts
import { create } from 'zustand';
import { Example } from '../services/exampleService';

interface ExampleStore {
  examples: Example[];
  setExamples: (examples: Example[]) => void;
  addExample: (example: Example) => void;
}

export const useExampleStore = create<ExampleStore>((set) => ({
  examples: [],
  setExamples: (examples) => set({ examples }),
  addExample: (example) => set((state) => ({
    examples: [...state.examples, example]
  }))
}));
```

5. **Add route** (`frontend/src/App.tsx`):
```typescript
import { ExamplePage } from './pages/ExamplePage';

<Route path="/example" element={<ExamplePage />} />
```

### State Management with Zustand

Zustand provides simple, type-safe state management:

```typescript
// Example: Using the auth store
import { useAuthStore } from './stores/authStore';

function MyComponent() {
  const { user, login, logout } = useAuthStore();

  const handleLogin = async () => {
    await login('email@example.com', 'password');
  };

  return (
    <div>
      {user ? (
        <button onClick={logout}>Logout</button>
      ) : (
        <button onClick={handleLogin}>Login</button>
      )}
    </div>
  );
}
```

### Form Handling

Use React Hook Form with Zod validation:

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  amount: z.number().positive('Amount must be positive')
});

type FormData = z.infer<typeof schema>;

function MyForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema)
  });

  const onSubmit = (data: FormData) => {
    console.log(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('name')} />
      {errors.name && <span>{errors.name.message}</span>}
      
      <input type="number" {...register('amount', { valueAsNumber: true })} />
      {errors.amount && <span>{errors.amount.message}</span>}
      
      <button type="submit">Submit</button>
    </form>
  );
}
```

## Testing Strategy

### Backend Testing

#### Unit Tests

Test individual functions and classes:

```python
# tests/unit/test_income_tax_calculator.py
from decimal import Decimal
from app.services.income_tax_calculator import IncomeTaxCalculator

def test_calculate_progressive_tax():
    calculator = IncomeTaxCalculator()
    result = calculator.calculate_progressive_tax(
        taxable_income=Decimal('50000'),
        tax_year=2026
    )
    assert result.total_tax > Decimal('0')
    assert result.effective_rate < Decimal('1')
```

#### Property-Based Tests

Use Hypothesis for property-based testing:

```python
# tests/properties/test_tax_properties.py
from hypothesis import given, strategies as st
from decimal import Decimal

@given(st.decimals(min_value=0, max_value=1000000, places=2))
def test_tax_monotonicity(income):
    """Tax should increase monotonically with income"""
    calculator = IncomeTaxCalculator()
    
    tax1 = calculator.calculate_progressive_tax(income, 2026).total_tax
    tax2 = calculator.calculate_progressive_tax(income + Decimal('1000'), 2026).total_tax
    
    assert tax2 >= tax1
```

#### Integration Tests

Test complete workflows:

```python
# tests/integration/test_transaction_workflow.py
def test_create_transaction_with_ocr(client, auth_headers, db):
    # Upload document
    with open('test_receipt.jpg', 'rb') as f:
        response = client.post(
            '/api/v1/documents/upload',
            files={'file': f},
            headers=auth_headers
        )
    document_id = response.json()['id']
    
    # Wait for OCR processing
    # ...
    
    # Confirm OCR and create transaction
    response = client.post(
        f'/api/v1/documents/{document_id}/confirm',
        json={'create_transaction': True},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'transaction_id' in response.json()
```

### Frontend Testing

Use Vitest for frontend testing:

```typescript
// tests/components/TransactionList.test.tsx
import { render, screen } from '@testing-library/react';
import { TransactionList } from '../components/TransactionList';

describe('TransactionList', () => {
  it('renders transactions', () => {
    const transactions = [
      { id: 1, description: 'Test', amount: '100.00' }
    ];
    
    render(<TransactionList transactions={transactions} />);
    
    expect(screen.getByText('Test')).toBeInTheDocument();
    expect(screen.getByText('€100.00')).toBeInTheDocument();
  });
});
```

### Running Tests

```bash
# Backend tests
cd backend
pytest                          # All tests
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests only
pytest --cov=app                # With coverage

# Frontend tests
cd frontend
npm run test                    # All tests
npm run test:coverage           # With coverage
```

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

### Quick Deployment Overview

1. **Build Docker images:**
```bash
docker build -t taxja-backend:latest -f backend/Dockerfile .
docker build -t taxja-frontend:latest -f frontend/Dockerfile .
```

2. **Deploy to Kubernetes:**
```bash
kubectl apply -f k8s/
```

3. **Set up monitoring:**
```bash
kubectl apply -f k8s/monitoring/
```

## Contributing Guidelines

### Code Style

**Python:**
- Use Black formatter (line length 100)
- Follow PEP 8
- Use type hints for all functions
- Write docstrings for public APIs

**TypeScript:**
- Use ESLint configuration
- Follow React best practices
- Use functional components with hooks
- Prefer named exports

### Git Workflow

1. Create a feature branch:
```bash
git checkout -b feature/my-feature
```

2. Make changes and commit:
```bash
git add .
git commit -m "feat: add new feature"
```

3. Push and create pull request:
```bash
git push origin feature/my-feature
```

### Commit Message Format

Follow Conventional Commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring
- `chore:` Build/tooling changes

### Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Request review from maintainers
4. Address review comments
5. Squash commits before merging

## Additional Resources

- [API Documentation](./API_DOCUMENTATION.md)
- [User Guide (German)](./USER_GUIDE_DE.md)
- [User Guide (English)](./USER_GUIDE_EN.md)
- [User Guide (Chinese)](./USER_GUIDE_ZH.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Performance Guide](./PERFORMANCE_AND_SECURITY.md)

## Support

For development questions:
- GitHub Issues: https://github.com/taxja/taxja/issues
- Developer Chat: https://discord.gg/taxja
- Email: dev@taxja.at

---

**Version:** 1.0  
**Last Updated:** March 2026  
**© 2026 Taxja GmbH**
