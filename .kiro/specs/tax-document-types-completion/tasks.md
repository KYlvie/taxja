# 实施任务：奥地利税务文档类型全面补齐

## Phase 0: 基础设施准备

### Task 0.1: DocumentType 枚举扩展（后端 + 数据库）
- [x] 在 `backend/app/models/document.py` 的 `DocumentType` 枚举中新增 9 个值：`L1_FORM`, `L1K_BEILAGE`, `L1AB_BEILAGE`, `E1A_BEILAGE`, `E1B_BEILAGE`, `E1KV_BEILAGE`, `U1_FORM`, `U30_FORM`, `JAHRESABSCHLUSS`
- [x] 在 `backend/app/services/document_classifier.py` 的 `DocumentType` 枚举中同步新增对应值
- [x] 执行 SQL 扩展 PostgreSQL 的 `documenttype` 枚举：`ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'xxx'`（9 条）
- [x] 验证：重启后端，确认新枚举值可正常使用

**涉及文件**: `backend/app/models/document.py`, `backend/app/services/document_classifier.py`
**对应需求**: 需求 5.1（验收标准 1, 2, 4）

### Task 0.2: DocumentClassifier 新增分类模式
- [x] 为 `L1_FORM` 添加关键词模式：`arbeitnehmerveranlagung`, `L 1`, `L1-PDF`, `erklärung zur arbeitnehmerveranlagung`
- [x] 为 `L1K_BEILAGE` 添加关键词模式：`L1k`, `beilage für kinder`, `familienbonus`, `kindermehrbetrag`
- [x] 为 `L1AB_BEILAGE` 添加关键词模式：`L1ab`, `absetzbeträge`, `alleinverdiener`, `alleinerzieher`, `pendlerpauschale`
- [x] 为 `E1A_BEILAGE` 添加关键词模式：`E1a`, `beilage zur einkommensteuererklärung`, `selbständige arbeit`, `einnahmen-ausgaben-rechnung`, `betriebseinnahmen`, `betriebsausgaben`
- [x] 为 `E1B_BEILAGE` 添加关键词模式：`E1b`, `vermietung und verpachtung`, `mieteinnahmen`, `KZ 9460`, `KZ 9500`
- [x] 为 `E1KV_BEILAGE` 添加关键词模式：`E1kv`, `kapitalvermögen`, `kapitalertragsteuer`, `KESt`, `kryptowährung`
- [x] 为 `U1_FORM` 添加关键词模式：`umsatzsteuererklärung`, `U1`, `jahresumsatzsteuer`
- [x] 为 `U30_FORM` 添加关键词模式：`umsatzsteuervoranmeldung`, `U30`, `UVA`, `voranmeldung`
- [x] 为 `JAHRESABSCHLUSS` 添加关键词模式：`jahresabschluss`, `einnahmen-ausgaben-rechnung`, `bilanz`, `gewinn- und verlustrechnung`
- [x] 添加优先级逻辑：L1 vs E1 区分（L1 含 "arbeitnehmerveranlagung"，E1 含 "einkommensteuererklärung"）
- [x] 添加优先级逻辑：E1b vs Mietvertrag 区分（E1b 是税表附表，Mietvertrag 是实际合同）
- [x] 编写测试 `backend/tests/test_document_classifier_new_types.py`：验证每种新类型的分类准确性

**涉及文件**: `backend/app/services/document_classifier.py`, `backend/tests/test_document_classifier_new_types.py`
**对应需求**: 需求 5.1（验收标准 3）

### Task 0.3: TaxFilingData 模型创建
- [x] 新建 `backend/app/models/tax_filing_data.py`，定义 `TaxFilingData` 模型（id, user_id, tax_year, data_type, source_document_id, data(JSON), status, created_at, confirmed_at）
- [x] 在 `backend/app/models/__init__.py` 中注册新模型
- [x] 在 `backend/app/db/base.py` 中导入新模型
- [x] 执行 SQL 创建表：`CREATE TABLE tax_filing_data (...)`
- [x] 新建 `backend/app/schemas/tax_filing_data.py`，定义 Pydantic schemas（TaxFilingDataCreate, TaxFilingDataResponse, TaxFilingDataList）
- [x] 编写测试 `backend/tests/test_tax_filing_data_model.py`：验证模型 CRUD 操作

