"""Pytest configuration and fixtures"""
import pytest
import os

# Import shared fixtures from fixtures package
# These are automatically discovered by pytest
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.models",
    "tests.fixtures.services",
]

# Only import app-related modules if not running property tests
# Property tests don't need the full app context
if not os.environ.get('PYTEST_PROPERTY_TESTS_ONLY'):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.db.base import Base, get_db

    # Test database URL (SQLite for simple unit tests)
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


    @pytest.fixture(scope="function")
    def db():
        """
        Create test database (SQLite).
        
        Note: For E2E tests requiring PostgreSQL features (enums, UUID),
        use the db_session fixture from tests.fixtures.database instead.
        """
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)


    @pytest.fixture(scope="function")
    def client(db):
        """Create test client"""
        def override_get_db():
            try:
                yield db
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()
