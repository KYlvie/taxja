# 实施任务：奥地利税务数据准确性审计

## 任务概览

共 12 个任务，按优先级排序。每个任务包含具体的文件修改和验证步骤。

**进度: 11/12 完成**

---

- [x] 1. 修正 Pendlerpauschale（通勤补贴）值
  - **优先级**: P0
  - **需求**: REQ-2.1, REQ-2.2, REQ-2.5
  - **文件**: `backend/app/services/deduction_calculator.py`, `backend/app/models/tax_configuration.py`
  - **修改内容**:
    - 修正 `COMMUTE_BRACKETS_LARGE` 常量:
      - 新增 `2: Decimal('31.00')` (2-20km 档位)
      - 修改 `20: Decimal('123.00')` (原为 €31)
      - 修改 `40: Decimal('214.00')` (原为 €123)
      - 修改 `60: Decimal('306.00')` (原为 €214)
    - 修改 `calculate_commuting_allowance` 方法:
      - Großes Pendlerpauschale 最低距离从 20km 改为 2km
      - 更新距离判断逻辑以支持 2-20km 档位
    - 更新 `tax_configuration.py` 中 `get_2026_tax_config()` 的 `commuting_brackets.large`
  - **验证**: 运行 `pytest backend/tests/test_deduction_calculator.py`
  - **完成说明**: `COMMUTE_BRACKETS_LARGE` 已更新为 {2: €31, 20: €123, 40: €214, 60: €306}，`calculate_commuting_allowance` 已支持 2km 起始距离，`get_2026_tax_config()` 已同步更新。

- [x] 2. 更新 Pendlerpauschale 测试和相关文件
  - **优先级**: P0
  - **需求**: REQ-2.3, REQ-2.4
  - **文件**: `backend/tests/test_deduction_calculator.py`, `backend/app/services/knowledge_base_service.py`, `backend/app/services/e1_form_service.py`
  - **修改内容**:
    - 更新测试中的期望值以匹配新的 Großes Pendlerpauschale 值
    - 添加 2-20km 档位的测试用例
    - 更新 `knowledge_base_service.py` 中 Pendlerpauschale 描述（三种语言）:
      - Großes: 2-20km €31/月, 20-40km €123/月, 40-60km €214/月, 60km+ €306/月
    - 验证 `e1_form_service.py` L1 表单中的年度值与新月度值一致
  - **验证**: 运行 `pytest backend/tests/test_deduction_calculator.py` 和 `pytest backend/tests/ -k pendler`
  - **完成说明**: 测试已包含所有档位的 property-based 测试（含 2-20km）。`knowledge_base_service.py` 三种语言描述已正确。`e1_form_service.py` L1 表单年度值（€372/€1,476/€2,568/€3,672）与月度值×12 一致。

- [x] 3. 修正所得税级距文档一致性
  - **优先级**: P0
  - **需求**: REQ-1.1, REQ-1.2, REQ-1.3
  - **文件**: `backend/app/services/income_tax_calculator.py`, `backend/app/services/dashboard_service.py`
  - **修改内容**:
    - 更新 `IncomeTaxCalculator` 类文档字符串中的级距值为 2026 正确值:
      - €0 – €13,539: 0%
      - €13,539 – €21,992: 20%
      - €21,992 – €36,458: 30%
      - €36,458 – €70,365: 40%
      - €70,365 – €104,859: 48%
      - €104,859 – €1,000,000: 50%
      - €1,000,000+: 55%
    - 验证 `dashboard_service.py` 中的级距宽度计算（已确认正确，添加注释说明）
  - **验证**: 运行 `pytest backend/tests/test_income_tax_properties.py`
  - **完成说明**: `income_tax_calculator.py` 文档字符串已显示正确的 2026 级距。`dashboard_service.py` 级距宽度（€8,453/€14,466/€33,907/€34,494/€895,141）和免税额 €13,539 均已正确。`knowledge_base_service.py` 三种语言描述也已正确。