**涉及文件**: `backend/app/models/tax_filing_data.py`, `backend/app/schemas/tax_filing_data.py`, `backend/tests/test_tax_filing_data_model.py`
**对应需求**: 需求 1.5（验收标准 3）

### Task 0.4: 通用确认端点
- [x] 在 `backend/app/api/v1/endpoints/documents.py` 新增 `POST /documents/{id}/confirm-tax-data` 端点
- [x] 端点逻辑：读取 `document.ocr_result.import_suggestion.type`，根据类型路由到对应的确认处理函数
- [x] 确认处理：创建 `TaxFilingData` 记录（status="confirmed"），将 suggestion 标记为 "confirmed"
- [x] 对于含亏损的类型（E1a/Jahresabschluss），自动创建/更新 `LossCarryforward` 记录
- [x] 编写测试 `backend/tests/test_confirm_tax_data_endpoint.py`

**涉及文件**: `backend/app/api/v1/endpoints/documents.py`, `backend/tests/test_confirm_tax_data_endpoint.py`
**对应需求**: 需求 1.5（验收标准 3）, 需求 2.4（验收标准 4）

### Task 0.5: 前端 DocumentType 翻译和分组
- [x] 在 `frontend/src/i18n/locales/zh.json` 新增所有新文档类型的中文翻译
- [x] 在 `frontend/src/i18n/locales/en.json` 新增英文翻译
- [x] 在 `frontend/src/i18n/locales/de.json` 新增德文翻译
- [x] 在 DocumentsPage 的文档类型筛选器中实现分组显示（雇员类/自由职业类/房东类/企业类/通用类）
- [x] 验证：前端文档类型下拉菜单显示所有新类型

**涉及文件**: `frontend/src/i18n/locales/zh.json`, `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/de.json`, `frontend/src/pages/DocumentsPage.tsx`
**对应需求**: 需求 5.1（验收标准 5）, 需求 5.2（验收标准 1, 2）

---

## Phase 1: 雇员报税系列

### Task 1.1: L16 Lohnzettel 提取器实现
- [x] 新建 `backend/app/services/l16_extractor.py`
- [x] 实现 `L16Data` 数据类：tax_year, employer_name, employee_name, sv_nummer, kz_210, kz_215, kz_220, kz_230, kz_245, kz_260, kz_718, kz_719, familienbonus, telearbeitspauschale, confidence
- [x] 实现 `L16Extractor.extract(text)` 方法：
  - 策略1: 解析 AcroForm 字段（`--- FORM FIELDS ---` 段落中的 Kz 前缀字段）
  - 策略2: 正则匹配 KZ 码 + 金额模式（`KZ\s*(\d{3})\s+(\d+[.,]\d{2})`）
  - 策略3: 关键词上下文匹配（"Bruttobezüge" → kz_210, "Lohnsteuer" → kz_260 等）
- [x] 实现 `L16Extractor.to_dict(data)` 方法
- [x] 实现置信度计算：基于成功提取的关键字段数量（tax_year + kz_245 + kz_260 = 高置信度）
- [x] 编写测试 `backend/tests/test_l16_extractor.py`

**涉及文件**: `backend/app/services/l16_extractor.py`, `backend/tests/test_l16_extractor.py`
**对应需求**: 需求 1.1（验收标准 1, 2, 4）

