import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('178.104.73.139', username='root',
               key_filename=r'C:\Users\yk1e25\taxja-server-nopass', timeout=20)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err: print('ERR:', err)
    return out

# 直接在数据库里验证邮箱
print('=== 强制验证邮箱 ===')
run('''docker exec taxja-postgres psql -U taxja -d taxja -c \
  "UPDATE users SET email_verified=true, email_verification_token=NULL WHERE email=\'admin@taxja.at\';"''')

# 测试登录
print('\n=== 测试登录 ===')
run('''curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d \'{"email":"admin@taxja.at","password":"Admin123!"}\' ''')

client.close()
