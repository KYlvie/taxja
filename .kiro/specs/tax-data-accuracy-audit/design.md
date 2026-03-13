# 奥地利税务数据准确性审计 - 设计文档

## 设计原则

1. **数据库驱动优先**: 税务参数应从 `TaxConfiguration` 数据库模型读取，硬编码常量仅作为回退默认值
2. **单一数据源**: 每个税务参数只在一个地方定义，其他地方引用
3. **向后兼容**: 修改不应破坏现有 API 接口
4. **测试覆盖**: 每项修改必须有对应的测试验证

---

## D-1: 所得税级距一致性方案

### 当前问题
- `income_tax_calculator.py`: 类文档字符串中有 2026 级距描述，但实际计算通过 `__init__` 接收 `tax_config` 参数（来自 DB），所以计算本身是正确的
- `dashboard_service.py`: 有独立的硬编码级距用于快速估算，使用级距宽度方式
- `knowledge_base_service.py`: 硬编码描述文本

### 修改方案
1. 更新 `income_tax_calculator.py` 类文档字符串中的级距值为 2026 正确值
2. 验证 `dashboard_service.py` 中的级距宽度计算：
   - 第1档宽度: €21,992 - €13,539 = €8,453 ✓
   - 第2档宽度: €36,458 - €21,992 = €14,466 ✓
   - 第3档宽度: €70,365 - €36,458 = €33,907 ✓
   - 第4档宽度: €104,859 - €70,365 = €34,494 ✓
   - 第5档宽度: €1,000,000 - €104,859 = €895,141 ✓
   - 免税额: €13,539 ✓
   - **结论**: dashboard_service 的级距宽度已经是 2026 正确值
3. `knowledge_base_service.py` 已使用正确的 2026 值，无需修改

---

## D-2: Pendlerpauschale 修正方案

### 当前问题
`deduction_calculator.py` 和 `e1_form_service.py` 的 Großes Pendlerpauschale 值不一致。

### 分析
经对比 L1 表单年度值和 `deduction_calculator.py` 月度值：

**Kleines Pendlerpauschale**（L1 表单 vs deduction_calculator）:
- 20-40km: €696/年 = €58×12 ✓
- 40-60km: €1,356/年 = €113×12 ✓  
- 60km+: €2,016/年 = €168×12 ✓

**Großes Pendlerpauschale**（L1 表单 vs deduction_calculator）:
- 2-20km: €372/年 → deduction_calculator 完全缺失此档位 ❌
- 20-40km: €1,476/年 → deduction_calculator 有 €31/月 = €372/年 ❌（应为 €123/月）
- 40-60km: €2,568/年 → deduction_calculator 有 €123/月 = €1,476/年 ❌（应为 €214/月）
- 60km+: €3,672/年 → deduction_calculator 有 €214/月 = €2,568/年 ❌（应为 €306/月）

### 修改方案
```python
# 修正后的 Großes Pendlerpauschale
COMMUTE_BRACKETS_LARGE = {
    2: Decimal('31.00'),    # 2-20km: €31/月 = €372/年
    20: Decimal('123.00'),  # 20-40km: €123/月 = €1,476/年
    40: Decimal('214.00'),  # 40-60km: €214/月 = €2,568/年
    60: Decimal('306.00'),  # 60km+: €306/月 = €3,672/年
}
```

同时修改 `calculate_commuting_allowance` 方法：
- Großes Pendlerpauschale 的最低距离从 20km 降为 2km
- 更新距离判断逻辑

### 影响范围
- `deduction_calculator.py`: 修改常量和计算逻辑
- `tax_configuration.py` `get_2026_tax_config()`: 更新 commuting_brackets
- `knowledge_base_service.py`: 更新描述
- `test_deduction_calculator.py`: 更新测试期望值
- `test_income_tax_properties.py`: 检查是否有 Pendlerpauschale 相关测试

---

## D-3: Basispauschalierung 更新方案

### 修改内容
- `FLAT_RATE_12_PERCENT` → `FLAT_RATE_13_5_PERCENT = Decimal("0.135")`
- 相关枚举值 `BASIC_12` → `BASIC_13_5`
- 添加营业额上限检查 €320,000

### 影响范围
- `flat_rate_tax_comparator.py`: 费率和枚举
- `knowledge_base_service.py`: 描述更新
- `test_flat_rate_comparison_properties.py`: 测试更新