- [x] 4. 更新 Basispauschalierung 费率
  - **优先级**: P1
  - **需求**: REQ-3.1, REQ-3.2, REQ-3.3
  - **文件**: `backend/app/services/flat_rate_tax_comparator.py`, `backend/app/services/knowledge_base_service.py`
  - **修改内容**:
    - 将 `FLAT_RATE_12_PERCENT = Decimal("0.12")` 改为 `FLAT_RATE_13_5_PERCENT = Decimal("0.135")`
    - 将枚举 `BASIC_12 = "basic_12"` 改为 `BASIC_13_5 = "basic_13_5"`
    - 更新 `_calculate_flat_rate()` 中的引用: `FlatRateType.BASIC_12` → `FlatRateType.BASIC_13_5`，`self.FLAT_RATE_12_PERCENT` → `self.FLAT_RATE_13_5_PERCENT`，`rate_label = "12%"` → `"13.5%"`
    - 更新 `_check_eligibility()` 添加营业额上限 €320,000 检查
    - 更新 `_generate_comparison_summary()` 和 `_generate_recommendation_explanation()` 中的 12% 引用
    - 在 `knowledge_base_service.py` 中添加 Basispauschalierung 描述（三种语言），当前完全缺失
  - **当前状态**: 枚举已更新为 `BASIC_13_5 = "basic_13_5"`，常量已更新为 `FLAT_RATE_13_5_PERCENT = Decimal("0.135")`
  - **验证**: 运行 `pytest backend/tests/test_flat_rate_comparison_properties.py`
  - **完成说明**: `FlatRateType.BASIC_13_5` 枚举和 `FLAT_RATE_13_5_PERCENT = Decimal("0.135")` 常量已就位。`_check_eligibility()` 包含 €320,000 营业额上限检查。`_calculate_flat_rate()` / `_generate_comparison_summary()` / `_generate_recommendation_explanation()` 均使用 13.5% 引用。`knowledge_base_service.py` 已有三语 Basispauschalierung 条目（13.5%/6%/€320,000/Grundfreibetrag 15% max €4,950/利润上限 €33,000）。

- [x] 5. 实现缺失的 Absetzbeträge - Werbungskostenpauschale 和 Verkehrsabsetzbetrag
  - **优先级**: P1
  - **需求**: REQ-4.1, REQ-4.4
  - **文件**: `backend/app/services/deduction_calculator.py`, `backend/app/services/tax_calculation_engine.py`
  - **修改内容**:
    - 在 `deduction_calculator.py` 中添加:
      - `WERBUNGSKOSTENPAUSCHALE = Decimal('132.00')` — 雇员标准扣除，从收入中扣除
      - `VERKEHRSABSETZBETRAG = Decimal('463.00')` — 交通税收抵免，从税额中扣除
    - 添加 `calculate_employee_deductions()` 方法
    - 在 `tax_calculation_engine.py` 的 `calculate_total_tax()` 中:
      - 对雇员用户自动应用 Werbungskostenpauschale（除非实际 Werbungskosten 更高）
      - 对雇员用户自动应用 Verkehrsabsetzbetrag（从税额中扣除）
  - **当前状态**: `deduction_calculator.py` 已包含 `WERBUNGSKOSTENPAUSCHALE = Decimal('132.00')` 和 `VERKEHRSABSETZBETRAG = Decimal('463.00')` 及 `calculate_employee_deductions()` 方法。`tax_calculation_engine.py` 的 `calculate_total_tax()` 已对雇员用户应用 Werbungskostenpauschale（从收入扣除）和 Verkehrsabsetzbetrag（从税额扣除）
  - **验证**: 添加新测试并运行
  - **完成说明**: `deduction_calculator.py` 新增 `WERBUNGSKOSTENPAUSCHALE = Decimal('132.00')`、`VERKEHRSABSETZBETRAG = Decimal('463.00')` 和 `calculate_employee_deductions()` 方法。`tax_calculation_engine.py` 在步骤 4b 中对雇员自动应用 Verkehrsabsetzbetrag 作为税收抵免。Werbungskostenpauschale 通过 `calculate_total_deductions(is_employee=True)` 从收入中扣除。

