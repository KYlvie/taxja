import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass', timeout=20)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

print('=== 端口监听 ===')
out, _ = run('ss -tlnp | grep -E "443|80"')
print(out or '(无)')

print('\n=== nginx访问日志(最近30条) ===')
out, _ = run('docker logs taxja-nginx --tail 100 2>&1 | grep -v "notice\\|start\\|epoll\\|built\\|OS:\\|getrlimit\\|Sourcing\\|Launching\\|Configuration\\|entrypoint"')
print(out or '(无访问记录)')

print('\n=== 从外部curl测试(带Host头) ===')
out, _ = run('curl -s -o /dev/null -w "HTTP %{http_code}" -H "Host: taxja.at" http://localhost/')
print(out)

print('\n=== docker-compose.server.yml内容 ===')
out, _ = run('cat /opt/taxja/docker-compose.server.yml')
print(out)

client.close()
