# Taxja LLM GPU 服务器部署 - Hetzner（生产环境）

## 适用场景
- 用户量稳定，需要 7x24 运行
- 从 RunPod 测试阶段迁移过来
- 需要 GDPR 严格合规（德国机房）

## 推荐配置
| 项目 | 配置 |
|------|------|
| 服务商 | Hetzner Dedicated |
| 型号 | GEX44 |
| GPU | NVIDIA RTX 4000 SFF Ada (20GB VRAM) |
| CPU | AMD Ryzen 9 7950X3D |
| RAM | 64GB DDR5 ECC |
| 存储 | 2x 512GB NVMe SSD |
| 费用 | ~€205/月 + 一次性安装费 €264 |
| 机房 | Falkenstein (德国) |

> Qwen2.5-32B-Instruct-AWQ（4bit量化）需要 ~20GB VRAM，20GB 的 RTX 4000 SFF 比较紧张。
> 如果选 GEX44（20GB VRAM），建议用 Qwen2.5-14B-Instruct（~9GB AWQ）更稳。
> 如果想跑 32B，建议选有 RTX 4090（24GB）的服务器。

## 订购步骤

1. 访问 https://www.hetzner.com/dedicated-rootserver/gex44/
2. 选择 Ubuntu 22.04 LTS
3. 机房选 Falkenstein (FSN)
4. 下单，约 1-2 小时交付
5. 收到邮件后 SSH 登录

## 部署步骤

### 1. SSH 登录
```bash
ssh root@你的服务器IP
```

### 2. 上传并运行部署脚本
```bash
# 从本地上传
scp deploy/gpu-server/setup.sh root@你的服务器IP:/root/

# 登录执行
ssh root@你的服务器IP
bash /root/setup.sh
```

脚本会自动：
- 安装 NVIDIA 驱动 + CUDA
- 安装 vLLM
- 下载 Qwen2.5-7B-Instruct 模型
- 配置防火墙
- 创建 systemd 服务（开机自启）

### 3. 配置 Taxja 后端
```bash
# backend/.env
OLLAMA_ENABLED=false
GPT_OSS_ENABLED=true
GPT_OSS_BASE_URL=http://你的服务器IP:8080/v1
GPT_OSS_MODEL=Qwen/Qwen2.5-32B-Instruct-AWQ
GPT_OSS_API_KEY=脚本生成的密钥
```

### 4. 验证
```bash
python deploy/check_llm_server.py --url http://你的服务器IP:8080/v1 --key 你的密钥
```

## 从 RunPod 迁移

迁移非常简单，只需改 `backend/.env`：

```diff
- GPT_OSS_BASE_URL=https://xxx-8000.proxy.runpod.net/v1
- GPT_OSS_API_KEY=runpod时的密钥
+ GPT_OSS_BASE_URL=http://hetzner服务器IP:8080/v1
+ GPT_OSS_API_KEY=hetzner的密钥
```

代码零修改，重启后端即可。

## 安全加固

```bash
# 1. 只允许你的后端服务器IP访问 vLLM 端口
ufw delete allow 8080/tcp
ufw allow from 你的后端IP to any port 8080

# 2. SSH key 登录，禁用密码
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# 3. 自动安全更新
apt install unattended-upgrades -y
dpkg-reconfigure -plow unattended-upgrades
```

## 监控

```bash
# 查看 GPU 使用情况
nvidia-smi

# 查看 vLLM 服务状态
systemctl status taxja-llm

# 查看日志
journalctl -u taxja-llm -f

# 测试响应
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer 你的密钥" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"Hallo"}]}'
```

## 费用对比

| 方案 | 月费 | 适合 |
|------|------|------|
| RunPod 按小时 | €25-50（每天2-4小时） | 测试阶段 |
| Hetzner GEX44 按月 | ~€205 | 生产环境 |
| 盈亏平衡点 | 每天 ~15小时 | 超过这个用 Hetzner 更划算 |