- [x] 6. 集成 Familienbonus Plus 和 Alleinverdienerabsetzbetrag
  - **优先级**: P1
  - **需求**: REQ-4.2, REQ-4.3
  - **文件**: `backend/app/services/deduction_calculator.py`, `backend/app/services/tax_calculation_engine.py`
  - **修改内容**:
    - 在 `deduction_calculator.py` 中添加:
      - `FAMILIENBONUS_UNDER_18 = Decimal('2000.00')`
      - `FAMILIENBONUS_18_24 = Decimal('700.00')`
      - `ALLEINVERDIENER_BASE = Decimal('520.00')`
      - `ALLEINVERDIENER_PER_CHILD = Decimal('704.00')`
    - 扩展 `FamilyInfo` dataclass 添加子女年龄信息（当前仅有 `num_children` 和 `is_single_parent`）
    - 添加 `calculate_familienbonus()` 和 `calculate_alleinverdiener()` 方法
    - 在 `tax_calculation_engine.py` 中集成（从税额中扣除）
  - **当前状态**: `FamilyInfo` 已扩展为包含 `children_under_18: int`、`children_18_to_24: int`、`is_sole_earner: bool`。已有 `FAMILIENBONUS_UNDER_18/18_24` 和 `ALLEINVERDIENER_BASE/PER_CHILD` 常量及对应方法。`tax_calculation_engine.py` 步骤 4b 已集成 Familienbonus Plus 和 Alleinverdienerabsetzbetrag 作为税收抵免
  - **验证**: 添加新测试并运行
  - **完成说明**: `FamilyInfo` 扩展了 `children_under_18`、`children_18_to_24`、`is_sole_earner` 字段。`deduction_calculator.py` 新增 `calculate_familienbonus()` 和 `calculate_alleinverdiener()` 方法，常量 `FAMILIENBONUS_UNDER_18 = €2,000`、`FAMILIENBONUS_18_24 = €700`、`ALLEINVERDIENER_BASE = €520`、`ALLEINVERDIENER_PER_CHILD = €704`。`tax_calculation_engine.py` 在步骤 4b 中从税额扣除这些抵免。

- [x] 7. 实现 Grundfreibetrag 在主税务引擎中的应用
  - **优先级**: P1
  - **需求**: REQ-4.5
  - **文件**: `backend/app/services/tax_calculation_engine.py`
  - **修改内容**:
    - 对非定额扣除的自雇人员，在 `calculate_total_tax()` 计算应税收入时应用 Grundfreibetrag（15%，最高 €4,950）
    - 当前仅在 `flat_rate_tax_comparator.py` 的 `_calculate_flat_rate()` 中使用
    - 使用 `tax_configuration.py` 中已有的 `basic_exemption_rate` 和 `basic_exemption_max`
  - **当前状态**: `calculate_total_tax()` 步骤 3b 已对 GSVG/Neue Selbständige 应用 Grundfreibetrag（15%，最高 €4,950），使用 `tax_config` 中的 `basic_exemption_rate` 和 `basic_exemption_max`
  - **验证**: 运行 `pytest backend/tests/test_income_tax_properties.py`
  - **完成说明**: `tax_calculation_engine.py` 的 `calculate_total_tax()` 在步骤 3b 中对 `UserType.GSVG` 和 `UserType.NEUE_SELBSTAENDIGE` 自动应用 Grundfreibetrag。使用 `deduction_config.basic_exemption_rate`（默认 0.15）和 `deduction_config.basic_exemption_max`（默认 4950）从 `tax_config` 读取，与 `flat_rate_tax_comparator.py` 中的值一致。

