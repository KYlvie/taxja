# 技术设计：奥地利税务文档类型全面补齐

## 概述

本设计基于现有的 `DocumentPipelineOrchestrator` 架构进行增量扩展。核心思路是：为每种新文档类型创建专用提取器（Extractor），注册到 Pipeline 的路由表中，复用现有的 OCR → 分类 → 验证 → 建议 → 持久化 流程。

## 现有架构分析

### 处理链路
```
文件上传 → MinIO 存储 → OCR Engine (Tesseract/VLM/LLM)
  → DocumentClassifier (关键词匹配)
  → DocumentPipelineOrchestrator:
      _stage_ocr → _stage_classify → _stage_validate → _stage_suggest → _finalize
  → 前端显示 import_suggestion → 用户确认 → 创建记录
```

### 已有专用提取器
- `kaufvertrag_extractor.py` — Kaufvertrag (VLM + Regex)
- `mietvertrag_extractor.py` — Mietvertrag (VLM + Regex)
- `bescheid_extractor.py` — Einkommensteuerbescheid (Regex)
- `e1_form_extractor.py` — E1 Form (Regex + AcroForm)
- `field_extractor.py` — Receipt/Invoice (Regex)
- `llm_extractor.py` — 通用 LLM 后备提取

### 扩展策略
每个新提取器遵循统一接口：

```python
class XxxExtractor:
    def extract(self, text: str) -> XxxData:
        """从 OCR 文本提取结构化数据"""
        ...
    def to_dict(self, data: XxxData) -> Dict[str, Any]:
        """转换为可 JSON 序列化的字典"""
        ...
```

Pipeline 路由扩展（在 `ocr_engine.py` 的 `process_document` 中）：
```python
elif doc_type == DocumentType.L1_FORM:
    return self._route_to_l1_extractor(raw_text, start_time)
elif doc_type == DocumentType.E1A_BEILAGE:
    return self._route_to_e1a_extractor(raw_text, start_time)
# ... 以此类推
```

---

## 数据库变更

### 1. DocumentType 枚举扩展

需要在 PostgreSQL 中扩展 `documenttype` 枚举（通过直接 SQL，因为 Alembic 迁移链已断）：

```sql
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'L1_FORM';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'L1K_BEILAGE';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'L1AB_BEILAGE';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'E1A_BEILAGE';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'E1B_BEILAGE';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'E1KV_BEILAGE';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'U1_FORM';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'U30_FORM';
ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'JAHRESABSCHLUSS';
```

### 2. TaxFilingData 新模型（可选）

用于存储从各类文档提取并确认的年度税务数据汇总：

```python
class TaxFilingData(Base):
    __tablename__ = "tax_filing_data"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tax_year = Column(Integer, nullable=False)
    data_type = Column(String(50), nullable=False)  # 'l16', 'l1', 'e1a', 'e1b', etc.
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    data = Column(JSON, nullable=False)  # 提取的结构化数据
    status = Column(String(20), default="pending")  # pending/confirmed/rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
```

这个模型作为"中间层"，存储从文档提取但尚未最终确认的税务数据。用户确认后，数据流入 TaxReport 或 LossCarryforward 等最终模型。

---

## Phase 1 详细设计：雇员报税系列

### 1.1 L16 Lohnzettel 提取器

**新建文件**: `backend/app/services/l16_extractor.py`

```python
@dataclass
class L16Data:
    tax_year: Optional[int] = None
    employer_name: Optional[str] = None
    employee_name: Optional[str] = None
    sv_nummer: Optional[str] = None          # 社保号
    kz_210: Optional[Decimal] = None         # 总收入
    kz_215: Optional[Decimal] = None         # 免税加班费
    kz_220: Optional[Decimal] = None         # 其他免税收入
    kz_230: Optional[Decimal] = None         # 已扣社保
    kz_245: Optional[Decimal] = None         # 应税收入
    kz_260: Optional[Decimal] = None         # 已扣工资税
    kz_718: Optional[Decimal] = None         # Pendlerpauschale
    kz_719: Optional[Decimal] = None         # Pendlereuro
    familienbonus: Optional[Decimal] = None  # Familienbonus Plus
    telearbeitspauschale: Optional[Decimal] = None
    confidence: float = 0.0
```

提取策略：
1. 优先解析 AcroForm 字段（PDF 表单域）— L16 通常是结构化 PDF
2. 回退到 KZ 码 + 金额的正则匹配
3. 最后回退到 LLM 提取

