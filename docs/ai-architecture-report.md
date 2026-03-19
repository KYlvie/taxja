# Taxja AI 架构详细报告

> 生成日期：2026-03-16  
> 基于源代码实际分析，所有数值均来自代码常量定义

---

## 目录

1. [系统总览](#1-系统总览)
2. [LLM 提供商链](#2-llm-提供商链)
3. [交易分类管道](#3-交易分类管道)
4. [LLM 分类器详情](#4-llm-分类器详情)
5. [Per-User 分类规则](#5-per-user-分类规则)
6. [学习闭环](#6-学习闭环)
7. [AI 聊天与 RAG 系统](#7-ai-聊天与-rag-系统)
8. [可抵扣性检查器](#8-可抵扣性检查器)
9. [OCR 文档处理管道](#9-ocr-文档处理管道)
10. [省税建议系统](#10-省税建议系统)
11. [知识库管理](#11-知识库管理)
12. [意图识别系统](#12-意图识别系统)
13. [GDPR 合规](#13-gdpr-合规)
14. [治理与可观测性框架](#14-治理与可观测性框架)
15. [前端 AI UI 组件](#15-前端-ai-ui-组件)
16. [阈值速查表](#16-阈值速查表)

---

## 1. 系统总览

Taxja 的 AI 层采用多级降级架构，核心设计原则：

- **规则优先**：能用规则解决的不调 ML，能用 ML 解决的不调 LLM
- **多级降级**：每个 AI 功能都有从云端 LLM → 本地模型 → 规则引擎的降级路径
- **缓存驱动**：所有 LLM 调用结果都缓存，避免重复消耗
- **自学习**：用户纠正和 LLM 结果自动反馈到 ML 训练数据和 Per-User 规则

```
┌─────────────────────────────────────────────────────────┐
│                    AI Orchestrator                        │
│              (意图识别 → 工具路由 → 响应格式化)            │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│ 交易分类  │ RAG问答   │ 可抵扣检查 │ OCR管道   │ 省税建议    │
│ 4级管道   │ 4级降级   │ 规则+AI   │ 4阶段     │ 规则+AI     │
├──────────┴──────────┴──────────┴──────────┴──────────────┤
│                    LLM Service                           │
│     Groq → Groq-fallback → GPT-OSS → OpenAI → Ollama    │
├──────────────────────────────────────────────────────────┤
│  Redis Cache │ ChromaDB Vector │ PostgreSQL │ ML Models   │
└──────────────────────────────────────────────────────────┘
```

---

## 2. LLM 提供商链

> 源文件：`backend/app/services/llm_service.py`

### 2.1 提供商配置

| 优先级 | 提供商 | 模型 | 用途 | 环境变量 |
|--------|--------|------|------|----------|
| 1 (自托管) | GPT-OSS-120B | `openai/gpt-oss-120b` | Vision优先 | `GPT_OSS_ENABLED`, `GPT_OSS_BASE_URL` |
| 2 (云端) | Groq | `llama-3.3-70b-versatile` | Text优先 | `GROQ_ENABLED`, `GROQ_API_KEY` |
| 3 (云端) | Groq Fallback | `openai/gpt-oss-120b` | Text备用 | `GROQ_FALLBACK_MODEL` |
| 4 (云端) | OpenAI | `gpt-4o-mini` | 全能备用 | `OPENAI_API_KEY` |
| 5 (本地) | Ollama | `qwen3:8b` | CPU本地 | `OLLAMA_ENABLED` |

### 2.2 文本任务提供商链（Text Provider Chain）

调用顺序由 `_build_text_provider_chain()` 定义：

```
Groq (llama-3.3-70b-versatile)
  ↓ 失败/限流
Groq-fallback (openai/gpt-oss-120b)
  ↓ 失败/限流
GPT-OSS (自托管 openai/gpt-oss-120b)
  ↓ 失败
OpenAI (gpt-4o-mini)
```

### 2.3 视觉任务提供商链（Vision Provider Chain）

调用顺序由 `_build_vision_provider_chain()` 定义：

```
GPT-OSS (openai/gpt-oss-120b) ← 视觉模型优先
  ↓ 失败
OpenAI (gpt-4o-mini)
  ↓ 失败
Groq (llama-3.3-70b-versatile)
  ↓ 失败
Groq-fallback (openai/gpt-oss-120b)
```

### 2.4 限流重试策略

- 每个提供商最多重试 1 次（共 2 次尝试）
- 从 `retry-after` header 读取等待时间，上限 30 秒
- 默认等待 5 秒
- 超过 30 秒直接跳到下一个提供商
- Vision 调用额外支持 `max_tokens` 递减重试（全量 → 1/2 → 1/4）

### 2.5 Ollama 本地模式

当且仅当 GPT-OSS、Groq、OpenAI 全部不可用时启用：
- 模型：`qwen3:8b`
- 对话历史限制为最近 4 条（2轮对话）
- 输出限制 300 tokens
- 禁用 thinking 模式以加速
- 跳过 RAG 向量检索（SentenceTransformer 在 CPU 上太慢）
- 系统提示追加简洁指令（max 3-4 句话）

---

## 3. 交易分类管道

> 源文件：`backend/app/services/transaction_classifier.py`

### 3.1 四级分类流程

```
输入: Transaction (description, amount, type, user_id)
  │
  ▼
Step 0: Per-User 规则查找
  │ ├─ 命中 strict 规则 → 返回 (method="user_rule", confidence=1.00)
  │ ├─ 命中 soft 规则 → 返回 (method="user_rule_soft", confidence≤0.80)
  │ ├─ 命中 frozen 规则 → 跳过（规则已冻结，不可信）
  │ └─ 命中时调用 record_hit() 更新 last_hit_at
  │ 未命中
  ▼
Step 1: 规则引擎 (RuleBasedClassifier)
  │ confidence >= 0.95 → 直接返回 (method="rule")
  │ confidence < 0.95
  ▼
Step 2: ML 模型 (MLClassifier / scikit-learn)
  │ 取 rule vs ML 中置信度更高者作为 best
  │ best.confidence >= 0.90 → 返回 best
  │ best.confidence < 0.90
  ▼
Step 3: LLM 分类 (LLMTransactionClassifier)
  │ 成功 → 返回 (method="llm")
  │ 失败 → 返回 Step 2 的 best
```

### 3.2 核心阈值

| 常量 | 值 | 作用 |
|------|-----|------|
| `HIGH_CONFIDENCE_THRESHOLD` | `0.95` | 规则引擎结果达到此值直接采用，跳过 ML |
| `LLM_THRESHOLD` | `0.90` | best(rule, ML) 低于此值才调用 LLM |

### 3.3 ML 模型详情

- 算法：`RandomForestClassifier`（scikit-learn）
- 参数：`n_estimators=50, max_depth=10, random_state=42`
- 特征：TF-IDF 文本向量 + 金额标准化
- 分别训练 income 和 expense 两个模型
- 最低训练样本数：`min_training_samples = 10`
- 模型文件存储在 `models/` 目录

---

## 4. LLM 分类器详情

> 源文件：`backend/app/services/llm_classifier.py`

### 4.1 缓存架构

**双层缓存**：Redis 主 → 内存降级

| 参数 | 值 | 说明 |
|------|-----|------|
| `CACHE_TTL` | 7 天 (604,800s) | 缓存过期时间 |
| `MAX_CACHE_SIZE` | 10,000 | 内存缓存最大条目数 |
| Redis 前缀 | `llm_cls:` | Redis key 前缀 |
| 连接超时 | 2 秒 | Redis 连接/读写超时 |

**缓存 Key 生成**：
```python
raw = f"{merchant_normalized}|{txn_type}|{user_type}|{business_type}|{business_industry}"
key = SHA256(raw)[:32]
```

**商户名标准化** (`_normalize_merchant`)：
- 转小写
- 去除常见前缀（"zahlung an", "überweisung an" 等）
- 去除分店号（filiale/kasse + 数字）
- 去除邮编和城市名
- 去除尾部数字（收据号等）

### 4.2 置信度处理

| 常量 | 值 | 作用 |
|------|-----|------|
| `MIN_LLM_CONFIDENCE` | `0.50` | 置信度下限 clamp |
| `MAX_LLM_CONFIDENCE` | `0.95` | 置信度上限 clamp |
| `DEFAULT_CONFIDENCE` | `0.75` | LLM 未返回置信度时的默认值 |
| `MIN_CACHEABLE_CONFIDENCE` | `0.60` | 低于此值不缓存、不存储纠正记录 |

**置信度流程**：
```
LLM 返回 JSON → 提取 confidence 字段
  → 无效/缺失 → 使用 DEFAULT (0.75)
  → 有效 → clamp 到 [0.50, 0.95]
  → < 0.60 → 不缓存、不写 ClassificationCorrection、不创建 user_rule
  → 0.60~0.84 → 缓存 + 写 ClassificationCorrection(source=llm_unverified)，不创建 user_rule
  → >= 0.85 → 缓存 + 写 ClassificationCorrection(source=llm_verified) + 创建 soft user_rule
```

### 4.3 LLM Prompt 设计

- 语言：德语（奥地利税务专业术语）
- 包含用户画像（user_type, business_type, business_industry）
- 明确列出所有合法分类类别（26 个 expense + 7 个 income）
- 要求返回 JSON：`{category, confidence, is_deductible, reason}`
- temperature = 0.1（低随机性，高确定性）
- max_tokens = 300

### 4.4 内存缓存淘汰策略

当内存缓存达到 `MAX_CACHE_SIZE`：
1. 先清除所有已过期条目
2. 如果仍然满，按 `expires_at` 排序删除最早的 25%

---

## 5. Per-User 分类规则

> 源文件：`backend/app/services/user_classification_service.py`，`backend/app/models/user_classification_rule.py`

### 5.1 设计原则

- Key = **完整标准化描述**（不是商户名）
- "amazon druckerpatrone" 和 "amazon kleidung" 产生不同规则
- 同一商户不同商品 → 不同分类
- 规则分为 **strict**（人工确认）和 **soft**（LLM 推断）两种类型

### 5.2 描述标准化 (`normalize_description`)

去除的噪声：
- 4位以上数字（卡号、店铺ID）
- 日期格式（15.03.2026）
- IBAN 片段（AT开头）
- 分店/收银台号（filiale/kasse + 数字）
- 多余空格

保留的信息：
- 商户名
- 产品关键词

### 5.3 规则类型

| 类型 | 来源 | 初始置信度 | 行为 |
|------|------|-----------|------|
| `strict` | 用户手动纠正 | `1.00` | 完全信任，直接采用 |
| `soft` | LLM 高置信度推断 (≥0.85) | `0.80` | 可被下游分类器挑战，置信度上限 0.80 |

**升级机制**：soft 规则被用户手动确认后自动升级为 strict（`upsert_rule` 中 `rule_type="strict"` 覆盖），置信度提升至 1.00。反向降级不会发生。

### 5.4 规则生命周期

```
创建来源：
  1. 用户手动纠正交易分类 → learn_from_correction() → upsert_rule(rule_type="strict")
  2. LLM 分类结果 (confidence >= 0.85) → _store_llm_correction() → upsert_rule(rule_type="soft")
  注意：LLM 结果 0.60 ≤ conf < 0.85 只写 ClassificationCorrection，不创建规则

查找：
  Step 0 of classify_transaction()
  → normalize_description(description)
  → 查询 UserClassificationRule (user_id, normalized_description, txn_type)
  → frozen=True → 跳过（返回 None，降级到规则引擎）
  → 命中 → record_hit() 更新 last_hit_at
  → strict → 返回 ClassificationResult(method="user_rule", confidence=1.00)
  → soft → 返回 ClassificationResult(method="user_rule_soft", confidence≤0.80)

冲突记录：
  learn_from_correction() 中，如果已有规则的 category 与用户纠正不同
  → record_conflict() → conflict_count += 1
  → soft 规则 conflict_count >= 3 → 自动冻结 (frozen=True)

衰减：
  decay_stale_soft_rules(stale_days=90)
  → soft 规则超过 90 天未命中 → confidence -= 0.10（下限 0.50）
  → 管理员通过 POST /admin/governance/decay-rules 触发

归档：
  archive_low_hit_rules(min_hits=1, stale_days=180)
  → hit_count ≤ 1 且超过 180 天未命中 → 删除
  → 管理员通过 POST /admin/governance/archive-rules 触发

删除：
  用户主动删除 / GDPR 账户注销时批量清除
```

### 5.5 数据模型

```python
UserClassificationRule:
  - user_id: int (FK → users)
  - normalized_description: str  # 标准化后的描述
  - original_description: str    # 原始描述（展示用）
  - txn_type: str               # "income" / "expense"
  - category: str               # 分类结果
  - confidence: Decimal          # strict=1.00, soft=0.80（可衰减至0.50）
  - hit_count: int              # 命中次数
  - rule_type: str              # "strict" / "soft"
  - last_hit_at: DateTime       # 最后命中时间（生命周期追踪）
  - conflict_count: int         # 冲突次数（用户纠正与规则不一致）
  - frozen: bool                # 是否冻结（soft规则冲突≥3次自动冻结）
  - created_at: DateTime
  - updated_at: DateTime
  唯一约束: (user_id, normalized_description, txn_type)
```

---

## 6. 学习闭环

> 源文件：`backend/app/services/classification_learning.py`，`backend/app/services/transaction_classifier.py`

### 6.1 数据流

```
用户纠正交易分类 (learn_from_correction)
  │
  ├─→ ClassificationCorrection 记录 (DB)
  │     - original_category, correct_category
  │     - original_confidence
  │     - source = "human_verified"
  │     - transaction_id, user_id
  │
  ├─→ 冲突检测：已有规则 category ≠ correct_category?
  │     → 是 → record_conflict() → conflict_count += 1
  │     → soft 规则 conflict_count >= 3 → 自动冻结
  │
  ├─→ UserClassificationRule upsert (rule_type="strict", 立即生效)
  │     - 下次相同描述直接命中 Step 0
  │     - 如果已有 soft 规则 → 升级为 strict
  │
  └─→ 累计检查：corrections_since_last_training >= 50?
        │ 是
        ▼
      ML 模型重训练 (RandomForest)
        - 仅使用可信来源的训练数据（见 6.3）
        - (description, amount, correct_category, type)
        - 训练后记录 last_trained_at 时间戳
        - 后续只计算新增纠正数
```

### 6.2 重训练阈值

| 参数 | 值 | 说明 |
|------|-----|------|
| `min_corrections_for_retrain` | 50 | 自上次训练后新增纠正数达到此值触发重训练 |
| `min_training_samples` | 10 | ML 模型最低训练样本数 |

### 6.3 训练数据来源过滤

`get_training_data()` 严格过滤训练数据来源，防止错误自我强化：

| 来源 (source) | 是否参与训练 | 说明 |
|---------------|-------------|------|
| `human_verified` | ✅ 是 | 用户手动纠正，最可信 |
| `llm_consensus` | ✅ 是 | LLM 结果与规则/ML 一致 |
| `None` (legacy) | ✅ 是 | 历史数据（source 字段引入前的记录） |
| `llm_verified` | ❌ 否 | LLM 高置信度但未经人工确认 |
| `llm_unverified` | ❌ 否 | LLM 中等置信度，风险较高 |
| `system_default` | ❌ 否 | 系统默认值，无分类价值 |

### 6.4 LLM 结果分层写入策略

`_store_llm_correction()` 使用三层策略控制 LLM 结果的存储范围：

```
LLM 分类结果
  │
  ├─ Tier A (confidence >= 0.85):
  │   → ClassificationCorrection (source="llm_verified")
  │   → UserClassificationRule (rule_type="soft", confidence=0.80)
  │   → 参与审计但不参与 ML 训练
  │
  ├─ Tier B (0.60 ≤ confidence < 0.85):
  │   → ClassificationCorrection (source="llm_unverified")
  │   → 不创建 UserClassificationRule
  │   → 参与审计但不参与 ML 训练
  │
  └─ Tier C (confidence < 0.60):
      → 不存储任何记录
      → 不缓存
      → 仅返回给用户
```

**设计理由**：
- Tier A 创建 soft 规则加速未来分类，但标记为 `llm_verified` 不参与 ML 训练，避免 LLM 错误污染模型
- Tier B 只记录纠正用于审计追踪，不创建规则避免"一次坏的 LLM 调用污染所有未来分类"
- Tier C 完全不持久化，低置信度结果不值得存储

### 6.5 训练数据审计报告

`get_training_audit_report()` 生成训练数据质量报告：

```python
{
    "total_corrections": 150,
    "by_source": {
        "human_verified": {"count": 80, "ratio": 0.533},
        "llm_consensus": {"count": 20, "ratio": 0.133},
        "llm_verified": {"count": 15, "ratio": 0.100},
        "llm_unverified": {"count": 25, "ratio": 0.167},
        "system_default": {"count": 5, "ratio": 0.033},
        "legacy_null": {"count": 5, "ratio": 0.033},
    },
    "trainable_sources": ["human_verified", "llm_consensus", "legacy_null"],
    "excluded_sources": ["llm_unverified", "system_default", "llm_verified"],
    "trainable_count": 105,
    "excluded_count": 45,
    "net_trainable_ratio": 0.70,
    "min_samples_for_retrain": 50,
    "ready_to_retrain": True,
}
```

管理员通过 `GET /admin/governance/training-audit` 查看。

### 6.6 OCR 纠正追踪

- 用户修正 OCR 提取结果 → 存入 `document.ocr_result.learning_data[]`
- `get_extraction_accuracy()` 计算每个字段的准确率
- 低准确率字段（< 80% 且样本 >= 5）标记为 `low_accuracy_fields`
- 管理员通过 `GET /admin/ocr-accuracy` 查看

---

## 7. AI 聊天与 RAG 系统

> 源文件：`backend/app/services/ai_orchestrator.py`，`backend/app/services/rag_service.py`

### 7.1 AI Orchestrator 总体流程

```
用户消息
  │
  ▼
detect_intent(message) → IntentResult(intent, confidence, params)
  │
  ├─ 计算类意图 → ToolRegistry 调用对应计算引擎 → 格式化结果
  │   (calculate_tax, calculate_vat, calculate_svs, calculate_kest,
  │    calculate_immoest, check_deductibility, classify_transaction,
  │    what_if, summarize_status)
  │
  ├─ 优化类意图 → 获取用户财务摘要 → RAG 生成建议
  │   (optimize_tax)
  │
  └─ 问答/未知意图 → RAG 降级链
      (tax_qa, unknown, explain_doc)
```

### 7.2 RAG 降级链（4级）

```
Level 1: Full RAG (LLM + ChromaDB 向量检索)
  │ 失败 / Ollama模式跳过
  ▼
Level 2: Direct LLM (无向量检索，仅用户数据 + 对话历史)
  │ 失败 / Ollama模式跳过
  ▼
Level 3: Lightweight Ollama RAG (本地 CPU)
  │ 失败
  ▼
Level 4: Rule-based 规则回复 (_generate_rule_based_response)
```

### 7.3 知识检索来源

Full RAG 从以下 ChromaDB collection 检索：

| Collection | 内容 | 每次检索条数 |
|------------|------|-------------|
| `austrian_tax_law` | 手写税法知识 | 3 |
| `usp_2026_tax_tables` | 2026 USP 税率表 | 3 |
| `tax_faq` | 常见问题 | 3 |
| `steuerbuch_guides` | BMF 税务指南 PDF 分块 | 5 |
| `admin_knowledge_updates` | 管理员上传的知识更新 | 3 |

所有检索都带 `language` 过滤器。

### 7.4 对话摘要扩展记忆（⑤）

| 参数 | 值 | 说明 |
|------|-----|------|
| `RECENT_WINDOW` | 6 | 最近 6 条消息原文传给 LLM |
| `SUMMARY_WINDOW` | 20 | 更早的 20 条消息生成摘要 |
| `_SUMMARY_CACHE_MAX` | 500 | 摘要缓存最大条目数 |
| 摘要最大长度 | 200 词 | 超出截断 |
| 缓存数据结构 | `OrderedDict` | 真正的 LRU（`move_to_end` on hit/write） |
| 淘汰策略 | 满时删除最早 10% | `list(keys)[:max//10]` |

**流程**：
```
获取最近 26 条消息 (6 + 20)
  │
  ├─ <= 6 条 → 全部原文传给 LLM
  │
  └─ > 6 条 → 分割：
       older = messages[:-6]  (最多20条)
       recent = messages[-6:]  (最近6条)
       │
       ├─ older → MD5(id+content[:60]) 生成 cache_key
       │   ├─ 缓存命中 → 使用缓存摘要
       │   └─ 缓存未命中 → LLM 生成摘要 → 存入缓存
       │
       └─ 组装: [system: 摘要] + recent 原文
```

### 7.5 用户财务摘要

`_build_financial_summary()` 从数据库构建的上下文包括：
- 年度收入/支出/可抵扣总额
- 收入/支出分类明细
- 文档数量
- 家庭信息（子女数、单亲）
- 通勤信息（距离、公共交通）
- Home office 资格
- 房产组合（购买价、建筑价值、折旧率、累计折旧）
- 贷款利息
- 定期交易
- 小企业主免税额度检查（€55,000 阈值）
- 缺失抵扣检测（通勤、Home office、育儿费用）
- 年度同比变化

---

## 8. 可抵扣性检查器

> 源文件：`backend/app/services/deductibility_checker.py`

### 8.1 两层架构

```
输入: (expense_category, user_type, ocr_data?, description?, business_type?, business_industry?)
  │
  ▼
Layer 0: 行业特定覆盖 (business_deductibility_rules)
  │ 有覆盖 → 返回
  │ 无覆盖
  ▼
Layer 1: 规则表查找 (_RULES[user_type][category])
  │
  ├─ True → 直接可抵扣
  ├─ False → 直接不可抵扣
  └─ "NEEDS_AI" → 进入 Layer 2
       │
       ▼
Layer 2: AI 分析 (_ai_analyze)
  │ 先查缓存 → 命中返回
  │ 未命中 → 调用 LLM
  │ LLM 不可用 → 降级默认值
  │   - 商业用户 → 默认可抵扣
  │   - 雇员 → 默认不可抵扣
```

### 8.2 规则表覆盖

5 种用户类型各有完整的 26 类别规则表：

| 用户类型 | NEEDS_AI 的类别 |
|----------|----------------|
| `employee` | 无（全部明确） |
| `self_employed` | groceries, clothing, other |
| `landlord` | other |
| `mixed` | groceries, clothing, other |
| `gmbh` | groceries, clothing, other |

### 8.3 AI 可抵扣性缓存

| 参数 | 值 | 说明 |
|------|-----|------|
| TTL | 7 天 (604,800s) | 与 LLM 分类缓存一致 |
| 最大条目数 | 5,000 | |
| Key | `SHA256(category\|user_type\|business_industry\|merchant)[:32]` | |
| 淘汰策略 | 满时删除最早 25% | 按 `expires_at` 排序 |

### 8.4 AI Prompt 设计

- 包含行业上下文（INDUSTRY_CONTEXTS）
- 包含 OCR 行项目（最多 15 项）
- 明确规则：大宗采购 = 通常可抵扣，纯私人物品 = 不可抵扣
- 混合收据：商业部分可抵扣 + 给出建议
- 返回 JSON：`{deductible, reason, tax_tip}`
- temperature = 0.1, max_tokens = 300

---

## 9. OCR 文档处理管道

> 源文件：`backend/app/services/document_pipeline_orchestrator.py`

### 9.1 管道阶段

```
上传文档
  │
  ▼
Stage 1: OCR + 初始分类
  │ Tesseract/PyMuPDF 提取文本
  │ 正则模式匹配 → 文件名提示 → LLM 分类（风险触发）
  ▼
Stage 2: 数据提取
  │ 专用提取器或 LLM 提取结构化字段
  ▼
Stage 3: 验证 + 自动修正
  │ 负数→绝对值, 缺失日期→今天, 字段交叉验证
  ▼
Stage 4: AI Review Gate
  │ 综合评估 → accept / flag / reject
  │ reject → needs_review=True, 停止
  ▼
Stage 5: 自动创建（置信度门控）
  │ confidence >= threshold → 自动创建记录
  │ confidence < threshold → 跳过自动创建，用户手动确认
```

### 9.2 分类策略（C+ 风险触发）

LLM 分类触发条件（不是所有文档都调 LLM）：
1. 正则结果为 UNKNOWN
2. 正则置信度 < 0.75
3. 检测到冲突关键词信号（同时匹配多种文档类型）
4. 高风险混淆对（receipt↔invoice, lohnzettel↔svs_notice 等）

**融合策略**（优先级制，非置信度比较）：
- 正则 UNKNOWN → 信任 LLM
- 正则 vs LLM 不一致：
  - 正则 >= 0.88 → 保持正则
  - 有冲突信号 + 风险原因 → LLM 覆盖（confidence=0.78）
  - 无冲突信号 → 保持正则，降低置信度 0.05
- 正则 = LLM → 置信度 +0.10（上限 0.95）

### 9.3 自动创建置信度门控（⑧）

| 文档类型 | 阈值 | 说明 |
|----------|------|------|
| `receipt` | 0.75 | 收据 |
| `invoice` | 0.80 | 发票 |
| `payslip` / `lohnzettel` | 0.85 | 工资单 |
| `mietvertrag` | 0.90 | 租赁合同 |
| `e1_form` | 0.90 | E1 税表 |
| `einkommensteuerbescheid` | 0.90 | 所得税评估通知 |
| `kaufvertrag` | 0.95 | 购买合同（高价值） |
| 默认 | 0.80 | 其他类型 |

**门控逻辑**：
```python
if actual_confidence < auto_create_threshold:
    # 记录审计日志
    # return — 跳过整个 auto-create 阶段
    # 用户必须手动确认
```

### 9.4 自动创建的记录类型

| 文档类型 | 自动创建 |
|----------|----------|
| Kaufvertrag | Property（房产）或 Asset（车辆/设备） |
| Mietvertrag | Recurring Income（定期租金收入） |
| Receipt / Invoice | Transaction（交易） |
| Lohnzettel | Transaction（工资交易） |
| E1 Form / Bescheid | 历史数据提取（不创建交易） |

---

## 10. 省税建议系统

> 源文件：`backend/app/services/savings_suggestion_service.py`

### 10.1 双层建议生成

```
用户打开 Dashboard
  │
  ▼
5 项规则检查（并行）：
  ├─ _check_commuting_allowance()    → 通勤补贴
  ├─ _check_home_office_deduction()  → Home Office 抵扣
  ├─ _check_flat_rate_tax()          → 固定比例征税对比
  ├─ _check_family_deductions()      → 家庭抵扣
  └─ _check_svs_deductibility()     → SVS 社保抵扣
  │
  ▼
AI 消费模式分析（④）：
  │ 前提：用户至少有 5 笔交易
  │ 输入：expense_category 分布 + total_income + user_type
  │ 已有建议标题传入 existing_titles 避免重复
  │ LLM 生成最多 3 条个性化建议
  │ 返回 JSON: [{title, description, estimated_savings_eur, action_required}]
  ▼
合并 + 按 potential_savings 降序排序
```

### 10.2 规则检查条件

| 检查项 | 触发条件 | 预估节税计算 |
|--------|----------|-------------|
| 通勤补贴 | distance >= 20km | 补贴金额 × 30% 边际税率 |
| Home Office | employee 或 self_employed | €300 × 30% = €90 |
| 固定比例征税 | self_employed/mixed + eligible | 实际 vs 固定比例差额 |
| 家庭抵扣 | num_children > 0 | 抵扣金额 × 30% |
| SVS 抵扣 | svs_contributions > 0 | 贡献额 × 30% |

### 10.3 AI 建议 Prompt

- 角色：奥地利税务顾问 AI
- 输入：用户类型、税年、支出分类明细、总收入
- 排除已有建议（existing_titles）
- 限制：最多 3 条，必须符合 EStG 2026
- 建议类别标记为 `ai_suggestion`，优先级 = 4（最低）

---

## 11. 知识库管理

> 源文件：`backend/app/tasks/knowledge_update_tasks.py`，`backend/app/services/vector_db_service.py`

### 11.1 向量数据库

- 引擎：ChromaDB（PersistentClient，本地持久化）
- 嵌入模型：`paraphrase-multilingual-MiniLM-L12-v2`（SentenceTransformer）
- 支持多语言（德/英/中）

### 11.2 知识更新流程（⑦）

```
管理员将 .md/.json/.txt 文件放入 knowledge_updates/ 目录
  │
  ▼
POST /admin/knowledge/scan  或  Celery Beat 定时任务
  │
  ▼
scan_and_ingest():
  1. 读取 manifest.json（已摄入文件的 MD5 哈希记录）
  2. 遍历目录中的 .md/.json/.txt 文件
  3. 计算文件 MD5 → 与 manifest 对比
     ├─ 哈希相同 → 跳过
     └─ 哈希不同（新增/更新）→ 处理：
        a. _delete_old_chunks(filename) ← 先删旧 chunk
        b. 解析文件内容
        c. 分块（Markdown/Text: ≤500 词/块）
        d. 生成 embedding → 写入 ChromaDB collection "admin_knowledge_updates"
  4. 更新 manifest.json
```

### 11.3 文件格式

**Markdown/Text**：
- 自动分块，每块最多 500 词
- 语言从文件名推断：`_en` → English, `_zh` → Chinese, 默认 German
- metadata: `{language, source_file, chunk_index, source}`

**JSON**：
```json
[
  {
    "text": "知识内容...",
    "metadata": {"source": "BMF 2026", "category": "...", "language": "de"}
  }
]
```

### 11.4 Chunk ID 生成

```python
id = f"ku_{MD5(f'{filename}:{index}')[:16]}"
```

### 11.5 管理端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/knowledge/scan` | POST | 触发扫描和摄入 |
| `/admin/knowledge/manifest` | GET | 查看已摄入文件清单 |

---

## 12. 意图识别系统

> 源文件：`backend/app/services/ai_orchestrator.py`

### 12.1 双层意图识别

```
用户消息
  │
  ▼
Layer 1: 正则模式匹配 (加权置信度)
  │ 遍历 _INTENT_PATTERNS 中所有意图的正则列表
  │ 每个意图取第一个匹配的模式
  │ 按置信度降序排序（同分时特定意图优先于通用意图）
  │
  ├─ 最高置信度 >= 0.6 → 使用该意图
  │
  └─ 最高置信度 < 0.6 且意图为 TAX_QA（默认）
       │
       ▼
Layer 2: LLM 意图回退 (_llm_intent_fallback)
  │ 缓存 Key = MD5(message[:100].lower().strip())[:16]
  │ 缓存命中 → 返回缓存结果
  │ 缓存未命中 → 调用 LLM (temperature=0, max_tokens=20)
  │ LLM 返回意图名 → 映射到 UserIntent enum
  │ 成功 → confidence=0.80, 存入缓存
  │ 失败/返回 TAX_QA → 不覆盖默认值
```

### 12.2 12 种意图类型

| 意图 | 值 | 路由目标 |
|------|-----|----------|
| `TAX_QA` | `tax_qa` | RAG 问答 |
| `CALCULATE_TAX` | `calculate_tax` | 所得税计算引擎 |
| `CALCULATE_VAT` | `calculate_vat` | 增值税计算器 |
| `CALCULATE_SVS` | `calculate_svs` | SVS 社保计算器 |
| `CALCULATE_KEST` | `calculate_kest` | 资本利得税计算器 |
| `CALCULATE_IMMOEST` | `calculate_immoest` | 房产利得税 → RAG |
| `CLASSIFY_TRANSACTION` | `classify_tx` | 交易分类器 |
| `CHECK_DEDUCTIBILITY` | `check_deduct` | 可抵扣性检查器 |
| `OPTIMIZE_TAX` | `optimize_tax` | 财务摘要 + RAG |
| `WHAT_IF` | `what_if` | 假设模拟（双场景对比） |
| `EXPLAIN_DOCUMENT` | `explain_doc` | RAG 问答 |
| `SUMMARIZE_STATUS` | `summarize_status` | 财务摘要 + RAG |

### 12.3 正则模式设计

- 支持三语（德/英/中）
- CJK 字符不使用 `\b` 词边界（不适用）
- 每个意图 4-8 个模式，权重 0.80-0.95
- 特定意图（VAT/SVS/KESt 等）在同分时优先于通用 CALCULATE_TAX

### 12.4 意图缓存

| 参数 | 值 |
|------|-----|
| 缓存类型 | 内存 Dict |
| Key 生成 | `MD5(message[:100].lower().strip())[:16]` |
| 最大条目数 | 1,000 (`_INTENT_CACHE_MAX_SIZE`) |
| 淘汰策略 | 满时全部清空 (`_intent_cache.clear()`) |
| LLM 回退置信度 | 固定 0.80 |

### 12.5 数值参数提取

计算类意图自动从消息中提取：
- 金额：`€50000`, `50.000€`, `50000 Euro`, `einkommen: 50000` 等
- 支持德式（50.000,50）和英式（50,000.50）数字格式
- 年份：`2024`, `2025`, `2026` 等四位数年份

---

## 13. GDPR 合规

### 13.1 AI 相关数据清理

账户注销时清理的 AI 数据：

| 数据 | 清理方式 | 服务 |
|------|----------|------|
| `UserClassificationRule` | 按 user_id 批量删除 | `account_cancellation_service.py` |
| `ClassificationCorrection` | 按 user_id 批量删除 | `gdpr_service.py` |
| 对话历史 | 按 user_id 删除 | `gdpr_service.py` |
| 文档 + OCR 结果 | 按 user_id 删除 | `gdpr_service.py` |
| 交易数据 | 按 user_id 删除 | `account_cancellation_service.py` |

### 13.2 数据最小化

- LLM 分类缓存 Key 使用 SHA256 哈希，不存储原始描述
- 可抵扣性缓存 Key 同样使用 SHA256 哈希
- 意图缓存 Key 使用 MD5 哈希
- 对话摘要缓存 Key = `{user_id}:{MD5(content)}`
- 所有缓存有 TTL，自动过期

### 13.3 GDPR 考量

- 当前阶段使用 Groq API（数据出境）→ 用户量增长后需评估自托管
- GPT-OSS 自托管模式已预留（GDPR 安全）
- Ollama 本地模式完全不出境
- ChromaDB 本地持久化，知识库数据不含用户个人信息

---

## 14. 治理与可观测性框架

> 源文件：`backend/app/services/governance_metrics.py`，`backend/app/services/user_classification_service.py`，`backend/app/services/classification_learning.py`，`backend/app/api/v1/endpoints/admin.py`

### 14.1 治理指标服务 (GovernanceMetricsService)

提供系统级和用户级的分类治理可观测性指标：

**规则指标 (`get_rule_metrics`)**：
| 指标 | 说明 |
|------|------|
| `total_rules` | 规则总数 |
| `strict_rules` / `soft_rules` | 按类型分布 |
| `frozen_rules` | 已冻结规则数 |
| `strict_rule_ratio` / `soft_rule_ratio` | 类型占比 |
| `total_hits` / `strict_hits` / `soft_hits` | 命中次数统计 |
| `strict_hit_rate` / `soft_hit_rate` | 命中率 |
| `avg_soft_confidence` / `avg_strict_confidence` | 平均置信度 |

**纠正来源指标 (`get_correction_source_metrics`)**：
| 指标 | 说明 |
|------|------|
| `total_corrections` | 纠正记录总数 |
| `by_source` | 按来源分布（human_verified, llm_verified, llm_unverified, llm_consensus, system_default, legacy_null） |
| `trainable_count` / `excluded_count` | 可训练 vs 排除的记录数 |
| `human_verified_ratio` | 人工确认占比 |
| `llm_unverified_exclusion_rate` | LLM 未验证排除率 |

**Soft→Strict 升级计数 (`get_soft_to_strict_upgrade_count`)**：
- 启发式方法：strict 规则且 hit_count > 1 → 可能从 soft 升级而来
- 精确追踪需要审计日志（当前为合理近似）

**综合报告 (`get_full_report`)**：
- 合并 rule_metrics + correction_metrics + upgrade_count
- 支持 `user_id` 参数限定单用户范围

### 14.2 规则生命周期管理

| 操作 | 方法 | 触发条件 | 效果 |
|------|------|---------|------|
| 命中记录 | `record_hit(rule)` | 规则匹配成功 | 更新 `last_hit_at` |
| 冲突记录 | `record_conflict(rule)` | 用户纠正与规则不一致 | `conflict_count += 1`；soft 规则 ≥3 次自动冻结 |
| 置信度衰减 | `decay_stale_soft_rules(stale_days=90)` | 管理员手动触发 | soft 规则超期未命中 → confidence -= 0.10（下限 0.50） |
| 低命中归档 | `archive_low_hit_rules(min_hits=1, stale_days=180)` | 管理员手动触发 | hit_count ≤ 1 且超期未命中 → 删除 |

### 14.3 管理员 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/governance/metrics` | GET | 综合治理指标报告（支持 `user_id` 过滤） |
| `/admin/governance/training-audit` | GET | 训练数据审计报告（来源分布、可训练比例） |
| `/admin/governance/decay-rules` | POST | 触发指定用户的 soft 规则置信度衰减 |
| `/admin/governance/archive-rules` | POST | 触发指定用户的低命中规则归档删除 |

### 14.4 训练数据审计报告

`get_training_audit_report()` 提供训练数据质量的完整视图：

- 按来源统计纠正记录数量和占比
- 明确区分可训练来源（human_verified, llm_consensus, legacy_null）和排除来源（llm_unverified, system_default, llm_verified）
- 计算净可训练比例 (`net_trainable_ratio`)
- 判断是否满足重训练条件 (`ready_to_retrain`)

---

## 15. 前端 AI UI 组件

### 15.1 管理员治理面板 (GovernancePanel)

> 源文件：`frontend/src/components/admin/GovernancePanel.tsx`

集成在 AdminDashboard 的 "AI Governance" 标签页中，展示：

- 规则系统指标：strict/soft/frozen 规则数量、命中率、平均置信度
- 训练数据来源分布：各来源的记录数和占比
- Soft→Strict 升级计数
- 可训练数据比例和重训练就绪状态
- 管理操作按钮：触发规则衰减、触发规则归档

### 15.2 用户分类规则管理页面 (ClassificationRules)

> 源文件：`frontend/src/components/transactions/ClassificationRules.tsx`，`frontend/src/pages/ClassificationRulesPage.tsx`

- 路由：`/classification-rules`
- 侧边栏导航入口（✨ 图标，位于 Reports 和 Advanced 之间）
- 展示用户的所有分类规则列表（按命中次数降序）
- 显示规则类型（strict/soft）、置信度、命中次数、冻结状态
- 支持删除单条规则
- 后端 API：`GET /classification-rules/`，`DELETE /classification-rules/{rule_id}`

### 15.3 交易详情分类管道可视化

> 源文件：`frontend/src/components/transactions/TransactionDetail.tsx`

在交易详情页中，替换了原来的单一分类方法标签，改为可视化的分类管道链：

```
user_rule → rule_based → ml → llm
```

- 当前激活的阶段高亮显示
- 被跳过的阶段显示删除线
- 支持的方法标签：`user_rule`、`user_rule_soft`、`rule_based`、`ml`、`llm`、`llm_verified`、`llm_consensus`
- 三语 i18n 支持（de/en/zh）

### 15.4 AdminDashboard 标签系统

> 源文件：`frontend/src/pages/admin/AdminDashboard.tsx`

- 新增标签切换：Business | AI Governance
- Business 标签：原有的订阅管理、收入分析等
- AI Governance 标签：GovernancePanel 组件

---

## 16. 阈值速查表

### 16.1 交易分类

| 阈值 | 值 | 位置 | 作用 |
|------|-----|------|------|
| HIGH_CONFIDENCE_THRESHOLD | 0.95 | TransactionClassifier | 规则引擎直接采用 |
| LLM_THRESHOLD | 0.90 | TransactionClassifier | 低于此值触发 LLM |
| MIN_LLM_CONFIDENCE | 0.50 | LLMTransactionClassifier | LLM 置信度下限 clamp |
| MAX_LLM_CONFIDENCE | 0.95 | LLMTransactionClassifier | LLM 置信度上限 clamp |
| DEFAULT_CONFIDENCE | 0.75 | LLMTransactionClassifier | LLM 未返回置信度时默认值 |
| MIN_CACHEABLE_CONFIDENCE | 0.60 | LLMTransactionClassifier | 低于此值不缓存/不存储 |

### 16.2 缓存

| 缓存 | TTL | 最大条目 | 后端 |
|------|-----|---------|------|
| LLM 分类缓存 | 7 天 | 10,000 | Redis → 内存降级 |
| 可抵扣性缓存 | 7 天 | 5,000 | 内存 |
| 意图识别缓存 | 无 TTL | 1,000 | 内存（满时清空） |
| 对话摘要缓存 | 无 TTL | 500 | 内存 OrderedDict LRU |

### 16.3 OCR 自动创建

| 文档类型 | 阈值 |
|----------|------|
| receipt | 0.75 |
| invoice | 0.80 |
| payslip / lohnzettel | 0.85 |
| mietvertrag | 0.90 |
| e1_form | 0.90 |
| einkommensteuerbescheid | 0.90 |
| kaufvertrag | 0.95 |
| 默认 | 0.80 |

### 16.4 学习与重训练

| 参数 | 值 |
|------|-----|
| ML 重训练阈值 | 50 条新纠正 |
| ML 最低训练样本 | 10 条 |
| OCR 低准确率标记 | < 80% 且样本 >= 5 |

### 16.5 RAG 与对话

| 参数 | 值 |
|------|-----|
| 最近消息原文 | 6 条 |
| 摘要窗口 | 20 条 |
| 摘要缓存上限 | 500 条 |
| 摘要最大长度 | 200 词 |
| 意图 LLM 回退触发 | 正则置信度 < 0.6 |
| 意图 LLM 回退置信度 | 固定 0.80 |

### 16.6 省税建议

| 参数 | 值 |
|------|-----|
| AI 分析最低交易数 | 5 笔 |
| AI 最大建议数 | 3 条 |
| 边际税率估算 | 30% |

### 16.7 分类风险触发（OCR）

| 条件 | 触发 LLM |
|------|----------|
| 正则结果 = UNKNOWN | 是 |
| 正则置信度 < 0.75 | 是 |
| 冲突关键词 >= 2 个 | 是 |
| 高风险混淆对 | 是 |
| 正则 >= 0.88 且 LLM 不同意 | 保持正则 |
| 正则+LLM 一致 | 置信度 +0.10 |

### 16.8 规则治理

| 参数 | 值 | 说明 |
|------|-----|------|
| Soft 规则初始置信度 | 0.80 | LLM 创建的规则 |
| Soft 规则置信度上限 | 0.80 | 分类时 clamp |
| Soft 规则置信度下限 | 0.50 | 衰减后最低值 |
| 冲突冻结阈值 | 3 次 | soft 规则冲突 ≥3 次自动冻结 |
| 衰减触发天数 | 90 天 | 未命中超过此天数触发衰减 |
| 衰减幅度 | -0.10 | 每次衰减减少的置信度 |
| 归档触发天数 | 180 天 | 未命中超过此天数可归档 |
| 归档命中阈值 | ≤1 次 | hit_count 低于此值可归档 |
| LLM 规则创建阈值 | 0.85 | LLM 置信度 ≥ 此值才创建 soft 规则 |

---

## 附录 A：源文件索引

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| LLM 服务 | `backend/app/services/llm_service.py` | 提供商链管理、限流重试 |
| LLM 分类器 | `backend/app/services/llm_classifier.py` | 交易 LLM 分类 + 缓存 |
| 交易分类器 | `backend/app/services/transaction_classifier.py` | 4级分类管道编排 |
| 规则分类器 | `backend/app/services/rule_based_classifier.py` | 关键词规则匹配 |
| ML 分类器 | `backend/app/services/ml_classifier.py` | scikit-learn RandomForest |
| Per-User 规则服务 | `backend/app/services/user_classification_service.py` | 用户级分类覆盖 + 生命周期管理 |
| Per-User 规则模型 | `backend/app/models/user_classification_rule.py` | 规则数据模型（含 soft/strict、lifecycle 字段） |
| 学习服务 | `backend/app/services/classification_learning.py` | 纠正存储 + 重训练 + 训练审计 |
| 治理指标服务 | `backend/app/services/governance_metrics.py` | 规则/纠正可观测性指标 |
| AI 编排器 | `backend/app/services/ai_orchestrator.py` | 意图识别 + 工具路由 |
| RAG 服务 | `backend/app/services/rag_service.py` | 知识检索 + 对话摘要 |
| 可抵扣检查 | `backend/app/services/deductibility_checker.py` | 规则 + AI 可抵扣判断 |
| 省税建议 | `backend/app/services/savings_suggestion_service.py` | 规则 + AI 省税建议 |
| OCR 管道 | `backend/app/services/document_pipeline_orchestrator.py` | 文档处理全流程 |
| 知识更新 | `backend/app/tasks/knowledge_update_tasks.py` | ChromaDB 知识摄入 |
| 向量数据库 | `backend/app/services/vector_db_service.py` | ChromaDB + SentenceTransformer |
| 管理员 API | `backend/app/api/v1/endpoints/admin.py` | 治理端点、OCR 准确率、知识管理 |
| 分类规则 API | `backend/app/api/v1/endpoints/classification_rules.py` | 用户规则列表/删除端点 |
| 治理面板 UI | `frontend/src/components/admin/GovernancePanel.tsx` | 管理员治理指标展示 |
| 分类规则 UI | `frontend/src/components/transactions/ClassificationRules.tsx` | 用户规则管理界面 |
| 交易详情 UI | `frontend/src/components/transactions/TransactionDetail.tsx` | 分类管道可视化 |

## 附录 B：当前模型策略评估

**当前阶段（早期用户）**：
- 主力模型：Groq `llama-3.3-70b-versatile` — 免费/低成本、速度快、质量足够
- 备用模型：`openai/gpt-oss-120b` via Groq — 更大模型作为降级
- 最终备用：OpenAI `gpt-4o-mini` — 稳定性保障
- 本地备用：Ollama `qwen3:8b` — 完全离线能力

**扩展路线**：
- 0-10,000 用户：Groq API 足够
- 10,000-50,000 用户：混合模式（自托管 + Groq）
- 50,000+ 用户：全自托管（成本 + GDPR 双重驱动）
- GDPR 合规可能比成本更早驱动自托管决策

---

> 本报告基于 2026-03-16 的源代码生成，所有数值均来自代码中的常量定义。
> 如有代码变更，请重新生成此报告。