- [x] 8. SVS 社会保险值验证和注释
  - **优先级**: P2
  - **需求**: REQ-5.1, REQ-5.2, REQ-5.3, REQ-5.4
  - **文件**: `backend/app/services/svs_calculator.py`, `backend/app/services/knowledge_base_service.py`
  - **修改内容**:
    - 为所有 SVS 常量添加详细注释，说明数据来源和适用年份
    - 如果能确认 2026 年（Steuerjahr 2025）的正确值，则更新:
      - `ACCIDENT_FIXED`: 当前 €12.95
      - `GSVG_MIN_BASE_MONTHLY`: 当前 €551.10
      - `MAX_BASE_MONTHLY`: 当前 €8,085
    - 同步更新 `knowledge_base_service.py`
  - **当前状态**: `svs_calculator.py` 常量有简短行内注释但无数据来源说明。`knowledge_base_service.py` SVS 描述与 `svs_calculator.py` 值一致（18.5%/6.8%/€12.95/1.53%/€551.10/€8,085），但均无年份来源标注
  - **验证**: 运行 `pytest backend/tests/ -k svs`
  - **完成说明**: `svs_calculator.py` 模块文档和所有常量已添加详细注释，标注数据来源（SVS/WKO）、适用年份（Steuerjahr 2025）、法律依据（GSVG §§ 27–27a）。百分比费率（18.5%/6.8%/1.53%）已通过 WKO 确认。固定金额（€12.95 事故保险、€551.10 最低基数、€8,085 最高基数）保留当前值并添加 TODO 标注待 SVS 官方确认。`knowledge_base_service.py` 三种语言 SVS 描述已更新 metadata source 为 "SVS/WKO Steuerjahr 2025"，文本中添加年份和来源说明。`tax_configuration.py` 模型注释和 `get_2026_tax_config()` SVS 部分也已同步添加来源标注。49 个 SVS 测试全部通过。

- [x] 9. 修正 Dashboard 建议文本
  - **优先级**: P2
  - **需求**: REQ-6.1, REQ-6.2, REQ-6.3
  - **文件**: `backend/app/services/dashboard_service.py`
  - **修改内容**:
    - 将 `get_suggestions()` 中的硬编码英文文本改为翻译键或根据 `language` 参数返回对应语言文本
    - 修正 Home Office 建议: `"€1,260/year"` → `"€300/year"`（当前 description 写 "deduct up to €1,260/year" 但 potential_savings 是 300.0，自相矛盾）
    - Pendlerpauschale 建议: `">20km"` → `">2km"` (Großes) 或保持 ">20km" (Kleines)，需明确说明
    - 为 `get_calendar()` 的截止日期添加翻译键支持
  - **当前状态**: `get_suggestions()` 所有 title/description 均为硬编码英文。Home Office 描述错误写 "€1,260/year"。Pendlerpauschale 描述写 ">20km"。`get_calendar()` 未检查但可能也有硬编码
  - **验证**: 手动测试 API 响应
  - **完成说明**: `get_suggestions()` 和 `get_calendar()` 现在根据 `language` 参数（de/en/zh）返回本地化文本，通过模块级 `_SUGGESTION_TEXTS` 和 `_CALENDAR_TEXTS` 字典实现。Home Office 描述已从错误的 "€1,260/year" 修正为 "€300/year"。Pendlerpauschale 描述已更新为同时说明 Großes（2km 起）和 Kleines（20km 起）两种类型。所有硬编码英文字符串已替换为三语本地化文本。

