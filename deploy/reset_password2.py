import paramiko

HOST = "46.62.227.62"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username="root", pkey=pkey, timeout=15)

def run(cmd, timeout=30):
    print(f">>> {cmd[:80]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err: print("ERR:", err[:200])
    return out

# Check user
run("docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT id, email, account_status FROM users WHERE email = 'pro1@taxja.at';\"")

# Generate hash
hash_val = run("docker exec taxja-backend python3 -c \"from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('Test123!'))\"")

if hash_val and hash_val.startswith('$2b$'):
    print(f"\nHash: {hash_val}")
    # Update password
    run(f"docker exec taxja-postgres psql -U taxja -d taxja -c \"UPDATE users SET password_hash = '{hash_val}' WHERE email = 'pro1@taxja.at';\"")
    print("Password updated!")
else:
    print("Failed to generate hash")

client.close()
