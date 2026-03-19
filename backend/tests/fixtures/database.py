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


def reset_test_schema(engine):
    """
    Reset tables and enum types in the public schema.

    This avoids stale table definitions when model metadata changes and also
    sidesteps PostgreSQL drop-order issues caused by cyclic foreign keys.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                ) LOOP
                    EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
                END LOOP;

                FOR r IN (
                    SELECT t.typname
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typtype = 'e' AND n.nspname = 'public'
                ) LOOP
                    EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', r.typname);
                END LOOP;
            END $$;
        """))
        conn.commit()


@pytest.fixture(scope="function")
def db_engine():
    """
    Create a test database engine.
    
    This fixture creates the engine and enums, then cleans up after the test.
    Scope is function-level to ensure clean state for each test.
    """
    engine = create_engine(TEST_DATABASE_URL)

    # Start from a clean schema and let current SQLAlchemy metadata recreate
    # the exact tables and enum types needed by the test.
    reset_test_schema(engine)
    
    yield engine
    
    # Cleanup
    reset_test_schema(engine)
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
    # Create all tables from current metadata
    Base.metadata.create_all(bind=db_engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        # Cleanup
        session.close()

        # Reset full schema state to avoid stale tables/enums across tests.
        reset_test_schema(db_engine)


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