---

## D-4: Absetzbeträge 集成方案

### 设计决策
将新的 Absetzbeträge 添加到 `deduction_calculator.py`，并在 `tax_calculation_engine.py` 中集成。

### 新增常量
```python
VERKEHRSABSETZBETRAG = Decimal('463.00')        # 交通税收抵免
WERBUNGSKOSTENPAUSCHALE = Decimal('132.00')      # 雇员标准扣除
FAMILIENBONUS_UNDER_18 = Decimal('2000.00')      # 家庭奖金 <18岁
FAMILIENBONUS_18_24 = Decimal('700.00')          # 家庭奖金 18-24岁
ALLEINVERDIENER_BASE = Decimal('520.00')         # 单收入者基础
ALLEINVERDIENER_PER_CHILD = Decimal('704.00')    # 每额外子女
```

### 注意事项
- Absetzbeträge（税收抵免）直接从应纳税额中扣除，不同于 Absetzposten（从收入中扣除）
- 需要在 `TaxCalculationEngine` 中区分这两种扣除类型
- Familienbonus Plus 和 Verkehrsabsetzbetrag 是从税额中扣除的
- Werbungskostenpauschale 是从收入中扣除的

---

## D-5: SVS 值验证方案

### 待验证项
由于 2025 和 2026 年的值可能不同，且代码注释标注为 "2026"：
- 事故保险: €12.95/月（代码） vs €12.07/月（2025来源）
- 最低基数: €551.10/月（代码） vs €537.78/月（2025来源）
- 最高基数: €8,085/月（需验证）

### 方案
标记为需要人工验证的项目。如果无法获取 BMF Steuerbuch 2026 PDF 中的确切值，保留当前值并添加注释说明数据来源和年份。

---

## D-6: Dashboard i18n 方案

### 方案
`get_suggestions()` 和 `get_calendar()` 接受 `language` 参数但未使用。修改为：
1. 建议文本使用翻译键（如 `suggestions.home_office.title`）
2. 前端根据键值显示对应语言文本
3. 或者后端根据 language 参数返回对应语言文本

考虑到前端已有 i18n 系统，推荐方案：后端返回翻译键，前端负责翻译。

---

## D-7: 前端 i18n 方案

### 修改方式
1. 在 `de.json`、`en.json`、`zh.json` 中添加缺失的翻译键
2. 在组件中将硬编码字符串替换为 `t('key')` 调用
3. 补充 `en.json` 中缺失的 `documents.review.transactionType`

---

## 文件修改清单

| 文件 | 修改类型 | 优先级 |
|------|---------|--------|
| `backend/app/services/income_tax_calculator.py` | 更新文档字符串 | P0 |
| `backend/app/services/deduction_calculator.py` | 修正 Pendlerpauschale 值和逻辑 | P0 |
| `backend/app/services/e1_form_service.py` | 验证一致性 | P0 |
| `backend/app/services/flat_rate_tax_comparator.py` | 更新费率 12%→13.5% | P1 |
| `backend/app/services/tax_calculation_engine.py` | 集成 Absetzbeträge | P1 |
| `backend/app/services/svs_calculator.py` | 验证/更新值 | P2 |
| `backend/app/services/dashboard_service.py` | 修正建议文本、i18n | P2 |
| `backend/app/services/knowledge_base_service.py` | 同步所有值 | P2 |
| `backend/app/models/tax_configuration.py` | 更新 commuting_brackets | P0 |
| `backend/app/services/savings_suggestion_service.py` | 检查硬编码值 | P2 |
| `frontend/src/components/pwa/PWAUpdatePrompt.tsx` | i18n 修复 | P3 |
| `frontend/src/pages/DocumentsPage.tsx` | i18n 修复 | P3 |
| `frontend/src/components/documents/OCRReview.tsx` | i18n 修复 | P3 |
| `frontend/src/pages/auth/RegisterPage.tsx` | i18n 修复 | P3 |
| `frontend/src/i18n/locales/en.json` | 补充缺失键 | P3 |
| `backend/tests/test_deduction_calculator.py` | 更新测试 | P0 |
| `backend/tests/test_flat_rate_comparison_properties.py` | 更新测试 | P1 |
