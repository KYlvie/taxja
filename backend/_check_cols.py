import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, user='taxja', password='taxja_password', dbname='taxja')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
db_cols = [r[0] for r in cur.fetchall()]
conn.close()

print(f"DB has {len(db_cols)} columns:")
for c in db_cols:
    print(f"  {c}")

# Now check what SQLAlchemy model expects
from app.models.user import User
model_cols = [c.name for c in User.__table__.columns]
print(f"\nModel has {len(model_cols)} columns:")
for c in model_cols:
    print(f"  {c}")

missing_in_db = set(model_cols) - set(db_cols)
missing_in_model = set(db_cols) - set(model_cols)
if missing_in_db:
    print(f"\nMISSING IN DB: {missing_in_db}")
if missing_in_model:
    print(f"\nMISSING IN MODEL: {missing_in_model}")
if not missing_in_db and not missing_in_model:
    print("\nAll columns match!")
