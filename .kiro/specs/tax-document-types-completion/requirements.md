# 需求文档：奥地利税务文档类型全面补齐

## 简介

Taxja 系统当前支持 13 种文档类型（DocumentType 枚举），但其中仅 Kaufvertrag、Mietvertrag、Kreditvertrag、Receipt、Invoice、Einkommensteuerbescheid、E1 Form 拥有完善的专用提取器。其余类型（Lohnzettel/L16、SVS、Grundsteuer、Kontoauszug）仅能分类但无法提取结构化数据。

更关键的是，奥地利税务申报体系中大量核心表格完全缺失：雇员报税系列（L1/L1k/L1ab）、自由职业附表（E1a）、租赁附表（E1b）、资本收益附表（E1kv）、增值税系列（U1/U30）、年度财务报表（Jahresabschluss）等。

本功能将系统性补齐所有缺失的文档类型，使 Taxja 能够完整支持奥地利四类目标用户（雇员、房东、自由职业者、小企业主）的报税需求。

## 术语表

- **KZ (Kennzahl)**: 奥地利税表中的字段编号，如 KZ245 = 应税工资收入
- **Beilage**: 附表，主表的补充表格（如 E1a 是 E1 的附表）
- **Werbungskosten**: 工作相关费用扣除（雇员）
- **Sonderausgaben**: 特殊支出扣除（捐赠、教会税等）
- **Außergewöhnliche Belastungen**: 特殊负担扣除（医疗费等）
- **Familienbonus Plus**: 家庭奖金，每个孩子最高 €2,000.16/年的税收抵免
- **Pendlerpauschale**: 通勤补贴
- **Einnahmen-Ausgaben-Rechnung (E/A)**: 收支计算法，自由职业者/小企业主的简化记账方式
- **AfA (Absetzung für Abnutzung)**: 折旧
- **Vorsteuer**: 进项税（可抵扣的增值税）
- **Umsatzsteuer**: 销项税（收取的增值税）
- **UVA (Umsatzsteuervoranmeldung)**: 增值税预申报
- **Verlustvortrag**: 亏损结转
- **DocumentPipelineOrchestrator**: 现有的文档处理管道，负责 OCR → 分类 → 验证 → 建议 → 持久化
- **DocumentClassifier**: 文档分类器，基于关键词模式匹配判断文档类型
- **FieldExtractor**: 字段提取器，使用正则表达式从 OCR 文本中提取结构化数据
- **LLM Extractor**: 大语言模型提取器，当正则提取置信度不足时的后备方案
- **VLM (Vision Language Model)**: 视觉语言模型，直接从文档图像提取数据

## 实施阶段划分

本项目分为 4 个阶段（Phase），按优先级递减排列：

- **Phase 1**: 雇员报税系列（L1/L1k/L1ab/L16 专用提取器）— 覆盖最大用户群
- **Phase 2**: 自由职业/房东附表（E1a/E1b/E1kv）— 覆盖第二大用户群
- **Phase 3**: 增值税系列 + 财务报表（U1/U30/Jahresabschluss）— 企业用户
- **Phase 4**: 已有类型提取器补全 + 辅助文件（SVS/Grundsteuer/Kontoauszug 等）

---

## Phase 1: 雇员报税系列

### 需求 1.1：L16 Lohnzettel 专用提取器

**用户故事：** 作为雇员，我希望上传 L16 工资税卡后系统能自动提取我的年度收入、已扣税额和社保缴费，用于自动填充报税数据。

#### 验收标准

