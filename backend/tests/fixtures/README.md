# Test Fixtures Package

This package provides reusable fixtures for E2E and integration tests, resolving circular dependency issues and simplifying test setup.

## Problem Solved

The original E2E tests had several issues:
1. **Circular dependencies**: Properties ↔ Documents ↔ Transactions created complex foreign key relationships
2. **Duplicate fixture code**: Each test file defined its own database setup
3. **Enum handling**: PostgreSQL enums required manual creation in each test
4. **User model instantiation**: Inconsistent user creation across tests
5. **Complex teardown**: Manual cleanup logic in each test file

## Solution

The refactored fixtures package provides:
- Centralized database setup with proper enum handling
- Factory functions for creating test data
- Reusable fixtures for common test scenarios
- Automatic cleanup and teardown
- Proper handling of PostgreSQL-specific features

## Structure

```
tests/fixtures/
├── __init__.py          # Package exports
├── database.py          # Database session fixtures
├── models.py            # Model factory functions and fixtures
├── services.py          # Service layer fixtures
└── README.md            # This file
```

## Usage

### 1. Database Fixtures

```python
def test_something(db_session: Session):
    """
    db_session fixture provides:
    - PostgreSQL connection
    - All enums created
    - All tables created
    - Automatic cleanup after test
    """
    user = User(email="test@example.com", ...)
    db_session.add(user)
    db_session.commit()
```

### 2. Model Factory Functions

```python
from tests.fixtures import create_test_user, create_test_property

def test_property_creation(db_session: Session):
    # Create user
    user = create_test_user(db_session, email="landlord@example.com")
    
    # Create property
    property = create_test_property(
        db_session,
        user=user,
        street="Teststraße 123",
        purchase_price=Decimal("400000.00")
    )
```

### 3. Pre-configured Fixtures

```python
def test_with_fixtures(test_user: User, test_property: Property):
    """
    test_user and test_property fixtures provide ready-to-use instances
    """
    assert test_user.user_type == UserType.LANDLORD
    assert test_property.user_id == test_user.id
```

### 4. Service Fixtures

```python
def test_service_logic(
    property_service: PropertyService,
    afa_calculator: AfACalculator,
    test_user: User
):
    """Service fixtures are automatically configured with db_session"""
    property = property_service.create_property(test_user.id, ...)
    depreciation = afa_calculator.calculate_annual_depreciation(property, 2024)
```

## Available Fixtures

### Database Fixtures (database.py)

- `db_engine`: PostgreSQL engine with enums created
- `db_session`: Session with tables created and automatic cleanup
- `db_session_no_cleanup`: Session without automatic cleanup (for inspection)

### Model Fixtures (models.py)

Factory functions:
- `create_test_user(db_session, **kwargs)`: Create a user
- `create_test_property(db_session, user, **kwargs)`: Create a property
- `create_test_transaction(db_session, user, **kwargs)`: Create a transaction
- `create_test_document(db_session, user, **kwargs)`: Create a document

Pre-configured fixtures:
- `test_user`: Landlord user
- `test_employee_user`: Employee user
- `test_property`: Property owned by test_user
- `test_rental_income`: Rental income transaction
- `test_depreciation_transaction`: Depreciation transaction

### Service Fixtures (services.py)

- `property_service`: PropertyService instance
- `afa_calculator`: AfACalculator instance
- `historical_service`: HistoricalDepreciationService instance
- `annual_service`: AnnualDepreciationService instance
- `address_matcher`: AddressMatcher instance
- `report_service`: PropertyReportService instance
- `e1_service`: E1FormImportService instance
- `bescheid_service`: BescheidImportService instance

## PostgreSQL Enums

The database fixtures automatically create these enums:
- `propertytype`: rental, owner_occupied, mixed_use
- `propertystatus`: active, sold, archived
- `transactiontype`: income, expense
- `incomecategory`: agriculture, self_employment, business, employment, capital_gains, rental, other_income
- `expensecategory`: office_supplies, equipment, travel, marketing, professional_services, insurance, maintenance, property_tax, loan_interest, depreciation, groceries, utilities, commuting, home_office, vehicle, telecom, rent, bank_fees, svs_contributions, property_management_fees, property_insurance, depreciation_afa, other
- `usertype`: employee, self_employed, landlord, mixed, gmbh
- `documenttype`: payslip, receipt, invoice, rental_contract, bank_statement, property_tax, lohnzettel, svs_notice, einkommensteuerbescheid, other

## Configuration

Set the `TEST_DATABASE_URL` environment variable to override the default PostgreSQL connection:

```bash
export TEST_DATABASE_URL="postgresql://user:password@localhost:5432/test_db"
```

Default: `postgresql://taxja:taxja_password@localhost:5432/taxja_test`

## Running Tests

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Run E2E tests
pytest backend/tests/test_property_e2e_refactored.py -v

# Run all tests
pytest backend/tests/ -v
```

## Migration Guide

### Before (Old Approach)

```python
@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL)
    
    # Manual enum creation
    with engine.connect() as conn:
        conn.execute(text("CREATE TYPE propertytype AS ENUM ..."))
        # ... more enums
    
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # Manual cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)
    # ... drop enums

@pytest.fixture
def test_user(db_session):
    user = User(email="test@example.com", ...)
    db_session.add(user)
    db_session.commit()
    return user
```

### After (New Approach)

```python
# No fixture definitions needed - just use them!

def test_something(db_session: Session, test_user: User):
    # db_session and test_user are automatically provided
    property = create_test_property(db_session, user=test_user)
```

## Benefits

1. **No circular dependencies**: Factory functions handle relationships correctly
2. **DRY principle**: Fixtures defined once, used everywhere
3. **Consistent setup**: All tests use the same database configuration
4. **Easy maintenance**: Update fixtures in one place
5. **Better readability**: Tests focus on business logic, not setup
6. **Automatic cleanup**: No manual teardown code needed
7. **Type safety**: All fixtures are properly typed

## Troubleshooting

### "Type does not exist" error

Make sure PostgreSQL is running:
```bash
docker-compose up -d postgres
```

### "Relation already exists" error

The database wasn't cleaned up properly. Restart PostgreSQL:
```bash
docker-compose restart postgres
```

### Import errors

Make sure you're importing from the fixtures package:
```python
from tests.fixtures import create_test_user, test_user
```

Or let pytest auto-discover fixtures (recommended):
```python
# No imports needed - fixtures are auto-discovered via conftest.py
def test_something(test_user: User):
    pass
```
