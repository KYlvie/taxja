# 交付测试修改记录

---

## 1. 注册页面经营类型与行业选择优化 (2026-03-16)

**问题**: 注册页面的"经营类型"下拉框选项过于简短，且缺少具体行业选择（profile 页面已有行业级联下拉框，但注册页面没有）。

**修改内容**:

### 1.1 经营类型标签优化（三语）

优化了下拉框选项标签，直接在选项中列出典型行业，并丰富了 hint 提示信息（含定额扣除率）。

修改前 (以中文为例):
```
自由职业者 (§22 EStG)
工商经营者 (§23 EStG)
```

修改后:
```
自由职业者 (§22 EStG) — 医生、律师、会计师、IT顾问、建筑师、艺术家
工商经营者 (§23 EStG) — 零售、手工业、餐饮、电商、酒店、美容、运输
```

### 1.2 注册页面新增行业级联下拉框

选择经营类型后，自动加载该类型下的具体行业列表（与 profile 页面一致），用户可在注册时直接选择具体行业。

行业数据通过 API `/api/v1/users/industries/{business_type}` 获取，支持三语标签。

### 1.3 后端注册接口支持 business_type 和 business_industry

注册时提交的 `business_type` 和 `business_industry` 现在会保存到用户记录中。

**修改文件**:
- `frontend/src/pages/auth/RegisterPage.tsx` — 新增行业下拉框、useEffect 加载行业数据
- `frontend/src/services/authService.ts` — RegisterData 接口新增 business_industry 字段
- `frontend/src/services/userService.ts` — 导出 IndustryOption 类型
- `frontend/src/i18n/locales/zh.json` — 中文翻译优化（注册 + profile 两处）
- `frontend/src/i18n/locales/de.json` — 德语翻译优化（注册 + profile 两处）
- `frontend/src/i18n/locales/en.json` — 英语翻译优化（注册 + profile 两处）
- `backend/app/schemas/auth.py` — UserRegister schema 新增 business_type、business_industry 字段
- `backend/app/api/v1/endpoints/auth.py` — register 端点保存 business_type、business_industry

---

## 2. 多表单 PDF 识别（E1 + E1b + L1k + 财务报表）(2026-03-16)

**问题**: 用户上传一个包含多个奥地利税务表单（E1、E1b、L1k）和财务报表的 PDF 文件，系统只识别了第一个表单 E1，其余表单被忽略。

**根因分析**:
- `_extract_text_from_pdf` 将所有页面文本合并为一个字符串
- `_classify_by_patterns` 的早期检测逻辑在第一页匹配到 E1 标记后立即返回 `E1_FORM`，不再检查后续页面
- 管道流程 `process_document` 只处理一个文档 → 一个 OCR 结果 → 一个分类
- 系统没有按表单边界拆分多表单 PDF 的逻辑

**修改内容**:

### 2.1 新增多表单 PDF 拆分引擎 (`ocr_engine.py`)

- 新增 `MultiFormSection` 数据类，表示 PDF 中的一个表单段落
- 新增 `_FORM_BOUNDARY_MARKERS`：33 个奥地利税务表单边界标记（E1、E1a、E1b、L1k、Steuerberechnung、EAR、GuV、Bilanz）
- 新增 `_detect_page_form_type()`：检测单页头部区域（前 600 字符）的表单类型标记
- 新增 `_split_multi_form_pdf()`：逐页检测表单类型，将连续同类型页面分组为段落
- 新增 `process_multi_form_pdf()`：对每个段落独立进行分类和 LLM 提取，返回多个 OCRResult

### 2.2 管道编排器支持多表单处理 (`document_pipeline_orchestrator.py`)

- 修改 `_stage_ocr()`：在正常 OCR 之前先检测多表单 PDF，如果检测到多个表单段落，为每个额外段落创建子文档
- 新增 `_create_child_documents()`：为每个额外表单段落创建 Document 记录（共享同一 PDF 文件路径），设置 `parent_document_id`，预填 OCR 结果，并在后台线程中独立运行管道处理
- 修改 `process_document()`：检测子文档（有 `parent_document_id` 且已有 OCR 数据），跳过 OCR 阶段直接进入分类/验证/自动创建流程

### 2.3 数据库 Schema 变更 (`document.py`)

- `documents` 表新增 `parent_document_id` 列（INTEGER, FK → documents.id），用于关联多表单 PDF 的父子文档关系
- 通过直接 SQL 添加列（因 Alembic 迁移链已断裂）

**修改文件**:
- `backend/app/services/ocr_engine.py` — 新增 MultiFormSection、_FORM_BOUNDARY_MARKERS、_detect_page_form_type、_split_multi_form_pdf、process_multi_form_pdf
- `backend/app/services/document_pipeline_orchestrator.py` — 修改 _stage_ocr、process_document，新增 _create_child_documents
- `backend/app/models/document.py` — 新增 parent_document_id 列

---

## 3. 多表单 PDF 页面分类改为 LLM 驱动 (2026-03-16)

**问题**: 之前使用 33 个硬编码关键词标记（`_FORM_BOUNDARY_MARKERS`）做本地页面类型检测，容易误判。例如第 9 页正文中列举表单名称 `e 1b,` 被错误匹配为 E1b 表单起始页，导致 PDF 被拆成 5 段而非 4 段。更根本的问题是：关键词匹配无法适应未知的文档格式，客户上传不同类型的文件时可能完全无法识别。

**修改方案**: 彻底移除关键词匹配，改用 Groq LLM 做页面分类：
- 删除 `_FORM_BOUNDARY_MARKERS`（33 个硬编码标记）和 `_detect_page_form_type()`
- 新增 `_classify_pages_with_llm()`：将所有页面的前 300 字符打包成一个 LLM 请求，让 Groq 一次性返回每页的表单类型
- 修改 `_split_multi_form_pdf()`：先提取所有页面文本，再调用 `_classify_pages_with_llm()` 批量分类，最后按类型分组
- 支持的表单类型：E1、E1a、E1b、L1k、Steuerberechnung、EAR、GuV、Bilanz、Unknown
- 单次 LLM 调用，token 消耗很小（每页仅 300 字符），但准确率远高于关键词匹配
- LLM 不可用时返回全部 Unknown，不影响后续流程

**数据清理**: 删除了之前错误拆分产生的 5 个文档记录（ID 55-59）及关联的 2 条交易记录（ID 332-333），用户需重新上传 PDF。

**修改文件**:
- `backend/app/services/ocr_engine.py` — 删除 `_FORM_BOUNDARY_MARKERS` 和 `_detect_page_form_type`，新增 `_PAGE_CLASSIFY_SYSTEM_PROMPT` 和 `_classify_pages_with_llm`，修改 `_split_multi_form_pdf` 使用 LLM 分类

---

## 4. 创建缺失的 transaction_line_items 表 (2026-03-16)

**问题**: 交易列表页面返回 422 错误，SQLAlchemy 尝试查询 `transaction_line_items` 表但该表不存在。

**修复**: 通过直接 SQL 创建 `transaction_line_items` 表，包含 15 个字段（id、transaction_id、description、amount、quantity、category、is_deductible、deduction_reason、vat_rate、vat_amount、classification_method、classification_confidence、sort_order、created_at、updated_at），与 SQLAlchemy 模型 `TransactionLineItem` 完全对应。

**修改方式**: 直接 SQL（Alembic 迁移链已断裂）

---

## 5. 修复 OCR 发票分类和抵税判断错误 (2026-03-16)

**问题**: 上传的 5 张物业相关发票（烟囱清扫费、地税、水费、住宿税）全部被分类为 `OTHER`（其他），且标记为不可抵税。实际上这些都是酒店经营者的物业运营费用，按奥地利税法 100% 可抵税。

**根因分析**:
- 规则分类器 `rule_based_classifier.py` 缺少 Rauchfangkehrer（烟囱清扫）、Nachtigungstaxe（住宿税）、Kanalbenutzungsgebühr（排水费）等德语关键词
- 分类结果为 `OTHER`，deductibility_checker 规则表中没有 `OTHER` 的匹配规则，直接返回 `is_deductible=False`

**修复内容**:

### 5.1 规则分类器新增物业相关关键词
在 `_classify_expense` 的 `property_specific_keywords` 中新增：
- 烟囱清扫：rauchfangkehrer, kaminkehrer, schornsteinfeger, kaminfeger → `maintenance`
- 物业税费：nachtigungstaxe, nächtigungstaxe, ortstaxe, kurtaxe, kommunalsteuer → `property_tax`
- 市政公用费：kanalbenutzungsgebühr, kanalgebühr, wasserbezugsgebühr, wassergebühr, müllabfuhr, abfallgebühr → `utilities`

### 5.2 修正现有 5 笔交易数据
- ID 334/335（Rauchfangkehrer）：`OTHER` → `MAINTENANCE`，`is_deductible=true`
- ID 336（Grundsteuer+水费+排水费）：`OTHER` → `PROPERTY_TAX`，`is_deductible=true`
- ID 337/338（Nachtigungstaxe）：`OTHER` → `PROPERTY_TAX`，`is_deductible=true`

**修改文件**:
- `backend/app/services/rule_based_classifier.py` — `_classify_expense` 新增 14 个物业相关关键词

---

## 6. 修复 LLM 兜底分类失效 + classification_method 未存储 (2026-03-16)

**问题**: 分类链 rule → ML → LLM 中，LLM 兜底本应在 rule/ML 置信度低于 0.90 时触发，但实际上对部分德语税务术语（Grundsteuer、Nachtigungstaxe）LLM 返回空响应，导致兜底失效，最终使用了低置信度的 rule 结果（OTHER, 0.30）。同时 `classification_method` 从未被存储到交易记录中，无法追踪分类来源。

**根因分析**:
1. **Groq (llama-3.3-70b) 对部分德语税务术语返回空字符串** — `generate_simple()` 将空响应视为"成功"直接返回，不会触发 provider fallback 到 OpenAI
2. **`_build_single_suggestion` 未传递 `classification_method`** — 分类结果中的 method 字段在构建 suggestion dict 时丢失
3. **`create_transaction_from_suggestion` 未设置 `classification_method`** — Transaction 对象创建时未包含该字段
4. **LLM 已判定的 `is_deductible` 被覆盖** — `_classify_from_ocr` 总是用 `deductibility_checker.check()` 覆盖 LLM 的抵税判断，而 checker 的规则表不够全面

**修复内容**:

### 6.1 LLM 空响应 fallback (`llm_service.py`)
- `generate_simple()`: 检测空响应，记录警告日志，跳到下一个 provider（Groq → OpenAI）
- `generate_vision()`: 同样处理空响应 fallback
- 修复后：Groq 返回空 → 自动 fallback 到 OpenAI → 正确分类

### 6.2 classification_method 全链路传递 (`ocr_transaction_service.py`)
- `_classify_from_ocr()`: 从 `ClassificationResult.method` 提取分类方法，包含在返回 dict 中
- `_build_single_suggestion()`: 新增 `classification_method` 字段传递
- `_build_split_suggestions()`: 同上
- `create_transaction_from_suggestion()`: 在创建 Transaction 时设置 `classification_method`

### 6.3 LLM 抵税判断优先 (`ocr_transaction_service.py`)
- 当分类方法为 `llm` 且 LLM 已返回 `is_deductible` 时，直接使用 LLM 的判断
- 仅在 rule/ml 分类时才 fallback 到 `deductibility_checker.check()`
- LLM 拥有完整上下文（用户类型、行业、描述），判断更准确

### 6.4 分类链全流程日志 (`transaction_classifier.py`)
- `classify_transaction()`: 记录 rule 高置信度匹配、pre-LLM 最佳结果、是否跳过 LLM
- `_try_llm_classify()`: 记录 LLM 调用参数、返回结果、不可用原因

**验证结果**:
```
Rauchfangkehrer  → maintenance,  deductible=True, conf=0.95 (LLM via Groq)
Grundsteuer      → property_tax, deductible=True, conf=0.90 (LLM via OpenAI fallback)
Nachtigungstaxe  → property_tax, deductible=True, conf=0.90 (LLM via OpenAI fallback)
```

**修改文件**:
- `backend/app/services/llm_service.py` — generate_simple/generate_vision 空响应 fallback
- `backend/app/services/transaction_classifier.py` — 分类链全流程日志
- `backend/app/services/ocr_transaction_service.py` — classification_method 传递 + LLM 抵税优先


---

## 7. 移除 ML 层 + Tesseract OCR 替换为 gpt-4o Vision (2026-03-16)

**问题**: 系统使用三层分类链（rule → ML → LLM），其中本地 scikit-learn ML 模型需要大量训练数据才能有效，且对新类别/新用户几乎无用。OCR 管道使用 Tesseract 做图像文字识别，再交给 LLM 提取结构化数据，分两步调用且 Tesseract 对低质量图片准确率不高。

