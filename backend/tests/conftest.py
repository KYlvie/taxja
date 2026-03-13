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

# Register SQLite type compilers for PostgreSQL-specific types (UUID, JSONB, ARRAY)
# This allows tests using SQLite to work with models that use these types.
try:
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

    @compiles(UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        return "VARCHAR(36)"

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    @compiles(ARRAY, "sqlite")
    def compile_array_sqlite(type_, compiler, **kw):
        return "JSON"
except Exception:
    pass

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
        from sqlalchemy import create_engine, event, text as sa_text
        from sqlalchemy.orm import sessionmaker
        from app.main import app as fastapi_app
        from app.db.base import Base, get_db

        # Test database URL (SQLite for simple unit tests)
        SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

        engine = create_engine(
            SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


        def _create_sqlite_tables(engine, metadata):
            """Create tables in SQLite, stripping PostgreSQL-specific features."""
            # Exclude tables that use PostgreSQL ARRAY type
            excluded_tables = {
                'historical_import_sessions',
                'historical_import_uploads',
                'import_conflicts',
                'import_metrics',
            }

            tables_to_create = [
                t for t in metadata.sorted_tables
                if t.name not in excluded_tables
            ]

            # Temporarily remove server_default for columns using gen_random_uuid()
            patched = []
            for table in tables_to_create:
                for col in table.columns:
                    if col.server_default is not None:
                        default_text = str(col.server_default.arg) if hasattr(col.server_default, 'arg') else str(col.server_default)
                        if 'gen_random_uuid' in default_text:
                            patched.append((col, col.server_default))
                            col.server_default = None
            try:
                for table in tables_to_create:
                    table.create(bind=engine, checkfirst=True)
            finally:
                # Restore server defaults
                for col, server_default in patched:
                    col.server_default = server_default


        @pytest.fixture(scope="function")
        def db():
            """
            Create test database (SQLite).

            Note: For E2E tests requiring PostgreSQL features (enums, UUID),
            use the db_session fixture from tests.fixtures.database instead.
            """
            _create_sqlite_tables(engine, Base.metadata)
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()
                # Drop only the tables that were created (excluding PostgreSQL ARRAY tables)
                excluded = {
                    'historical_import_sessions', 'historical_import_uploads',
                    'import_conflicts', 'import_metrics',
                }
                for t in reversed(Base.metadata.sorted_tables):
                    if t.name not in excluded:
                        t.drop(bind=engine, checkfirst=True)


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