1. WHEN 用户上传一份 L16 Lohnzettel 文档, THE DocumentClassifier SHALL 将其识别为 `LOHNZETTEL` 类型，Confidence_Score ≥ 0.7
2. WHEN OCR_Pipeline 处理 LOHNZETTEL 类型文档, THE L16Extractor SHALL 提取以下字段：雇主名称、税年、总收入(KZ210)、应税收入(KZ245)、已扣工资税(KZ260)、已扣社保(KZ230)、免税收入、Pendlerpauschale(KZ718)、Pendlereuro(KZ719)、Telearbeitspauschale、Familienbonus Plus
3. WHEN L16Extractor 成功提取数据, THE DocumentPipelineOrchestrator SHALL 将提取结果存入 `document.ocr_result` 并生成 `import_suggestion`（type: `import_lohnzettel`），建议将数据导入用户的年度税务记录
4. IF L16Extractor 的 Confidence_Score 低于 0.6, THEN THE Pipeline SHALL 标记文档为"需人工确认"
5. THE L16Extractor SHALL 支持多雇主场景（同一年度多份 L16）

### 需求 1.2：L1 雇员报税主表提取器

**用户故事：** 作为雇员，我希望上传已填写的 L1 表后系统能提取我的报税数据，用于核对和存档。

#### 验收标准

1. WHEN 用户上传一份 L1 表, THE DocumentClassifier SHALL 将其识别为 `L1_FORM` 类型
2. WHEN OCR_Pipeline 处理 L1_FORM 类型文档, THE L1FormExtractor SHALL 提取以下字段：税年、纳税人姓名、税号(Steuernummer)、Werbungskosten 各项（KZ717-724）、Sonderausgaben（KZ450/458/459）、außergewöhnliche Belastungen（KZ730/740）
3. WHEN L1FormExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_l1`），建议将扣除项数据导入系统
4. THE L1FormExtractor SHALL 能区分 L1 表和 E1 表（两者结构不同）

### 需求 1.3：L1k 子女附表提取器

**用户故事：** 作为有子女的雇员，我希望上传 L1k 附表后系统能提取 Familienbonus Plus 和子女相关扣除信息。

#### 验收标准

1. WHEN 用户上传一份 L1k 附表, THE DocumentClassifier SHALL 将其识别为 `L1K_BEILAGE` 类型
2. WHEN OCR_Pipeline 处理 L1K_BEILAGE 类型文档, THE L1kExtractor SHALL 提取以下字段：每个孩子的姓名、出生日期、Familienbonus Plus 金额(KZ770)、Kindermehrbetrag、Unterhaltsabsetzbetrag
3. WHEN L1kExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_l1k`），建议将子女扣除数据导入系统

### 需求 1.4：L1ab 扣除额附表提取器

**用户故事：** 作为雇员，我希望上传 L1ab 附表后系统能提取通勤补贴和其他扣除额信息。

#### 验收标准

1. WHEN 用户上传一份 L1ab 附表, THE DocumentClassifier SHALL 将其识别为 `L1AB_BEILAGE` 类型
2. WHEN OCR_Pipeline 处理 L1AB_BEILAGE 类型文档, THE L1abExtractor SHALL 提取以下字段：Alleinverdiener/Alleinerzieher 状态、Pendlerpauschale 金额和公里数、Pendlereuro、Unterhaltsabsetzbetrag
3. WHEN L1abExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_l1ab`）

### 需求 1.5：雇员文档导入确认流程（前端）

**用户故事：** 作为雇员，我希望在上传 L16/L1/L1k/L1ab 后能预览提取的数据并确认导入，确保数据准确。

#### 验收标准

1. WHEN OCR_Pipeline 生成雇员类 import_suggestion, THE DocumentsPage SHALL 显示对应的建议卡片，包含所有提取的 KZ 字段及其金额
2. THE 建议卡片 SHALL 按类别分组显示字段：收入类、扣除类、社保类、家庭类
3. WHEN 用户点击"确认导入", THE 系统 SHALL 将提取的数据存入用户的年度税务记录（TaxReport 或新建的 TaxFilingData 模型）
4. THE 建议卡片 SHALL 允许用户在确认前编辑任何字段的金额
5. WHEN 同一税年存在多份 L16, THE 系统 SHALL 自动合并多个雇主的收入数据

---

## Phase 2: 自由职业/房东附表

### 需求 2.1：E1a 自由职业收入附表提取器

**用户故事：** 作为自由职业者，我希望上传 E1a 附表后系统能提取我的营业收入和支出明细，用于所得税计算。

#### 验收标准

1. WHEN 用户上传一份 E1a 附表, THE DocumentClassifier SHALL 将其识别为 `E1A_BEILAGE` 类型
2. WHEN OCR_Pipeline 处理 E1A_BEILAGE 类型文档, THE E1aExtractor SHALL 提取以下字段：营业收入总额、营业支出总额（按类别：材料费、人工费、折旧、办公费、差旅费、保险费等）、净利润/亏损、Betriebsausgabenpauschale（经营费用包干扣除）
3. WHEN E1aExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_e1a`），建议将自由职业收支数据导入系统
4. THE E1aExtractor SHALL 支持 Einnahmen-Ausgaben-Rechnung（收支计算法）和 Bilanzierung（双式簿记）两种格式
5. WHEN 提取到亏损金额, THE Pipeline SHALL 自动更新 LossCarryforward 模型中对应年度的亏损记录