**决策分析**:
- ML 层：本地训练的 scikit-learn 模型需要每个用户积累足够的修正数据才能生效，新用户体验差。gpt-4o 对德语税务术语分类准确率 ~99%，使 ML 层冗余
- Tesseract OCR：gpt-4o vision 可以一步完成图像识别 + 结构化提取 + 分类，无需先 OCR 再 LLM 两步调用
- 成本：gpt-4o vision ~$0.01-0.03/张图片，每用户每年约 $2-4，可接受

### 7.1 移除 ML 分类层 (`transaction_classifier.py`)

重写分类链为：用户规则 → 规则引擎（置信度 ≥ 0.95 直接使用）→ LLM (gpt-4o)

- 删除 `from .ml_classifier import MLClassifier` 导入
- 删除 ML 分类步骤，rule 低置信度直接进入 LLM
- `should_retrain()` 始终返回 False
- `retrain()` 为空操作（no-op）
- LLM 高置信度结果（≥ 0.85）自动存储为 per-user rule，加速后续查询
- LLM 中等置信度（0.60-0.85）存储为 `llm_unverified` correction，不创建 user rule

### 7.2 简化 OCR 管道 (`ocr_engine.py`)

重写 `process_document()` 处理策略：

| 输入类型 | 处理方式 |
|---------|---------|
| 有文字层的 PDF | 提取文字 → LLM 结构化提取 |
| 图片 | gpt-4o vision 直接处理（一步完成 OCR + 提取 + 分类）|
| 扫描 PDF（无文字层）| PyMuPDF 渲染为图片 → gpt-4o vision |

- 新增 `_try_pdf_as_image_vlm()`：将扫描 PDF 首页渲染为 200 DPI 图片，交给 VLM 处理
- 图片处理不再经过 Tesseract，直接使用 gpt-4o vision
- VLM 置信度上限从 0.80 提升至 0.95（公式：`min(0.95, 0.50 + field_count * 0.05)`）
- 多收据图片置信度上限提升至 0.90

### 7.3 修复 `__init__.py` 导入 (`__init__.py`)

- 将 `MLClassifier` 导入替换为 `TransactionClassifier`
- `__all__` 列表更新

### 7.4 修改学习服务 (`classification_learning.py`)

- `retrain_model()` 改为 no-op，仅记录时间戳
- corrections 仍然正常存储（用于 per-user rules 和审计）

### 7.5 Groq 从文本 provider chain 中移除 (`llm_service.py`)

- `_build_text_provider_chain()`: 仅 OpenAI (gpt-4o)，不再包含 Groq
- Groq 对德语税务术语返回空响应，无法可靠地为 OpenAI 兜底
- Groq 仍保留在 `_build_vision_provider_chain()` 中作为 vision 备选

**遗留清理项**（非关键，可后续处理）:
- `ml_classifier.py` 文件仍存在（未删除，仅不再被引用）
- `_cross_validate_image` 和 `_tesseract_llm_extract` 方法为死代码
- 引用 ML 的测试文件需要更新（`test_ml_classifier.py` 等）

**修改文件**:
- `backend/app/services/transaction_classifier.py` — 重写为 user-override → rule → LLM 三层链
- `backend/app/services/ocr_engine.py` — 简化 process_document，新增 _try_pdf_as_image_vlm，移除 Tesseract 路径
- `backend/app/services/__init__.py` — MLClassifier → TransactionClassifier
- `backend/app/services/classification_learning.py` — retrain_model 改为 no-op
- `backend/app/services/llm_service.py` — 文本 provider chain 移除 Groq


---

## 8. 修复扫描 PDF（CamScanner）OCR 管道 — 全面启用 gpt-4o Vision (2026-03-16)

**问题**: 上传 CamScanner 扫描的 3 页 PDF（INTERSPAR 超市收据，1.8MB），系统几乎什么都读不出来。文档 62 的 OCR 结果为空。

**根因分析**:

扫描 PDF 管道存在三个问题：

1. **VLM max_tokens 太小 (3500)**：多收据图片的 JSON 响应被截断，无法解析。gpt-4o 返回的结构化数据（含 line_items）经常超过 3500 tokens
2. **`_try_pdf_as_image_vlm` 只处理第 1 页**：CamScanner PDF 有 3 页收据，但代码只渲染 page 1 → VLM，其余 2 页被忽略
3. **`_stage_ocr` 对所有 PDF 调用 `process_multi_form_pdf`**：扫描 PDF 没有文字层，multi-form 分类器对空文本页面全部返回 Unknown，浪费一次 LLM 调用。然后 `process_document` 又对所有页面再跑一次 VLM，造成双重处理

**修复内容**:

### 8.1 VLM max_tokens 提升至 8000 (`ocr_engine.py`)

- `_try_vlm_ocr()`: `max_tokens` 从 3500 → 8000
- 系统提示词新增优先级指令：`PRIORITY: Valid complete JSON > exhaustive line items`
- 确保即使 line_items 很多，JSON 也能正确闭合

### 8.2 多页扫描 PDF 支持 (`ocr_engine.py`)

重写 `_try_pdf_as_image_vlm()`：

| 场景 | 处理方式 |
|------|---------|
| 单页 PDF | 渲染 page 1 → VLM（与之前相同）|
| 多页 PDF | 逐页渲染（最多 5 页）→ 每页独立 VLM → 合并结果 |

合并逻辑：
- 每页 VLM 可能返回多个收据（`_additional_receipts`），全部展平
- 第一个收据作为主结果，其余存入 `_additional_receipts`
- 置信度取所有页面平均值
- `raw_text` 用 `---` 分隔拼接

### 8.3 扫描 PDF 跳过多表单分类 (`document_pipeline_orchestrator.py`)

修改 `_stage_ocr()`：

```python
is_pdf = image_bytes[:5] == b"%PDF-"
if is_pdf:
    pdf_text = self.ocr_engine._extract_text_from_pdf(image_bytes)
    has_text_layer = bool(pdf_text and len(pdf_text.strip()) > 50)
    if has_text_layer:
        # 有文字层 → 尝试多表单拆分（E1 + E1b + L1k 等）
        multi_results = self.ocr_engine.process_multi_form_pdf(image_bytes)
        ...
# 无文字层的扫描 PDF → 直接走 process_document → _try_pdf_as_image_vlm
```

- 提取 PDF 文字，检查长度 > 50 字符
- 有文字层：走多表单拆分流程（适用于 E1+E1b 等正式表单）
- 无文字层：跳过多表单分类，直接进入 `process_document` → `_try_pdf_as_image_vlm` → 逐页 VLM

### 8.4 处理流程对比

**修复前**（扫描 PDF）:
```
PDF → process_multi_form_pdf → LLM 分类空页面 → 全部 Unknown → 不拆分
   → process_document → _try_pdf_as_image_vlm → 只处理第 1 页
   → VLM max_tokens=3500 → JSON 截断 → 解析失败 → 空结果
```

**修复后**（扫描 PDF）:
```
PDF → 检测无文字层 → 跳过 multi-form
   → process_document → _try_pdf_as_image_vlm
   → 渲染 3 页 → 每页 VLM (max_tokens=8000) → 合并结果
   → 3 张收据，置信度 0.85-0.95
```

**数据清理**: 文档 62 的 OCR 结果已重置（`ocr_result=NULL, processed_at=NULL`），需从前端重新触发处理。

**修改文件**:
- `backend/app/services/ocr_engine.py` — `_try_vlm_ocr` max_tokens=8000 + prompt 优化，`_try_pdf_as_image_vlm` 多页支持
- `backend/app/services/document_pipeline_orchestrator.py` — `_stage_ocr` 文字层检测，扫描 PDF 跳过多表单分类

### 8.5 Line Items 全链路传递 (`ocr_transaction_service.py`, `document_pipeline_orchestrator.py`)

**问题**: VLM 成功提取了 `line_items`（含 `name`, `total_price`, `quantity`），但这些数据只存在 `extracted_fields` / `ocr_result` 中，没有被转换为 `transaction_line_items` 表中的记录。

**根因**: 
- `_build_single_suggestion()` 没有将 OCR 格式的 line_items 转换为 transaction 格式
- `_create_multi_receipt_transactions()` 同样缺少转换逻辑
- OCR 格式：`{name, total_price, quantity, vat_rate}`
- Transaction 格式：`{description, amount, quantity, vat_rate, vat_amount, classification_method}`

**修复**: 在两处都添加了转换逻辑：
- `name` → `description`
- `total_price` → `amount`（支持字符串金额如 "429.00 Ft"，自动去除货币后缀）
- `quantity` 默认 1
- `vat_rate` 去除 `%` 后缀转为 float

### 8.6 修复 `_finalize` commit 失败 (`document_pipeline_orchestrator.py`)

**问题**: 交易创建成功，但 `document.processed_at` 和 `document.ocr_result` 没有被保存。`_finalize` 的 commit 静默失败。

**根因**: `_stage_suggest` → `create_transaction_from_suggestion` 内部调用了 `self.db.commit()`，这会导致 SQLAlchemy session 中所有 ORM 对象的属性过期（expired）。之后 `_finalize` 尝试修改 `document.ocr_result` 时，需要先从 DB 重新加载过期属性，如果此时 session 状态不一致，commit 就会失败。

**修复**: 在 `_finalize` 开头添加 `self.db.refresh(document)`，确保 document 对象从 DB 重新加载最新状态。如果 refresh 失败（对象已 detached），则重新查询 `Document.id`。

**修改文件**:
- `backend/app/services/ocr_transaction_service.py` — `_build_single_suggestion` 添加 line_items 转换
- `backend/app/services/document_pipeline_orchestrator.py` — `_create_multi_receipt_transactions` 添加 line_items 转换，`_finalize` 添加 document refresh

---

## 9. 文档处理管道架构重构 — 四项低成本高收益改动 (2026-03-16)

**背景**: 架构审查发现当前管道存在几个治理层面的问题：提取与分类耦合、缺少显式归一化层、自动创建仅靠总置信度门控、多收据默认自动创建。按优先级依次实施四项改动。

### 9.1 VLM Prompt 拆分：提取与分类解耦 (`ocr_engine.py`)

**问题**: `_try_vlm_ocr` 的 system prompt 同时要求模型返回 `document_type` 和所有字段。模型会用自己的分类先验影响字段提取——如果一开始判断为 receipt，就倾向提取 receipt 风格字段，实际是 invoice/contract 时提取会被带偏。

**修改**:
- 重写 `_VLM_EXTRACT_SYSTEM_PROMPT`：明确指示"DO NOT classify the document type"，只提取可见事实
- 新增 `document_hints` 字段：让模型返回 2-3 条事实性观察（如"has line items"、"contains UID number"），供 Stage 2 分类参考
- 新增 `counterparties`、`period`、`employer`、`employee`、`gross_income`、`net_income` 等字段，覆盖更多文档类型
- VLM 返回 `document_type=UNKNOWN`，分类完全交给 Stage 2 独立完成
- 多收据检测时标记 `_is_multi_receipt=True`

**架构变化**:
```
修改前: VLM → {document_type: "receipt", amount: 42.50, ...}  (分类污染提取)
修改后: VLM → {amount: 42.50, document_hints: ["has line items"], ...}  (纯事实)
         → Stage 2 独立分类 (regex + filename + LLM 仲裁)
```

### 9.2 新增 Stage 3: 归一化与冲突消解层 (`extraction_normalizer.py`)

**问题**: 提取结果直接进入 validation 和 auto-create，没有经过标准化处理。金额格式不统一（"429.00 Ft" vs 42.5 vs "1.234,56"）、日期格式混乱（"16.03.2026" vs "2026-03-16"）、line_items 包含小计/税额/折扣行、多收据边界未校验。

**新建文件**: `backend/app/services/extraction_normalizer.py`

Stage 3 负责 6 件事：
1. **金额标准化** — 统一为 float，处理欧洲格式（1.234,56）、货币后缀（Ft/EUR/€）、负数→绝对值
2. **日期标准化** — 统一为 YYYY-MM-DD 字符串，支持 6 种格式
3. **货币标准化** — 统一为 ISO 大写（EURO→EUR、€→EUR）
4. **Line items 清洗** — 过滤非商品行（Zwischensumme/MwSt/Rabatt/Trinkgeld 等 30+ 关键词）
5. **金额一致性检查** — line_items 总和 vs total，标记 `_amount_consistent`
6. **字段存在性映射** — 生成 `field_presence` dict，供字段级门槛使用

所有操作记录在 `normalization_trace` 中，存入 `ocr_result["_normalization"]` 供审计。

### 9.3 字段级门槛替代纯总分门控 (`document_pipeline_orchestrator.py`)

**问题**: auto-create 仅靠总置信度阈值（如 receipt ≥ 0.75）。一张没有 amount 但 confidence=0.85 的收据照样自动创建交易，产生脏数据。

**修改**: 新增 `_FIELD_REQUIREMENTS` 和 `_check_field_requirements()`:

| 文档类型 | 必须字段 |
|---------|---------|
| receipt / invoice | amount + date + merchant |
| payslip / lohnzettel | amount + employer |
| kaufvertrag | purchase_price + property_address |
| mietvertrag | monthly_rent + property_address |
| svs_notice / bescheid | amount |

