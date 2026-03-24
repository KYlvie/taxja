#!/usr/bin/env python3
"""Diagnose why the homepage is slow on the cloud server."""
import paramiko
import time

HOST = "46.62.227.62"
USER = "root"
KEY_PATH = r"C:\Users\yk1e25\taxja-server-nopass"

def run_cmd(client, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err and exit_code != 0:
        print(f"ERR: {err}")
    return exit_code, out, err

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
client.connect(HOST, username=USER, pkey=pkey, timeout=15)
transport = client.get_transport()
transport.set_keepalive(30)
print(f"Connected to {HOST}\n")

# 1. Server resource usage
print("=" * 60)
print("1. SERVER RESOURCES (CPU / RAM / Disk)")
print("=" * 60)
run_cmd(client, "uptime")
run_cmd(client, "free -h")
run_cmd(client, "df -h /")
run_cmd(client, "nproc")

# 2. Container resource usage
print("\n" + "=" * 60)
print("2. CONTAINER RESOURCE USAGE")
print("=" * 60)
run_cmd(client, "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")

# 3. Container status
print("\n" + "=" * 60)
print("3. CONTAINER STATUS")
print("=" * 60)
run_cmd(client, "cd /opt/taxja && docker compose -f docker-compose.server.yml ps")

# 4. Nginx response time for static files
print("\n" + "=" * 60)
print("4. RESPONSE TIMES (from server localhost)")
print("=" * 60)
run_cmd(client, "curl -s -o /dev/null -w 'Homepage: %{time_total}s (TTFB: %{time_starttransfer}s)\\n' http://localhost/")
run_cmd(client, "curl -s -o /dev/null -w 'Health API: %{time_total}s (TTFB: %{time_starttransfer}s)\\n' http://localhost/api/v1/health")
run_cmd(client, "curl -s -o /dev/null -w 'index.html size: %{size_download} bytes\\n' http://localhost/")

# 5. Check if gzip is working
print("\n" + "=" * 60)
print("5. GZIP COMPRESSION CHECK")
print("=" * 60)
run_cmd(client, "curl -s -H 'Accept-Encoding: gzip' -o /dev/null -w 'Gzip homepage: %{size_download} bytes\\n' http://localhost/")
run_cmd(client, "curl -s -I -H 'Accept-Encoding: gzip' http://localhost/ 2>&1 | grep -i 'content-encoding\\|content-length\\|content-type'")

# 6. Check frontend bundle sizes
print("\n" + "=" * 60)
print("6. FRONTEND BUNDLE SIZES")
print("=" * 60)
run_cmd(client, "ls -lhS /opt/taxja/frontend/dist/assets/*.js 2>/dev/null | head -10")
run_cmd(client, "ls -lhS /opt/taxja/frontend/dist/assets/*.css 2>/dev/null | head -5")
run_cmd(client, "du -sh /opt/taxja/frontend/dist/")

# 7. Check nginx config for caching headers
print("\n" + "=" * 60)
print("7. NGINX CONFIG (caching/compression)")
print("=" * 60)
run_cmd(client, "docker exec taxja-nginx cat /etc/nginx/conf.d/default.conf")

# 8. Backend startup time / worker count
print("\n" + "=" * 60)
print("8. BACKEND WORKERS & STARTUP")
print("=" * 60)
run_cmd(client, "docker logs taxja-backend 2>&1 | grep -i 'started\\|worker\\|uvicorn' | tail -5")

# 9. PostgreSQL connection pool / slow queries
print("\n" + "=" * 60)
print("9. POSTGRES CONNECTIONS & PERFORMANCE")
print("=" * 60)
run_cmd(client, "docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';\"")
run_cmd(client, "docker exec taxja-postgres psql -U taxja -d taxja -c \"SELECT count(*) as total_connections FROM pg_stat_activity;\"")

# 10. Redis memory
print("\n" + "=" * 60)
print("10. REDIS STATUS")
print("=" * 60)
run_cmd(client, "docker exec taxja-redis redis-cli INFO memory | grep 'used_memory_human\\|maxmemory_human'")

# 11. Check if backend is swapping or OOM
print("\n" + "=" * 60)
print("11. SWAP & OOM CHECK")
print("=" * 60)
run_cmd(client, "swapon --show")
run_cmd(client, "dmesg | grep -i 'oom\\|out of memory\\|killed process' | tail -5")

# 12. Network latency test
print("\n" + "=" * 60)
print("12. EXTERNAL ACCESS TIMING (via curl to public IP)")
print("=" * 60)
run_cmd(client, "curl -s -o /dev/null -w 'Direct IP http: %{time_total}s\\n' http://46.62.227.62/")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
client.close()
