#!/usr/bin/env python3
"""Diagnose missing files and frontend build error."""
import paramiko

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"

def run_cmd(client, cmd, timeout=120):
    print(f"\n>>> {cmd[:140]}")
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            for line in out.split('\n')[-20:]:
                print(f"  {line}")
        if err:
            for line in err.split('\n')[-10:]:
                print(f"  ERR: {line}")
        return exit_code, out, err
    except Exception as e:
        print(f"  TIMEOUT/ERROR: {e}")
        return -1, "", str(e)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
print(f"Connected\n")

# Check backend/app structure
print("=" * 50)
print("BACKEND APP STRUCTURE")
print("=" * 50)
run_cmd(client, "ls -la /opt/taxja/backend/app/")
run_cmd(client, "ls /opt/taxja/backend/app/models/ 2>/dev/null || echo 'NO MODELS DIR'")
run_cmd(client, "ls /opt/taxja/backend/app/services/ 2>/dev/null | head -5 || echo 'NO SERVICES DIR'")
run_cmd(client, "ls /opt/taxja/backend/app/schemas/ 2>/dev/null | head -5 || echo 'NO SCHEMAS DIR'")
run_cmd(client, "ls /opt/taxja/backend/app/api/ 2>/dev/null || echo 'NO API DIR'")

# Check frontend build error in detail
print("\n" + "=" * 50)
print("FRONTEND BUILD ERROR")
print("=" * 50)
run_cmd(client, 
    "cd /opt/taxja && docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine sh -c 'npm run build 2>&1' | head -50",
    timeout=300)

# Check frontend src structure
print("\n" + "=" * 50)
print("FRONTEND SRC STRUCTURE")
print("=" * 50)
run_cmd(client, "ls /opt/taxja/frontend/src/ 2>/dev/null || echo 'NO SRC DIR'")

client.close()
