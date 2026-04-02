import paramiko

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
    if out: print(out)

# Check if user exists
run("docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT id, email, account_status FROM users WHERE email = 'pro1@taxja.at';\"")

# Generate bcrypt hash for Test123! using Python inside the container
run("""docker exec taxja-backend python3 -c "
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
h = pwd_context.hash('Test123!')
print(h)
" """)

client.close()
