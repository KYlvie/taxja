import paramiko
import time

def run(client, cmd, timeout=120):
    print(f'\n$ {cmd[:100]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out[-2000:])
    if err:
        print('ERR:', err[-500:])
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass',
               timeout=20)
print('Connected!')

# Run migrations
run(client, 'docker exec taxja-backend alembic upgrade head 2>&1', timeout=120)

# Test backend health
run(client, 'curl -s http://localhost:8000/api/v1/health 2>/dev/null || curl -s http://localhost:8000/ | head -100')

# Test nginx (port 80)
run(client, 'curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:80/')

# Test API through nginx
run(client, 'curl -s -o /dev/null -w "API via nginx: HTTP %{http_code}" http://localhost:80/api/v1/health')

client.close()
print('\nAll done!')
