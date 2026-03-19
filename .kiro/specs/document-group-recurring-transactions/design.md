# 文档分组重构与贷款/保险定期交易 缺陷修复设计

## 概述

本次修复涉及 Taxja 文档管理模块的 5 个关联缺陷：贷款合同分组错误、"抵扣与减免"分组命名不直观、保险合同缺少定期交易生成、独立贷款无法创建还款定期交易、保险保费数据未被利用。修复策略分为两部分：前端分组配置调整（纯数据映射变更）和后端 OCR pipeline + 定期交易模型扩展（新增 RecurringTransactionType、suggestion 生成逻辑）。

## 术语表

- **Bug_Condition (C)**: 触发缺陷的条件集合——包括贷款合同被归入错误分组、分组名称不直观、保险/贷款文档未生成定期交易建议
- **Property (P)**: 修复后的期望行为——正确分组、直观命名、自动生成定期交易建议
- **Preservation**: 修复不得影响的现有行为——租赁合同分组、购房合同流程、已有定期交易生成逻辑、文档搜索/筛选/删除操作
- **documentGroups**: `DocumentList.tsx` 中定义的前端文档分组配置数组，决定文档在 UI 中的分类展示
- **_stage_suggest**: `DocumentPipelineOrchestrator` 中的 Stage 5 方法，根据文档类型分发到不同的 suggestion builder
- **RecurringTransactionType**: `recurring_transaction.py` 中的枚举，定义定期交易的业务类型（rental_income, loan_interest, depreciation 等）
- **check_source_entity_required**: `recurring_transactions` 表上的 CHECK 约束，限制不同 recurring_type 必须关联的外键

## 缺陷详情

### Bug Condition

缺陷在以下 5 个条件下触发：

1. 用户上传 LOAN_CONTRACT 类型文档时，前端将其归入 `property` 分组
2. 用户查看 `deductions` 分组时，名称"抵扣与减免"不直观
3. 用户上传 VERSICHERUNGSBESTAETIGUNG 文档且 OCR 提取到保费金额后，pipeline 不生成定期交易建议
4. 用户确认非房贷类贷款合同时，系统要求必须关联 PropertyLoan（需要 property_id）
5. 保险合同 OCR 结果中的保费金额和缴费周期数据未被利用

**形式化规约：**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {documentType, ocrData, actionContext}
  OUTPUT: boolean

  // 缺陷1: 贷款合同分组错误
  IF input.documentType == "loan_contract"
     AND getDocumentGroupId(input.documentType) == "property"
     RETURN true

  // 缺陷2: 分组名称不直观（静态配置问题，始终为 true）
  IF input.actionContext == "view_deductions_group"
     AND groupLabel("deductions") NOT IN ["税务优惠凭证", "Steuerliche Absetzposten", "Tax Deduction Documents"]
     RETURN true

  // 缺陷3+5: 保险合同无定期交易建议
  IF input.documentType == "versicherungsbestaetigung"
     AND input.ocrData.praemie IS NOT NULL
     AND pipelineDoesNotGenerateRecurringSuggestion(input)
     RETURN true

  // 缺陷4: 独立贷款无法创建还款定期交易
  IF input.documentType == "loan_contract"
     AND input.ocrData.monthly_payment IS NOT NULL
     AND input.ocrData.matched_property_id IS NULL
     AND cannotCreateStandaloneLoanRepayment(input)
     RETURN true

  RETURN false
