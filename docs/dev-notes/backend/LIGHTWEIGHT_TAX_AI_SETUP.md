# 轻量级本地税务 AI 设置指南

## 概述

这个方案使用轻量级本地模型（3B 参数）+ 税务知识库，专门回答奥地利税务问题。

### 优势

✅ **隐私优先**：所有数据在本地处理，不发送到云端  
✅ **成本为零**：完全免费，无 API 费用  
✅ **专注税务**：只需要税务知识，不需要通用能力  
✅ **CPU 友好**：3B 模型在 CPU 上 5-10 秒响应（比 8B 快 3 倍）  
✅ **离线可用**：无需互联网连接

### 与云端方案对比

| 特性 | 轻量级本地 | Groq 云端 | OpenAI 云端 |
|------|-----------|----------|------------|
| 响应时间 | 5-10秒 | 1-3秒 | 2-5秒 |
| 隐私 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 成本 | 免费 | 免费 | ~$0.002/次 |
| 质量 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 离线 | ✅ | ❌ | ❌ |

---

## 快速开始

### 1. 安装轻量级模型

```bash
# 推荐：Qwen2.5 3B（中文支持最好）
ollama pull qwen2.5:3b

# 或者：Phi-3 Mini（Microsoft 出品）
ollama pull phi3:mini

# 或者：Gemma 2B（最快）
ollama pull gemma2:2b
```

### 2. 配置环境变量

```bash
# backend/.env
LIGHTWEIGHT_TAX_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. 准备税务知识库

知识库文件放在 `backend/docs/austrian_tax/` 目录。

**支持两种格式：**

#### 方式 1：官方PDF文档（推荐）

直接从奥地利税务局下载官方PDF：

```
backend/docs/austrian_tax/
├── Einkommensteuerrichtlinien_2023.pdf    # 官方税务指南
├── Einkommensteuerrichtlinien_2024.pdf
├── Einkommensteuerrichtlinien_2025.pdf
├── Einkommensteuerrichtlinien_2026.pdf
├── USt-Richtlinien_2026.pdf               # 增值税指南
└── SVS_Beitragsgrundlagen_2026.pdf        # SVS社保
```

**下载来源：**
- BMF (财政部): https://www.bmf.gv.at/
- FinanzOnline: https://www.bmf.gv.at/egovernment/finanzonline/
- SVS: https://www.svs.at/

**优势：**
- ✅ 官方权威，法律依据
- ✅ 每年自动更新，下载新PDF即可
- ✅ 完整信息，无需人工整理
- ✅ 可追溯到具体页码

#### 方式 2：Markdown文档（辅助）

用于快速参考和总结：

```
backend/docs/austrian_tax/
├── tax_rates_2023.md      # 税率快速参考
├── tax_rates_2024.md
├── tax_rates_2025.md
├── tax_rates_2026.md
├── deductions_guide.md    # 抵扣指南
├── svs_insurance.md       # SVS 社保
├── vat_guide.md           # 增值税指南
└── property_tax.md        # 房产税
```

**加载优先级：** PDF（官方）> Markdown（总结）

### 4. 使用 API

```bash
# 使用轻量级本地模式
curl -X POST http://localhost:8000/api/v1/ai/chat?use_lightweight=true \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "什么是 Einkommensteuer?",
    "language": "zh"
  }'

# 使用云端模式（默认）
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "什么是 Einkommensteuer?",
    "language": "zh"
  }'
```

---

## 如何获取官方PDF文档

### 1. 奥地利财政部 (BMF)

访问：https://www.bmf.gv.at/themen/steuern/

**主要文档：**
- Einkommensteuerrichtlinien (所得税指南)
- Umsatzsteuerrichtlinien (增值税指南)
- Körperschaftsteuerrichtlinien (企业税指南)

**下载步骤：**
1. 进入 "Publikationen" 或 "Downloads"
2. 搜索年份（如 "2026"）
3. 下载 PDF 格式文档
4. 保存到 `backend/docs/austrian_tax/`

### 2. SVS 社保官网

访问：https://www.svs.at/

**主要文档：**
- Beitragsgrundlagen (缴费基数)
- Versicherungswerte (保险金额)
- Beitragssätze (缴费率)

### 3. 自动化下载脚本（可选）

创建 `backend/scripts/download_tax_docs.py`：

```python
import requests
from pathlib import Path