**修改文件**:
- `backend/app/services/ocr_engine.py` — 新增 `_route_to_l16_extractor()` 方法
- `backend/app/services/document_pipeline_orchestrator.py` — `_stage_validate` 新增 `_validate_lohnzettel()`，`_stage_suggest` 新增 L16 建议生成
- `backend/app/services/document_classifier.py` — 增强 LOHNZETTEL 关键词（区分月度工资单和年度 L16）

### 1.2 L1 Form 提取器

**新建文件**: `backend/app/services/l1_form_extractor.py`

```python
@dataclass
class L1FormData:
    tax_year: Optional[int] = None
    taxpayer_name: Optional[str] = None
    steuernummer: Optional[str] = None
    # Werbungskosten
    kz_717: Optional[Decimal] = None  # Gewerkschaftsbeiträge
    kz_719: Optional[Decimal] = None  # Arbeitsmittel
    kz_720: Optional[Decimal] = None  # Fachliteratur
    kz_721: Optional[Decimal] = None  # Reisekosten
    kz_722: Optional[Decimal] = None  # Fortbildung
    kz_723: Optional[Decimal] = None  # Doppelte Haushaltsführung
    kz_724: Optional[Decimal] = None  # Sonstige Werbungskosten
    # Sonderausgaben
    kz_450: Optional[Decimal] = None  # Topf-Sonderausgaben
    kz_458: Optional[Decimal] = None  # Kirchenbeitrag
    kz_459: Optional[Decimal] = None  # Spenden
    # Außergewöhnliche Belastungen
    kz_730: Optional[Decimal] = None  # mit Selbstbehalt
    kz_740: Optional[Decimal] = None  # ohne Selbstbehalt
    confidence: float = 0.0
```

关键区分逻辑（L1 vs E1）：
- L1 包含 "Arbeitnehmerveranlagung" 或 "L 1" 标识
- E1 包含 "Einkommensteuererklärung" 或 "E 1" 标识
- 在 DocumentClassifier 中添加优先级判断

### 1.3 L1k / L1ab 提取器

**新建文件**: `backend/app/services/l1k_extractor.py`, `backend/app/services/l1ab_extractor.py`

结构类似，提取对应的 KZ 字段。L1k 重点提取子女信息列表，L1ab 重点提取通勤和扣除额信息。

### 1.4 前端变更

**修改文件**:
- `frontend/src/pages/DocumentsPage.tsx` — 新增 L16/L1/L1k/L1ab 建议卡片组件
- `frontend/src/services/documentService.ts` — 新增 `confirmLohnzettel()`, `confirmL1()` 等方法
- `frontend/src/i18n/locales/{zh,en,de}.json` — 新增所有 KZ 字段的翻译

建议卡片设计：
```
┌─────────────────────────────────────────┐
│ 📄 L16 Lohnzettel 2025                 │
│ 雇主: MAGISTRAT DER STADT WIEN         │
│                                         │
│ 收入                                    │
│   总收入 (KZ210):        €45,000.00     │
│   应税收入 (KZ245):      €42,500.00     │
│                                         │
│ 已扣税费                                │
│   工资税 (KZ260):        €8,500.00      │
│   社保 (KZ230):          €6,750.00      │
│                                         │
│ 补贴                                    │
│   通勤补贴 (KZ718):      €696.00        │
│   远程办公 (Telearbeit):  €300.00       │
│                                         │
│  [✏️ 编辑]  [✅ 确认导入]  [❌ 忽略]    │
└─────────────────────────────────────────┘
```

---

## Phase 2 详细设计：自由职业/房东附表

### 2.1 E1a 提取器

**新建文件**: `backend/app/services/e1a_extractor.py`

```python
@dataclass
class E1aData:
    tax_year: Optional[int] = None
    steuernummer: Optional[str] = None
    # 收入
    betriebseinnahmen: Optional[Decimal] = None      # 营业收入
    # 支出（按类别）
    wareneinkauf: Optional[Decimal] = None            # 材料/商品采购
    personalaufwand: Optional[Decimal] = None         # 人工费
    afa: Optional[Decimal] = None                     # 折旧
    mietaufwand: Optional[Decimal] = None             # 办公租金
    reisekosten: Optional[Decimal] = None             # 差旅费
    versicherungen: Optional[Decimal] = None          # 保险费
    sonstige_ausgaben: Optional[Decimal] = None       # 其他支出
    betriebsausgaben_gesamt: Optional[Decimal] = None # 支出合计
    gewinn_verlust: Optional[Decimal] = None          # 利润/亏损
    betriebsausgabenpauschale: Optional[bool] = None  # 是否使用包干扣除
    pauschale_prozent: Optional[int] = None           # 包干扣除比例(6%/12%)
    confidence: float = 0.0
```

### 2.2 E1b 提取器

