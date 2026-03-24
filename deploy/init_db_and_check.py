#!/usr/bin/env python3
"""Init database and final health check."""
import paramiko
import time

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

# Init database
print("=" * 50)
print("INIT DATABASE")
print("=" * 50)
run_cmd(client, "docker cp /opt/taxja/docker/init-db/init.sql taxja-postgres:/tmp/init.sql")
run_cmd(client, 'docker exec taxja-postgres psql -U taxja -d taxja -f /tmp/init.sql 2>&1 | tail -15', timeout=120)
run_cmd(client, "docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT count(*) as tables FROM information_schema.tables WHERE table_schema = 'public';\"")

# Flush Redis
run_cmd(client, "docker exec taxja-redis redis-cli FLUSHALL")

# Final health check
print("\n" + "=" * 50)
print("FINAL HEALTH CHECK")
print("=" * 50)
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost:8000/api/v1/health")
run_cmd(client, "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost/")
run_cmd(client, "curl -s http://localhost:8000/api/v1/health 2>/dev/null | head -1")

# All containers
run_cmd(client, "docker ps --format 'table {{.Names}}\t{{.Status}}'")

# Disk usage
run_cmd(client, "df -h / | tail -1")

print("\n" + "=" * 50)
print(f"SERVER READY: http://{HOST}")
print("Next: SSL cert + DNS update")
print("=" * 50)

client.close()