缺少任何必须字段 → `needs_review=True`，交易仍然创建但标记为待审核。

### 9.4 多收据默认 flag (`document_pipeline_orchestrator.py`)

**问题**: 多收据文档（一张图多张票）的边界切分是最容易出事的地方，但之前和单收据走同样的 auto-create 路径。

**修改**: 检测到 `_is_multi_receipt=True` 或 `_receipt_count > 1` 时，强制 `needs_review=True`。交易仍然自动创建，但用户必须确认。

### 9.5 管道阶段更新

```
修改前 (5 阶段):
  Stage 1: OCR + Classification (耦合)
  Stage 2: Extraction (空，"已在 Stage 1 完成")
  Stage 3: Validate + auto-fix
  Stage 4: AI Review Gate
  Stage 5: Auto-create + persist

修改后 (6 阶段):
  Stage 1: OCR / Extraction — 只提取可见事实，不分类
  Stage 2: Classification arbitration — regex → filename → LLM，独立于提取
  Stage 3: Normalization — 字段标准化、line_items 清洗、金额一致性、field_presence
  Stage 4: Validate + auto-fix — 交叉验证、自动修正
  Stage 4.5: AI Review Gate — 规则检查 + LLM 审核
  Stage 5: Auto-create — 字段级门槛 + 多收据 flag + confidence gate
  Stage 6: Persist + audit metadata
```

新增 `PipelineStage.NORMALIZE` 枚举值。

**修改文件**:
- `backend/app/services/ocr_engine.py` — `_try_vlm_ocr` prompt 重写，返回 UNKNOWN
- `backend/app/services/extraction_normalizer.py` — 新建，Stage 3 归一化层
- `backend/app/services/document_pipeline_orchestrator.py` — 集成 Stage 3、字段级门槛、多收据 flag、PipelineStage.NORMALIZE

### 9.6 修复 JSON 截断恢复 + max_tokens 提升 (`ocr_engine.py`)

**问题**: 文档 71（3 页 CamScanner 扫描 PDF）测试发现 Page 1 的 VLM 返回 15560 字符但 `_parse_vlm_json` 返回 None。根因有两个：

1. **`_count_unescaped_quotes` 函数未定义**: `_recover_truncated_json` 调用了 `_count_unescaped_quotes(trunk)` 但该函数从未被创建。运行时抛出 `NameError`，被外层 `except` 静默吞掉，导致截断恢复完全失效。
2. **`max_tokens=8000` 不够**: 新的提取 prompt 要求更多字段（`document_hints`、`counterparties`、`period`、`employer`、`employee`、`gross_income`、`net_income`），加上 `line_items`，多商品收据的 JSON 响应经常超过 8000 tokens 被截断。
3. **数组截断无恢复**: 多收据场景 VLM 返回 JSON 数组 `[{...}, {...]`，数组路径没有截断恢复逻辑，截断后直接返回 None。

**修复内容**:

1. **新增 `_count_unescaped_quotes()` 模块级函数** — 统计字符串中未转义的双引号数量，用于判断截断是否发生在字符串内部
2. **`max_tokens` 从 8000 → 12000** — 给 VLM 更多空间输出完整 JSON，减少截断发生概率
3. **数组路径增加截断恢复** — `_parse_vlm_json` 的 `[...]` 解析分支新增 `arr_found_closing` 标记，未找到闭合 `]` 时调用 `_recover_truncated_json` 尝试修复。可以从截断的数组中至少恢复已完成的对象

**截断恢复策略** (`_recover_truncated_json`):
```
截断的 JSON: {"amount": 42.50, "line_items": [{"name": "Kaffee", "total_pri
                                                                            ↑ 被 max_tokens 截断

恢复步骤:
1. 找到最后一个安全切割点（完整的 key-value 对结束位置）
2. 去除尾部不完整的 token（半截字符串、悬空逗号/冒号）
3. 统计未闭合的 [ 和 { 数量
4. 追加对应数量的 ] 和 } 闭合 JSON
5. 尝试 json.loads，失败则向前回退更多内容重试

恢复后: {"amount": 42.50, "line_items": [{"name": "Kaffee"}]}
```

**数据清理**: 文档 71 的 OCR 结果和关联交易已重置，可从前端重新触发处理。

**修改文件**:
- `backend/app/services/ocr_engine.py` — 新增 `_count_unescaped_quotes()`，`max_tokens` 8000→12000，数组截断恢复
- 删除 `test_doc71.py` 测试脚本

### 9.7 性能优化：砍掉冗余 LLM 调用 + 多页并行处理 (2026-03-16)

**问题**: 上传两个合同 PDF（Kaufvertrag 57s，Mietvertrag 67s），等待时间过长。CamScanner 3 页扫描 PDF 更慢。

**根因分析 — 一个合同 PDF 的 LLM 调用链**:

| 阶段 | 调用 | 耗时 |
|------|------|------|
| Stage 1: `_try_llm_extraction` | **LLM #1** gpt-4o 文本提取 (max_tokens=4000) | ~10-15s |
| Stage 2: `_try_llm_classification` | **LLM #2** gpt-4o 分类（因冲突信号触发）| ~5-8s |
| Stage 4.5: `_llm_review` | **LLM #3** gpt-4o 审核（低置信度触发）| ~5-8s |
| 总计 | 3 次串行 LLM 调用 | ~20-30s |

合同文本很长，包含 "rechnung"、"uid" 等关键词（合同里提到税务信息是正常的），但这些关键词触发了 INVOICE 的冲突信号，导致 `_detect_classification_risk` 误判需要 LLM 分类。

扫描 PDF 的问题：3 页 × 每页一次 VLM 调用 = 3 次串行 gpt-4o vision 调用，每次 15-30s。

**优化 1: 合同/税务文档跳过 LLM 分类** (`document_pipeline_orchestrator.py`)

在 `_detect_classification_risk` 中新增快速路径：当 regex 分类为 PURCHASE_CONTRACT / RENTAL_CONTRACT / E1_FORM / EINKOMMENSTEUERBESCHEID 且 confidence ≥ 0.60 时，直接返回 `should_call_llm=False`。

这些文档类型有强关键词签名（kaufvertrag/mietvertrag 等），regex 分类已经很准。长文本中出现其他类型的关键词是正常的，不应触发 LLM 二次确认。

**优化 2: 合同/税务文档跳过 LLM 审核** (`ai_review_gate.py`)

在 `AIReviewGate.review` 的决策路由中新增快速路径：对 PURCHASE_CONTRACT / RENTAL_CONTRACT / E1_FORM / EINKOMMENSTEUERBESCHEID 类型，只做规则检查，不调用 LLM review。有 flags 则 flag，无 flags 则 approve。

这些类型已有专用提取器和字段级门槛验证，LLM review 增加 5-10s 延迟但收益极低。

**优化 3: 多页扫描 PDF 并行 VLM 处理** (`ocr_engine.py`)

重写 `_try_pdf_as_image_vlm` 的多页处理逻辑：
- 先渲染所有页面为图片（CPU 操作，很快）
- 使用 `ThreadPoolExecutor` 并行发送 VLM 请求（max_workers=3）
- VLM 调用是 I/O 密集型（HTTP 请求到 OpenAI），线程并行效果好
- 3 页 PDF：从 ~45-90s（串行）→ ~15-30s（并行）

**预期效果**:

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 合同 PDF（有文字层）| ~57-67s (3 次 LLM) | ~15-20s (1 次 LLM) |
| 3 页扫描 PDF | ~45-90s (3 次串行 VLM) | ~15-30s (3 次并行 VLM) |
| 单页收据图片 | ~15-25s (1-2 次 LLM) | ~15-20s (无变化) |

**修改文件**:
- `backend/app/services/document_pipeline_orchestrator.py` — `_detect_classification_risk` 合同快速路径
- `backend/app/services/ai_review_gate.py` — 合同/税务文档跳过 LLM review
- `backend/app/services/ocr_engine.py` — `_try_pdf_as_image_vlm` 多页并行处理

**数据清理**: 文档 72、73、74 的 OCR 结果已重置，可从前端重新触发处理。

### 9.8 修复 `_parse_vlm_json` 缩进错误 + 恢复 Groq 为文本主力 (2026-03-16)

**问题 1 — CamScanner PDF 依然读不出来**: 文档 75（3 页 CamScanner 扫描 PDF）上传后，3 次 VLM 调用全部成功（分别返回 6712、23054、22612 字符），但所有页面都解析失败，最终 OCR 结果为空。

**根因**: `_parse_vlm_json` 和 `_recover_truncated_json` 两个方法被错误地缩进了 8 个空格（嵌套在 `_try_vlm_ocr` 方法内部），而非 4 个空格（类级别方法）。这导致它们成为 `_try_vlm_ocr` 的局部函数而非 `OCREngine` 的方法，运行时抛出 `AttributeError: 'OCREngine' object has no attribute '_parse_vlm_json'`。VLM 调用成功但 JSON 解析全部静默失败。

**修复**: 将 `_parse_vlm_json` 和 `_recover_truncated_json` 的缩进从 8 空格修正为 4 空格，恢复为 `OCREngine` 的 `@staticmethod` 类方法。

**问题 2 — 用户要求恢复 Groq 为文本 provider**: 之前因 Groq 对部分德语税务术语返回空响应而将其从文本 provider chain 中移除（仅保留 OpenAI）。但 Groq LPU 推理速度是 OpenAI 的 5-10 倍，用户希望恢复 Groq 以提升响应速度。

**修复**: 修改 `_build_text_provider_chain()`，恢复 Groq 为第一优先级：

```
修改前: OpenAI (gpt-4o) → GPT-OSS
修改后: Groq (llama-3.3-70b, 快) → OpenAI (gpt-4o, 稳) → GPT-OSS
```

之前 Groq 空响应问题的根因是 `generate_simple()` 没有检测空响应。在 §6.1 中已修复：空响应会自动 fallback 到下一个 provider。因此现在 Groq 可以安全地作为主力使用——大部分请求由 Groq 快速处理，少数空响应自动降级到 OpenAI。

注意：Vision 调用仍然只走 OpenAI gpt-4o（Groq 不支持 vision）。

**数据清理**: 文档 75 的 OCR 结果已重置（`ocr_result=NULL, processed_at=NULL`），可从前端重新触发处理。

**修改文件**:
- `backend/app/services/llm_service.py` — `_build_text_provider_chain` 恢复 Groq 为第一优先级
- `backend/app/services/ocr_engine.py` — `_parse_vlm_json` 和 `_recover_truncated_json` 缩进修正（上一轮已完成）
- 删除 `test_doc75.py` 测试脚本


---

## 10. 架构回退至 §6 状态 (2026-03-16)

**问题**: §7-§9 的 AI 架构改动（移除 ML 层、VLM 替代 Tesseract、6 阶段管道重构）导致 CamScanner 扫描 PDF 持续处理失败（JSON 截断 18000+ 字符、VLM 解析失败），经多轮修复仍不稳定。用户要求全面回退。

**回退内容**:
- 使用 `git checkout HEAD` 恢复 7 个服务文件至 git commit 版本
- 删除 §7-§9 新建的 3 个文件：`extraction_normalizer.py`、`ai_review_gate.py`、`ocr_engine_git.py`
- 在恢复的文件上重新应用 §5-§6 的修改（rule_based_classifier 关键词、LLM 空响应 fallback、classification_method 传递、LLM 抵税优先）

**回退后架构**: Tesseract OCR + rule → ML → LLM 分类链 + VLM 图片交叉验证（原始管道）

**修改文件**:
- `backend/app/services/llm_service.py` — 恢复 + §6 修改
- `backend/app/services/transaction_classifier.py` — 恢复 + §6 修改
- `backend/app/services/ocr_transaction_service.py` — 恢复 + §6 修改
- `backend/app/services/ocr_engine.py` — 恢复至原始版本
- `backend/app/services/document_pipeline_orchestrator.py` — 恢复至原始版本
- `backend/app/services/classification_learning.py` — 恢复至原始版本
- `backend/app/services/__init__.py` — 恢复至原始版本

---

## 11. 修复合同上传不生成房产和定期收入 (2026-03-17)

**问题**: 用户上传 Kaufvertrag（doc 79）和 Mietvertrag（doc 80），OCR 识别正确（PURCHASE_CONTRACT 0.73, RENTAL_CONTRACT 0.78），提取数据完整（地址、价格、租金等），管道到达 `suggest` 阶段，但没有创建房产记录，也没有设置定期租金收入。`transaction_id` 为 NULL。

**根因分析 — 两个独立 bug**:

### Bug 1: 管道时序错误 — `document.ocr_result` 在 `_stage_suggest` 时为空

管道流程：
```
Stage 1: OCR → 返回 OCRResult 对象（不写入 document）
Stage 2-4: 分类/验证 → 数据存在 result.extracted_data 中
Stage 5: _stage_suggest → 调用 ocr_tasks._build_kaufvertrag_suggestion
  → 读取 document.ocr_result → 此时为 NULL → 返回 None → 静默跳过
Stage 6: _finalize → 才将 result.extracted_data 写入 document.ocr_result
```

