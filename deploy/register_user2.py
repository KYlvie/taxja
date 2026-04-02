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
    return stdout.read().decode().strip()

# Register
payload = json.dumps({
    "email": "pro1@taxja.at",
    "password": "Test123!",
    "name": "DI Maria Steiner",
    "user_type": "SELF_EMPLOYED"
})
result = run(f"curl -s -X POST http://localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' -d '{payload}'")
print("Register:", result[:300])

# Login
login_payload = json.dumps({"email": "pro1@taxja.at", "password": "Test123!"})
result = run(f"curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{login_payload}'")
try:
    d = json.loads(result)
    if 'access_token' in d:
        print("Login: SUCCESS")
    else:
        print("Login:", result[:200])
except:
    print("Login:", result[:200])

client.close()