# 示例：下载BMF文档
docs = {
    "2026": "https://www.bmf.gv.at/.../EStR_2026.pdf",
    # 添加更多URL
}

for year, url in docs.items():
    response = requests.get(url)
    path = Path(f"docs/austrian_tax/EStR_{year}.pdf")
    path.write_bytes(response.content)
    print(f"Downloaded: {path}")
```

---

## 知识库文件格式

### PDF文档（推荐）

系统会自动：
- 提取PDF文本内容
- 保留页码信息
- 限制加载页数（避免上下文溢出）
- 优先加载官方文档

**命名规范：**
- 包含年份：`*2026*.pdf` 或 `*2026*.PDF`
- 清晰描述：`Einkommensteuerrichtlinien_2026.pdf`

### Markdown文档（辅助）

```markdown
# 奥地利所得税税率 2025

## 税率表

| 年收入 | 税率 |
|--------|------|
| €0 - €12,816 | 0% |
| €12,816 - €20,818 | 20% |
| €20,818 - €34,513 | 30% |
...

## 抵扣项

### 交通抵扣
- 金额：€463/年
- 条件：有工作收入

### 通勤补贴
- 小额：€696 - €1,476
- 大额：€1,476 - €3,672
...
```

### 文件命名规则

- `tax_rates_YYYY.md` - 年度税率（系统会自动加载相关年份）
- 其他文件名自由，但要用 `.md` 扩展名
- 使用中文、德文或英文都可以

---

## 添加更多知识

### 方法 1：从现有文档提取

如果你有 PDF 或 Word 文档：

```bash
# 使用 pandoc 转换
pandoc input.pdf -o output.md

# 或手动复制粘贴关键信息
```

### 方法 2：从官方网站整理

参考来源：
- FinanzOnline: https://www.bmf.gv.at/
- SVS 官网: https://www.svs.at/
- WKO 商会: https://www.wko.at/

### 方法 3：使用 AI 辅助整理

```bash
# 用 ChatGPT/Claude 整理成 Markdown
"请将以下奥地利税务信息整理成 Markdown 格式，
包含清晰的标题、表格和要点..."
```

---

## 优化建议

### 1. 知识库组织

```
austrian_tax/
├── rates/              # 税率相关
│   ├── income_tax_2026.md
│   ├── vat_rates.md
│   └── svs_rates.md
├── deductions/         # 抵扣相关
│   ├── employee.md
│   ├── self_employed.md
│   └── landlord.md
├── guides/             # 指南
│   ├── filing_process.md
│   └── common_mistakes.md
└── faqs/               # 常见问题
    ├── general.md
    └── property.md
```

### 2. 内容质量

- ✅ 使用表格展示数字数据
- ✅ 添加具体例子
- ✅ 包含计算公式
- ✅ 标注适用年份
- ❌ 避免过于冗长的段落
- ❌ 避免模糊的描述

### 3. 性能优化

```bash
# .env 配置
LIGHTWEIGHT_TAX_MODEL=qwen2.5:3b  # 3B 最快
OLLAMA_BASE_URL=http://localhost:11434

# 如果还是太慢，可以用 2B 模型
LIGHTWEIGHT_TAX_MODEL=gemma2:2b
```

---

## 测试知识库

创建测试脚本 `test_lightweight_rag.py`：

```python
from app.services.lightweight_rag_service import get_lightweight_tax_rag

rag = get_lightweight_tax_rag()

# 测试问题
questions = [
    ("什么是 Einkommensteuer?", "zh"),
    ("Wie hoch ist der Steuersatz für €50.000?", "de"),
    ("What is the VAT rate in Austria?", "en"),
]

for question, lang in questions:
    print(f"\nQ: {question}")
    answer = rag.answer_tax_question(question, language=lang)
    print(f"A: {answer}\n")
