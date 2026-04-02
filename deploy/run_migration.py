#!/usr/bin/env python3
"""Run alembic migration on production server."""
import paramiko

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
print("Connected!")

def run(cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[-2000:])
    if err and exit_code != 0: print("ERR:", err[-500:])
    return exit_code, out

# Check current migration
run("docker exec taxja-postgres psql -U taxja -d taxja -c 'SELECT version_num FROM alembic_version;'")

# Run migration
code, out = run(
    "cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod run --rm backend alembic upgrade head",
    timeout=120
)
print(f"\nMigration exit code: {code}")

# Verify
run("docker exec taxja-postgres psql -U taxja -d taxja -c 'SELECT version_num FROM alembic_version;'")

# Restart backend
run("cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod restart backend celery-worker")

print("\nDone!")
client.close()