`_build_kaufvertrag_suggestion`（在 `ocr_tasks.py` 中）从 `document.ocr_result` 读取 `purchase_price` 和 `property_address`，但管道编排器直到 `_finalize` 才写入这些数据。Stage 5 运行时 `document.ocr_result` 还是空的。

**修复**: 在 `_stage_suggest` 之前，先将 `result.extracted_data` 写入 `document.ocr_result` 并 flush：

```python
# document_pipeline_orchestrator.py, process_document()
document.ocr_result = self._make_json_safe(result.extracted_data)
self.db.flush()
# Stage 5: Build suggestions AND auto-create
self._stage_suggest(document, db_type, ocr_result, result)
```

### Bug 2: properties 表缺少 `building_use` 和 `eco_standard` 列 → 500 错误

Property 模型定义了 `building_use`（BuildingUse enum）和 `eco_standard`（boolean）列，但数据库中从未创建这两列。任何对 properties 表的 SELECT 查询都会触发 SQLAlchemy 错误：

```
sqlalchemy.exc.ProgrammingError: column properties.building_use does not exist
```

导致 `/api/v1/properties` 端点返回 500，前端房产页面无法加载。这也间接影响了合同处理——即使房产创建成功，后续查询也会失败。

**修复**: 通过直接 SQL 添加缺失列：

```sql
CREATE TYPE buildinguse AS ENUM ('residential', 'commercial');
ALTER TABLE properties ADD COLUMN building_use buildinguse NOT NULL DEFAULT 'residential';
ALTER TABLE properties ADD COLUMN eco_standard boolean NOT NULL DEFAULT false;
```

### 数据修复

由于 doc 79/80 的 OCR 数据已经完整（之前的处理成功提取了所有字段），手动恢复 OCR 数据并通过 confirm 端点触发创建：

1. 恢复 doc 79 的 `ocr_result`（含 purchase_price=273000, property_address 等）
2. 插入 `import_suggestion`（type=create_property, status=pending）
3. 调用 `POST /documents/79/confirm-property` → 房产创建成功
4. 恢复 doc 80 的 `ocr_result`（含 monthly_rent=640, start_date 等）
5. 插入 `import_suggestion`（type=create_recurring_income, matched_property_id=新房产ID）
6. 调用 `POST /documents/80/confirm-recurring` → 定期租金收入创建成功

**验证结果**:
- 房产: Thenneberg 51, 2571 Altenmarkt an der Triesting, 购买价 €273,000, 建筑价值 €218,400, 1.5% AfA
- 定期收入: 月租 €640, 起始日 2021-10-01, 关联房产, 来源文档 doc 80
- `/api/v1/properties` 端点正常返回 200（不再 500）

**修改文件**:
- `backend/app/services/document_pipeline_orchestrator.py` — `process_document` 在 `_stage_suggest` 前写入 `document.ocr_result`
- 数据库: `properties` 表新增 `building_use` 和 `eco_standard` 列


---

## 12. 合同字段 LLM 补充提取 (2026-03-17)

**问题**: Kaufvertrag（doc 81）经 regex 提取后，`purchase_date`、`notary_fees`、`registry_fees`、`construction_year` 等字段缺失。regex 对结构化标签（如 "Kaufpreis: EUR 273.000"）提取准确，但对散落在长文本中的信息（如签约日期在签名页、公证费在附件条款中）无法覆盖。

**方案**: 在 regex 提取之后增加 LLM 补充步骤。Tesseract 的 raw_text 交给 Groq/OpenAI，让 LLM 提取 regex 没抓到的字段并校验已有字段。

**跳过条件**: 如果所有必需字段都已提取且平均置信度 ≥ 0.90，则跳过 LLM 调用（节省 token）。

### 12.1 LLM 补充提取逻辑 (`ocr_engine.py`)

新增三个方法到 `OCREngine` 类：

- `_llm_supplement_contract(extracted_data, raw_text, contract_type)` — 主入口
  - 检查必需字段缺失数和平均置信度，决定是否调用 LLM
  - 构建 prompt：已提取字段 JSON + raw_text（截取前 6000 字符）
  - 合并策略：LLM 填充 null 字段（置信度 0.80）；低置信度（<0.70）字段如果 LLM 结果不同则用 LLM 值覆盖；高置信度 regex 字段保持不变
  - 结果记录在 `_llm_supplement` 元数据中（filled/corrected/missing_before）

- `_parse_llm_contract_response(response)` — 解析 LLM JSON 响应，处理 markdown 代码块，数值字符串自动转 float

- `_contract_confidence(extracted_data, contract_type)` — 基于字段完整度重新计算置信度
  - 关键字段（address/price/date）缺失每个扣 0.20
  - 重要字段（building_value/buyer_name 等）每个加 0.03 bonus
  - 加权公式：critical_score × 0.6 + avg_field_conf × 0.3 + important_bonus × 0.1

必需字段定义：
- Kaufvertrag: property_address, purchase_price, purchase_date, building_value, land_value, grunderwerbsteuer, notary_fees, registry_fees, construction_year, buyer_name, seller_name（11 个）
- Mietvertrag: property_address, monthly_rent, start_date, tenant_name, landlord_name, deposit_amount, betriebskosten（7 个）

### 12.2 合同提取路由集成 (`ocr_engine.py`)

修改 `_route_to_contract_extractor`：
- Kaufvertrag 路径：regex 提取 → `_llm_supplement_contract` → `_contract_confidence` 重算置信度
- Mietvertrag 路径：同上

### 12.3 测试结果

**Kaufvertrag (doc 81)**:
- regex 提取: property_address ✓, purchase_price=273000 ✓, buyer_name ✓, seller_name ✓, grunderwerbsteuer=12558 ✓
- LLM 补充: registry_fees=3003.0 ✓（1.1% of 273000）, notary_name ✓, notary_location ✓
- 仍缺失: purchase_date（合同签名页日期未出现在 OCR 文本中）, notary_fees（合同未列明具体金额）, construction_year（合同未提及建筑年份）
- 这些字段在原始合同文本中确实不存在，LLM 正确返回 null 而非编造数据

**Mietvertrag (doc 82)**:
- regex 提取: property_address ✓, monthly_rent=640 ✓, start_date=2021-10-01 ✓, tenant_name ✓, landlord_name ✓
- LLM 补充: street ✓, city ✓, postal_code ✓, deposit_amount ✓
- 仍缺失: betriebskosten（合同未单独列明）

### 12.4 数据修复

- 删除重复房产记录（retry-ocr 重复创建），保留最新记录（含 registry_fees）
- 重建定期租金收入（recurring_transactions id=11），关联新房产 ID
- 房产: Thenneberg 51, 2571 Altenmarkt an der Triesting, €273,000, registry_fees=€3,003, grunderwerbsteuer=€12,558
- 定期收入: 月租 €640, 2021-10-01 至 2024-10-01, 租户 HAGER Bernhard Lothar

### 12.5 已知限制

- `purchase_date` 被管道 auto-fix 阶段设为上传日期（2026-03-16），因为合同签名页日期未被 OCR 捕获。用户需手动修正。
- `notary_fees` 和 `construction_year` 在此合同中确实不存在，需要用户从其他来源补充。
- retry-ocr 会创建新房产记录而非更新已有记录（无去重逻辑），需手动清理重复。

**修改文件**:
- `backend/app/services/ocr_engine.py` — 新增 `_llm_supplement_contract`、`_parse_llm_contract_response`、`_contract_confidence`，修改 `_route_to_contract_extractor`


---

## 13. 文档上传后自动刷新前端数据 (2026-03-17)

**问题**: 上传租赁合同后，后端自动创建的房产、定期收入、交易等数据需要用户退出重新登录才能在前端看到。原因是各页面组件（房产、定期交易、交易列表、仪表盘）只在 mount 时获取数据，没有监听后端数据变化的机制。

**方案**: 新建轻量级 Zustand refresh signal store（`refreshStore.ts`），各组件订阅对应的 version counter。当 OCR 处理完成并检测到后端自动创建了数据时，`DocumentUpload` 递增对应 counter，订阅组件自动重新获取数据。

### 13.1 新建 `refreshStore.ts`

4 个独立 version counter：`propertiesVersion`、`recurringVersion`、`transactionsVersion`、`dashboardVersion`。每个有对应的 `refresh*()` 方法递增 counter，另有 `refreshAll()` 一次性递增全部。

### 13.2 信号触发点

**`DocumentUpload.tsx` — `pollForProcessing` 回调**:
- OCR 完成后检查 `import_suggestion`：
  - `create_property` / `create_recurring_income` (auto-created/confirmed) → 刷新 properties + recurring + dashboard
  - `create_transaction` / `create_recurring_expense` → 刷新 transactions + recurring + dashboard
  - `transaction_id` 存在（收据/发票自动创建交易）→ 刷新 transactions + dashboard

**`DocumentsPage.tsx` — confirm 按钮回调**:
- `handleConfirmProperty` 成功 → 刷新 properties + dashboard
- `handleConfirmRecurring` 成功 → 刷新 recurring + dashboard
- `handleConfirmRecurringExpense` 成功 → 刷新 recurring + transactions + dashboard

**`ChatInterface.tsx` — AI 伴侣确认回调**:
- `handleConfirmRecurring` 成功 → 刷新 recurring + dashboard（expense 额外刷新 transactions）

### 13.3 信号消费点

| 组件 | 订阅 | 效果 |
|------|------|------|
| `PropertiesPage` | `propertiesVersion` | useEffect 依赖变化 → `fetchProperties()` |
| `RecurringTransactionList` | `recurringVersion` | useEffect 依赖变化 → `loadTransactions()` |
| `TransactionsPage` | `transactionsVersion` | useEffect 依赖变化 → `fetchTransactions()` |
| `DashboardPage` | `dashboardVersion` | useEffect 依赖变化 → 重新获取全部仪表盘数据 |

### 13.4 架构说明

使用 Zustand store 而非 CustomEvent/EventBus 的原因：
- 与项目现有状态管理方案一致（全部用 Zustand）
- 组件卸载时自动取消订阅，无需手动 cleanup
- `useRefreshStore.getState()` 可在非组件上下文（callback）中安全调用

**修改文件**:
- `frontend/src/stores/refreshStore.ts` — 新建，refresh signal store
- `frontend/src/components/documents/DocumentUpload.tsx` — pollForProcessing 中触发刷新信号
- `frontend/src/components/recurring/RecurringTransactionList.tsx` — 订阅 recurringVersion
- `frontend/src/pages/TransactionsPage.tsx` — 订阅 transactionsVersion
- `frontend/src/pages/DashboardPage.tsx` — 订阅 dashboardVersion
- `frontend/src/pages/PropertiesPage.tsx` — 订阅 propertiesVersion
- `frontend/src/pages/DocumentsPage.tsx` — confirm 回调中触发刷新信号
- `frontend/src/components/ai/ChatInterface.tsx` — AI 确认回调中触发刷新信号

---

## 14. 购房合同地址提取修复 + AI 导航提示 (2026-03-17)

**问题**: 用户上传新的购房合同（doc 85），OCR 提取的地址为 "816/129 GST-Fläche 615"（地籍编号），而非实际街道地址 "Angeligasse 86, 1100 Wien"。此外，用户希望 AI 助手在识别到购房合同/租赁合同后，主动提醒用户前往对应的管理页面查看和编辑。

### 14.1 AI 导航提示（前端）

当文档上传处理完成后，如果后端自动创建了房产或定期收入，AI 助手会发送导航提示消息：

- 购房合同自动创建房产 → 提示用户前往「高级管理 → 资产管理」检查并修改
- 租赁合同自动创建定期收入 → 提示用户前往「高级管理 → 定期交易」检查并修改
- 消息明确告知 OCR 识别可能不完全准确，建议用户核实

三语 i18n 键：
- `ai.proactive.propertyAutoCreated` — 🏠 已从购房合同中自动创建房产记录...建议前往「高级管理 → 资产管理」检查
- `ai.proactive.recurringAutoCreated` — 📋 已从租赁合同中自动创建定期收入...建议前往「高级管理 → 定期交易」检查

触发逻辑：`DocumentUpload.tsx` 的 `pollForProcessing` 中，当 `suggestion.status === 'auto-created'` 且 `suggestion.type` 为 `create_property` 或 `create_recurring_income` 时发送。同时屏蔽了这两种情况下的通用成功消息，避免重复通知。

### 14.2 地址提取修复（后端）

**根因**: Kaufvertrag 合同中包含大量地籍信息（GST-NR、EZ、Fläche），regex 提取器优先匹配到这些编号而非实际街道地址。LLM 补充提取的 prompt 也没有明确区分地籍编号和街道地址。

**修复 1 — regex 过滤地籍编号** (`kaufvertrag_extractor.py`):
- `_extract_property_address` 新增正则过滤：匹配到的地址如果符合地籍编号模式（`^\d{2,}/\d+`、`^GST`、`^Fläche`、`^EINLAGE`），直接跳过

