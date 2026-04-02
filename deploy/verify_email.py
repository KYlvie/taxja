import paramiko, json

HOST = "46.62.227.62"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username="root", pkey=pkey, timeout=15)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    if out: print(out[-300:])
    return out

# Verify email and activate account
run("docker exec taxja-postgres psql -U taxja -d taxja -c \"UPDATE users SET email_verified = true, account_status = 'ACTIVE' WHERE email = 'pro1@taxja.at';\"")
run("docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT id, email, email_verified, account_status FROM users WHERE email = 'pro1@taxja.at';\"")

# Test login
login_payload = json.dumps({"email": "pro1@taxja.at", "password": "Test123!"})
result = run(f"curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{login_payload}'")
try:
    d = json.loads(result)
    print("Login:", "SUCCESS" if 'access_token' in d else result[:200])
except:
    print("Login:", result[:200])

client.close()
