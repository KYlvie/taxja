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
    err = stderr.read().decode().strip()
    if out: print(out[-800:])
    if err and 'warning' not in err.lower(): print("ERR:", err[:200])
    return out

# Register via API
payload = json.dumps({
    "email": "pro1@taxja.at",
    "password": "Test123!",
    "name": "DI Maria Steiner"
})
print("=== Registering user ===")
run(f"curl -s -X POST http://localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' -d '{payload}'")

# Try login
print("\n=== Testing login ===")
run(f"curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{payload}' | python3 -c \"import sys,json; d=json.load(sys.stdin); print('OK' if 'access_token' in d else d)\"")

client.close()
