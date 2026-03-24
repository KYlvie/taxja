#!/usr/bin/env python3
"""Restart nginx to pick up new backend IP."""
import paramiko
import time

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"

def run_cmd(client, cmd, timeout=60):
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[-15:]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[-5:]:
            print(f"  ERR: {line}")
    return exit_code, out, err

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
transport = client.get_transport()
transport.set_keepalive(30)
print("Connected!\n")

run_cmd(client, "cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx 2>&1")
time.sleep(5)

run_cmd(client, "curl -s http://localhost/api/v1/health")
run_cmd(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost/api/v1/auth/login")

print("\nDone!")
client.close()