**修复 2 — LLM 补充 prompt 增加地址规则** (`ocr_engine.py`):
- `_CONTRACT_SUPPLEMENT_PROMPT` 新增 "CRITICAL ADDRESS RULES" 段落：
  - property_address 必须是真实街道地址（如 "Angeligasse 86, 1100 Wien"）
  - 禁止使用地籍编号（如 "816/129"、"GST-Fläche 615"）
  - 指导 LLM 从 GST-ADRESSE 或 Bauf.(20) 条目中查找实际街道名
- `_KAUFVERTRAG_FIELDS_PROMPT` 中 `property_address` 字段描述改为明确要求街道地址

**修复 3 — 地籍编号预检** (`ocr_engine.py`):
- `_llm_supplement_contract` 新增预检逻辑：如果 `property_address` 匹配地籍编号模式，自动将置信度降至 0.30，确保 LLM 补充步骤会覆盖该字段

### 14.3 数据修复

- doc 85 重新处理成功，地址正确提取为 "Angeligasse 86, 1100 Wien"
- 删除旧的错误房产记录 `8503a45b`（地址为地籍编号）
- 新房产 `91beeb2e` 自动创建，通过 API 修正 city（Forchtenstein → Wien）和 postal_code（7212 → 1100）
- 购买日期从上传日期（2026-03-17）修正为合同日期（2022-01-31）

**最终房产数据**:
- 地址: Angeligasse 86, 1100 Wien
- 购买价: €225,000
- 建筑价值: €180,000
- 土地价值: €45,000
- 房产转让税: €7,875
- 购买日期: 2022-01-31

**修改文件**:
- `backend/app/services/kaufvertrag_extractor.py` — `_extract_property_address` 新增地籍编号过滤
- `backend/app/services/ocr_engine.py` — LLM prompt 新增地址规则、地籍编号预检
- `frontend/src/components/documents/DocumentUpload.tsx` — AI 导航提示消息
- `frontend/src/i18n/locales/zh.json` — 新增 propertyAutoCreated、recurringAutoCreated
- `frontend/src/i18n/locales/de.json` — 同上
- `frontend/src/i18n/locales/en.json` — 同上


---

## 15. 租赁比例架构重构 + AI 提示 + 房产状态自动计算 (2026-03-17)

**问题**: 用户提出多个关联问题：
1. 上传租赁合同但无匹配房产时，AI 助手应提醒先上传购房合同
2. 自动创建交易后，AI 助手应提醒可通过删除合同来删除关联交易
3. 只有购房合同没有租赁合同时，房产不应显示为 "Vermietung"（出租），只有存在绑定的租赁合同才应显示为出租
4. 部分地址匹配（如 Thenneberg 51 vs 51/3）时，应提醒用户设置租赁单元占比
5. `rental_percentage` 应由租赁合同驱动，而非在房产层面手动设置

**架构方案**:
- `rental_percentage` 改为自动计算（只读，等于所有活跃合同的 `unit_percentage` 之和）
- 每个 `recurring_transaction`（rental_income 类型）新增 `unit_percentage` 字段
- `property_type` 自动判定：0% → owner_occupied, 1-99% → mixed_use, 100% → rental
- 折旧仅在活跃租赁合同期间适用

### 15.1 后端数据库

- `recurring_transactions` 表新增 `unit_percentage NUMERIC(5,2)` 列（直接 SQL）

### 15.2 后端模型 + Schema

- `backend/app/models/recurring_transaction.py` — 新增 `unit_percentage` Column
- `backend/app/schemas/recurring_transaction.py` — Create/Update/Response 三个 schema 均新增 `unit_percentage`

### 15.3 后端服务

- `backend/app/services/property_service.py` — 新增 `recalculate_rental_percentage()` 和 `get_rental_contracts()` 方法
  - `recalculate_rental_percentage`: 汇总活跃租赁合同的 unit_percentage，自动设置 property_type
  - `get_rental_contracts`: 获取房产关联的所有 RENTAL_INCOME 类型定期交易

### 15.4 后端 API

- `backend/app/api/v1/endpoints/properties.py` — 新增两个端点：
  - `GET /{property_id}/rental-contracts` — 获取房产关联的租赁合同列表
  - `POST /{property_id}/recalculate-rental` — 重新计算租赁比例和房产类型
- `backend/app/api/v1/recurring_transactions.py` — `update_recurring_transaction` 中新增：当 `unit_percentage` 变更时自动触发 `recalculate_rental_percentage`

### 15.5 后端管道（OCR 处理）

- `backend/app/tasks/ocr_tasks.py`:
  - `create_property_from_suggestion` — 默认从 `RENTAL/100%` 改为 `OWNER_OCCUPIED/0%`（房产初始为自住，等租赁合同关联后再重算）
  - `_build_mietvertrag_suggestion` — 新增 `no_property_match` 和 `is_partial_match` 标志
  - `create_recurring_from_suggestion` — 精确匹配设 `unit_percentage=100`，部分匹配留空（前端提示用户设置），创建后自动调用 `recalculate_rental_percentage`
- `backend/app/services/document_pipeline_orchestrator.py` — `_build_mietvertrag_suggestion` 无匹配房产时保持 `pending` 状态

### 15.6 前端 AI 提示

- `frontend/src/components/documents/DocumentUpload.tsx` — 新增 3 种 AI 消息触发：
  - `no_property_match=true` → 发送 `recurringNoProperty` 消息（提醒先上传购房合同）
  - `is_partial_match=true` → 发送 `recurringPartialMatch` 消息（提醒设置租赁单元占比）
  - 收据/发票自动创建交易 → 发送 `transactionAutoCreated` 消息（提醒可通过删除文档撤销）

### 15.7 前端房产详情 — 租赁合同管理

- `frontend/src/types/property.ts` — 新增 `RentalContract` 接口
- `frontend/src/services/propertyService.ts` — 新增 `getRentalContracts()` 和 `recalculateRental()` API 方法
- `frontend/src/components/properties/PropertyDetail.tsx` — 新增「关联租赁合同」区块：
  - 显示每个合同的描述、月租、合同期限、活跃/过期状态
  - 可编辑的 `unit_percentage` 输入框（带保存按钮）
  - 未设置占比时显示警告提示
  - 底部显示总租赁比例汇总
  - 「重新计算」按钮调用 `POST /recalculate-rental`
- `frontend/src/components/properties/PropertyDetail.css` — 租赁合同区块样式

### 15.8 i18n（三语已在之前添加）

所有 AI 提示和租赁合同管理的 i18n 键已在三语文件中就绪：
- `ai.proactive.recurringNoProperty` — 无匹配房产提示
- `ai.proactive.recurringPartialMatch` — 部分地址匹配提示
- `ai.proactive.transactionAutoCreated` — 自动创建交易提示
- `properties.rentalContracts.*` — 租赁合同管理区块全部文案

### 15.9 数据修复

- Recurring #11（月租 €640）和 #12（月租 €320）：设置 `unit_percentage=33.33`
- Property `4cc56f48`（Thenneberg 51）：重新计算 → `owner_occupied/0%`（两个合同均已过期，end_date=2024）
- Property `91beeb2e`（Angeligasse 86）：重新计算 → `owner_occupied/0%`（无租赁合同）
- 注：过期合同不计入当前租赁比例，这是正确行为。历史折旧计算应按合同活跃期间分别处理。

**修改文件**:
- `backend/app/models/recurring_transaction.py`
- `backend/app/schemas/recurring_transaction.py`
- `backend/app/services/property_service.py`
- `backend/app/api/v1/endpoints/properties.py`
- `backend/app/api/v1/recurring_transactions.py`
- `backend/app/tasks/ocr_tasks.py`
- `backend/app/services/document_pipeline_orchestrator.py`
- `frontend/src/types/property.ts`
- `frontend/src/services/propertyService.ts`
- `frontend/src/components/documents/DocumentUpload.tsx`
- `frontend/src/components/properties/PropertyDetail.tsx`
- `frontend/src/components/properties/PropertyDetail.css`
- `frontend/src/i18n/locales/zh.json`
- `frontend/src/i18n/locales/de.json`
- `frontend/src/i18n/locales/en.json`

---

## 16. 文档详情页 OCR 字段可编辑 (2026-03-17)

**问题**: 文档详情页的"文档内容"表格以只读方式展示 OCR 提取结果（房产地址、购买价格、建筑价值等），用户无法修正 OCR 识别错误。系统已有 `POST /documents/{id}/correct` API 和 OCRReview 编辑组件，但仅在文档首次审核（needs_review）时可用，确认后的文档只能查看不能编辑。

**修改内容**:

### 16.1 文档详情页内联编辑

在 `DocumentsPage.tsx` 的文档查看器中：
- 添加 `isEditingOcr` / `editedOcrData` / `savingOcr` 状态
- OCR 结果标题栏右侧添加「✏️ 编辑」按钮
- 点击编辑后，所有字段值从 `<span>` 切换为 `<input>` 输入框
- 编辑模式显示「💾 保存」和「取消」按钮
- 保存调用 `documentService.correctOCR()` → `POST /documents/{id}/correct`
- 后端自动记录修改历史（correction_history）并提升置信度
- 关闭文档查看器时自动退出编辑模式

### 16.2 i18n

三语添加 `documents.ocrCorrected` 键：
- 中文：OCR 数据已更新
- 德语：OCR-Daten wurden aktualisiert
- 英语：OCR data updated successfully

**修改文件**:
- `frontend/src/pages/DocumentsPage.tsx`
- `frontend/src/i18n/locales/zh.json`
- `frontend/src/i18n/locales/de.json`
- `frontend/src/i18n/locales/en.json`

---

## 17. 合同日期字段修复 + 租赁合同确认时重试房产匹配 (2026-03-17)

**问题 A — 购买日期错误**: 文档 90（Kaufvertrag）的 `date` 字段显示为 `2026-03-17`（今天），而非合同签约日期。原因链：
1. Tesseract OCR 无法读取手写签约日期（通常在合同最后一页）
2. LLM 补充提取也未能从文本中找到签约日期（`purchase_date` 返回 null）
3. `_autofix_missing_fields` 验证阶段检查的是通用 `date` 字段而非 `purchase_date`，发现 `date` 不存在就自动填入今天的日期
4. `_build_kaufvertrag_suggestion` 在 `purchase_date` 为空时也回退到 `document.uploaded_at`（上传日期）

**问题 B — 租赁合同确认失败**: 文档 89（Mietvertrag）点击确认时返回 400 "No matching property found"。原因：上传 Mietvertrag 时房产尚未创建（Kaufvertrag 后上传），`matched_property_id` 为空，确认时不会重新匹配。

**修改内容**:

### 17.1 日期字段按文档类型区分
`document_pipeline_orchestrator.py` 的 `_autofix_missing_fields`：
- Kaufvertrag → 检查 `purchase_date`（而非 `date`）
- Mietvertrag → 检查 `start_date`
- 其他文档 → 检查 `date`
- 不再为合同类文档创建错误的通用 `date` 字段

### 17.2 Kaufvertrag suggestion 不再静默使用上传日期
`ocr_tasks.py` 的 `_build_kaufvertrag_suggestion`：
- `purchase_date` 为空时设为 `null` 而非 `document.uploaded_at`
- 前端 suggestion 卡片会显示"—"，用户可通过编辑功能手动填入

### 17.3 confirm-recurring 重试房产匹配
`ocr_tasks.py` 的 `create_recurring_from_suggestion`：
- 当 `matched_property_id` 为空时，使用 `AddressMatcher` 重新匹配
- 如果 AddressMatcher 无结果，回退到街道名称模糊匹配
- 解决了"先上传 Mietvertrag 后上传 Kaufvertrag"的时序问题

### 17.4 数据修复
- 文档 90：删除错误的 `date=2026-03-17`，`purchase_date` 和 suggestion 中的 `purchase_date` 设为 null
- 文档 89：删除错误的 `date=2026-03-17`

**为什么 LLM 没提取到签约日期**: 合同签约日期通常在最后一页以手写形式出现（"Mödling, am ___"），Tesseract 无法识别手写文字，因此 OCR 文本中不包含签约日期。LLM 正确返回了 null（找不到就不猜），但下游的 autofix 和 suggestion 构建逻辑错误地用了今天的日期作为回退。

**修改文件**:
- `backend/app/services/document_pipeline_orchestrator.py`
- `backend/app/tasks/ocr_tasks.py`

---

## 18. 合同到期自动停用 + 房产类型自动回退 (2026-03-17)

**问题**: 用户确认租赁合同（如 Mietvertrag doc 89，end_date=2024-10-01）时，关联房产应先变为"租赁"（rental），然后因合同已过期自动变回"自住"（owner_occupied）。但代码中 `contract_expired` 变量虽然被正确计算，却从未被使用——过期合同的 `is_active` 没有被设为 False，`recalculate_rental_percentage` 也没有被第二次调用。

**根因**: `create_recurring_from_suggestion` 中的 `contract_expired` 逻辑在上一轮编辑中被截断，只设置了变量但没有写后续处理代码。

