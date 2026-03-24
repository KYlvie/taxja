#!/usr/bin/env python3
"""Final verification after DB migration fix."""
import paramiko
import time

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"

def run_cmd(client, cmd, timeout=60):
    print(f"\n>>> {cmd[:140]}")
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            lines = out.split('\n')
            if len(lines) > 12:
                print(f"  ...({len(lines)} lines, last 8)")
            for line in lines[-8:]:
                print(f"  {line}")
        if err:
            for line in err.split('\n')[-5:]:
                print(f"  ERR: {line}")
        return exit_code, out, err
    except Exception as e:
        print(f"  TIMEOUT/ERROR: {e}")
        return -1, "", str(e)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
transport = client.get_transport()
transport.set_keepalive(30)
print(f"Connected\n")

# Restart backend to clear any cached errors
run_cmd(client, "cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod restart backend 2>&1", timeout=60)
time.sleep(10)

# Test login API
print("=" * 50)
print("TEST LOGIN")
print("=" * 50)
run_cmd(client, """curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"test@test.com","password":"test"}' 2>&1""")

# Test health
run_cmd(client, "curl -s http://localhost:8000/api/v1/health")

# All containers
run_cmd(client, "docker ps --format 'table {{.Names}}\t{{.Status}}'")

# Backend logs
run_cmd(client, "docker logs taxja-backend --tail 5 2>&1")

print("\n" + "=" * 50)
print("DONE - taxja.at should be working now")
print("=" * 50)

client.close()