### 需求 2.2：E1b 租赁收入附表提取器

**用户故事：** 作为房东，我希望上传 E1b 附表后系统能提取每套房产的租赁收支明细，用于 V+V 收入计算。

#### 验收标准

1. WHEN 用户上传一份 E1b 附表, THE DocumentClassifier SHALL 将其识别为 `E1B_BEILAGE` 类型
2. WHEN OCR_Pipeline 处理 E1B_BEILAGE 类型文档, THE E1bExtractor SHALL 提取以下字段（每套房产）：房产地址、租金收入(KZ9460)、AfA 折旧(KZ9500)、贷款利息(KZ9510)、维修费(KZ9520)、其他费用(KZ9530)、净租赁收入(KZ9414)
3. WHEN E1bExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_e1b`），并尝试将每套房产的数据与系统中已有的 Property 记录进行地址匹配
4. IF 提取的房产地址与系统中某个 Property 匹配, THEN THE Pipeline SHALL 在 suggestion 中标记 `matched_property_id`
5. WHEN 用户确认导入, THE 系统 SHALL 更新对应 Property 的年度租赁收支数据

### 需求 2.3：E1kv 资本收益附表提取器

**用户故事：** 作为投资者，我希望上传 E1kv 附表后系统能提取我的资本收益和已扣 KESt 信息。

#### 验收标准

1. WHEN 用户上传一份 E1kv 附表, THE DocumentClassifier SHALL 将其识别为 `E1KV_BEILAGE` 类型
2. WHEN OCR_Pipeline 处理 E1KV_BEILAGE 类型文档, THE E1kvExtractor SHALL 提取以下字段：股票/基金收益、加密货币收益、利息收入、股息收入、已扣 KESt 税额、应补税额
3. WHEN E1kvExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_e1kv`）
4. THE E1kvExtractor SHALL 区分 27.5% 特别税率收入和普通税率收入

### 需求 2.4：自由职业/房东文档导入确认流程（前端）

**用户故事：** 作为自由职业者或房东，我希望在上传 E1a/E1b/E1kv 后能预览提取的数据并确认导入。

#### 验收标准

1. WHEN OCR_Pipeline 生成 E1a/E1b/E1kv 类 import_suggestion, THE DocumentsPage SHALL 显示对应的建议卡片
2. E1b 建议卡片 SHALL 按房产分组显示，每套房产显示收入和各项支出明细
3. WHEN E1b 建议中存在 `matched_property_id`, THE 卡片 SHALL 显示匹配的房产名称和地址
4. WHEN 用户确认 E1a 导入且存在亏损, THE 系统 SHALL 自动创建/更新 LossCarryforward 记录
5. THE 建议卡片 SHALL 允许用户在确认前编辑任何字段

---

