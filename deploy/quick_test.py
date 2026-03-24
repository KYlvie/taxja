#!/usr/bin/env python3
"""Quick test after restart."""
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
            for line in out.split('\n')[-10:]:
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

print("Waiting 15s for backend to fully start...")
time.sleep(15)

# Health
run_cmd(client, "curl -s http://localhost:8000/api/v1/health")

# Login test
run_cmd(client, """curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"test@test.com","password":"test"}'""")

# Frontend
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost/")

# Container status
run_cmd(client, "docker ps --format 'table {{.Names}}\t{{.Status}}'")

client.close()