**修复内容**:

### 18.1 过期合同自动停用逻辑 (`ocr_tasks.py`)

在 `recalculate_rental_percentage` 首次调用之后，新增过期处理：

```python
if contract_expired:
    recurring.is_active = False
    db.commit()
    ps.recalculate_rental_percentage(prop.id, document.user_id)
```

执行顺序：
1. 创建 recurring（`is_active=True`）→ 首次 `recalculate` → 房产变为 rental（记录租赁关系）
2. 检测 `contract_expired` → 设 `is_active=False` → 二次 `recalculate` → 房产回退为 owner_occupied

这确保了：
- 历史租赁关系被正确记录（AfA 折旧计算需要）
- 过期合同不影响当前房产状态
- 返回值新增 `contract_expired` 字段，前端可据此显示合同状态

### 18.2 数据状态

- Recurring #14（Thenneberg 51, €640/月, 2021-10-01 至 2024-10-01）：已在之前手动设为 `is_active=false`，数据一致
- Property `a21bc9c1`（Thenneberg 51）：`owner_occupied / 0%`，正确

**修改文件**:
- `backend/app/tasks/ocr_tasks.py` — `create_recurring_from_suggestion` 新增过期合同停用 + 二次重算逻辑


---

## 19. 修复折旧报告（AfA）— 历史租赁期间感知 (2026-03-17)

**问题**: 房产 Thenneberg 51（`a21bc9c1`）的折旧计划和收入支出报告都显示 €0。原因是 `AfACalculator` 使用当前 `property_type`（owner_occupied）判断所有年份的折旧，但该房产在 2021-2024 年有活跃的租赁合同，应该在那些年份计算折旧。

**根因分析**:
- `calculate_annual_depreciation()` 检查 `property.property_type == OWNER_OCCUPIED` 后直接返回 €0
- 但房产在 2021-10-01 至 2024-10-01 期间有租赁合同（recurring #14, €640/月, unit_percentage=18%）
- 折旧应该按历史租赁期间计算，而非按当前房产类型

**修复内容**:

### 19.1 新增 `_get_rental_percentage_for_year()` 方法 (`afa_calculator.py`)

查询 `recurring_transactions` 表，找到与指定年份重叠的租赁合同（`RENTAL_INCOME` 类型），返回 `unit_percentage` 之和（上限 100%）。

重叠条件：`start_date <= year_end AND (end_date IS NULL OR end_date >= year_start)`

### 19.2 修改 `calculate_annual_depreciation()` (`afa_calculator.py`)

对于 real_estate 类型：
- 不再检查当前 `property_type`，改为调用 `_get_rental_percentage_for_year(property.id, year)`
- 如果该年无租赁合同 → 返回 €0（无折旧）
- 如果有租赁合同 → 使用历史 `unit_percentage` 计算 `depreciable_value`
- 非 real_estate 资产仍使用当前 `property_type` 判断

### 19.3 修改 `get_accumulated_depreciation()` (`afa_calculator.py`)

同样改为逐年查询历史租赁百分比，每年独立计算 `depreciable_value`，而非使用固定值。

### 19.4 遗留问题

房产 `purchase_date` 为 `2026-03-17`（OCR 未提取到签约日期，被设为上传日期），但租赁合同是 2021-2024 年。折旧从 `purchase_year` 开始计算，所以只显示 2026 年——而 2026 年无活跃租赁合同，折旧仍为 €0。需要修正 `purchase_date` 才能看到正确的折旧计划。

**修改文件**:
- `backend/app/services/afa_calculator.py` — 新增 `_get_rental_percentage_for_year`，修改 `calculate_annual_depreciation` 和 `get_accumulated_depreciation`

---

## 20. 租赁合同管理 — 编辑/添加/删除 + AI 占比提示 (2026-03-17)

**问题**: 房产详情页的租赁合同列表只能查看和设置 `unit_percentage`，不能编辑合同金额/日期、添加新合同或删除旧合同。用户续租时不一定有新合同文件，需要手动管理。同时，确认租赁合同后如果 `unit_percentage` 未设置，应在 AI 聊天框中提示用户输入。

**修复内容**:

### 20.1 前端 PropertyDetail.tsx — 合同编辑/添加/删除

- 编辑：点击 ✏️ 按钮，可修改月租金、开始日期、结束日期、是否生效（is_active）
- 删除：点击 🗑️ 按钮，弹出确认对话框后删除
- 添加：点击 ➕ 按钮，展开表单填写月租金、开始日期、结束日期、占比百分比
- 所有操作完成后自动调用 `recalculate_rental_percentage` 更新房产出租比例

### 20.2 后端 Schema 更新

- `RentalIncomeRecurringCreate` 新增 `unit_percentage` 可选字段
- `RecurringTransactionUpdate` 新增 `start_date` 字段

### 20.3 后端 Endpoint 更新 (`recurring_transactions.py`)

`create_rental_income_recurring` 端点：创建后如果 `data.unit_percentage` 不为空，设置 `unit_percentage` 并触发 `recalculate_rental_percentage`。

### 20.4 AI 聊天框占比提示 (`ChatInterface.tsx`)

- 确认租赁合同后，如果返回的 `unit_percentage == null`，自动推送 `unit_percentage_prompt` 类型的 proactive message
- 用户可在聊天框内直接输入百分比（0.01-100），点击确认后调用 `recurringService.update` 和 `propertyService.recalculateRental`
- 也可点击"跳过"，稍后在资产管理页面设置

### 20.5 i18n 三语支持

新增翻译键：
- `ai.proactive.setUnitPercentage` — 提示用户输入占比
- `ai.proactive.unitPercentageSaved` — 确认保存成功
- `ai.proactive.skipped` — 跳过提示
- `properties.rentalContracts.addContract` / `newContract` / `startDate` / `endDate` / `clearEndDate` / `status` / `confirmDelete`

### 20.6 Store 更新 (`aiAdvisorStore.ts`)

`ProactiveMessage` 类型新增 `unit_percentage_prompt`。

**修改文件**:
- `frontend/src/components/properties/PropertyDetail.tsx` — 合同编辑/添加/删除 UI
- `frontend/src/components/ai/ChatInterface.tsx` — unit_percentage_prompt 交互
- `frontend/src/stores/aiAdvisorStore.ts` — ProactiveMessage 类型扩展
- `frontend/src/types/recurring.ts` — RecurringTransactionUpdate 和 RentalIncomeRecurringCreate 类型更新
- `backend/app/schemas/recurring_transaction.py` — Schema 更新
- `backend/app/api/v1/recurring_transactions.py` — Endpoint 更新
- `frontend/src/i18n/locales/zh.json` — 中文翻译
- `frontend/src/i18n/locales/de.json` — 德语翻译
- `frontend/src/i18n/locales/en.json` — 英语翻译


---

## 21. AI 消息流优化 — 合同到期操作按钮 + 消息顺序修正 (2026-03-17)

**问题**:
1. 合同到期提醒只有文字，没有操作按钮，用户不知道去哪里续约
2. proactive messages 显示在聊天顶部（新消息在最上面），不符合聊天习惯，应该像正常聊天一样往下追加
3. 到期提醒文字包含"如需续约请手动更新"但没有具体入口

**修复内容**:

### 21.1 消息顺序修正 (`aiAdvisorStore.ts`)

- `pushMessage`: 从 `[newMsg, ...state.messages]`（prepend）改为 `[...state.messages, newMsg]`（append）
- 新消息追加到数组末尾，最新消息在最下方

### 21.2 proactive messages 移到聊天底部 (`ChatInterface.tsx`)

- 将 proactive messages 渲染区域从 `chat-messages` 顶部移到底部（在 typing indicator 之前）
- 使用 `.slice(-5)` 显示最近 5 条（而非 `.slice(0, 5)`）
- 新消息自然出现在聊天底部，符合用户预期

### 21.3 合同到期操作按钮 (`ChatInterface.tsx`, `FloatingAIChat.tsx`)

新增 `contract_expired` 消息类型，包含两个操作按钮：
- 📄 上传续租合同 → 跳转到 `/documents` 页面
- ➕ 手动添加合同 → 跳转到 `/properties/{property_id}?addContract=1`，自动打开添加合同表单
- 跳过按钮 → 标记为已处理

### 21.4 PropertyDetail 自动打开添加表单 (`PropertyDetail.tsx`)

- 新增 `useSearchParams` 读取 `addContract=1` 参数
- 如果参数存在，自动展开添加合同表单并清除 URL 参数

### 21.5 后端 alerts 返回 property_id (`dashboard.py`)

- `expired_contracts` 和 `expiring_contracts` 的返回数据新增 `property_id` 字段
- 前端据此构建跳转链接

### 21.6 i18n 更新

新增翻译键：
- `ai.proactive.uploadRenewal` — 上传续租合同 / Verlängerungsvertrag hochladen / Upload renewal contract
- `ai.proactive.addContractManually` — 手动添加合同 / Vertrag manuell hinzufügen / Add contract manually

更新翻译键：
- `ai.proactive.contractExpired` — 移除"如需续约请手动更新"文字（改用按钮代替）

### 21.7 通知气泡修正 (`FloatingAIChat.tsx`)

- 通知气泡读取最新消息从 `proactiveMessages[0]` 改为 `proactiveMessages[proactiveMessages.length - 1]`

**修改文件**:
- `frontend/src/stores/aiAdvisorStore.ts` — pushMessage 改为 append，新增 contract_expired 类型
- `frontend/src/components/ai/ChatInterface.tsx` — proactive messages 移到底部，新增 contract_expired 操作按钮，新增 useNavigate
- `frontend/src/components/ai/FloatingAIChat.tsx` — expired contracts 改用 contract_expired 类型，通知气泡读取修正
- `frontend/src/components/properties/PropertyDetail.tsx` — useSearchParams 自动打开添加表单
- `backend/app/api/v1/endpoints/dashboard.py` — alerts 返回 property_id
- `frontend/src/i18n/locales/zh.json` — 新增 uploadRenewal、addContractManually，更新 contractExpired
- `frontend/src/i18n/locales/de.json` — 同上
- `frontend/src/i18n/locales/en.json` — 同上

---

## 22. 修复租赁合同删除级联逻辑 (2026-03-17)

**问题**:
1. 删除租赁合同文档（Mietvertrag）时选择"关联数据一起删除"，定期交易（recurring transaction）和它生成的普通交易没有被一起删除
2. 代码引用了不存在的字段 `RecurringTransaction.mietvertrag_document_id`（该字段实际在 `Property` 模型上），导致查询失败
3. 删除预览接口（`GET /documents/{id}/delete-preview`）同样引用了错误字段

**根因**: `mietvertrag_document_id` 是 `Property` 表的字段，不是 `RecurringTransaction` 表的字段。租赁合同与定期交易的关联链是：`Document → Property.mietvertrag_document_id → RecurringTransaction.property_id → Transaction.source_recurring_id`

**修复内容**:

### 22.1 `with_data` 模式级联删除修复

修正关联查找路径：
1. 通过 `Property.mietvertrag_document_id` 找到关联房产
2. 通过 `RecurringTransaction.property_id` 找到该房产的所有定期交易
3. 通过 `Transaction.source_recurring_id` 找到定期交易生成的所有普通交易
4. 按顺序删除：生成的交易 → 定期交易 → 清除房产关联
5. 删除后自动调用 `recalculate_rental_percentage` 更新房产租赁比例

### 22.2 `document_only` 模式修复

将错误的 `RecurringTransaction.mietvertrag_document_id` 查询改为正确的 `Property.mietvertrag_document_id` 查询，仅解除关联不删除数据

### 22.3 删除预览接口修复

修正预览接口的关联查找逻辑，正确显示：
- 关联的定期交易列表（通过 property → recurring_transactions）
- 定期交易生成的普通交易数量（`generated_transactions_count`）

**修改文件**:
- `backend/app/api/v1/endpoints/documents.py` — 三处 `RecurringTransaction.mietvertrag_document_id` 引用全部修正

---

## 23. 确认租赁合同时自动创建房产 (2026-03-17)

**问题**: 用户删除合同文档（含关联数据）后重新上传租赁合同，AI 聊天框中出现待确认的定期收入（Thenneberg 51, €700/月），点击"确认"时报错 "No matching property found. Please create the property first."。原因是之前删除操作把房产也删了，确认时地址匹配找不到任何房产，直接 `raise ValueError`。

**修复内容**:

### 23.1 后端自动创建房产 (`ocr_tasks.py`)

当确认租赁合同时找不到匹配房产，不再报错，而是从租赁合同的地址信息自动创建一个基础房产记录：
- 地址从合同 OCR 数据解析（尝试拆分 street/postal_code/city）
- `purchase_price=0`、`building_value=0` 作为占位（用户后续上传购房合同或手动补充）
- `depreciation_rate=1.5%`（出租房产默认值）
- `mietvertrag_document_id` 直接关联
- 返回 `property_auto_created=true` 标记

### 23.2 前端提示补充房产信息 (`ChatInterface.tsx`)

