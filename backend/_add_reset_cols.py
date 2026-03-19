import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, user='taxja', password='taxja_password', dbname='taxja')
cur = conn.cursor()

cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='users' AND column_name IN ('password_reset_token','password_reset_sent_at')
""")
existing = [r[0] for r in cur.fetchall()]
print('existing:', existing)

if 'password_reset_token' not in existing:
    cur.execute('ALTER TABLE users ADD COLUMN password_reset_token VARCHAR(255)')
    cur.execute('CREATE INDEX ix_users_password_reset_token ON users(password_reset_token)')
    print('added password_reset_token')

if 'password_reset_sent_at' not in existing:
    cur.execute('ALTER TABLE users ADD COLUMN password_reset_sent_at TIMESTAMP')
    print('added password_reset_sent_at')

conn.commit()
conn.close()
print('done')
