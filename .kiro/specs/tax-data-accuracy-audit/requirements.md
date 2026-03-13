# 奥地利税务数据准确性审计 - 需求文档

## 背景

Taxja 系统目标是使用 2026 年 USP 税率（即 Steuerjahr 2025，2026年申报）。经过全面审计，发现多处税务数据与官方来源（BMF Steuerbuch 2026、PWC Austria、USP.gv.at）存在差异。本 spec 旨在修正所有已发现的不一致问题。

## 官方数据来源

- BMF Steuerbuch 2026: https://www.bmf.gv.at/services/publikationen/das-steuerbuch.html
- PWC Austria Tax Facts 2025/2026: https://www.pwc.at/de/services/steuerberatung/einkommensteuer.html
- USP.gv.at: https://www.usp.gv.at/
- SVS: https://www.svs.at/
- acciyo.com (汇总): https://www.acciyo.com/at/

---

## REQ-1: 所得税级距一致性 (Einkommensteuer Brackets)

### REQ-1.1
`income_tax_calculator.py` 中的硬编码 `TAX_BRACKETS_2026` 类常量必须删除或与数据库配置 `get_2026_tax_config()` 保持一致。当前硬编码值仍为 2025 年数据（€13,308 / €21,617 / €35,836 / €69,166 / €103,072），正确的 2026 值为 €13,539 / €21,992 / €36,458 / €70,365 / €104,859 / €1,000,000。

### REQ-1.2
`dashboard_service.py` 中的税率估算硬编码级距必须与 2026 官方级距一致。当前使用的是级距宽度方式计算，需验证其数值正确性。

### REQ-1.3
`knowledge_base_service.py` 中所有三种语言的所得税级距描述必须与代码中的实际计算值一致。

---

## REQ-2: Pendlerpauschale（通勤补贴）修正

### REQ-2.1
`deduction_calculator.py` 中的 Großes Pendlerpauschale（大通勤补贴）必须增加 2-20km 档位（€31/月 = €372/年），当前代码完全缺失此档位。

### REQ-2.2
`deduction_calculator.py` 中 Großes Pendlerpauschale 的月度金额需与 `e1_form_service.py` L1 表单中的年度金额保持一致：
- 2-20km: €372/年（当前缺失）
- 20-40km: €1,476/年（当前 €31×12=€372 ❌，应为 €123/月）
- 40-60km: €2,568/年（当前 €123×12=€1,476 ❌，应为 €214/月）
- 60km+: €3,672/年（当前 €214×12=€2,568 ❌，应为 €306/月）

### REQ-2.3
Kleines Pendlerpauschale 的值需要验证（当前 €58/€113/€168 对应 €696/€1,356/€2,016 年度值，与 L1 表单一致）。

### REQ-2.4
`knowledge_base_service.py` 中的 Pendlerpauschale 描述必须与修正后的值同步。

### REQ-2.5
`tax_configuration.py` 中 `get_2026_tax_config()` 的 `commuting_brackets` 必须与修正后的值同步。

---

## REQ-3: Basispauschalierung（基本定额扣除）更新

### REQ-3.1
`flat_rate_tax_comparator.py` 中的 12% 定额费率必须更新为 13.5%（2025年起生效）。

### REQ-3.2
营业额上限需从隐含的 €220,000 验证并更新为 €320,000（如代码中有此限制）。

### REQ-3.3
`knowledge_base_service.py` 中相关描述需同步更新。

---

## REQ-4: 缺失的 Absetzbeträge（税收抵免）

### REQ-4.1
实现 Verkehrsabsetzbetrag（交通税收抵免）：€463/年（2025年值），适用于所有雇员。

### REQ-4.2
将 Alleinverdienerabsetzbetrag / Alleinerzieherabsetzbetrag 从 `e1_form_service.py` 集成到主税务计算引擎。当前仅在 L1 表单中实现（€520 基础 + €704/额外子女）。

### REQ-4.3
将 Familienbonus Plus 从 `e1_form_service.py` 集成到主税务计算引擎（€2,000/18岁以下子女，€700/19-24岁子女）。

### REQ-4.4
实现 Werbungskostenpauschale（雇员标准扣除）：€132/年，适用于所有雇员。

### REQ-4.5
对非定额扣除的自雇人员，在主税务引擎中应用 Grundfreibetrag（基本利润免税额）：15%，最高 €4,950。当前仅在 `flat_rate_tax_comparator.py` 中实现。

---

## REQ-5: SVS 社会保险值验证

### REQ-5.1
验证并更新事故保险固定金额：代码使用 €12.95/月，2025年来源显示 €12.07/月。需确认 2026 年（Steuerjahr 2025）的正确值。

### REQ-5.2
验证并更新最低缴费基数：代码使用 €551.10/月，2025年来源显示 €537.78/月。需确认正确年份的值。

### REQ-5.3
验证最高缴费基数 €8,085/月是否为 2026 年正确值。

### REQ-5.4
`knowledge_base_service.py` 中的 SVS 值必须与计算器同步。

---

## REQ-6: Dashboard 和建议的 i18n 修复

### REQ-6.1
`dashboard_service.py` 中 `get_suggestions()` 的所有建议文本必须使用 i18n 翻译键，而非硬编码英文。

### REQ-6.2
Home office 建议中的 "€1,260/year" 必须修正为 €300/year（与 `deduction_calculator.py` 一致）。

### REQ-6.3
`dashboard_service.py` 中 `get_calendar()` 的截止日期描述应支持多语言。

---

## REQ-7: 前端硬编码字符串 i18n 修复

### REQ-7.1
`PWAUpdatePrompt.tsx` 中的 "App ready to work offline" 和 "New version available" 必须使用 `t()` 函数。

### REQ-7.2
`DocumentsPage.tsx` 和 `OCRReview.tsx` 中的 "Loading preview..." 必须使用 `t()` 函数。

### REQ-7.3
`RegisterPage.tsx` 中的 `<label>Name</label>` 必须使用 `t()` 函数。

### REQ-7.4
`en.json` 中缺失的 `documents.review.transactionType` 键必须补充。

---

## REQ-8: Knowledge Base 全面同步

### REQ-8.1
`knowledge_base_service.py` 中所有硬编码的税务数值必须与对应计算器中的值完全一致。

### REQ-8.2
修正后需验证三种语言（de/en/zh）的描述一致性。

---

## REQ-9: 雇员社保信息展示

### REQ-9.1
对于雇员用户，SVS 计算器当前返回 0 并注明"由雇主扣除"。应考虑展示雇员社保费率信息（养老 10.25%、医疗 3.87%、失业 3%）作为参考，即使不参与计算。

---

## 优先级排序

1. **P0 - 关键**: REQ-1（所得税级距）、REQ-2（Pendlerpauschale）
2. **P1 - 高**: REQ-3（Basispauschalierung）、REQ-4（缺失 Absetzbeträge）
3. **P2 - 中**: REQ-5（SVS 验证）、REQ-6（Dashboard i18n）、REQ-8（Knowledge Base 同步）
4. **P3 - 低**: REQ-7（前端 i18n）、REQ-9（雇员社保信息）
