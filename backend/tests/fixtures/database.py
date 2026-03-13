"""
Shared database fixtures for E2E and integration tests.

This module provides reusable database fixtures that handle:
- PostgreSQL test database setup
- Enum creation for PostgreSQL
- Clean state management between tests
- Proper teardown and cleanup
"""
import os
from typing import Generator
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.db.base import Base


# Test database URL - can be overridden via environment variable
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://taxja:taxja_password@localhost:5432/taxja_test"
)


def create_test_enums(engine):
    """
    Create PostgreSQL enums required for the schema.
    
    This function is idempotent - it won't fail if enums already exist.
    """
    with engine.connect() as conn:
        # Property-related enums
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE propertytype AS ENUM ('rental', 'owner_occupied', 'mixed_use');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE propertystatus AS ENUM ('active', 'sold', 'archived');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Transaction-related enums
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE transactiontype AS ENUM ('income', 'expense');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE incomecategory AS ENUM (
                    'agriculture', 'self_employment', 'business', 'employment',
                    'capital_gains', 'rental', 'other_income'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE expensecategory AS ENUM (
                    'office_supplies', 'equipment', 'travel', 'marketing',
                    'professional_services', 'insurance', 'maintenance',
                    'property_tax', 'loan_interest', 'depreciation',
                    'groceries', 'utilities', 'commuting', 'home_office',
                    'vehicle', 'telecom', 'rent', 'bank_fees',
                    'svs_contributions', 'property_management_fees',
                    'property_insurance', 'depreciation_afa', 'other'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # User-related enums
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE usertype AS ENUM (
                    'employee', 'self_employed', 'landlord', 'mixed', 'gmbh'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Document-related enums
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE documenttype AS ENUM (
                    'payslip', 'receipt', 'invoice', 'rental_contract',
                    'bank_statement', 'property_tax', 'lohnzettel',
                    'svs_notice', 'einkommensteuerbescheid', 'other'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        conn.commit()


def drop_test_enums(engine):
    """
    Drop PostgreSQL enums after tests complete.
    
    Uses CASCADE to handle dependencies.
    """
    with engine.connect() as conn:
        conn.execute(text("DROP TYPE IF EXISTS propertytype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS propertystatus CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS transactiontype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS incomecategory CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS expensecategory CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS usertype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS documenttype CASCADE"))
        conn.commit()


@pytest.fixture(scope="function")
def db_engine():
    """
    Create a test database engine.
    
    This fixture creates the engine and enums, then cleans up after the test.
    Scope is function-level to ensure clean state for each test.
    """
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create enums first
    create_test_enums(engine)
    
    yield engine
    
    # Cleanup
    drop_test_enums(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Create a test database session with clean state.
    
    This fixture:
    1. Creates all tables
    2. Provides a session for the test
    3. Cleans up by dropping all tables after the test
    
    Usage:
        def test_something(db_session: Session):
            user = User(email="test@example.com")
            db_session.add(user)
            db_session.commit()
    """
    # Create all tables
    Base.metadata.create_all(bind=db_engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        # Cleanup
        session.close()
        
        # Drop all tables to ensure clean state for next test
        Base.metadata.drop_all(bind=db_engine)


@pytest.fixture(scope="function")
def db_session_no_cleanup(db_engine) -> Generator[Session, None, None]:
    """
    Create a test database session WITHOUT automatic table cleanup.
    
    Use this fixture when you need to inspect the database state after a test
    or when running multiple related tests that share data.
    
    Note: You must manually clean up tables when using this fixture.
    """
    # Create all tables
    Base.metadata.create_all(bind=db_engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
