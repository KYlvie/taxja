import paramiko
import time

def run(client, cmd, timeout=300, show_all=False):
    print(f'\n$ {cmd[:100]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out[-3000:] if not show_all else out)
    if err and 'WARNING' not in err[:20]:
        print('ERR:', err[-1000:])
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass',
               timeout=20)
print('Connected!')

# Build and start
run(client, 'cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod build --no-cache 2>&1 | tail -20', timeout=600)
run(client, 'cd /opt/taxja && docker compose -f docker-compose.server.yml --env-file .env.prod up -d', timeout=120)

# Wait for services
print('\nWaiting 20s for services to start...')
time.sleep(20)

run(client, 'docker ps')
run(client, 'docker logs taxja-backend --tail 20 2>&1')

# Run migrations
print('\nRunning migrations...')
run(client, 'docker exec taxja-backend alembic upgrade head 2>&1', timeout=120)

# Test
run(client, 'curl -s http://localhost:8000/api/v1/health || curl -s http://localhost:8000/health || echo "checking..."')
run(client, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:80/')

client.close()
print('\nDeploy complete!')
