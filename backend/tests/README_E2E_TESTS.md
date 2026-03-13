# E2E Tests for Property Asset Management

## Overview

The E2E tests validate complete workflows from user actions through API endpoints, services, and database persistence. These tests require a PostgreSQL database and proper environment configuration.

## Prerequisites

### 1. PostgreSQL Database

Start PostgreSQL using Docker Compose:

```bash
docker-compose up -d postgres
```

Or set the `TEST_DATABASE_URL` environment variable to point to your test database:

```bash
export TEST_DATABASE_URL="postgresql://user:password@localhost:5432/taxja_test"
```

### 2. Environment Variables

Create a `.env` file in the `backend` directory with the following variables:

```bash
# Security
SECRET_KEY=test_secret_key_min_32_characters_long_for_testing
ENCRYPTION_KEY=test_encryption_key_32_chars_12
ALGORITHM=HS256

# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=taxja
POSTGRES_PASSWORD=taxja_password
POSTGRES_DB=taxja_test
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=taxja-documents
MINIO_SECURE=false
```

Alternatively, set these as environment variables before running tests.

## Running E2E Tests

### Run All E2E Tests

```bash
cd backend
pytest tests/test_property_e2e.py -v
pytest tests/test_e1_import_property_linking_e2e.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_e1_import_property_linking_e2e.py::TestE1ImportPropertyLinkingFlow -v
```

### Run Specific Test

```bash
pytest tests/test_e1_import_property_linking_e2e.py::TestE1ImportPropertyLinkingFlow::test_e1_import_with_exact_address_match_high_confidence -v
```

### Run with Coverage

```bash
pytest tests/test_e1_import_property_linking_e2e.py --cov=app.services --cov-report=html
```

## Test Coverage

### test_e1_import_property_linking_e2e.py

This test file validates the complete E1 import to property linking flow (Task D.4.2):

1. **test_e1_import_with_exact_address_match_high_confidence**
   - Creates property with known address
   - Imports E1 with rental income (KZ 350)
   - Verifies property suggestions
   - Links transaction to property
   - Validates data persistence

2. **test_e1_import_with_multiple_properties_manual_selection**
   - Creates multiple properties
   - Imports E1 with rental income
   - Verifies all properties are suggested
   - User selects correct property
   - Validates linking works correctly

3. **test_e1_import_without_existing_properties_suggests_create_new**
   - Imports E1 when user has no properties
   - Verifies empty suggestions
   - Creates new property
   - Links transaction to new property

4. **test_e1_import_multiple_years_link_to_same_property**
   - Imports E1 forms for multiple years
   - Links all rental income to same property
   - Verifies all transactions are properly linked

5. **test_e1_import_link_validation_prevents_wrong_user_property**
   - Tests ownership validation
   - Prevents linking to another user's property
   - Verifies error handling

6. **test_e1_import_with_mixed_income_types_only_rental_requires_linking**
   - Imports E1 with multiple income types
   - Verifies only rental income requires property linking
   - Validates other income types are not affected

## Troubleshooting

### Database Connection Errors

If you see connection errors, ensure PostgreSQL is running:

```bash
docker-compose ps postgres
```

If not running, start it:

```bash
docker-compose up -d postgres
```

### Settings Validation Errors

If you see "Field required" errors for settings, ensure your `.env` file exists and contains all required variables, or set them as environment variables:

```bash
export SECRET_KEY=test_secret_key_min_32_characters_long
export ENCRYPTION_KEY=test_encryption_key_32_chars_12
export POSTGRES_SERVER=localhost
export POSTGRES_USER=taxja
export POSTGRES_PASSWORD=taxja_password
export POSTGRES_DB=taxja_test
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
```

### Import Errors

If you see import errors, ensure you're running from the `backend` directory and have installed all dependencies:

```bash
cd backend
pip install -r requirements.txt
pytest tests/test_e1_import_property_linking_e2e.py -v
```

## CI/CD Integration

For CI/CD pipelines, use environment variables and ensure PostgreSQL service is available:

```yaml
# Example GitHub Actions workflow
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_USER: taxja
      POSTGRES_PASSWORD: taxja_password
      POSTGRES_DB: taxja_test
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5

env:
  SECRET_KEY: test_secret_key_min_32_characters_long_for_testing
  ENCRYPTION_KEY: test_encryption_key_32_chars_12
  POSTGRES_SERVER: localhost
  POSTGRES_USER: taxja
  POSTGRES_PASSWORD: taxja_password
  POSTGRES_DB: taxja_test
  MINIO_ENDPOINT: localhost:9000
  MINIO_ACCESS_KEY: minioadmin
  MINIO_SECRET_KEY: minioadmin
```

## Notes

- E2E tests create and drop database tables for each test to ensure clean state
- Tests use real PostgreSQL (not SQLite) to support PostgreSQL-specific features
- Each test is independent and can be run in isolation
- Tests validate Austrian tax law compliance and business logic correctness