END FUNCTION
```

### 示例

- 用户上传消费贷款合同 → 系统将其归入"房产与租赁"分组 → 用户在该分组中找不到（期望归入"保险与贷款"）
- 用户查看"抵扣与减免"分组 → 不理解该分组包含捐赠确认、子女照护费等凭证（期望看到"税务优惠凭证"）
- 用户上传 Allianz 家庭保险确认书，OCR 提取到年缴保费 €1,200 → 系统无任何定期交易建议（期望生成保险缴费定期支出建议）
- 用户上传车贷合同，月供 €450，无关联房产 → 系统无法创建还款定期交易（期望创建独立贷款还款定期交易）

## 期望行为

### Preservation Requirements

**不变行为：**
- 租赁合同（RENTAL_CONTRACT）继续归入 `property` 分组，自动生成租金收入定期交易
- 购房合同（PURCHASE_CONTRACT）继续归入 `property` 分组，生成房产创建建议
- 房贷类贷款合同继续支持 PropertyLoan + loan_interest RecurringTransaction 完整流程
- "工资与雇佣"、"自营/企业"、"房产与租赁"、"税务申报与通知"、"票据发票"、"银行资料"、"其他"分组的文档类型映射不变
- `generate_due_transactions` 对已有 recurring_type（rental_income, loan_interest, depreciation, other_income, other_expense, manual）的生成逻辑不变
- 文档搜索、筛选、下载、删除操作不受影响

**范围：**
所有不涉及 LOAN_CONTRACT 分组变更、deductions 命名变更、VERSICHERUNGSBESTAETIGUNG 定期交易生成、独立贷款还款创建的输入，行为完全不变。

## 假设根因分析

基于代码分析，5 个缺陷的根因如下：

1. **LOAN_CONTRACT 分组配置错误**：`DocumentList.tsx` 中 `documentGroups` 数组将 `DocumentType.LOAN_CONTRACT` 放在 `property` 分组的 `types` 数组中。贷款合同不一定与房产相关，应移至 `social_insurance` 分组。

2. **deductions 分组命名不直观**：i18n 翻译文件中 `documents.groups.deductions` 的翻译值不够直观（中文"抵扣与减免"、德文"Absetzbeträge & Freibeträge"、英文"Deductions & Allowances"），需更新为更具描述性的名称。

3. **保险合同无 suggestion 生成逻辑**：`_stage_suggest` 方法中没有 `VERSICHERUNGSBESTAETIGUNG` 的分支处理。该类型文档走入 `else` 分支（Receipt/Invoice/Other），只生成普通交易建议，不生成定期交易建议。需要新增专门的 `_build_versicherung_suggestion` 方法。

4. **独立贷款受 PropertyLoan 约束**：当前 `create_loan_from_suggestion` 函数创建 `PropertyLoan` 记录（需要 `property_id`），然后通过 `RecurringTransactionService.create_loan_interest_recurring` 创建定期交易。非房贷类贷款没有 property_id，无法走通此流程。需要新增 `LOAN_REPAYMENT` RecurringTransactionType，支持不关联房产的独立贷款还款。

5. **保险保费数据未利用**：OCR classifier 能识别 VERSICHERUNGSBESTAETIGUNG 并提取 `praemie`（保费）字段，但 pipeline 没有消费这些数据来生成定期交易建议。

## 正确性属性

Property 1: Bug Condition - 文档分组与定期交易生成修复

_For any_ 输入满足 isBugCondition 条件（贷款合同分组、deductions 命名、保险定期交易、独立贷款还款），修复后的系统 SHALL：(a) 将 LOAN_CONTRACT 归入"保险与贷款"分组；(b) 将 deductions 分组显示为"税务优惠凭证"/"Steuerliche Absetzposten"/"Tax Deduction Documents"；(c) 为含保费数据的保险合同生成定期交易建议；(d) 支持创建不关联房产的独立贷款还款定期交易。

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - 现有分组与定期交易行为不变

_For any_ 输入不满足 isBugCondition 条件（非贷款合同分组查询、非 deductions 命名查询、非保险合同 OCR、非独立贷款确认），修复后的系统 SHALL 产生与修复前完全相同的行为，保留所有现有文档分组映射、定期交易生成逻辑和文档操作功能。

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## 修复实现

### 所需变更

假设根因分析正确：

**文件**: `frontend/src/components/documents/DocumentList.tsx`

**变更 1 - 移动 LOAN_CONTRACT 分组**:
- 从 `property` 分组的 `types` 数组中移除 `DocumentType.LOAN_CONTRACT`
- 将 `DocumentType.LOAN_CONTRACT` 添加到 `social_insurance` 分组的 `types` 数组中

**文件**: `frontend/src/i18n/locales/zh.json`, `de.json`, `en.json`

**变更 2 - 重命名 social_insurance 分组**:
- zh: `"social_insurance": "保险与贷款"`
- de: `"social_insurance": "Versicherung & Kredit"`
- en: `"social_insurance": "Insurance & Loans"`

**变更 3 - 重命名 deductions 分组**:
- zh: `"deductions": "税务优惠凭证"`
- de: `"deductions": "Steuerliche Absetzposten"`
- en: `"deductions": "Tax Deduction Documents"`

**文件**: `backend/app/models/recurring_transaction.py`

**变更 4 - 新增 RecurringTransactionType 枚举值**:
- 添加 `INSURANCE_PREMIUM = "insurance_premium"`
- 添加 `LOAN_REPAYMENT = "loan_repayment"`

**变更 5 - 更新 CHECK 约束**:
- 修改 `check_source_entity_required` 约束，允许 `insurance_premium` 和 `loan_repayment` 类型不要求 property_id 或 loan_id

**文件**: `backend/app/services/document_pipeline_orchestrator.py`

**变更 6 - 新增保险合同 suggestion 分支**:
- 在 `_stage_suggest` 方法中添加 `VERSICHERUNGSBESTAETIGUNG` 分支
- 新增 `_build_versicherung_suggestion` 方法，从 OCR 数据中提取保费金额和缴费频率，生成 `create_insurance_recurring` 类型的 suggestion

**文件**: `backend/app/tasks/ocr_tasks.py`

**变更 7 - 新增 `_build_versicherung_suggestion` 函数**:
- 从 `ocr_result` 中读取 `praemie`（保费金额）、`zahlungsfrequenz`（缴费频率，默认年缴）、保险类型
- 构建 `import_suggestion`，type 为 `create_insurance_recurring`，包含金额、频率、保险类型

**变更 8 - 新增 `create_insurance_recurring_from_suggestion` 函数**:
- 创建 `RecurringTransaction`，recurring_type 为 `INSURANCE_PREMIUM`，transaction_type 为 `expense`，category 为 `insurance`
- 关联 source_document_id

**变更 9 - 扩展贷款建议支持独立还款**:
- 修改 `_build_kreditvertrag_suggestion`，当无 `matched_property_id` 时，suggestion type 改为 `create_loan_repayment`
- 新增 `create_standalone_loan_repayment` 函数，创建 recurring_type 为 `LOAN_REPAYMENT` 的 RecurringTransaction，不要求 property_id

**文件**: `backend/app/services/recurring_transaction_service.py`

**变更 10 - 新增 service 方法**:
- 添加 `create_insurance_premium_recurring` 方法
- 添加 `create_loan_repayment_recurring` 方法
- 更新 `_generate_transaction_from_recurring` 中的 expense_category 映射，支持新类型

**文件**: `backend/app/api/v1/endpoints/documents.py`

**变更 11 - 新增确认端点**:
- 添加 `POST /{document_id}/confirm-insurance-recurring` 端点
- 添加 `POST /{document_id}/confirm-loan-repayment` 端点（或扩展现有 `confirm-loan` 端点）

**文件**: `backend/alembic/versions/` (新迁移文件)

**变更 12 - 数据库迁移**:
- 添加 `insurance_premium` 和 `loan_repayment` 到 `recurringtransactiontype` 枚举
- 更新 `check_source_entity_required` 约束


## 测试策略

### 验证方法

测试策略分两阶段：首先在未修复代码上发现反例以确认缺陷，然后验证修复的正确性和现有行为的保持。

### 探索性 Bug Condition 检查

**目标**: 在实施修复前，发现能证明缺陷存在的反例，确认或否定根因分析。

**测试计划**: 编写测试验证当前代码中的 5 个缺陷行为，在未修复代码上运行以观察失败模式。

**测试用例**:
1. **分组映射测试**: 验证 `getDocumentGroupId(LOAN_CONTRACT)` 返回 `property`（未修复代码上会通过，证明缺陷存在）
2. **保险 suggestion 测试**: 模拟 VERSICHERUNGSBESTAETIGUNG 文档通过 `_stage_suggest`，验证不生成定期交易建议（未修复代码上会通过，证明缺陷存在）
3. **独立贷款测试**: 模拟无 property_id 的贷款合同通过 `create_loan_from_suggestion`，验证失败（未修复代码上会失败，证明缺陷存在）
4. **i18n 命名测试**: 验证 `documents.groups.deductions` 翻译值不是"税务优惠凭证"（未修复代码上会通过，证明缺陷存在）

**预期反例**:
- LOAN_CONTRACT 被映射到 `property` 而非 `social_insurance`
- VERSICHERUNGSBESTAETIGUNG 走入 else 分支，只生成普通交易建议
- 无 property_id 的贷款无法创建 PropertyLoan

### Fix Checking

**目标**: 验证对所有满足 bug condition 的输入，修复后的函数产生期望行为。

**伪代码:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := processWithFixedCode(input)
  ASSERT expectedBehavior(result)
END FOR
```

