import os
import sys
sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text

pw = os.environ.get("POSTGRES_PASSWORD", "taxja_prod_2026")
pg_url = f"postgresql://taxja:{pw}@postgres:5432/taxja"
engine = create_engine(pg_url)

# Import all models
from app.db.base import Base
import app.models  # noqa: F401 - registers all models

# Create all tables
Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
    ))
    count = result.scalar()
    print(f"Tables created: {count}")

engine.dispose()
print("Done!")