## Phase 3: 增值税系列 + 财务报表

### 需求 3.1：U1 年度增值税申报提取器

**用户故事：** 作为自由职业者/企业主，我希望上传 U1 年度增值税申报后系统能提取年度 VAT 汇总数据。

#### 验收标准

1. WHEN 用户上传一份 U1 表, THE DocumentClassifier SHALL 将其识别为 `U1_FORM` 类型
2. WHEN OCR_Pipeline 处理 U1_FORM 类型文档, THE U1Extractor SHALL 提取以下字段：税年、年度总营业额（按税率分：20%/13%/10%/0%）、总销项税、总进项税(Vorsteuer)、应补/退税额
3. WHEN U1Extractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_u1`）

### 需求 3.2：U30 增值税预申报(UVA)提取器

**用户故事：** 作为自由职业者/企业主，我希望上传月度/季度 UVA 后系统能提取当期 VAT 数据，用于增值税追踪。

#### 验收标准

1. WHEN 用户上传一份 U30 表, THE DocumentClassifier SHALL 将其识别为 `U30_FORM` 类型
2. WHEN OCR_Pipeline 处理 U30_FORM 类型文档, THE U30Extractor SHALL 提取以下字段：申报期间（月/季度）、当期营业额（按税率分）、当期销项税、当期进项税、应缴税额
3. WHEN U30Extractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_u30`）

### 需求 3.3：Jahresabschluss 年度财务报表提取器

**用户故事：** 作为自由职业者/企业主，我希望上传年度财务报表后系统能提取年度收支汇总和利润/亏损数据。

#### 验收标准

1. WHEN 用户上传一份 Jahresabschluss, THE DocumentClassifier SHALL 将其识别为 `JAHRESABSCHLUSS` 类型
2. WHEN OCR_Pipeline 处理 JAHRESABSCHLUSS 类型文档, THE JahresabschlussExtractor SHALL 提取以下字段：税年、总收入、总支出（按类别）、净利润/亏损、资产折旧明细
3. WHEN 提取到亏损金额, THE Pipeline SHALL 自动更新 LossCarryforward 模型
4. THE JahresabschlussExtractor SHALL 支持 E/A（收支计算法）和 Bilanz（资产负债表）两种格式

### 需求 3.4：增值税/财务报表导入确认流程（前端）

**用户故事：** 作为企业用户，我希望在上传 U1/U30/Jahresabschluss 后能预览和确认导入。

#### 验收标准

1. WHEN OCR_Pipeline 生成 U1/U30/Jahresabschluss 类 import_suggestion, THE DocumentsPage SHALL 显示对应的建议卡片
2. U1/U30 建议卡片 SHALL 按税率分组显示营业额和税额
3. Jahresabschluss 建议卡片 SHALL 显示收支汇总和利润/亏损
4. WHEN 用户确认导入, THE 系统 SHALL 将数据存入对应的年度税务记录

---

## Phase 4: 已有类型提取器补全 + 辅助文件

### 需求 4.1：SVS 社保通知专用提取器

**用户故事：** 作为自由职业者，我希望上传 SVS 缴费通知后系统能提取年度社保缴费明细，用于税务扣除计算。

#### 验收标准

