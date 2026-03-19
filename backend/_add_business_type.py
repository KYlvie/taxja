import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, user='taxja', password='taxja_password', dbname='taxja')
cur = conn.cursor()

# Check if selfemployedtype enum exists
cur.execute("SELECT 1 FROM pg_type WHERE typname = 'selfemployedtype'")
if not cur.fetchone():
    cur.execute("CREATE TYPE selfemployedtype AS ENUM ('freiberufler', 'gewerbetreibende', 'neue_selbstaendige', 'land_forstwirtschaft')")
    print("created selfemployedtype enum")

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='business_type'")
if not cur.fetchone():
    cur.execute("ALTER TABLE users ADD COLUMN business_type selfemployedtype")
    print("added business_type column")
else:
    print("business_type already exists")

conn.commit()
conn.close()
print("done")