```

```bash
python test_lightweight_rag.py
```

---

## 常见问题

### Q: 模型下载很慢怎么办？

A: Ollama 会从官方源下载。如果慢，可以：
```bash
# 使用镜像（如果有）
export OLLAMA_HOST=your-mirror-url
ollama pull qwen2.5:3b
```

### Q: 如何更新知识库？

A: 直接编辑 `backend/docs/austrian_tax/` 下的 Markdown 文件，无需重启服务。

### Q: 能同时使用轻量级和云端模式吗？

A: 可以！前端可以让用户选择：
- 轻量级模式：隐私优先，离线可用
- 云端模式：速度更快，质量更高

### Q: 知识库文件太大会影响性能吗？

A: 会。建议：
- 单个文件 < 50KB
- 总知识库 < 500KB
- 只包含核心税务信息

### Q: 如何验证模型是否可用？

```bash
curl http://localhost:11434/api/tags
# 应该看到 qwen2.5:3b 在列表中
```

---

## 前端集成

在前端添加模式选择：

```typescript
// 轻量级模式（本地）
const response = await fetch('/api/v1/ai/chat?use_lightweight=true', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: question,
    language: 'zh',
  }),
});

// 云端模式（默认）
const response = await fetch('/api/v1/ai/chat', {
  method: 'POST',
  // ...
});
```

---

## 下一步

1. ✅ 安装轻量级模型
2. ✅ 准备税务知识库文件
3. ⬜ 添加更多年份的税率信息
4. ⬜ 添加 SVS、VAT 等专题指南
5. ⬜ 在前端添加模式切换开关
6. ⬜ 收集用户反馈优化知识库

---

## 技术细节

### 工作原理

1. 用户提问 → API 接收
2. 加载相关税务知识（Markdown 文件）
3. 构建 System Prompt（知识 + 用户上下文）
4. 调用本地 3B 模型生成回答
5. 添加免责声明返回

### 与 RAG 的区别

- **传统 RAG**：向量数据库 + 语义搜索 + 大模型
- **轻量级方案**：直接加载 Markdown + 小模型
- **优势**：更简单、更快、更可控

### 限制

- 知识库需要手动维护
- 不能回答知识库外的问题
- 质量取决于知识库完整性


创建 `backend/scripts/download_tax_docs.py`：

```python
import requests
from pathlib import Path

# 示例：下载BMF文档
docs = {
    "2026": "https://www.bmf.gv.at/.../EStR_2026.pdf",
    # 添加更多URL
}

for year, url in docs.items():
    response = requests.get(url)
    path = Path(f"docs/austrian_tax/EStR_{year}.pdf")
    path.write_bytes(response.content)
    print(f"Downloaded: {path}")
```

运行：
```bash
python -m backend.scripts.download_tax_docs
```

---

## PDF vs Markdown 对比

| 特性 | PDF（官方） | Markdown（总结） |
|------|------------|-----------------|
| 权威性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 完整性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 更新频率 | 每年官方发布 | 需手动维护 |
| 可读性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 加载速度 | 较慢（需提取） | 快 |
| 推荐用途 | 主要知识来源 | 快速参考 |

**最佳实践：**
- 使用PDF作为主要知识来源（官方权威）
- 使用Markdown作为快速参考（常见问题）
- 系统会自动优先加载PDF

---

## 知识库更新流程

### 每年更新（推荐）

```bash
# 1. 下载新年度PDF
cd backend/docs/austrian_tax
wget https://www.bmf.gv.at/.../EStR_2026.pdf

# 2. 验证文件
ls -lh *.pdf

# 3. 测试加载
python -m backend.test_lightweight_rag

# 完成！无需重启服务
```

### 手动更新Markdown（可选）

```bash
# 编辑现有文件
nano backend/docs/austrian_tax/tax_rates_2026.md

# 或创建新文件
touch backend/docs/austrian_tax/new_guide.md
```

---

## 性能优化

### PDF加载限制

系统会自动限制PDF页数，避免上下文溢出：

```python
# lightweight_rag_service.py
max_pages = 30  # 年度查询
max_pages = 20  # 通用查询
```

### 知识库大小建议

- 单个PDF: < 100页
- 总知识库: < 500KB文本
- 只包含核心税务信息

### 如果响应太慢

```bash
# 1. 减少PDF页数
# 编辑 lightweight_rag_service.py
max_pages = 10  # 减少到10页

# 2. 使用更小的模型
ollama pull gemma2:2b  # 2B参数，更快

# 3. 只加载特定年份
# API调用时指定 tax_year=2026
```
