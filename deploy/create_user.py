import paramiko, hashlib, os, base64

HOST = "46.62.227.62"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username="root", pkey=pkey, timeout=15)

def run(cmd, timeout=30):
    print(f">>> {cmd[:100]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[-500:])
    if err: print("ERR:", err[:300])
    return out

# Use werkzeug to generate bcrypt hash (available in the container)
hash_out = run("""docker exec taxja-backend python3 -c "
import bcrypt
h = bcrypt.hashpw(b'Test123!', bcrypt.gensalt()).decode()
print(h)
" """)

if not hash_out or not hash_out.startswith('$2b$'):
    # Try alternative
    hash_out = run("""docker exec taxja-backend python3 -c "
from app.core.security import get_password_hash
print(get_password_hash('Test123!'))
" """)

print(f"Hash: {hash_out[:30]}...")

if hash_out and ('$2b$' in hash_out or '$2a$' in hash_out):
    h = hash_out.strip()
    sql = f"""INSERT INTO users (email, password_hash, name, user_type, account_status, email_verified, is_admin, trial_used, created_at, updated_at)
VALUES ('pro1@taxja.at', '{h}', 'DI Maria Steiner', 'self_employed', 'active', true, false, false, NOW(), NOW())
ON CONFLICT (email) DO UPDATE SET password_hash = '{h}', account_status = 'active';"""
    run(f"docker exec taxja-postgres psql -U taxja -d taxja -c \"{sql}\"")
    run("docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT id, email, account_status FROM users WHERE email = 'pro1@taxja.at';\"")
else:
    print("Could not generate hash!")

client.close()
