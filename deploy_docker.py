import paramiko
import time

def run(client, cmd, timeout=180):
    print(f'\n$ {cmd[:80]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out[-1500:])
    if err and 'WARNING' not in err and 'warning' not in err:
        print('ERR:', err[-500:])
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass',
               timeout=20)
print('Connected!')

# Install Docker via official script
run(client, 'curl -fsSL https://get.docker.com | sh', timeout=300)
run(client, 'docker --version')
run(client, 'docker compose version')

# Check git branch
run(client, 'git -C /opt/taxja branch -a')
run(client, 'git -C /opt/taxja checkout codex/recovery-worktree-20260323 2>/dev/null || git -C /opt/taxja checkout main 2>/dev/null || echo "on default branch"')
run(client, 'git -C /opt/taxja log --oneline -3')

client.close()
print('\nDocker installed!')