### Task 1.2: L16 Pipeline 路由和建议生成
- [x] 在 `backend/app/services/ocr_engine.py` 新增 `_route_to_l16_extractor(raw_text, start_time)` 方法
- [x] 在 `ocr_engine.py` 的 `process_document` 中添加 LOHNZETTEL 类型路由（PDF 文本层和 Tesseract 两个分支都要加）
- [x] 在 `document_pipeline_orchestrator.py` 的 `_stage_validate` 中新增 `_validate_lohnzettel(data, validation)` 方法：验证 tax_year、kz_245、kz_260 必填
- [x] 在 `document_pipeline_orchestrator.py` 的 `_stage_suggest` 中新增 LOHNZETTEL 分支：调用 `_build_lohnzettel_suggestion(document, result)` 生成 import_suggestion（type: `import_lohnzettel`）
- [x] 编写测试 `backend/tests/test_pipeline_lohnzettel.py`：验证 L16 文档端到端处理流程

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_lohnzettel.py`
**对应需求**: 需求 1.1（验收标准 2, 3, 5）

### Task 1.3: L1 Form 提取器实现
- [x] 新建 `backend/app/services/l1_form_extractor.py`
- [x] 实现 `L1FormData` 数据类：tax_year, taxpayer_name, steuernummer, kz_717~724（Werbungskosten 各项）, kz_450/458/459（Sonderausgaben）, kz_730/740（außergewöhnliche Belastungen）, confidence
- [x] 实现 `L1FormExtractor.extract(text)` 方法
- [x] 实现 `L1FormExtractor.to_dict(data)` 方法
- [x] 编写测试 `backend/tests/test_l1_form_extractor.py`

**涉及文件**: `backend/app/services/l1_form_extractor.py`, `backend/tests/test_l1_form_extractor.py`
**对应需求**: 需求 1.2（验收标准 1, 2, 4）

### Task 1.4: L1 Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_l1_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 L1_FORM 验证和建议生成
- [x] 编写测试 `backend/tests/test_pipeline_l1.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_l1.py`
**对应需求**: 需求 1.2（验收标准 3）

### Task 1.5: L1k 子女附表提取器实现
- [x] 新建 `backend/app/services/l1k_extractor.py`
- [x] 实现 `L1kData` 数据类
- [x] 实现 `L1kExtractor.extract(text)` 方法
- [x] 编写测试 `backend/tests/test_l1k_extractor.py`

**涉及文件**: `backend/app/services/l1k_extractor.py`, `backend/tests/test_l1k_extractor.py`
**对应需求**: 需求 1.3（验收标准 1, 2, 3）

### Task 1.6: L1k Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_l1k_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 L1K_BEILAGE 验证和建议生成
- [x] 编写测试 `backend/tests/test_pipeline_l1k.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_l1k.py`
**对应需求**: 需求 1.3（验收标准 3）

### Task 1.7: L1ab 扣除额附表提取器实现
- [x] 新建 `backend/app/services/l1ab_extractor.py`
- [x] 实现 `L1abData` 数据类
- [x] 实现 `L1abExtractor.extract(text)` 方法
- [x] 编写测试 `backend/tests/test_l1ab_extractor.py`

**涉及文件**: `backend/app/services/l1ab_extractor.py`, `backend/tests/test_l1ab_extractor.py`
**对应需求**: 需求 1.4（验收标准 1, 2, 3）

### Task 1.8: L1ab Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_l1ab_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 L1AB_BEILAGE 验证和建议生成
- [x] 编写测试 `backend/tests/test_pipeline_l1ab.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_l1ab.py`
**对应需求**: 需求 1.4（验收标准 3）

### Task 1.9: 雇员文档建议卡片（前端）
- [x] 新建 `frontend/src/components/documents/suggestion-cards/LohnzettelSuggestionCard.tsx`：显示 L16 提取数据（收入/扣税/社保分组），支持字段编辑，确认/忽略按钮
- [x] 新建 `frontend/src/components/documents/suggestion-cards/L1SuggestionCard.tsx`：显示 L1 提取数据（Werbungskosten/Sonderausgaben/außergewöhnliche Belastungen 分组）
- [x] 新建 `frontend/src/components/documents/suggestion-cards/L1kSuggestionCard.tsx`：显示子女列表和 Familienbonus 金额
- [x] 新建 `frontend/src/components/documents/suggestion-cards/L1abSuggestionCard.tsx`：显示扣除额信息
- [x] 在 `DocumentsPage.tsx` 中集成建议卡片工厂，根据 `import_suggestion.type` 渲染对应卡片
- [x] 在 `documentService.ts` 新增 `confirmTaxData(documentId: number)` 方法，调用 `POST /documents/{id}/confirm-tax-data`
- [x] 新增 i18n 翻译：所有 KZ 字段名称（zh/en/de），如 "KZ245 应税收入" / "KZ245 Taxable Income" / "KZ245 Steuerpflichtige Bezüge"
- [x] 编写前端测试：验证每种卡片正确渲染

**涉及文件**: `frontend/src/components/documents/suggestion-cards/*.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/services/documentService.ts`, `frontend/src/i18n/locales/{zh,en,de}.json`
**对应需求**: 需求 1.5（验收标准 1, 2, 3, 4, 5）

### Task 1.10: 多 L16 合并逻辑
- [x] 在确认端点中实现多 L16 合并：当同一税年已有 L16 数据时，合并收入（kz_210 累加）、合并扣税（kz_260 累加）
- [x] 在前端建议卡片中，当检测到同年已有 L16 数据时，显示"将与已有数据合并"提示
- [x] 编写测试：验证两份 L16 合并后的数据正确性

**涉及文件**: `backend/app/api/v1/endpoints/documents.py`, `frontend/src/components/documents/suggestion-cards/LohnzettelSuggestionCard.tsx`, `backend/tests/test_l16_merge.py`
**对应需求**: 需求 1.1（验收标准 5）, 需求 1.5（验收标准 5）

---

## Phase 2: 自由职业/房东附表

### Task 2.1: E1a 自由职业附表提取器实现
- [x] 新建 `backend/app/services/e1a_extractor.py`
- [x] 实现 `E1aData` 数据类
- [x] 实现 `E1aExtractor.extract(text)` 方法
- [x] 实现亏损检测
- [x] 编写测试 `backend/tests/test_e1a_extractor.py`

**涉及文件**: `backend/app/services/e1a_extractor.py`, `backend/tests/test_e1a_extractor.py`
**对应需求**: 需求 2.1（验收标准 1, 2, 4）

### Task 2.2: E1a Pipeline 路由、建议生成和亏损结转
- [x] 在 `ocr_engine.py` 新增 `_route_to_e1a_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 E1A_BEILAGE 验证和建议生成
- [x] 在确认端点中，当 E1a 数据含亏损时，自动创建/更新 `LossCarryforward` 记录
- [x] 编写测试 `backend/tests/test_pipeline_e1a.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/app/api/v1/endpoints/documents.py`, `backend/tests/test_pipeline_e1a.py`
**对应需求**: 需求 2.1（验收标准 3, 5）

### Task 2.3: E1b 租赁附表提取器实现
- [x] 新建 `backend/app/services/e1b_extractor.py`
- [x] 实现 `E1bData` 数据类（多房产支持）
- [x] 实现 `E1bExtractor.extract(text)` 方法
- [x] 实现地址匹配逻辑
- [x] 编写测试 `backend/tests/test_e1b_extractor.py`

**涉及文件**: `backend/app/services/e1b_extractor.py`, `backend/tests/test_e1b_extractor.py`
**对应需求**: 需求 2.2（验收标准 1, 2, 3, 4）

### Task 2.4: E1b Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_e1b_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 E1B_BEILAGE 验证和建议生成
- [x] 建议生成时查询用户的 Property 列表，尝试地址匹配
- [x] 编写测试 `backend/tests/test_pipeline_e1b.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_e1b.py`
**对应需求**: 需求 2.2（验收标准 3, 4, 5）

### Task 2.5: E1kv 资本收益附表提取器实现
- [x] 新建 `backend/app/services/e1kv_extractor.py`
- [x] 实现 `E1kvData` 数据类
- [x] 实现 `E1kvExtractor.extract(text)` 方法
- [x] 编写测试 `backend/tests/test_e1kv_extractor.py`

**涉及文件**: `backend/app/services/e1kv_extractor.py`, `backend/tests/test_e1kv_extractor.py`
**对应需求**: 需求 2.3（验收标准 1, 2, 4）

### Task 2.6: E1kv Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_e1kv_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 E1KV_BEILAGE 验证和建议生成
- [x] 编写测试 `backend/tests/test_pipeline_e1kv.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_e1kv.py`
**对应需求**: 需求 2.3（验收标准 3）

### Task 2.7: 自由职业/房东建议卡片（前端）
- [x] 新建 `frontend/src/components/documents/suggestion-cards/E1aSuggestionCard.tsx`：显示营业收支明细，亏损高亮显示
- [x] 新建 `frontend/src/components/documents/suggestion-cards/E1bSuggestionCard.tsx`：按房产分组显示，匹配的房产显示名称，支持字段编辑
- [x] 新建 `frontend/src/components/documents/suggestion-cards/E1kvSuggestionCard.tsx`：显示资本收益明细和已扣 KESt
- [x] 在 DocumentsPage 建议卡片工厂中注册新卡片类型
- [x] 新增 i18n 翻译（zh/en/de）
- [x] 编写前端测试

**涉及文件**: `frontend/src/components/documents/suggestion-cards/*.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/i18n/locales/{zh,en,de}.json`
**对应需求**: 需求 2.4（验收标准 1, 2, 3, 5）

---

## Phase 3: 增值税 + 财务报表

### Task 3.1: U1 年度增值税提取器实现
- [x] 新建 `backend/app/services/vat_form_extractor.py`
- [x] 实现 `VatFormData` 数据类
- [x] 实现 `VatFormExtractor.extract(text)` 方法（含 extract_u1）
- [x] 编写测试 `backend/tests/test_vat_form_extractor.py`

**涉及文件**: `backend/app/services/vat_form_extractor.py`, `backend/tests/test_vat_form_extractor.py`
**对应需求**: 需求 3.1（验收标准 1, 2）

### Task 3.2: U30 增值税预申报提取器实现
- [x] 在 `vat_form_extractor.py` 中实现 `VatFormExtractor.extract_u30(text)` 方法
- [x] 编写测试：U30 月度和季度格式

**涉及文件**: `backend/app/services/vat_form_extractor.py`, `backend/tests/test_vat_form_extractor.py`
**对应需求**: 需求 3.2（验收标准 1, 2）

### Task 3.3: U1/U30 Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_vat_form_extractor()` 方法（U1 和 U30 共用）
- [x] 在 `document_pipeline_orchestrator.py` 新增 U1_FORM 和 U30_FORM 验证和建议生成
- [x] 编写测试 `backend/tests/test_pipeline_vat.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_vat.py`
**对应需求**: 需求 3.1（验收标准 3）, 需求 3.2（验收标准 3）

### Task 3.4: Jahresabschluss 年度财务报表提取器实现
- [x] 新建 `backend/app/services/jahresabschluss_extractor.py`
- [x] 实现 `JahresabschlussData` 数据类
- [x] 实现 `JahresabschlussExtractor.extract(text)` 方法
- [x] 实现亏损检测
- [x] 编写测试 `backend/tests/test_jahresabschluss_extractor.py`

**涉及文件**: `backend/app/services/jahresabschluss_extractor.py`, `backend/tests/test_jahresabschluss_extractor.py`
**对应需求**: 需求 3.3（验收标准 1, 2, 4）

### Task 3.5: Jahresabschluss Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_jahresabschluss_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 JAHRESABSCHLUSS 验证和建议生成
- [x] 确认端点中处理亏损结转
- [x] 编写测试 `backend/tests/test_pipeline_jahresabschluss.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_jahresabschluss.py`
**对应需求**: 需求 3.3（验收标准 3）

### Task 3.6: 增值税/财务报表建议卡片（前端）
- [x] 新建 `frontend/src/components/documents/suggestion-cards/U1SuggestionCard.tsx`：按税率分组显示营业额和税额，显示进项税/销项税/应缴差额
- [x] 新建 `frontend/src/components/documents/suggestion-cards/U30SuggestionCard.tsx`：显示申报期间、当期营业额和税额
- [x] 新建 `frontend/src/components/documents/suggestion-cards/JahresabschlussSuggestionCard.tsx`：显示收支汇总、利润/亏损（亏损红色高亮）、支出明细折叠面板
- [x] 在 DocumentsPage 建议卡片工厂中注册 `import_u1`、`import_u30`、`import_jahresabschluss` 类型
- [x] 新增 i18n 翻译（zh/en/de）：增值税相关术语（Umsatz/Vorsteuer/Zahllast 等）
- [x] 编写前端测试：验证 U1/U30/Jahresabschluss 卡片正确渲染

**涉及文件**: `frontend/src/components/documents/suggestion-cards/U1SuggestionCard.tsx`, `frontend/src/components/documents/suggestion-cards/U30SuggestionCard.tsx`, `frontend/src/components/documents/suggestion-cards/JahresabschlussSuggestionCard.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/i18n/locales/{zh,en,de}.json`
**对应需求**: 需求 3.4（验收标准 1, 2, 3, 4）

---

## Phase 4: 已有类型提取器补全 + 辅助文件

### Task 4.1: SVS 社保通知提取器实现
- [x] 新建 `backend/app/services/svs_extractor.py`
- [x] 实现 `SvsData` 数据类
- [x] 实现 `SvsExtractor.extract(text)` 方法
- [x] 编写测试 `backend/tests/test_svs_extractor.py`

**涉及文件**: `backend/app/services/svs_extractor.py`, `backend/tests/test_svs_extractor.py`
**对应需求**: 需求 4.1（验收标准 1）

### Task 4.2: SVS Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_svs_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 SVS_NOTICE 验证和建议生成
- [x] 建议中标注社保缴费可作为 Sonderausgaben 扣除
- [x] 编写测试 `backend/tests/test_pipeline_svs.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_svs.py`
**对应需求**: 需求 4.1（验收标准 2）

### Task 4.3: Grundsteuerbescheid 房产税提取器实现
- [x] 新建 `backend/app/services/grundsteuer_extractor.py`
- [x] 实现 `GrundsteuerData` 数据类
- [x] 实现 `GrundsteuerExtractor.extract(text)` 方法
- [x] 实现地址匹配逻辑
- [x] 编写测试 `backend/tests/test_grundsteuer_extractor.py`

**涉及文件**: `backend/app/services/grundsteuer_extractor.py`, `backend/tests/test_grundsteuer_extractor.py`
**对应需求**: 需求 4.2（验收标准 1, 2）

### Task 4.4: Grundsteuer Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_grundsteuer_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 PROPERTY_TAX 验证和建议生成
- [x] 建议生成时查询用户 Property 列表进行地址匹配
- [x] 编写测试 `backend/tests/test_pipeline_grundsteuer.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_grundsteuer.py`
**对应需求**: 需求 4.2（验收标准 2, 3）

### Task 4.5: Kontoauszug 银行对账单提取器实现
- [x] 新建 `backend/app/services/kontoauszug_extractor.py`
- [x] 实现 `KontoauszugData` 数据类
- [x] 实现 `KontoauszugExtractor.extract(text)` 方法
- [x] 实现交易去重
- [x] 编写测试 `backend/tests/test_kontoauszug_extractor.py`

**涉及文件**: `backend/app/services/kontoauszug_extractor.py`, `backend/tests/test_kontoauszug_extractor.py`
**对应需求**: 需求 4.3（验收标准 1, 3）

### Task 4.6: Kontoauszug Pipeline 路由和建议生成
- [x] 在 `ocr_engine.py` 新增 `_route_to_kontoauszug_extractor()` 方法
- [x] 在 `document_pipeline_orchestrator.py` 新增 BANK_STATEMENT 验证和建议生成
- [x] 建议中包含交易列表
- [x] 编写测试 `backend/tests/test_pipeline_kontoauszug.py`

**涉及文件**: `backend/app/services/ocr_engine.py`, `backend/app/services/document_pipeline_orchestrator.py`, `backend/tests/test_pipeline_kontoauszug.py`
**对应需求**: 需求 4.3（验收标准 2）

### Task 4.7: Phase 4 建议卡片（前端）
- [x] 新建 `frontend/src/components/documents/suggestion-cards/SvsSuggestionCard.tsx`：显示社保缴费明细（各险种分组），标注可扣除金额
- [x] 新建 `frontend/src/components/documents/suggestion-cards/GrundsteuerSuggestionCard.tsx`：显示房产税额和匹配的房产信息
- [x] 新建 `frontend/src/components/documents/suggestion-cards/KontoauszugSuggestionCard.tsx`：
  - 以表格形式显示交易列表（日期/金额/对方/用途）
  - 每行有勾选框，允许用户选择要导入的交易
  - 重复交易灰色显示并默认不勾选
  - 底部显示"导入选中的 X 笔交易"按钮
- [x] 在 DocumentsPage 建议卡片工厂中注册 `import_svs`、`import_grundsteuer`、`import_bank_statement` 类型
- [x] 新增 i18n 翻译（zh/en/de）
- [x] 编写前端测试

**涉及文件**: `frontend/src/components/documents/suggestion-cards/SvsSuggestionCard.tsx`, `frontend/src/components/documents/suggestion-cards/GrundsteuerSuggestionCard.tsx`, `frontend/src/components/documents/suggestion-cards/KontoauszugSuggestionCard.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/i18n/locales/{zh,en,de}.json`
**对应需求**: 需求 4.4（验收标准 1, 2, 3）

### Task 4.8: Kontoauszug 批量导入 + 自动分类
- [x] 在 `backend/app/api/v1/endpoints/documents.py` 新增 `POST /documents/{id}/confirm-bank-transactions` 端点
- [x] 端点接收选中的交易 ID 列表，批量创建 Transaction 记录
- [x] 对每笔新建的 Transaction 调用 `TransactionClassifier.classify()` 进行自动分类
- [x] 设置每笔 Transaction 的 `source_document_id` 为对账单文档 ID
- [x] 在 `documentService.ts` 新增 `confirmBankTransactions(documentId: number, transactionIds: number[])` 方法
- [x] 编写测试 `backend/tests/test_bank_transaction_import.py`：
  - 测试批量创建交易
  - 测试自动分类触发
  - 测试重复交易过滤

**涉及文件**: `backend/app/api/v1/endpoints/documents.py`, `frontend/src/services/documentService.ts`, `backend/tests/test_bank_transaction_import.py`
**对应需求**: 需求 4.3（验收标准 2）, 需求 4.4（验收标准 3）

---

## Phase 5: 集成与汇总

### Task 5.1: 建议卡片工厂组件
- [x] 新建 `frontend/src/components/documents/SuggestionCardFactory.tsx`
- [x] 实现统一的卡片路由逻辑：根据 `import_suggestion.type` 渲染对应的建议卡片组件
- [x] 处理未知类型的 fallback（显示通用的 JSON 数据预览卡片）
- [x] 统一卡片样式：所有卡片共享基础布局（标题/图标/字段列表/操作按钮）
- [x] 新建 `frontend/src/components/documents/suggestion-cards/SuggestionCardBase.tsx`：基础卡片组件，提供编辑/确认/忽略的通用逻辑
- [x] 新建 `frontend/src/components/documents/suggestion-cards/SuggestionCardBase.css`
- [x] 将 DocumentsPage 中现有的 Kaufvertrag/Mietvertrag/Kreditvertrag 建议卡片逻辑迁移到工厂模式
- [x] 编写前端测试：验证工厂组件根据不同 type 渲染正确卡片

**涉及文件**: `frontend/src/components/documents/SuggestionCardFactory.tsx`, `frontend/src/components/documents/suggestion-cards/SuggestionCardBase.tsx`, `frontend/src/components/documents/suggestion-cards/SuggestionCardBase.css`, `frontend/src/pages/DocumentsPage.tsx`
**对应需求**: 需求 1.5, 2.4, 3.4, 4.4

### Task 5.2: 税务数据汇总 API
- [x] 新建 `backend/app/api/v1/endpoints/tax_filing.py`
- [x] 实现 `GET /tax-filing/{year}/summary` 端点：
  - 查询指定税年的所有 TaxFilingData 记录
  - 按数据类型分组汇总：收入类（L16/E1a/E1b/E1kv）、扣除类（L1/L1k/L1ab）、增值税类（U1/U30）
  - 计算预估应税收入和预估税额（调用现有 TaxCalculationEngine）
  - 标注每个数据项的来源文档 ID 和文件名
  - 检测数据冲突（如 L16 收入 vs Bescheid 收入不一致）
- [x] 在 `backend/app/main.py` 中注册新路由
- [x] 新建 `backend/app/schemas/tax_filing.py`：定义 TaxFilingSummary 响应 schema
- [x] 编写测试 `backend/tests/test_tax_filing_summary.py`：
  - 测试空数据返回
  - 测试单类型数据汇总
  - 测试多类型数据汇总
  - 测试数据冲突检测

**涉及文件**: `backend/app/api/v1/endpoints/tax_filing.py`, `backend/app/schemas/tax_filing.py`, `backend/app/main.py`, `backend/tests/test_tax_filing_summary.py`
**对应需求**: 需求 5.3（验收标准 1, 2, 3）

### Task 5.3: 税务数据汇总仪表板（前端）
- [x] 在 `frontend/src/pages/TaxToolsPage.tsx` 新增"年度税务数据汇总"面板
- [x] 实现年度选择器（下拉菜单，列出有数据的年份）
- [x] 显示收入汇总卡片：按来源分组（工资/自由职业/租赁/资本收益），每项显示金额和来源文档链接
- [x] 显示扣除汇总卡片：按类别分组（Werbungskosten/Sonderausgaben/außergewöhnliche Belastungen/Familienbonus）
- [x] 显示预估税额卡片：应税收入、适用税率、预估税额、已扣税额、预估退税/补税
- [x] 数据冲突时显示黄色警告条，列出冲突项和来源文档
- [x] 在 `frontend/src/services/taxFilingService.ts` 新增 `getTaxFilingSummary(year: number)` 方法
- [x] 新增 i18n 翻译（zh/en/de）
- [x] 编写前端测试

**涉及文件**: `frontend/src/pages/TaxToolsPage.tsx`, `frontend/src/services/taxFilingService.ts`, `frontend/src/i18n/locales/{zh,en,de}.json`
**对应需求**: 需求 5.3（验收标准 1, 2, 3）

### Task 5.4: 端到端集成测试
- [x] 编写 `backend/tests/test_document_type_integration.py`：
  - 测试每种新文档类型的完整流程：上传 → OCR → 分类 → 提取 → 建议生成 → 确认 → 数据写入
  - 测试亏损结转跨年度流程：上传 E1a（含亏损）→ 确认 → LossCarryforward 更新 → 下一年度 E1 提取时显示可用亏损
  - 测试多文档合并：同年度 2 份 L16 → 合并收入
  - 测试 E1b 地址匹配：上传 E1b → 匹配已有 Property → 确认 → 更新 Property 年度数据
  - 测试 Kontoauszug 批量导入：上传对账单 → 选择交易 → 批量创建 → 自动分类
- [x] 编写 `backend/tests/test_classifier_priority.py`：
  - 测试 L1 vs E1 区分准确性（至少 5 个样本）
  - 测试 E1b vs Mietvertrag 区分准确性
  - 测试 L16 vs 月度工资单区分准确性
  - 测试 U1 vs U30 区分准确性

**涉及文件**: `backend/tests/test_document_type_integration.py`, `backend/tests/test_classifier_priority.py`
**对应需求**: 跨阶段验证

### Task 5.5: 前端集成测试
- [x] 编写 `frontend/src/__tests__/SuggestionCardFactory.test.tsx`：
  - 测试所有 16 种 suggestion type 渲染正确的卡片组件
  - 测试未知 type 渲染 fallback 卡片
  - 测试卡片编辑功能（修改字段值）
  - 测试确认按钮调用正确的 API
  - 测试忽略按钮调用 dismiss API
- [x] 编写 `frontend/src/__tests__/DocumentTypeFilter.test.tsx`：
  - 测试文档类型分组筛选器正确分组
  - 测试选择分组后文档列表正确过滤
- [x] 编写 `frontend/src/__tests__/TaxFilingSummary.test.tsx`：
  - 测试年度选择器
  - 测试收入/扣除/税额汇总卡片渲染
  - 测试数据冲突警告显示

**涉及文件**: `frontend/src/__tests__/SuggestionCardFactory.test.tsx`, `frontend/src/__tests__/DocumentTypeFilter.test.tsx`, `frontend/src/__tests__/TaxFilingSummary.test.tsx`
**对应需求**: 跨阶段验证

---

## 任务统计

| 阶段 | 后端任务 | 前端任务 | 测试文件 | 新建文件 | 修改文件 |
|------|---------|---------|---------|---------|---------|
| Phase 0 | 4 | 1 | 3 | 4 | 4 |
| Phase 1 | 8 | 2 | 9 | 6 | 4 |
| Phase 2 | 6 | 1 | 7 | 4 | 4 |
| Phase 3 | 4 | 1 | 5 | 3 | 4 |
| Phase 4 | 6 | 2 | 7 | 4 | 4 |
| Phase 5 | 2 | 2 | 5 | 5 | 3 |
| **合计** | **30** | **9** | **36** | **26** | **~12** |

## 预估工时

| 阶段 | 预估工时 | 说明 |
|------|---------|------|
| Phase 0 | 3-4h | 基础设施，枚举/模型/端点/翻译 |
| Phase 1 | 8-10h | 4 个提取器 + Pipeline 路由 + 4 个前端卡片 + 合并逻辑 |
| Phase 2 | 6-8h | 3 个提取器 + Pipeline 路由 + 3 个前端卡片 + 地址匹配 |
| Phase 3 | 5-6h | 3 个提取器 + Pipeline 路由 + 3 个前端卡片 |
| Phase 4 | 8-10h | 3 个提取器（Kontoauszug 最复杂）+ Pipeline 路由 + 3 个前端卡片 + 批量导入 |
| Phase 5 | 4-5h | 卡片工厂重构 + 汇总 API + 汇总仪表板 + 集成测试 |
| **合计** | **34-43h** | |
