# Taxja LLM 部署方案 - RunPod（测试阶段）

## 为什么选 RunPod
- 按秒计费，不用就停机，停了只收少量存储费
- RTX 4090 24GB ~$0.44/hr，每天测试2小时 ≈ $0.88/天 ≈ €25/月
- 有欧洲节点（EU-RO-1 罗马尼亚）
- 预置 vLLM 模板，部署简单

## 费用估算
| 使用场景 | 每月费用 |
|---------|---------|
| 每天测试2小时 | ~€25 |
| 每天测试4小时 | ~€50 |
| 7x24全天运行 | ~€320（不如直接用Hetzner） |

## 第一步：注册 RunPod

1. 访问 https://www.runpod.io/
2. 注册账号，充值 $10 起步就够测试
3. 进入 Dashboard → Pods

## 第二步：创建 GPU Pod

1. 点击 "Deploy" → "GPU Pods"
2. 选择配置：
   - GPU: `RTX 4090` (24GB VRAM)
   - 地区: 选 `EU` 节点（如果有 EU-RO-1）
   - Template: 选 `RunPod vLLM` 预置模板
3. 环境变量设置：
   ```
   VLLM_MODEL=Qwen/Qwen2.5-32B-Instruct-AWQ
   VLLM_API_KEY=你的自定义密钥（随便写一个强密码）
   VLLM_MAX_MODEL_LEN=4096
   VLLM_GPU_MEMORY_UTILIZATION=0.92
   VLLM_DTYPE=auto
   VLLM_QUANTIZATION=awq
   ```
4. 磁盘: Container Disk 20GB, Volume Disk 60GB（存模型，32B量化后约20GB）
5. 点击 Deploy

## 第三步：等待启动

- 首次启动需要下载模型（~20GB），大约15-20分钟
- 之后重启只需1-2分钟（模型已缓存在 Volume）
- 在 Pod 详情页可以看到日志

## 第四步：获取连接信息

Pod 启动后，在 "Connect" 标签页找到：
- HTTP端口: `https://xxx-8000.proxy.runpod.net/v1`（8000是vLLM默认端口）
- 这个URL就是你的 `GPT_OSS_BASE_URL`

## 第五步：配置 Taxja 后端

修改 `backend/.env`：
```bash
# 关闭本地 Ollama
OLLAMA_ENABLED=false

# 启用远程 GPU 服务器
GPT_OSS_ENABLED=true
GPT_OSS_BASE_URL=https://你的pod-id-8000.proxy.runpod.net/v1
GPT_OSS_MODEL=Qwen/Qwen2.5-32B-Instruct-AWQ
GPT_OSS_API_KEY=你设置的密钥
```

## 第六步：测试连接

```bash
# 测试 vLLM 是否正常
curl https://你的pod-id-8000.proxy.runpod.net/v1/chat/completions \
  -H "Authorization: Bearer 你的密钥" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-32B-Instruct-AWQ",
    "messages": [{"role": "user", "content": "Was ist Pendlerpauschale?"}],
    "max_tokens": 500
  }'
```

## 省钱技巧

- 测试完就在 Dashboard 里 Stop Pod（停机后只收存储费 ~$0.10/hr）
- 不用了可以 Terminate Pod（完全不收费，但模型要重新下载）
- 用 Volume 存模型，这样 Stop/Start 不用重新下载

## 迁移到生产

测试满意后，迁移到 Hetzner 独立服务器：
1. 参考 `deploy/gpu-server/README.md`
2. 只需要改 `backend/.env` 里的 `GPT_OSS_BASE_URL` 和 `GPT_OSS_API_KEY`
3. 代码零修改