- [x] 10. 前端 i18n 硬编码字符串修复
  - **优先级**: P3
  - **需求**: REQ-7.1, REQ-7.2, REQ-7.3, REQ-7.4
  - **文件**: `frontend/src/components/pwa/PWAUpdatePrompt.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/components/documents/OCRReview.tsx`, `frontend/src/pages/auth/RegisterPage.tsx`, `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/de.json`, `frontend/src/i18n/locales/zh.json`
  - **修改内容**:
    - `PWAUpdatePrompt.tsx`: 将所有硬编码英文替换为 i18n 调用:
      - "App ready to work offline" → `t('pwa.offlineReady')`
      - "You can now use Taxja without an internet connection." → `t('pwa.offlineDescription')`
      - "Got it" → `t('pwa.gotIt')`
      - "New version available" → `t('pwa.newVersion')`
      - "Click reload to update to the latest version." → `t('pwa.newVersionDescription')`
      - "Reload" → `t('pwa.reload')`
      - "Later" → `t('pwa.later')`
      - 需要添加 `useTranslation` import 和 hook
    - `DocumentsPage.tsx`: 将 `"Loading preview..."` (第128行 viewer-fallback) 替换为 `t('common.loadingPreview')`
    - `OCRReview.tsx`: 将 `"Loading preview..."` (preview-loading div) 替换为 `t('common.loadingPreview')`
    - `RegisterPage.tsx`: 将 `<label>Name</label>` 替换为 `<label>{t('auth.name')}</label>`
    - 在三个语言文件中添加对应翻译键
  - **当前状态**: `PWAUpdatePrompt.tsx` 已使用 `useTranslation` 和 `t()` 调用。`DocumentsPage.tsx` 和 `OCRReview.tsx` 的 "Loading preview..." 已替换为 `t('common.loadingPreview')`。`RegisterPage.tsx` 的 `<label>Name</label>` 已替换为 `t('auth.name')`
  - **验证**: 运行 `npm run build` 确认无编译错误
  - **完成说明**: `PWAUpdatePrompt.tsx` 新增 `useTranslation` hook，7 个硬编码字符串替换为 `t('pwa.*')` 调用。`DocumentsPage.tsx` 和 `OCRReview.tsx` 使用 `t('common.loadingPreview')`。`RegisterPage.tsx` 使用 `t('auth.name')`。三个语言文件（en/de/zh.json）已添加所有对应翻译键。

- [x] 11. Knowledge Base 全面同步验证
  - **优先级**: P2
  - **需求**: REQ-8.1, REQ-8.2
  - **文件**: `backend/app/services/knowledge_base_service.py`
  - **修改内容**:
    - 在完成任务 4-9 后，全面检查 `knowledge_base_service.py` 中所有数值
    - 确保三种语言描述与计算器中的实际值完全一致
    - 特别关注:
      - 所得税级距（已正确 ✓）
      - Pendlerpauschale（已正确 ✓）
      - SVS 值（当前与 svs_calculator.py 一致 ✓，但需确认年份来源）
      - Basispauschalierung（当前完全缺失，需在任务 4 中添加）
      - Home Office（knowledge_base 写 €300 ✓，但 dashboard 写 €1,260 ✗）
      - Werbungskostenpauschale / Verkehrsabsetzbetrag（当前缺失，需在任务 5 后添加）
      - Familienbonus Plus / Alleinverdienerabsetzbetrag（当前缺失，需在任务 6 后添加）
  - **当前状态**: `initialize_tax_law_documents()` 包含 21 条文档（7 个主题 × 3 语言）。缺少 Basispauschalierung、Werbungskostenpauschale、Verkehrsabsetzbetrag、Familienbonus Plus、Alleinverdienerabsetzbetrag、Grundfreibetrag 的描述
  - **验证**: 人工审查对比

- [x] 12. 雇员社保信息展示（可选增强）
  - **优先级**: P3
  - **需求**: REQ-9.1
  - **文件**: `backend/app/services/svs_calculator.py`
  - **修改内容**:
    - 在雇员 SVS 结果中添加详细参考信息字段:
      ```python
      note="Employee contributions are deducted by employer. "
           "Reference rates: Pension 10.25%, Health 3.87%, Unemployment 3%. "
           "Max contribution base: €6,060/month (2025)."
      ```
    - 这是信息展示，不影响计算
  - **当前状态**: 雇员分支已有 `note="Employee contributions are deducted by employer"`，但缺少详细的参考费率（Pension 10.25%、Health 3.87%、Unemployment 3%）和最高缴费基数（€6,060/月）信息
  - **验证**: 检查 API 响应中的 note 字段