### Preservation Checking

**目标**: 验证对所有不满足 bug condition 的输入，修复后的函数产生与原函数相同的结果。

**伪代码:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**测试方法**: 推荐使用 Property-Based Testing 进行 preservation checking，因为：
- 自动生成大量测试用例覆盖输入域
- 捕获手动单元测试可能遗漏的边界情况
- 对非缺陷输入的行为不变提供强保证

**测试计划**: 先在未修复代码上观察非缺陷输入的行为，然后编写 property-based tests 捕获该行为。

**测试用例**:
1. **租赁合同分组保持**: 验证 RENTAL_CONTRACT 修复前后都归入 `property` 分组
2. **购房合同流程保持**: 验证 PURCHASE_CONTRACT 修复前后都生成房产创建建议
3. **房贷流程保持**: 验证有 property_id 的贷款合同修复前后都能创建 PropertyLoan + loan_interest
4. **其他分组映射保持**: 验证所有非 LOAN_CONTRACT 文档类型的分组映射不变
5. **已有定期交易生成保持**: 验证 rental_income、loan_interest、depreciation 类型的 `generate_due_transactions` 行为不变

### 单元测试

- 测试 `getDocumentGroupId(LOAN_CONTRACT)` 返回 `social_insurance`
- 测试 `documentGroups` 中 `social_insurance` 包含 LOAN_CONTRACT、SVS_NOTICE、VERSICHERUNGSBESTAETIGUNG
- 测试 `documentGroups` 中 `property` 不再包含 LOAN_CONTRACT
- 测试 i18n 翻译键 `documents.groups.social_insurance` 和 `documents.groups.deductions` 的新值
- 测试 `_build_versicherung_suggestion` 从含 praemie 的 OCR 数据生成正确的 suggestion
- 测试 `_build_versicherung_suggestion` 在无 praemie 时返回 None
- 测试 `create_insurance_recurring_from_suggestion` 创建正确的 RecurringTransaction
- 测试 `create_standalone_loan_repayment` 创建不关联房产的 RecurringTransaction
- 测试 `_generate_transaction_from_recurring` 对 INSURANCE_PREMIUM 和 LOAN_REPAYMENT 类型生成正确的 expense 交易
- 测试 CHECK 约束允许 insurance_premium 和 loan_repayment 不关联 property_id/loan_id

### Property-Based Tests

- 生成随机 DocumentType 值，验证 `getDocumentGroupId` 的分组映射与预期一致（覆盖所有类型）
- 生成随机 OCR 数据（含/不含 praemie），验证 `_build_versicherung_suggestion` 的行为正确性
- 生成随机 RecurringTransactionType 和关联数据，验证 `_generate_transaction_from_recurring` 对所有类型产生正确的交易
- 生成随机日期和金额，验证 `generate_due_transactions` 对新旧 recurring_type 都能正确生成和回填

### 集成测试

- 端到端测试：上传保险合同 → OCR 识别 → 生成保险缴费定期交易建议 → 用户确认 → 创建 RecurringTransaction → 自动生成到期交易
- 端到端测试：上传消费贷款合同 → OCR 识别 → 生成独立贷款还款建议 → 用户确认 → 创建 RecurringTransaction → 自动生成到期交易
- 回归测试：上传租赁合同 → 验证仍归入 property 分组 → 仍自动生成租金收入定期交易
- 回归测试：上传房贷合同（有 property_id）→ 验证仍走 PropertyLoan + loan_interest 流程
