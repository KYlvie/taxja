# LLM 配置指南 / LLM Setup Guide

## 问题：本地 Ollama 太慢

你的 CPU-only 环境运行 Ollama qwen3:8b 很慢（30-60秒响应）。

## 推荐方案

### 🚀 方案 1：Groq API（推荐）

**优点**：
- ✅ 免费额度很大（每天数千次请求）
- ✅ 速度极快（1-3秒响应，比 OpenAI 还快）
- ✅ Llama 3.3 70B 质量接近 GPT-4
- ✅ 无需本地资源

**设置步骤**：

1. 注册账号：https://console.groq.com/
2. 创建 API Key：https://console.groq.com/keys
3. 配置 `.env`：

```bash
# backend/.env
GROQ_ENABLED=true
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# 禁用其他 LLM
OLLAMA_ENABLED=false
OPENAI_API_KEY=
```

4. 重启后端服务

**可用模型**：
- `llama-3.3-70b-versatile` - 最佳质量（推荐）
- `llama-3.1-8b-instant` - 更快速度
- `mixtral-8x7b-32768` - 长上下文

---

### 💰 方案 2：OpenAI API

**优点**：
- ✅ 质量最稳定
- ✅ 速度快（2-5秒）
- ✅ 支持多种模型

**成本**：
- `gpt-4o-mini`: $0.15/1M input tokens, $0.60/1M output tokens
- 估算：每次对话约 $0.001-0.003（很便宜）

**设置步骤**：

1. 获取 API Key：https://platform.openai.com/api-keys
2. 配置 `.env`：

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# 禁用其他 LLM
GROQ_ENABLED=false
OLLAMA_ENABLED=false
```

---

### 🏠 方案 3：优化本地 Ollama

如果坚持使用本地模型：

**选项 A：使用更小的模型**

```bash
# 3B 参数模型，速度快 3 倍
ollama pull qwen2.5:3b

# 或 Microsoft Phi-3
ollama pull phi3:mini
```

```bash
# .env
OLLAMA_ENABLED=true
OLLAMA_MODEL=qwen2.5:3b
```

**选项 B：量化模型**

```bash
# 4-bit 量化，速度快 2 倍
ollama pull qwen3:8b-q4_0
```

```bash
# .env
OLLAMA_MODEL=qwen3:8b-q4_0
```

**选项 C：调整生成参数**（已在代码中实现）
- ✅ 限制输出长度（300 tokens）
- ✅ 禁用思考模式
- ✅ 减少对话历史

---

## 性能对比

| 方案 | 响应时间 | 质量 | 成本 | 推荐度 |
|------|---------|------|------|--------|
| Groq (Llama 3.3 70B) | 1-3秒 | ⭐⭐⭐⭐⭐ | 免费 | ⭐⭐⭐⭐⭐ |
| OpenAI (gpt-4o-mini) | 2-5秒 | ⭐⭐⭐⭐⭐ | ~$0.002/次 | ⭐⭐⭐⭐ |
| Ollama (qwen3:8b CPU) | 30-60秒 | ⭐⭐⭐ | 免费 | ⭐⭐ |
| Ollama (qwen2.5:3b CPU) | 10-20秒 | ⭐⭐⭐ | 免费 | ⭐⭐⭐ |

---

## 测试配置

重启后端后测试：

```bash
# 检查 LLM 服务状态
curl http://localhost:8000/api/v1/health

# 测试 AI 助手（需要登录 token）
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "什么是 Einkommensteuer?", "language": "zh"}'
```

---

## Docker 部署注意事项

如果在 Docker 中运行：

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      # 使用云端 API（推荐）
      - GROQ_ENABLED=true
      - GROQ_API_KEY=${GROQ_API_KEY}
      
      # 或连接宿主机的 Ollama
      - OLLAMA_ENABLED=true
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
```

---

## 常见问题

**Q: Groq 有使用限制吗？**
A: 免费层每分钟 30 次请求，每天 14,400 次请求，对个人项目足够。

**Q: 数据隐私如何？**
A: Groq/OpenAI 会处理你的请求，但不会用于训练。敏感数据建议用本地 Ollama。

**Q: 能同时配置多个 LLM 吗？**
A: 可以，优先级：Groq > OpenAI > Ollama。系统会自动选择第一个可用的。

**Q: 如何切换回 Ollama？**
A: 在 `.env` 中设置 `GROQ_ENABLED=false` 和 `OPENAI_API_KEY=`，然后 `OLLAMA_ENABLED=true`。
