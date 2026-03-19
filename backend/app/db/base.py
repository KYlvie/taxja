"""Database base configuration"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,              # persistent connections per worker
    max_overflow=30,           # extra connections under load
    pool_timeout=30,           # wait max 30s for a connection
    pool_recycle=1800,         # recycle connections every 30min (PgBouncer friendly)
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