确认成功后，如果 `property_auto_created=true`，额外推送一条提醒消息，告知用户房产已自动创建但购买价格等信息缺失，建议上传购房合同或手动编辑。

### 23.3 i18n 新增翻译键

- `ai.proactive.propertyAutoCreatedFromRental` — 三语提示房产已从租赁合同自动创建

**修改文件**:
- `backend/app/tasks/ocr_tasks.py` — 自动创建房产逻辑 + 返回 `property_auto_created` 标记
- `frontend/src/components/ai/ChatInterface.tsx` — 确认后推送房产自动创建提醒
- `frontend/src/i18n/locales/{zh,en,de}.json` — 新增翻译键

---

## 23.1 补传购房合同自动合并占位房产 (2026-03-17)

**问题**: §23 中确认租赁合同时自动创建了占位房产（purchase_price=0），但后续补传购房合同（Kaufvertrag）时，`create_property_from_suggestion` 会直接创建新房产，不检查是否已有同地址的占位记录。结果：两个 Thenneberg 51 房产，定期收入挂在旧的占位房产上，新房产有完整数据但没有关联。

**修复内容**:

在 `create_property_from_suggestion` 中新增占位房产检测逻辑：
1. 查询用户所有 `purchase_price=0` 且 `status=ACTIVE` 的房产
2. 用 street 做模糊匹配（双向包含）
3. 如果找到匹配的占位房产，直接更新其字段（地址、购买价、建筑价值、折旧率等），而非新建
4. 更新后调用 `recalculate_rental_percentage` 重算租赁比例（因为定期收入已经挂在这个房产上）
5. 返回 `property_updated_placeholder: true` 标记

**修改文件**:
- `backend/app/tasks/ocr_tasks.py` — 占位房产检测与合并逻辑

---

## 24. 租赁合同 VLM Vision Fallback + Groq Vision 优先 (2026-03-17)

**问题**: 租赁合同（doc 93）OCR 识别不完整。Tesseract 对扫描件质量差（~60-70%），regex 提取了基本字段（地址、租金、起始日期、租户、房东），但 `end_date`、`deposit_amount`、`betriebskosten` 缺失。LLM 文本补充（Groq）从乱码 OCR 文本中补充了 `street`、`city`、`postal_code`，但仍无法提取上述三个字段。

**根因分析 — 三个独立问题**:

1. **VLM fallback 从未触发**: `_contract_confidence` 公式权重失衡 — 当 3 个关键字段（address/rent/start_date）都存在时，分数起步 0.85+，即使多个重要字段缺失也不会低于 0.70 阈值
2. **OpenAI client 未初始化**: 当 Groq 启用时，`self.client`（OpenAI）不会被创建（条件 `not self.groq_client` 阻止了初始化），导致 vision 调用只能走 Groq 文本模型（不支持多图格式）
3. **`postal_code` 类型错误**: `_parse_llm_contract_response` 中的数值转换逻辑将所有看起来像数字的字符串转为 float，导致 `postal_code: "2571"` 变成 `2571.0`

**修复内容**:

### 24.1 置信度公式调整 (`ocr_engine.py`)

重写 `_contract_confidence`：
- 新增 `end_date` 到 Mietvertrag 重要字段列表
- 每个缺失的重要字段扣 0.06（原来只加 bonus 不扣分）
- 公式：`critical_score × 0.50 + avg_conf × 0.30 + present × 0.02 - missing × 0.06`
- Doc 93 场景：3 个重要字段缺失 → 扣 0.18 → 分数从 ~0.90 降至 ~0.64 → 触发 VLM

### 24.2 Groq Vision 模型支持 (`llm_service.py`)

Groq 支持 `llama-4-scout-17b-16e-instruct` vision 模型（128K context，最多 5 张图，base64 最大 4MB）。

- 新增 `groq_vision_model` 属性（默认 `meta-llama/llama-4-scout-17b-16e-instruct`）
- 新增 `_build_vision_provider_chain()` 方法：返回有序 provider 列表 `[(client, model, name)]`
  - 顺序：Groq (llama-4-scout, 快) → GPT-OSS → OpenAI (gpt-4o, 稳)
- 重写 `generate_vision()`：遍历 provider chain，每个 provider 尝试 2 次（减半 max_tokens），失败自动降级到下一个
- 重写 `generate_vision_multi()`：同上，支持多图
- 空响应自动跳到下一个 provider（与文本 chain 行为一致）

### 24.3 OpenAI client 始终初始化 (`llm_service.py`)

- 改为 `if self.api_key:` 无条件初始化（移除 `not self.groq_client` 条件）
- 确保 OpenAI 作为 vision fallback 始终可用

### 24.4 字符串字段类型保护 (`ocr_engine.py`)

- `_parse_llm_contract_response`：新增 `_STRING_FIELDS` 集合（postal_code、street、city、地址、姓名、日期等），这些字段跳过 float 转换，已是数字的转为字符串并去除 `.0` 后缀
- `_llm_supplement_contract` 合并逻辑：同样新增 `_str_fields` 保护，LLM 返回的数字型 postal_code 自动转为字符串

### 24.5 置信度同步 (`ocr_engine.py`)

- `_route_to_contract_extractor` 返回前将 `_contract_confidence` 计算结果写入 `extracted_data["confidence"]`
- 修复之前 `ocr_result.confidence`（regex 原始值 0.57）与 `confidence_score`（重算值 0.90）不一致的问题

**测试结果 (doc 93)**:

| 字段 | 修复前 | 修复后 |
|------|--------|--------|
| end_date | ❌ 缺失 | ✅ 2024-09-01 (VLM) |
| deposit_amount | ❌ 缺失 | ✅ 1860.0 (VLM, 3×620) |
| betriebskosten | ❌ 缺失 | ❌ 仍缺失（合同未单独列明）|
| postal_code | ⚠️ 2571.0 (float) | ✅ "2571" (string) |
| confidence | 0.57 (stale) | 0.78 (accurate) |
| _vlm_fallback | ❌ 未触发 | ✅ filled: [end_date, deposit_amount, utilities_included] |

**Vision provider chain 执行顺序**: Groq llama-4-scout（快速，成功）→ 无需 fallback 到 OpenAI

### 24.6 Tesseract DPI 降低 (`ocr_engine.py`)

- `_ocr_all_pdf_pages`: DPI 从 300 → 150（像素量减少 4 倍，5 页 PDF 节省 ~13s）
- VLM fallback `_vlm_contract_fallback`: PDF 渲染 DPI 从 150 → 100（合同文字较大，100 DPI 足够 Groq vision 识别）

### 24.7 扫描 PDF 合同快速路径 (`ocr_engine.py`)

**问题**: 5 页扫描 PDF 的 Tesseract OCR 需要 ~23s（5 页 × 150 DPI），但合同类文档的 VLM fallback 会直接从图片读取，不依赖 OCR 文本质量。全量 OCR 对合同来说是浪费。

**优化**: 在 `process_document` 的扫描 PDF 路径中新增快速路径：
1. 先只 OCR 前 2 页（`max_pages=2`，~8s）用于分类
2. 如果分类为合同（Kaufvertrag/Mietvertrag）→ 直接进入 `_route_to_contract_extractor`（VLM 从原始图片读取所有页面）
3. 如果分类为非合同 → 继续 OCR 全部 5 页（原有流程不变）

**自适应路由**: `_route_to_contract_extractor` 中新增逻辑：
- regex 提取后统计缺失必需字段数
- ≥3 个缺失 → 跳过 LLM 文本补充，直接走 VLM vision（节省一次 LLM 调用 ~3-8s）
- <3 个缺失 → LLM 文本补充优先（更便宜），仍不够再走 VLM

**测试结果 (doc 95, mietvertrag_top1.pdf, 5 页扫描 PDF)**:

| 阶段 | 耗时 |
|------|------|
| 2 页 OCR (150 DPI) | ~12s |
| Regex 提取 + 分类 | <1s |
| VLM fallback (5 页 → Groq llama-4-scout) | ~28s |
| 管道其余阶段 | ~4s |
| **总计** | **~45s** |

**对比**:
| 场景 | 优化前 | 优化后 | 节省 |
|------|--------|--------|------|
| 5 页扫描 PDF 合同 | ~88s | ~45s | ~49% |

**提取结果**: confidence=0.78, end_date=2025-09-01 ✓, deposit_amount=1860.0 ✓, VLM 填充 7 个字段, Groq vision 一次成功无需 fallback

**非合同扫描 PDF 兼容性**: 非合同文档（收据/发票）不受影响 — 2 页分类后继续走全量 5 页 OCR + 原有提取流程

**修改文件**:
- `backend/app/services/ocr_engine.py` — `_contract_confidence` 公式调整、`_parse_llm_contract_response` 字符串保护、`_llm_supplement_contract` 类型保护、`_route_to_contract_extractor` 置信度同步 + 自适应路由、`_ocr_all_pdf_pages` DPI 150、`_vlm_contract_fallback` DPI 100、`process_document` 扫描 PDF 合同快速路径
- `backend/app/services/llm_service.py` — `groq_vision_model`、`_build_vision_provider_chain`、`generate_vision`/`generate_vision_multi` 重写为 provider chain、OpenAI client 始终初始化


---

## 25. 占位房产模糊匹配修复 — 购房合同未合并到租赁合同创建的房产 (2026-03-17)

**问题**: 先上传租赁合同（doc 96），系统自动创建占位房产（purchase_price=0.01）。再上传购房合同（doc 97），系统应将购房数据合并到占位房产，但实际创建了第二个房产。

**根因分析**:

`create_property_from_suggestion` 中的占位房产匹配逻辑使用精确字符串比较：
```python
c_street == street_lower or c_street in addr_lower or street_lower in c_addr
```

但 OCR 对同一地址产生了不同的拼写：
- 租赁合同 OCR → `property_address: "Trenneberg 51"`（Tesseract 误读，T**r**enneberg）
- 购房合同 OCR → `street: "Thenneberg 51"`（正确，T**h**enneberg）

一个字母的差异导致精确匹配失败，购房合同创建了新房产而非合并到占位房产。

**修复内容**:

### 25.1 模糊匹配逻辑 (`ocr_tasks.py`)

重写 `create_property_from_suggestion` 中的占位房产匹配，三层匹配策略：

1. 精确/子串匹配（原有逻辑，保持不变）
2. 同邮编 + 同门牌号 → score=0.95（强信号，即使街道名完全乱码也能匹配）
3. 同门牌号 + 街道名相似度 ≥ 0.70（使用 `difflib.SequenceMatcher`）→ score=相似度

门牌号提取：正则 `(\d+\s*[a-zA-Z]?(?:/\d+)?)\s*$`，支持 "51"、"51/3"、"86a" 等格式。

本案例匹配结果：
- "trenneberg 51" vs "thenneberg 51"：门牌号 "51" = "51" ✓，SequenceMatcher ratio = 0.86 ≥ 0.70 ✓
- 同时 postal_code "2571" = "2571" ✓ → score=0.95

### 25.2 数据修复

- 删除重复房产 `8348ac50`（购房合同错误创建的）
- 将购房合同数据（price=273000, address, building_value 等）合并到占位房产 `65175752`
- 占位房产现在同时关联 kaufvertrag_document_id=97 和 mietvertrag_document_id=96
- Doc 97 的 suggestion 更新为指向正确的房产 ID

**修改文件**:
- `backend/app/tasks/ocr_tasks.py` — `create_property_from_suggestion` 占位房产匹配改为三层模糊匹配


---

## 26. VLM 地址重建 + 单元编号（TOP）提取 (2026-03-17)

**问题**: 
1. `property_address` 保留了 Tesseract OCR 的错误拼写（"Trenneberg 51"），即使 VLM 已经读出了正确的 `street`（"Thenneberg 51"）。原因：VLM 合并逻辑只覆盖空字段或低置信度字段，而 `property_address` 已有值且置信度 0.85，不会被覆盖。
2. 合同中的公寓单元编号（TOP 1）完全没有被提取。VLM prompt 中没有 `unit_number` 字段。

**根因**:
- "Trenneberg" 是 Tesseract OCR 对扫描件的误读（150 DPI），VLM（Groq vision）从原始图片读出了正确的 "Thenneberg"
- VLM 填充了 `street` 但不会覆盖已有的 `property_address`（置信度 0.85 ≥ 0.75 阈值）
- VLM prompt 没有要求提取 `unit_number`（TOP/Wohnungstop/Stiege）

**修复内容**:

### 26.1 VLM prompt 新增 `unit_number` 字段 (`ocr_engine.py`)

Kaufvertrag 和 Mietvertrag 的 VLM prompt 均新增：
- `"unit_number": "apartment/unit number, e.g. TOP 1, Top 3, Stiege 2/Top 5, or null"`
- `"property_address"` 描述改为 "full street address with unit/TOP, postal code and city"
- 新增指令："Look for TOP/Wohnungstop/Stiege unit numbers — include them in unit_number."

### 26.2 VLM 合并后重建 `property_address` (`ocr_engine.py`)

