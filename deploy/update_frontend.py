"""快速更新前端 + nginx.conf 到服务器"""
import paramiko, os, tarfile, tempfile, time

SERVER_IP = '46.62.227.62'
SSH_KEY = r'C:\Users\yk1e25\taxja-server-nopass'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER_IP, username='root', key_filename=SSH_KEY, timeout=30)
print('已连接')

# 打包前端
tar_path = os.path.join(tempfile.gettempdir(), 'taxja_fe.tar.gz')
with tarfile.open(tar_path, 'w:gz') as tar:
    tar.add('frontend/dist', arcname='dist')
    tar.add('frontend/nginx.conf', arcname='nginx.conf')
print(f'打包: {os.path.getsize(tar_path)/1024/1024:.1f} MB')

# 上传
sftp = client.open_sftp()
sftp.put(tar_path, '/tmp/taxja_fe.tar.gz')
sftp.close()
print('已上传')

# 解压 + 重启 nginx
for cmd in [
    'rm -rf /opt/taxja/frontend/dist',
    'tar xzf /tmp/taxja_fe.tar.gz -C /opt/taxja/frontend/',
    'cd /opt/taxja && docker compose -f docker-compose.server.yml restart nginx',
]:
    print(f'  $ {cmd[:80]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    if out: print(f'    {out[-200:]}')

time.sleep(3)
stdin, stdout, stderr = client.exec_command('curl -s -o /dev/null -w "%{http_code}" http://localhost:80/', timeout=10)
code = stdout.read().decode().strip()
print(f'nginx: HTTP {code}')

client.close()
print('完成')
