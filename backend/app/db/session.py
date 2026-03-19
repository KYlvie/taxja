"""Database session management with connection pooling.

When using PgBouncer in transaction mode (production), SQLAlchemy should use
NullPool so that PgBouncer manages the actual connection pool. In development
(direct PostgreSQL), we use QueuePool with sensible defaults.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

_USE_PGBOUNCER = os.getenv("USE_PGBOUNCER", "false").lower() == "true"

# When PgBouncer handles pooling, use NullPool on the app side to avoid
# double-pooling. Otherwise keep a local pool for dev convenience.
_pool_kwargs = (
    {"poolclass": NullPool}
    if _USE_PGBOUNCER
    else {
        "pool_pre_ping": True,
        "pool_size": 30,
        "max_overflow": 20,
        "pool_recycle": 1800,
        "pool_timeout": 30,
    }
)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    future=True,
    **_pool_kwargs,
)

# Create sync engine for Celery tasks
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    **_pool_kwargs,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create sync session factory for Celery tasks
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency for getting async database session.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database (create tables if needed)"""
    from app.db.base import Base
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()