**新建文件**: `backend/app/services/e1b_extractor.py`

复用现有 `E1FormExtractor` 中的 `RentalPropertyDetail` 数据结构，但作为独立提取器处理纯 E1b 附表。

```python
@dataclass
class E1bData:
    tax_year: Optional[int] = None
    steuernummer: Optional[str] = None
    properties: List[RentalPropertyDetail] = field(default_factory=list)
    total_vv_income: Optional[Decimal] = None  # V+V 总收入
    confidence: float = 0.0
```

### 2.3 E1kv 提取器

**新建文件**: `backend/app/services/e1kv_extractor.py`

```python
@dataclass
class E1kvData:
    tax_year: Optional[int] = None
    # 27.5% 特别税率收入
    aktien_gewinne: Optional[Decimal] = None       # 股票收益
    fonds_gewinne: Optional[Decimal] = None        # 基金收益
    krypto_gewinne: Optional[Decimal] = None       # 加密货币收益
    zinsen: Optional[Decimal] = None               # 利息收入
    dividenden: Optional[Decimal] = None           # 股息收入
    # 已扣税
    kest_einbehalten: Optional[Decimal] = None     # 已扣 KESt
    # 应补税
    nachversteuerung: Optional[Decimal] = None     # 应补税额
    confidence: float = 0.0
```

---

## Phase 3 详细设计：增值税 + 财务报表

### 3.1 U1/U30 提取器

**新建文件**: `backend/app/services/vat_form_extractor.py`

```python
@dataclass
class VatFormData:
    form_type: str = "u1"  # "u1" or "u30"
    tax_year: Optional[int] = None
    period: Optional[str] = None  # "2025" for U1, "Q1 2025" for U30
    # 营业额按税率分
    umsatz_20: Optional[Decimal] = None   # 20% 税率营业额
    umsatz_13: Optional[Decimal] = None   # 13% 税率营业额
    umsatz_10: Optional[Decimal] = None   # 10% 税率营业额
    umsatz_0: Optional[Decimal] = None    # 免税营业额
    umsatz_gesamt: Optional[Decimal] = None
    # 税额
    ust_gesamt: Optional[Decimal] = None  # 总销项税
    vorsteuer: Optional[Decimal] = None   # 总进项税
    zahllast: Optional[Decimal] = None    # 应缴税额(正)或退税额(负)
    confidence: float = 0.0
```

### 3.2 Jahresabschluss 提取器

**新建文件**: `backend/app/services/jahresabschluss_extractor.py`

```python
@dataclass
class JahresabschlussData:
    tax_year: Optional[int] = None
    format_type: str = "ea"  # "ea" (收支法) or "bilanz" (双式簿记)
    einnahmen_gesamt: Optional[Decimal] = None
    ausgaben_gesamt: Optional[Decimal] = None
    gewinn_verlust: Optional[Decimal] = None
    afa_gesamt: Optional[Decimal] = None
    # 支出明细
    ausgaben_detail: Dict[str, Decimal] = field(default_factory=dict)
    confidence: float = 0.0
```

---

## Phase 4 详细设计：已有类型提取器补全

### 4.1 SVS 提取器

**新建文件**: `backend/app/services/svs_extractor.py`

### 4.2 Grundsteuer 提取器

**新建文件**: `backend/app/services/grundsteuer_extractor.py`

### 4.3 Kontoauszug 提取器

**新建文件**: `backend/app/services/kontoauszug_extractor.py`

银行对账单提取是最复杂的，因为各银行格式差异大。策略：
1. 先尝试 CSV/MT940 格式解析（如果用户上传的是导出文件）
2. 回退到 LLM 提取（PDF 对账单）
3. 支持主流银行模板：Erste Bank、Raiffeisen、Bank Austria、BAWAG

---

## 前端整体变更

### DocumentsPage 建议卡片工厂

新增 `SuggestionCardFactory` 组件，根据 `import_suggestion.type` 渲染不同的卡片：

```typescript
const SUGGESTION_CARD_MAP: Record<string, React.FC<SuggestionCardProps>> = {
  'create_property': KaufvertragSuggestionCard,
  'create_recurring': MietvertragSuggestionCard,
  'create_loan': KreditvertragSuggestionCard,
  'import_lohnzettel': LohnzettelSuggestionCard,
  'import_l1': L1SuggestionCard,
  'import_l1k': L1kSuggestionCard,
  'import_l1ab': L1abSuggestionCard,
  'import_e1a': E1aSuggestionCard,
  'import_e1b': E1bSuggestionCard,
  'import_e1kv': E1kvSuggestionCard,
  'import_u1': U1SuggestionCard,
  'import_u30': U30SuggestionCard,
  'import_jahresabschluss': JahresabschlussSuggestionCard,
  'import_svs': SvsSuggestionCard,
  'import_grundsteuer': GrundsteuerSuggestionCard,
  'import_bank_statement': KontoauszugSuggestionCard,
};
```

