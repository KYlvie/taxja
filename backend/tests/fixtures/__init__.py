"""
Test fixtures package.

This package provides reusable fixtures for E2E and integration tests.
Import fixtures from submodules as needed.
"""
from .database import db_engine, db_session, db_session_no_cleanup
from .models import (
    create_test_user,
    create_test_property,
    create_test_transaction,
    create_test_document,
    test_user,
    test_employee_user,
    test_property,
    test_rental_income,
    test_depreciation_transaction,
)
from .services import (
    property_service,
    afa_calculator,
    historical_service,
    annual_service,
    address_matcher,
)

__all__ = [
    # Database fixtures
    "db_engine",
    "db_session",
    "db_session_no_cleanup",
    # Model factory functions
    "create_test_user",
    "create_test_property",
    "create_test_transaction",
    "create_test_document",
    # Model fixtures
    "test_user",
    "test_employee_user",
    "test_property",
    "test_rental_income",
    "test_depreciation_transaction",
    # Service fixtures
    "property_service",
    "afa_calculator",
    "historical_service",
    "annual_service",
    "address_matcher",
]
