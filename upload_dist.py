import paramiko
import tarfile
import os
import io

# 打包 frontend/dist
print('Packing frontend/dist...')
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w:gz') as tar:
    tar.add('frontend/dist', arcname='dist')
buf.seek(0)
data = buf.read()
print(f'Packed: {len(data)/1024:.0f} KB')

# 上传
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass',
               timeout=20)
print('Connected!')

sftp = client.open_sftp()
with sftp.open('/tmp/dist.tar.gz', 'wb') as f:
    f.write(data)
print('Uploaded dist.tar.gz')
sftp.close()

# 解压
stdin, stdout, stderr = client.exec_command(
    'rm -rf /opt/taxja/frontend/dist && tar -xzf /tmp/dist.tar.gz -C /opt/taxja/frontend/ && ls /opt/taxja/frontend/dist | head -5'
)
print(stdout.read().decode())
print(stderr.read().decode())

client.close()
print('Done!')