### 文档类型分组筛选器

```typescript
const DOCUMENT_TYPE_GROUPS = {
  employee: ['LOHNZETTEL', 'L1_FORM', 'L1K_BEILAGE', 'L1AB_BEILAGE'],
  selfEmployed: ['E1_FORM', 'E1A_BEILAGE', 'E1KV_BEILAGE'],
  landlord: ['E1B_BEILAGE', 'PURCHASE_CONTRACT', 'RENTAL_CONTRACT', 'PROPERTY_TAX'],
  business: ['U1_FORM', 'U30_FORM', 'JAHRESABSCHLUSS'],
  general: ['RECEIPT', 'INVOICE', 'BANK_STATEMENT', 'LOAN_CONTRACT', 'SVS_NOTICE'],
  assessment: ['EINKOMMENSTEUERBESCHEID'],
};
```

### API 端点扩展

新增确认端点（`backend/app/api/v1/endpoints/documents.py`）：

```python
POST /documents/{id}/confirm-tax-data   # 通用确认端点，根据 suggestion.type 路由
```

统一使用一个端点而非每种类型一个，减少 API 膨胀。

---

## 测试策略

### 单元测试（每个提取器）

每个新提取器需要：
1. **正向测试**: 使用真实文档样本的 OCR 文本，验证所有字段正确提取
2. **边界测试**: 空文本、部分字段缺失、格式异常
3. **置信度测试**: 验证不同质量的输入产生合理的置信度分数

测试文件命名：`backend/tests/test_{extractor_name}.py`

### 集成测试

1. **Pipeline 路由测试**: 验证新文档类型正确路由到对应提取器
2. **确认流程测试**: 验证用户确认后数据正确写入目标模型
3. **多文档合并测试**: 验证同一税年多份 L16 的合并逻辑

### 前端测试

1. **建议卡片渲染测试**: 验证每种 suggestion type 渲染正确的卡片
2. **编辑和确认流程测试**: 验证用户编辑字段后确认的数据正确

---

## 涉及文件汇总

### 新建文件
- `backend/app/services/l16_extractor.py`
- `backend/app/services/l1_form_extractor.py`
- `backend/app/services/l1k_extractor.py`
- `backend/app/services/l1ab_extractor.py`
- `backend/app/services/e1a_extractor.py`
- `backend/app/services/e1b_extractor.py`
- `backend/app/services/e1kv_extractor.py`
- `backend/app/services/vat_form_extractor.py`
- `backend/app/services/jahresabschluss_extractor.py`
- `backend/app/services/svs_extractor.py`
- `backend/app/services/grundsteuer_extractor.py`
- `backend/app/services/kontoauszug_extractor.py`
- `backend/tests/test_l16_extractor.py`
- `backend/tests/test_l1_form_extractor.py`
- `backend/tests/test_l1k_extractor.py`
- `backend/tests/test_l1ab_extractor.py`
- `backend/tests/test_e1a_extractor.py`
- `backend/tests/test_e1b_extractor.py`
- `backend/tests/test_e1kv_extractor.py`
- `backend/tests/test_vat_form_extractor.py`
- `backend/tests/test_jahresabschluss_extractor.py`
- `backend/tests/test_svs_extractor.py`
- `backend/tests/test_grundsteuer_extractor.py`
- `backend/tests/test_kontoauszug_extractor.py`
- `frontend/src/components/documents/SuggestionCardFactory.tsx`
- `frontend/src/components/documents/suggestion-cards/` (各类型卡片组件)

### 修改文件
- `backend/app/models/document.py` — DocumentType 枚举扩展
- `backend/app/services/document_classifier.py` — 新增分类模式 + DocumentType 同步
- `backend/app/services/ocr_engine.py` — 新增路由方法
- `backend/app/services/document_pipeline_orchestrator.py` — 新增验证和建议生成
- `backend/app/schemas/document.py` — 新增 schema 支持
- `backend/app/api/v1/endpoints/documents.py` — 新增确认端点
- `frontend/src/pages/DocumentsPage.tsx` — 建议卡片工厂 + 类型分组筛选
- `frontend/src/services/documentService.ts` — 新增确认方法
- `frontend/src/i18n/locales/zh.json` — 中文翻译
- `frontend/src/i18n/locales/en.json` — 英文翻译
- `frontend/src/i18n/locales/de.json` — 德文翻译