1. WHEN OCR_Pipeline 处理 SVS_NOTICE 类型文档, THE SvsExtractor SHALL 提取以下字段：缴费年度、缴费总额、养老保险(Pensionsversicherung)、医疗保险(Krankenversicherung)、意外保险(Unfallversicherung)、缴费基数(Beitragsgrundlage)
2. WHEN SvsExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_svs`），建议将社保缴费数据导入系统作为可扣除支出

### 需求 4.2：Grundsteuerbescheid 房产税通知提取器

**用户故事：** 作为房东，我希望上传房产税通知后系统能提取年度房产税额，自动关联到对应房产。

#### 验收标准

1. WHEN OCR_Pipeline 处理 PROPERTY_TAX 类型文档, THE GrundsteuerExtractor SHALL 提取以下字段：房产地址、年度房产税额、Einheitswert（统一评估值）、税率
2. WHEN GrundsteuerExtractor 成功提取数据, THE Pipeline SHALL 尝试将房产地址与系统中已有的 Property 记录匹配
3. IF 匹配成功, THEN THE Pipeline SHALL 生成 `import_suggestion`（type: `import_grundsteuer`），建议将房产税作为该房产的年度支出

### 需求 4.3：Kontoauszug 银行对账单提取器

**用户故事：** 作为纳税人，我希望上传银行对账单后系统能提取交易明细，用于自动匹配和分类。

#### 验收标准

1. WHEN OCR_Pipeline 处理 BANK_STATEMENT 类型文档, THE KontoauszugExtractor SHALL 提取以下字段：银行名称、账号(IBAN)、对账期间、每笔交易的日期/金额/对方/用途
2. WHEN KontoauszugExtractor 成功提取数据, THE Pipeline SHALL 生成 `import_suggestion`（type: `import_bank_statement`），建议批量导入交易记录
3. THE KontoauszugExtractor SHALL 支持主流奥地利银行的对账单格式（Erste Bank、Raiffeisen、Bank Austria、BAWAG）

### 需求 4.4：辅助文件提取器补全（前端）

**用户故事：** 作为纳税人，我希望在上传 SVS/Grundsteuer/Kontoauszug 后能预览和确认导入。

#### 验收标准

1. WHEN OCR_Pipeline 生成 SVS/Grundsteuer/Kontoauszug 类 import_suggestion, THE DocumentsPage SHALL 显示对应的建议卡片
2. Kontoauszug 建议卡片 SHALL 以表格形式显示交易列表，允许用户勾选要导入的交易
3. WHEN 用户确认导入 Kontoauszug, THE 系统 SHALL 对每笔交易运行 TransactionClassifier 进行自动分类

---

## 跨阶段需求

### 需求 5.1：DocumentType 枚举扩展

**验收标准：**

1. THE DocumentType 枚举（`backend/app/models/document.py`）SHALL 新增以下值：`L1_FORM`、`L1K_BEILAGE`、`L1AB_BEILAGE`、`E1A_BEILAGE`、`E1B_BEILAGE`、`E1KV_BEILAGE`、`U1_FORM`、`U30_FORM`、`JAHRESABSCHLUSS`
2. THE DocumentClassifier（`backend/app/services/document_classifier.py`）的 DocumentType 枚举 SHALL 同步新增对应值
3. THE DocumentClassifier SHALL 为每个新增类型添加关键词匹配模式
4. THE PostgreSQL 数据库中的 `documenttype` 枚举 SHALL 通过 SQL 扩展新增值
5. THE 前端文档类型选择器 SHALL 显示所有新增的文档类型，并提供中/英/德三语翻译

### 需求 5.2：文档上传页文档类型分组显示

**验收标准：**

1. THE DocumentsPage 的文档类型筛选器 SHALL 按类别分组显示：雇员类（L16/L1/L1k/L1ab）、自由职业类（E1/E1a/E1kv）、房东类（E1b/Kaufvertrag/Mietvertrag/Grundsteuer）、企业类（U1/U30/Jahresabschluss）、通用类（Receipt/Invoice/Kontoauszug）
2. THE 文档列表 SHALL 支持按文档类型分组筛选

### 需求 5.3：税务数据汇总仪表板

**验收标准：**

1. WHEN 用户导入了某个税年的多份文档, THE TaxToolsPage SHALL 显示该年度的税务数据汇总：总收入（按来源分）、总扣除（按类别分）、预估应税收入、预估税额
2. THE 汇总 SHALL 标注每个数据项的来源文档，方便用户追溯
3. WHEN 数据存在冲突（如 L16 的收入与 Bescheid 的收入不一致）, THE 系统 SHALL 显示警告提示
