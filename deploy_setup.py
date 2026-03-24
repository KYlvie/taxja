import paramiko
import time

def run(client, cmd, timeout=120):
    print(f'\n$ {cmd}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out[-2000:])  # last 2000 chars
    if err:
        print('ERR:', err[-500:])
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass',
               timeout=20)
print('Connected!')

# Install Docker
run(client, 'apt-get update -qq')
run(client, 'apt-get install -y docker.io docker-compose-plugin git curl', timeout=300)
run(client, 'systemctl enable docker && systemctl start docker')
run(client, 'docker --version')
run(client, 'docker compose version')

# Clone repo
run(client, 'rm -rf /opt/taxja')
run(client, 'git clone https://github.com/KYlvie/taxja.git /opt/taxja', timeout=120)
run(client, 'ls /opt/taxja')

client.close()
print('\nSetup done!')
