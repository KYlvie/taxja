# E2E Test Setup and Execution Guide

## Overview

This guide provides comprehensive instructions for setting up, running, and maintaining the End-to-End (E2E) test suite for the Property Asset Management feature in Taxja.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Test Infrastructure](#test-infrastructure)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Writing New E2E Tests](#writing-new-e2e-tests)
6. [Troubleshooting](#troubleshooting)
7. [CI/CD Integration](#cicd-integration)

## Prerequisites

### Required Software

- **Python 3.11+**: Backend runtime
- **PostgreSQL 15+**: Test database (required for enum types and array support)
- **Docker & Docker Compose**: For running PostgreSQL in containers
- **pytest**: Testing framework

### Environment Setup

1. **Start PostgreSQL**:
   ```bash
   # Start PostgreSQL container
   docker-compose up -d postgres
   
   # Verify PostgreSQL is running
   docker-compose ps postgres
   ```

2. **Install Python Dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure Test Database** (optional):
   ```bash
   # Set custom test database URL
   export TEST_DATABASE_URL="postgresql://user:password@localhost:5432/test_db"
   ```
   
   Default: `postgresql://taxja:taxja_password@localhost:5432/taxja_test`

## Test Infrastructure

### Shared Fixtures Package

The E2E tests use a centralized fixtures package located at `backend/tests/fixtures/`:

```
backend/tests/fixtures/
├── __init__.py          # Package exports
├── database.py          # Database session fixtures
├── models.py            # Model factory functions
├── services.py          # Service layer fixtures
└── README.md            # Detailed fixture documentation
```

### Key Components

#### 1. Database Fixtures (`database.py`)

Provides:
- PostgreSQL connection with proper enum creation
- Automatic table creation and cleanup
- Transaction isolation between tests
- Idempotent enum creation (safe to run multiple times)

**Enums Created**:
- `propertytype`: rental, owner_occupied, mixed_use
- `propertystatus`: active, sold, archived
- `transactiontype`: income, expense
- `incomecategory`: 7 Austrian income categories
- `expensecategory`: 23 expense categories
- `usertype`: employee, self_employed, landlord, mixed, gmbh
- `documenttype`: 10 document types

#### 2. Model Fixtures (`models.py`)

Provides factory functions for creating test data:
- `create_test_user()`: Create users with sensible defaults
- `create_test_property()`: Create properties with auto-calculations
- `create_test_transaction()`: Create transactions with proper relationships
- `create_test_document()`: Create document records

Pre-configured fixtures:
- `test_user`: Ready-to-use landlord user
- `test_employee_user`: Ready-to-use employee user
- `test_property`: Property owned by test_user
- `test_rental_income`: Rental income transaction
- `test_depreciation_transaction`: Depreciation transaction

#### 3. Service Fixtures (`services.py`)

Provides service instances:
- `property_service`: PropertyService
- `afa_calculator`: AfACalculator
- `historical_service`: HistoricalDepreciationService
- `annual_service`: AnnualDepreciationService
- `address_matcher`: AddressMatcher
- `report_service`: PropertyReportService
- `e1_service`: E1FormImportService
- `bescheid_service`: BescheidImportService

### Fixture Auto-Discovery

Fixtures are automatically discovered via `conftest.py`:

```python
# backend/tests/conftest.py
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.models",
    "tests.fixtures.services",
]
```

No need to import fixtures explicitly in test files!

## Running Tests

### Run All E2E Tests

```bash
cd backend

# Run all refactored E2E tests
pytest tests/test_property_e2e_refactored.py -v

# Run with coverage
pytest tests/test_property_e2e_refactored.py --cov=app.services --cov=app.models -v

# Run with detailed output
pytest tests/test_property_e2e_refactored.py -vv -s
```

### Run Specific Test Classes

```bash
# Run only property registration tests
pytest tests/test_property_e2e_refactored.py::TestE2E_RegisterPropertyCalculateDepreciationViewDetails -v

# Run only historical backfill tests
pytest tests/test_property_e2e_refactored.py::TestE2E_CreatePropertyBackfillHistoricalDepreciation -v

# Run only multi-property portfolio tests
pytest tests/test_property_e2e_refactored.py::TestE2E_MultiPropertyPortfolioWithReports -v
```

### Run Specific Test Methods

```bash
# Run a single test method
pytest tests/test_property_e2e_refactored.py::TestE2E_RegisterPropertyCalculateDepreciationViewDetails::test_complete_property_registration_workflow -v
```

### Run with Markers

```bash
# Run only slow tests (if marked)
pytest tests/test_property_e2e_refactored.py -m slow -v

# Skip slow tests
pytest tests/test_property_e2e_refactored.py -m "not slow" -v
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest tests/test_property_e2e_refactored.py -n 4 -v
```

## Test Coverage

### Current E2E Test Suite

The refactored E2E test suite includes 9 comprehensive test classes:

1. **TestE2E_RegisterPropertyCalculateDepreciationViewDetails**
   - Property registration with auto-calculations
   - Depreciation rate determination
   - Pro-rated depreciation for partial years
   - Property listing and retrieval

2. **TestE2E_CreatePropertyBackfillHistoricalDepreciation**
   - Historical depreciation calculation
   - Backfill transaction creation
   - Accumulated depreciation validation
   - Multi-year depreciation verification

3. **TestE2E_MultiPropertyPortfolioCalculateTotals**
   - Multiple property management
   - Portfolio-level calculations
   - Annual depreciation generation
   - Transaction aggregation

4. **TestE2E_ArchivePropertyVerifyTransactionsPreserved**
   - Property archival workflow
   - Transaction preservation
   - Historical data retention
   - Archived property retrieval

5. **TestE2E_MixedUsePropertyWorkflow**
   - Mixed-use property creation
   - Partial depreciation calculation
   - Rental percentage handling

6. **TestE2E_ImportE1LinkPropertyVerifyTransactions**
   - E1 form import simulation
   - Property linking workflow
   - Transaction verification
   - Import source tracking

7. **TestE2E_ImportBescheidAutoMatchConfirmLink**
   - Bescheid import simulation
   - Address matching with confidence scores
   - Auto-linking suggestions
   - Property matching validation

8. **TestE2E_MultiPropertyPortfolioWithReports**
   - Multi-property portfolio management
   - Income statement generation
   - Depreciation schedule generation
   - Portfolio-level aggregations
   - Report structure validation

9. **TestE2E_CompletePropertyLifecycle**
   - End-to-end property lifecycle
   - Registration → Backfill → Transactions → Archival
   - Property metrics calculation
   - Complete workflow validation

### Coverage Metrics

Run coverage report:
```bash
pytest tests/test_property_e2e_refactored.py --cov=app.services.property_service --cov=app.services.afa_calculator --cov=app.services.historical_depreciation_service --cov=app.services.annual_depreciation_service --cov=app.services.address_matcher --cov=app.services.property_report_service --cov-report=html
```

View HTML report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Writing New E2E Tests

### Test Structure Template

```python
class TestE2E_YourFeatureName:
    """
    E2E Test: Brief description of the workflow
    
    User story: As a [user type], I want to [action], so that [benefit].
    """

    def test_your_workflow_name(
        self,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test description"""
        # Step 1: Setup - Create test data
        property = create_test_property(
            db_session,
            user=test_user,
            street="Test Street"
        )
        
        # Step 2: Action - Perform the operation
        result = property_service.some_operation(property.id)
        
        # Step 3: Verification - Assert expected outcomes
        assert result.status == "expected_status"
        
        # Step 4: Database verification - Check persistence
        db_property = db_session.query(Property).filter(
            Property.id == property.id
        ).first()
        assert db_property is not None
```

### Best Practices

1. **Use Descriptive Names**: Test class and method names should clearly describe the workflow
2. **Follow AAA Pattern**: Arrange, Act, Assert
3. **Use Factory Functions**: Leverage `create_test_*` functions for test data
4. **Verify Database State**: Always check that changes are persisted
5. **Test Edge Cases**: Include boundary conditions and error scenarios
6. **Document Steps**: Use comments to mark workflow steps
7. **Keep Tests Independent**: Each test should be runnable in isolation
8. **Clean Up Automatically**: Let fixtures handle cleanup (don't add manual cleanup)

### Example: Adding a New E2E Test

```python
class TestE2E_PropertyExpenseTracking:
    """
    E2E Test: Property expense tracking workflow
    
    User story: As a landlord, I want to track property-specific expenses,
    so that I can calculate accurate net rental income.
    """

    def test_property_expense_tracking_workflow(
        self,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test complete expense tracking workflow"""
        # Step 1: Create property
        property = create_test_property(
            db_session,
            user=test_user,
            street="Expense Test Street"
        )
        
        # Step 2: Add various expense types
        expense_types = [
            (ExpenseCategory.PROPERTY_INSURANCE, Decimal("1200.00")),
            (ExpenseCategory.MAINTENANCE, Decimal("2500.00")),
            (ExpenseCategory.PROPERTY_TAX, Decimal("800.00")),
        ]
        
        for category, amount in expense_types:
            txn = create_test_transaction(
                db_session,
                user=test_user,
                transaction_type=TransactionType.EXPENSE,
                amount=amount,
                expense_category=category,
                property=property
            )
        
        # Step 3: Calculate property metrics
        metrics = property_service.calculate_property_metrics(property.id)
        
        # Step 4: Verify expense totals
        expected_total = sum(amount for _, amount in expense_types)
        assert metrics["total_expenses"] >= expected_total
        
        # Step 5: Verify all expenses linked to property
        property_txns = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id
        )
        
        expense_txns = [t for t in property_txns if t.type == TransactionType.EXPENSE]
        assert len(expense_txns) >= len(expense_types)
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "Type does not exist" Error

**Error Message**:
```
psycopg2.errors.UndefinedObject: type "propertytype" does not exist
```

**Solution**:
```bash
# Ensure PostgreSQL is running
docker-compose up -d postgres

# Verify connection
docker-compose exec postgres psql -U taxja -d taxja_test -c "\dt"
```

#### 2. "Fixture not found" Error

**Error Message**:
```
fixture 'db_session' not found
```

**Solution**:
Check that `conftest.py` has the correct pytest_plugins configuration:
```python
# backend/tests/conftest.py
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.models",
    "tests.fixtures.services",
]
```

#### 3. "Relation already exists" Error

**Error Message**:
```
psycopg2.errors.DuplicateTable: relation "properties" already exists
```

**Solution**:
```bash
# Restart PostgreSQL to clean up
docker-compose restart postgres

# Or drop and recreate test database
docker-compose exec postgres psql -U taxja -c "DROP DATABASE IF EXISTS taxja_test;"
docker-compose exec postgres psql -U taxja -c "CREATE DATABASE taxja_test;"
```

#### 4. Tests Fail Intermittently

**Possible Causes**:
- Database state not cleaned between tests
- Race conditions in parallel execution
- External dependencies (Redis, MinIO) not available

**Solutions**:
```bash
# Run tests sequentially
pytest tests/test_property_e2e_refactored.py -v

# Use fresh database for each test
pytest tests/test_property_e2e_refactored.py --create-db -v

# Check all services are running
docker-compose ps
```

#### 5. Slow Test Execution

**Optimization Tips**:
```bash
# Run tests in parallel
pytest tests/test_property_e2e_refactored.py -n auto -v

# Run only fast tests during development
pytest tests/test_property_e2e_refactored.py -m "not slow" -v

# Use pytest-sugar for better output
pip install pytest-sugar
pytest tests/test_property_e2e_refactored.py -v
```

### Debug Mode

Run tests with detailed debugging:
```bash
# Show print statements
pytest tests/test_property_e2e_refactored.py -s -v

# Show local variables on failure
pytest tests/test_property_e2e_refactored.py -l -v

# Drop into debugger on failure
pytest tests/test_property_e2e_refactored.py --pdb -v

# Show full diff on assertion failures
pytest tests/test_property_e2e_refactored.py -vv
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
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
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run E2E tests
        env:
          TEST_DATABASE_URL: postgresql://taxja:taxja_password@localhost:5432/taxja_test
        run: |
          cd backend
          pytest tests/test_property_e2e_refactored.py -v --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Running E2E tests..."
cd backend
pytest tests/test_property_e2e_refactored.py -v

if [ $? -ne 0 ]; then
    echo "E2E tests failed. Commit aborted."
    exit 1
fi

echo "E2E tests passed!"
```

## Performance Benchmarks

### Expected Test Execution Times

| Test Class | Approximate Duration |
|-----------|---------------------|
| TestE2E_RegisterPropertyCalculateDepreciationViewDetails | 2-3 seconds |
| TestE2E_CreatePropertyBackfillHistoricalDepreciation | 3-4 seconds |
| TestE2E_MultiPropertyPortfolioCalculateTotals | 4-5 seconds |
| TestE2E_ArchivePropertyVerifyTransactionsPreserved | 3-4 seconds |
| TestE2E_MixedUsePropertyWorkflow | 2-3 seconds |
| TestE2E_ImportE1LinkPropertyVerifyTransactions | 2-3 seconds |
| TestE2E_ImportBescheidAutoMatchConfirmLink | 3-4 seconds |
| TestE2E_MultiPropertyPortfolioWithReports | 5-7 seconds |
| TestE2E_CompletePropertyLifecycle | 4-5 seconds |

**Total Suite Duration**: ~30-40 seconds (sequential), ~10-15 seconds (parallel with 4 workers)

## Additional Resources

- **Fixture Documentation**: `backend/tests/fixtures/README.md`
- **Migration Guide**: `backend/tests/E2E_TEST_MIGRATION_GUIDE.md`
- **Refactoring Summary**: `backend/tests/REFACTORING_SUMMARY.md`
- **pytest Documentation**: https://docs.pytest.org/
- **SQLAlchemy Testing**: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html

## Maintenance

### Regular Tasks

1. **Update fixtures** when models change
2. **Add new service fixtures** when new services are created
3. **Review test coverage** monthly
4. **Optimize slow tests** as needed
5. **Update documentation** when workflows change

### Deprecation Policy

- Old test file (`test_property_e2e.py`) kept for reference
- Will be removed after 3 months of stable refactored tests
- All new tests should use refactored fixtures

## Contact

For questions or issues with E2E tests:
- Review this documentation
- Check `backend/tests/fixtures/README.md`
- Consult the migration guide
- Open an issue in the project repository

---

**Last Updated**: 2026-03-08  
**Version**: 1.0  
**Status**: Production Ready
