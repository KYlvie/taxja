"""Pytest configuration and fixtures"""
import pytest
import os
import sys

# Ensure backend directory is on the Python path
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Set default environment variables for testing if not already set
_test_env_defaults = {
    "SECRET_KEY": "test-secret-key-for-testing-only",
    "ENCRYPTION_KEY": "kywOxc1r2B+CXiiwju1RAPpkEO353AlBz/M3LeQ9a/M=",
    "POSTGRES_SERVER": "localhost",
    "POSTGRES_USER": "taxja",
    "POSTGRES_PASSWORD": "taxja_test_password",
    "POSTGRES_DB": "taxja_test",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
}
for _key, _value in _test_env_defaults.items():
    if _key not in os.environ:
        os.environ[_key] = _value

# Import shared fixtures from fixtures package
# These are automatically discovered by pytest
# Only load fixture plugins when the app module is available
try:
    import app  # noqa: F401
    _app_available = True
except Exception:
    _app_available = False

if _app_available:
    pytest_plugins = [
        "tests.fixtures.database",
        "tests.fixtures.models",
        "tests.fixtures.services",
    ]

# Only import app-related modules if not running property tests
# and if the app module can be loaded (requires env vars)
if not os.environ.get('PYTEST_PROPERTY_TESTS_ONLY') and _app_available:
    try:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.main import app as fastapi_app
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

            fastapi_app.dependency_overrides[get_db] = override_get_db
            with TestClient(fastapi_app) as test_client:
                yield test_client
            fastapi_app.dependency_overrides.clear()

    except Exception:
        # App can't be loaded (missing env vars, etc.)
        # Standalone tests will still work
        pass
