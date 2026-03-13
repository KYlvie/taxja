# E2E Test Migration Guide

This guide explains how to migrate from the old E2E test infrastructure to the refactored version.

## What Changed

### Problem: Circular Dependencies

The original test setup had circular dependency issues:
```
properties table → documents table (kaufvertrag_document_id, mietvertrag_document_id)
documents table → transactions table (transaction_id)
transactions table → properties table (property_id)
```

This created issues during:
- Table creation order
- Foreign key constraint validation
- Test data setup
- Cleanup and teardown

### Solution: Centralized Fixtures

The refactored approach uses:
1. **Shared database fixtures** that handle enum creation and table setup
2. **Factory functions** for creating test data with proper relationship handling
3. **Pre-configured fixtures** for common test scenarios
4. **Automatic cleanup** to ensure clean state between tests

## File Structure

### Old Structure
```
backend/tests/
├── conftest.py                    # Basic fixtures
└── test_property_e2e.py          # All fixtures + tests (1096 lines)
```

### New Structure
```
backend/tests/
├── conftest.py                    # Imports shared fixtures
├── fixtures/
│   ├── __init__.py               # Package exports
│   ├── database.py               # Database session fixtures
│   ├── models.py                 # Model factories and fixtures
│   ├── services.py               # Service fixtures
│   └── README.md                 # Documentation
├── test_property_e2e.py          # Original tests (keep for reference)
└── test_property_e2e_refactored.py  # Refactored tests
```

## Migration Steps

### Step 1: Update conftest.py

The `conftest.py` now imports shared fixtures:

```python
# backend/tests/conftest.py
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.models",
    "tests.fixtures.services",
]
```

### Step 2: Remove Duplicate Fixtures

**Before:**
```python
# In test_property_e2e.py
@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL)
    # ... 50 lines of setup code
    yield session
    # ... 20 lines of cleanup code

@pytest.fixture
def test_user(db_session):
    user = User(email="test@example.com", ...)
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def property_service(db_session):
    return PropertyService(db_session)
```

**After:**
```python
# No fixture definitions needed!
# Just use them in your tests:

def test_something(
    db_session: Session,
    test_user: User,
    property_service: PropertyService
):
    # Fixtures are auto-discovered from tests.fixtures
    pass
```

### Step 3: Use Factory Functions

**Before:**
```python
def test_create_property(db_session, test_user):
    property = Property(
        user_id=test_user.id,
        street="Test Street",
        city="Wien",
        postal_code="1010",
        address="Test Street, 1010 Wien",
        purchase_date=date(2024, 1, 1),
        purchase_price=Decimal("400000.00"),
        building_value=Decimal("320000.00"),
        land_value=Decimal("80000.00"),
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
        property_type=PropertyType.RENTAL,
    )
    db_session.add(property)
    db_session.commit()
    db_session.refresh(property)
```

**After:**
```python
from tests.fixtures import create_test_property

def test_create_property(db_session, test_user):
    property = create_test_property(
        db_session,
        user=test_user,
        street="Test Street",
        purchase_price=Decimal("400000.00")
    )
    # All other fields have sensible defaults
```

### Step 4: Simplify Test Setup

**Before:**
```python
def test_multi_property_workflow(db_session, test_user):
    # Create property 1
    prop1 = Property(...)
    db_session.add(prop1)
    db_session.commit()
    db_session.refresh(prop1)
    
    # Create property 2
    prop2 = Property(...)
    db_session.add(prop2)
    db_session.commit()
    db_session.refresh(prop2)
    
    # Create transactions
    txn1 = Transaction(...)
    db_session.add(txn1)
    # ... etc
```

**After:**
```python
from tests.fixtures import create_test_property, create_test_transaction

def test_multi_property_workflow(db_session, test_user):
    # Create properties
    prop1 = create_test_property(db_session, test_user, street="Street 1")
    prop2 = create_test_property(db_session, test_user, street="Street 2")
    
    # Create transactions
    txn1 = create_test_transaction(
        db_session, test_user, 
        transaction_type=TransactionType.INCOME,
        amount=Decimal("15000.00"),
        property=prop1
    )
```

## Comparison: Before vs After

### Test File Size
- **Before**: 1096 lines (fixtures + tests)
- **After**: ~600 lines (tests only)
- **Reduction**: 45% smaller, more focused

### Fixture Definitions
- **Before**: 150+ lines of fixture code per test file
- **After**: 0 lines (reuse shared fixtures)
- **Benefit**: DRY principle, single source of truth

### Database Setup
- **Before**: Manual enum creation, table creation, cleanup in each file
- **After**: Automatic via shared fixtures
- **Benefit**: Consistent setup, no forgotten cleanup

### User Creation
- **Before**: Inconsistent across tests, sometimes missing fields
- **After**: Standardized via factory function
- **Benefit**: Consistent test data, fewer bugs

## Running Tests

### Old Tests (Original)
```bash
# These still work but use old fixtures
pytest backend/tests/test_property_e2e.py -v
```

### New Tests (Refactored)
```bash
# These use shared fixtures
pytest backend/tests/test_property_e2e_refactored.py -v
```

### All Tests
```bash
# Run everything
pytest backend/tests/ -v
```

## Troubleshooting

### Issue: "fixture 'db_session' not found"

**Solution**: Make sure `conftest.py` has the pytest_plugins configuration:
```python
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.models",
    "tests.fixtures.services",
]
```

### Issue: "Type propertytype does not exist"

**Solution**: Start PostgreSQL:
```bash
docker-compose up -d postgres
```

### Issue: "Circular import error"

**Solution**: The fixtures package handles this. Make sure you're importing from `tests.fixtures`:
```python
from tests.fixtures import create_test_user, create_test_property
```

### Issue: "User model instantiation error"

**Solution**: Use the factory function instead of direct instantiation:
```python
# Don't do this:
user = User(email="test@example.com", password_hash="...")

# Do this:
user = create_test_user(db_session, email="test@example.com")
```

## Next Steps

1. **Review refactored tests**: Check `test_property_e2e_refactored.py`
2. **Update existing tests**: Migrate other test files to use shared fixtures
3. **Add new tests**: Use factory functions for new test scenarios
4. **Remove old fixtures**: Once migration is complete, remove duplicate fixture code

## Benefits Summary

✅ **Resolved circular dependencies** - Proper handling of foreign key relationships
✅ **Simplified test setup** - Factory functions with sensible defaults
✅ **Fixed User model instantiation** - Consistent user creation
✅ **Updated database schema** - Matches production schema
✅ **Centralized fixtures** - Single source of truth
✅ **Automatic cleanup** - No manual teardown needed
✅ **Better maintainability** - Update fixtures in one place
✅ **Improved readability** - Tests focus on business logic

## Questions?

See:
- `backend/tests/fixtures/README.md` - Detailed fixture documentation
- `backend/tests/test_property_e2e_refactored.py` - Example usage
- `backend/tests/fixtures/models.py` - Available factory functions
