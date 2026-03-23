"""验证credits/balance轮询是否已停止"""
import paramiko
import time

SERVER_IP = '178.104.73.139'
SSH_KEY = r'C:\Users\yk1e25\taxja-server-nopass'

def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_IP, username='root', key_filename=SSH_KEY, timeout=20)
    return client

def run_remote(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    return out

def main():
    client = ssh_connect()
    print('已连接，等待10秒后检查日志...')
    time.sleep(10)

    # 统计最近10秒内credits/balance的请求次数
    out = run_remote(client, 'docker logs taxja-backend --since 10s 2>&1 | grep "credits/balance" | wc -l')
    print(f'最近10秒内 /credits/balance 请求次数: {out}')

    out2 = run_remote(client, 'docker logs taxja-backend --since 10s 2>&1 | grep "credits/balance" | tail -5')
    if out2:
        print(f'最近请求:\n{out2}')
    else:
        print('没有新的 credits/balance 请求 ✓')

    # 检查订阅状态
    print('\n=== 数据库中用户状态 ===')
    out3 = run_remote(client, '''docker exec taxja-backend python3 -c "
import sys; sys.path.insert(0, '/app')
from app.db.base import SessionLocal
from app.models.user import User
from app.models.credit_balance import CreditBalance
from app.models.subscription import Subscription
db = SessionLocal()
for u in db.query(User).all():
    sub = db.query(Subscription).filter(Subscription.user_id == u.id).first()
    cb = db.query(CreditBalance).filter(CreditBalance.user_id == u.id).first()
    credits = (cb.plan_balance + cb.topup_balance) if cb else 0
    status = sub.status if sub else 'none'
    print(f'{u.email}: sub={status}, credits={credits}')
db.close()
" 2>/dev/null''')
    print(out3)

    client.close()

if __name__ == '__main__':
    main()