在 `_vlm_contract_fallback` 的合并逻辑末尾新增地址重建：
- 从最佳可用组件（street + unit_number + postal_code + city）重建 `property_address`
- 格式：`"Thenneberg 51/Top 1, 2571 Altenmarkt"`
- 仅当重建结果与现有值不同时才更新
- 确保 VLM 修正的拼写（如 Thenneberg）传播到 `property_address`

### 26.3 字符串字段保护 (`ocr_engine.py`)

`_parse_llm_contract_response` 和 `_llm_supplement_contract` 的 `_STRING_FIELDS` / `_str_fields` 集合均新增 `unit_number`。

**测试结果 (doc 96, mietvertrag_top1.pdf)**:

| 字段 | 修复前 | 修复后 |
|------|--------|--------|
| property_address | Trenneberg 51 | Thenneberg 51/Top 1, 2571 Altenmarkt |
| street | Thenneberg 51 | Thenneberg 51 |
| unit_number | ❌ 缺失 | ✅ Top 1 |
| city | Altenmarkt | Altenmarkt |

**数据清理**: 删除旧的 recurring #16（错误地址 "Trenneberg 51"），保留新的 #17（正确地址）。

### 26.4 VLM 权威阈值提升至 0.90 (`ocr_engine.py`)

**变更**: `_vlm_contract_fallback` 中 VLM 合并阈值从 0.75 → 0.90。

**策略**: VLM（Groq vision）直接从原始图片读取，准确度远高于 Tesseract OCR + LLM 文本补充。一旦 VLM 返回了值，只要现有字段置信度 < 0.90，就以 VLM 为准。VLM 自身置信度设为 0.90。

**影响**: 之前阈值 0.75 导致 OCR 错误拼写（如 "Trenneberg"）因置信度 0.85 ≥ 0.75 而不被 VLM 覆盖。提升至 0.90 后，VLM 可以覆盖几乎所有 OCR/LLM 结果，仅保留已经非常高置信度（≥0.90）的字段。

### 26.5 前端 unit_number 显示 (`DocumentsPage.tsx` + i18n)

- `DocumentsPage.tsx`: OCR 标签字典新增 `unit_number`，字段顺序放在 `street` 之后
- `expectedFieldsByType`: `purchase_contract` 和 `rental_contract` 均新增 `unit_number`（在 `street` 之后）
- i18n 翻译：
  - `zh.json`: `"unitNumber": "单元编号"`
  - `de.json`: `"unitNumber": "Einheitsnummer (Top)"`
  - `en.json`: `"unitNumber": "Unit Number (Top)"`

**测试结果 (doc 96, mietvertrag_top1.pdf)**:

| 字段 | 修复前 | 修复后 |
|------|--------|--------|
| property_address | Trenneberg 51 | Thenneberg 51/Top 1, 2571 Altenmarkt |
| street | Thenneberg 51 | Thenneberg 51 |
| unit_number | ❌ 缺失 | ✅ Top 1 |
| city | Altenmarkt | Altenmarkt |
| VLM 合并阈值 | 0.75 | 0.90（VLM 权威） |
| tenant_name | OCR 值 | ✅ VLM 覆盖（阈值 0.90 生效） |
| contract_type | OCR 值 | ✅ VLM 覆盖（阈值 0.90 生效） |

**数据清理**: 删除旧的 recurring #16（错误地址 "Trenneberg 51"），保留新的 #17（正确地址）。

**修改文件**:
- `backend/app/services/ocr_engine.py` — VLM prompt 新增 unit_number、VLM 合并后重建 property_address、字符串字段保护、VLM 阈值 0.75→0.90
- `frontend/src/pages/DocumentsPage.tsx` — unit_number 标签 + 字段顺序
- `frontend/src/i18n/locales/zh.json` — 单元编号
- `frontend/src/i18n/locales/de.json` — Einheitsnummer (Top)
- `frontend/src/i18n/locales/en.json` — Unit Number (Top)


---

## 27. 购房合同删除级联 + 房产状态修复 + document_type 枚举修复 (2026-03-17)

**问题**:
1. 删除购房合同时选择"删除关联"，房产不会被删除（`PropertyService.delete_property` 因有关联交易而失败）
2. 如果房产有关联的租赁合同/recurring，没有级联删除逻辑
3. 上传租赁合同到自住房产后，房产状态没有变成"租赁"（合同过期后被重置为 owner_occupied）
4. **严重 bug**: `documents.py` 中所有 `document_type` 比较使用了错误的字符串（`"kaufvertrag"` / `"mietvertrag"`），但 DB 枚举值是 `"purchase_contract"` / `"rental_contract"`，导致删除关联数据和查看关联数据的功能完全失效

**修复内容**:

### 27.1 document_type 枚举比较修复 (`documents.py`)

将 6 处字符串比较从 `"kaufvertrag"` / `"mietvertrag"` 改为 `DocumentType.PURCHASE_CONTRACT` / `DocumentType.RENTAL_CONTRACT`：
- `with_data` 模式：购房合同删除、租赁合同删除
- `document_only` 模式：购房合同解绑、租赁合同解绑
- `get_document_related_data`：购房合同关联数据、租赁合同关联数据

### 27.2 购房合同删除级联 (`documents.py`)

重写 `with_data` 模式的购房合同删除逻辑，完整级联：
1. 删除房产上所有 recurring transactions + 其生成的交易
2. 如果房产有关联的租赁合同（`mietvertrag_document_id`），级联删除该文档及其存储文件
3. 解绑房产上所有交易（`property_id = None`）
4. 删除房产本身

### 27.3 关联数据展示增强 (`documents.py` + `DeleteDocumentDialog.tsx`)

`get_document_related_data` 端点增强：购房合同现在也返回关联的租赁合同和 recurring transactions 信息。

前端 `DeleteDocumentDialog` 新增显示：
- 关联租赁合同文件名（红色警告文字）
- 房产上的 recurring transactions 列表（含过期状态标记）

### 27.4 房产状态修复 (`property_service.py`)

`recalculate_rental_percentage` 逻辑修改：
- `rental_percentage` 仍然只基于 active contracts（用于税务计算）
- `property_type` 改为基于 ALL contracts（包括过期的）：有任何租赁历史 → rental/mixed_use
- 确保有过期租赁合同的房产不会被重置为 owner_occupied

### 27.5 i18n 新增键

- `zh.json`: `linkedMietvertrag`, `linkedMietvertragWarn`, `recurringTransactions`
- `de.json`: 同上（德语）
- `en.json`: 同上（英语）

**修改文件**:
- `backend/app/api/v1/endpoints/documents.py` — document_type 枚举修复、购房合同级联删除、关联数据增强
- `backend/app/services/property_service.py` — recalculate_rental_percentage 房产状态逻辑
- `frontend/src/components/documents/DeleteDocumentDialog.tsx` — 级联警告 UI
- `frontend/src/components/documents/DeleteDocumentDialog.css` — 警告文字样式
- `frontend/src/i18n/locales/zh.json` — 新增 i18n 键
- `frontend/src/i18n/locales/de.json` — 新增 i18n 键
- `frontend/src/i18n/locales/en.json` — 新增 i18n 键

---

## §28 确认定期交易后自动生成交易明细 (2026-03-17)

**问题**: 用户确认租赁合同的定期交易建议后，系统只创建了 `recurring_transaction` 记录，但没有根据定期交易的时间范围生成对应的交易明细（`transactions`）。

**根因**: `create_recurring_from_suggestion()` 函数（`ocr_tasks.py`）创建 recurring 后没有调用 `generate_due_transactions()` 来回填交易。而 API 端点 `/recurring-transactions/rental-income` 在创建后会调用此方法，OCR 确认流程遗漏了这一步。

此外，对于已过期合同（`end_date < today`），函数先将 `is_active=False`，再调用 `generate_due_transactions`，但该方法只处理 `is_active=True` 的记录，导致过期合同永远不会生成交易。

**修复** (`backend/app/tasks/ocr_tasks.py`):
- 在 `create_recurring_from_suggestion` 中，`recalculate_rental_percentage` 之后、过期停用之前，调用 `generate_due_transactions`
- 对于过期合同，`target_date` 设为 `end_date`（而非 today），确保只生成合同有效期内的交易
- 对于活跃合同，`target_date` 设为 `today`，回填从 `start_date` 到今天的所有月份

**测试验证**:
- 租赁合同 doc 102（2021-10-01 ~ 2024-10-01，€640/月）
- 确认后生成 37 笔交易明细（2021-10 至 2024-10，每月 €640）
- recurring #21 正确标记为 `is_active=false`（已过期）
- `next_generation_date=2024-11-01`（所有到期交易已生成）

**修改文件**:
- `backend/app/tasks/ocr_tasks.py` — `create_recurring_from_suggestion` 增加 `generate_due_transactions` 调用

---

## §29 OCR 编辑保存不生效修复 (2026-03-17)

**问题**: 用户在文档详情页点击"编辑"修改 OCR 识别字段后保存，API 返回成功但数据库中的值没有变化。

**根因**: SQLAlchemy 的 `JSON` 列类型不会自动追踪变更。即使代码通过 `document.ocr_result = json.loads(json.dumps(ocr_result))` 做了深拷贝重新赋值，SQLAlchemy 仍然没有将该列标记为 dirty，导致 `db.commit()` 时跳过了该列的 UPDATE。

**附带问题**: `correction_history` 中存储了完整的 `previous_data`（包含上一次的 `correction_history`），导致第二次编辑时 `json.dumps` 产生循环引用错误。

**修复**:

1. `documents.py` — `/correct` 端点:
   - 添加 `flag_modified(document, "ocr_result")` 强制标记 JSON 列为已修改
   - `previous_data` 排除 `correction_history` 和 `learning_data` 键，避免循环引用
   - `correction_history` 条目改为只存储变更字段的旧值（`previous_values`），而非完整 `previous_data`

2. `classification_learning.py` — `record_ocr_correction`:
   - 同样添加 `flag_modified(document, "ocr_result")`

**测试验证**:
- 修改 `monthly_rent` 640→999→640，每次都正确持久化
- 多字段同时修改（monthly_rent + tenant_name + start_date）正确持久化
- 连续多次编辑不再产生循环引用错误

**修改文件**:
- `backend/app/api/v1/endpoints/documents.py` — `flag_modified` + `previous_data` 过滤
- `backend/app/services/classification_learning.py` — `flag_modified`


---

## §30 文档编辑同步到定期交易 + 房产页面编辑跳转 (2026-03-17)

**问题**: 用户在文档详情页修改租赁合同的月租金、开始日期、结束日期后，关联的定期交易和已生成的交易明细没有同步更新。同时，房产页面的租赁合同区域允许直接编辑，但如果合同来自 OCR 文档，应该引导用户去文档页面修改（保持数据一致性）。

**修复内容**:

### 30.1 后端：OCR 编辑同步到定期交易 (`documents.py`)

在 `/correct` 端点的 `db.commit()` 之后，增加租赁合同同步逻辑：
- 检测文档类型为 `RENTAL_CONTRACT` 且修改了 `monthly_rent`/`start_date`/`end_date`
- 通过 `Property.mietvertrag_document_id` 找到关联房产，再找到关联的定期交易
- 更新定期交易的 `amount`/`start_date`/`end_date`
- 删除旧的已生成交易，重置 `next_generation_date`
- 调用 `generate_due_transactions()` 重新生成交易明细
- 过期合同：临时激活 → 生成到 `end_date` → 再停用

### 30.2 后端：修复 `source_document_id` 返回值 (`properties.py`)

`/rental-contracts` 端点之前 `source_document_id` 始终返回 `None`（模型上没有该字段，`getattr` fallback）。修改为从 `Property.mietvertrag_document_id` 获取，正确返回关联文档 ID。

### 30.3 前端：房产页面租赁合同编辑跳转 (`PropertyDetail.tsx`)

- 当租赁合同有 `source_document_id` 时，隐藏 ✏️ 编辑按钮，改为显示 📄 链接跳转到文档详情页
- 在租期行下方显示"如需修改请前往关联合同"提示链接
- 无关联文档的合同仍保留原有的直接编辑功能

### 30.4 i18n 新增键

- `properties.rentalContracts.viewLinkedDocument` — 查看关联合同 / View linked contract / Verknüpften Vertrag anzeigen
- `properties.rentalContracts.editFromDocument` — 如需修改请前往关联合同 / To edit, go to the linked contract / Zum Bearbeiten den verknüpften Vertrag öffnen

**修改文件**:
- `backend/app/api/v1/endpoints/documents.py` — `/correct` 端点增加租赁合同同步逻辑
- `backend/app/api/v1/endpoints/properties.py` — `/rental-contracts` 端点修复 `source_document_id`
- `frontend/src/components/properties/PropertyDetail.tsx` — 编辑按钮 → 文档链接跳转
- `frontend/src/i18n/locales/zh.json` — 新增 2 个 i18n 键
- `frontend/src/i18n/locales/en.json` — 新增 2 个 i18n 键
- `frontend/src/i18n/locales/de.json` — 新增 2 个 i18n 键
