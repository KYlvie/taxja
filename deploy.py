"""
一键部署脚本 - 将本地代码更新部署到生产服务器
用法: python deploy.py [--backend-only | --frontend-only]
"""
import paramiko
import subprocess
import sys
import os
import time

SERVER_IP = '178.104.73.139'
SSH_KEY = r'C:\Users\yk1e25\taxja-server-nopass'
REMOTE_DIR = '/opt/taxja'
BRANCH = 'codex/recovery-worktree-20260323'

def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_IP, username='root', key_filename=SSH_KEY, timeout=20)
    return client

def run_remote(client, cmd, timeout=120):
    print(f'  $ {cmd[:80]}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f'  {out[-500:]}')
    if err and 'warning' not in err.lower(): print(f'  ERR: {err[-300:]}')
    return out

def run_local(cmd, cwd=None):
    print(f'  $ {cmd}')
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout: print(f'  {result.stdout.strip()[-300:]}')
    if result.returncode != 0:
        print(f'  ERR: {result.stderr.strip()[-300:]}')
        return False
    return True

def deploy_backend(client):
    print('\n=== 部署后端 ===')
    # 服务器上 git pull
    run_remote(client, f'git -C {REMOTE_DIR} fetch origin')
    run_remote(client, f'git -C {REMOTE_DIR} reset --hard origin/{BRANCH}')
    # 重建并重启 backend 容器
    run_remote(client, f'docker compose -f {REMOTE_DIR}/docker-compose.server.yml build backend', timeout=300)
    run_remote(client, f'docker compose -f {REMOTE_DIR}/docker-compose.server.yml up -d backend')
    time.sleep(5)
    # 验证
    out = run_remote(client, 'curl -s http://localhost:8000/api/v1/health')
    if 'healthy' in out:
        print('  ✓ 后端部署成功')
    else:
        print('  ✗ 后端可能有问题，检查日志: docker logs taxja-backend')

def deploy_frontend(client):
    print('\n=== 构建前端 ===')
    # 本地 build
    ok = run_local('npx vite build', cwd='frontend')
    if not ok:
        print('前端构建失败，中止部署')
        return

    print('\n=== 上传前端 ===')
    sftp = client.open_sftp()

    # 上传 dist 目录
    dist_dir = 'frontend/dist'
    remote_dist = f'{REMOTE_DIR}/frontend/dist'

    # 清空远程 dist
    run_remote(client, f'rm -rf {remote_dist} && mkdir -p {remote_dist}')

    # 递归上传
    uploaded = 0
    for root, dirs, files in os.walk(dist_dir):
        # 创建远程目录
        rel_root = os.path.relpath(root, dist_dir).replace('\\', '/')
        remote_root = remote_dist if rel_root == '.' else f'{remote_dist}/{rel_root}'
        try:
            sftp.mkdir(remote_root)
        except Exception:
            pass
        for f in files:
            local_path = os.path.join(root, f)
            remote_path = f'{remote_root}/{f}'
            sftp.put(local_path, remote_path)
            uploaded += 1

    sftp.close()
    print(f'  上传了 {uploaded} 个文件')

    # 重启 nginx
    run_remote(client, 'docker restart taxja-nginx')
    time.sleep(3)
    out = run_remote(client, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:80/')
    print(f'  nginx 状态: HTTP {out}')
    if out == '200':
        print('  ✓ 前端部署成功')

def main():
    args = sys.argv[1:]
    backend_only = '--backend-only' in args
    frontend_only = '--frontend-only' in args

    print(f'连接服务器 {SERVER_IP}...')
    client = ssh_connect()
    print('已连接')

    if not frontend_only:
        deploy_backend(client)

    if not backend_only:
        deploy_frontend(client)

    client.close()
    print('\n部署完成')

if __name__ == '__main__':
    main()
