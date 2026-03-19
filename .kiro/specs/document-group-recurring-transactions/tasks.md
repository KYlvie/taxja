# 实施计划

- [x] 1. 编写 Bug Condition 探索性测试
  - **Property 1: Bug Condition** - 文档分组与定期交易生成缺陷
  - **重要**: 此测试必须在实施修复之前编写
  - **关键**: 此测试在未修复代码上运行时必须 FAIL — 失败即确认缺陷存在
  - **不要**在测试失败时尝试修复测试或代码
  - **说明**: 此测试编码了期望行为 — 修复后测试通过即验证修复正确
  - **目标**: 发现证明缺陷存在的反例
  - **Scoped PBT 方法**: 针对确定性缺陷，将属性范围限定到具体失败用例以确保可重现性
  - 使用 Hypothesis 编写 property-based test（后端 `backend/tests/test_document_group_recurring_properties.py`）
  - 测试 1a: 验证 `documentGroups` 中 LOAN_CONTRACT 当前归入 `property` 分组（前端单元测试 `frontend/src/__tests__/DocumentGroupMapping.test.tsx`）
  - 测试 1b: 验证 `_stage_suggest` 对 VERSICHERUNGSBESTAETIGUNG 文档不生成定期交易建议（后端 Hypothesis 测试）
  - 测试 1c: 验证 `create_loan_from_suggestion` 在无 `property_id` 时失败（后端 Hypothesis 测试）
  - 测试 1d: 验证 i18n `documents.groups.deductions` 翻译值不是"税务优惠凭证"（前端单元测试）
  - 在未修复代码上运行测试
  - **预期结果**: 测试 FAIL（这是正确的 — 证明缺陷存在）
  - 记录发现的反例以理解根因
  - 当测试编写完成、运行完毕且失败已记录后，标记任务完成
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. 编写 Preservation 属性测试（在实施修复之前）
  - **Property 2: Preservation** - 现有分组与定期交易行为不变
  - **重要**: 遵循观察优先方法论
  - 在未修复代码上观察非缺陷输入的行为：
  - 观察: `getDocumentGroupId(RENTAL_CONTRACT)` 返回 `property`
  - 观察: `getDocumentGroupId(PURCHASE_CONTRACT)` 返回 `property`
  - 观察: `getDocumentGroupId(PAYSLIP)` 返回 `employment`
  - 观察: 所有非 LOAN_CONTRACT 文档类型的分组映射不变
  - 观察: `_stage_suggest` 对 RENTAL_CONTRACT 生成 `create_recurring_income` 建议
  - 观察: `_stage_suggest` 对 PURCHASE_CONTRACT 生成 `create_property` 建议
  - 观察: `generate_due_transactions` 对 rental_income、loan_interest、depreciation 类型正确生成交易
  - 观察: 有 property_id 的贷款合同能成功创建 PropertyLoan + loan_interest
  - 使用 Hypothesis 编写 property-based test（后端 `backend/tests/test_document_group_recurring_properties.py`）
  - 前端 preservation 测试（`frontend/src/__tests__/DocumentGroupMapping.test.tsx`）：对所有非 LOAN_CONTRACT 类型，分组映射与当前行为一致
  - 后端 preservation 测试：对所有非 VERSICHERUNGSBESTAETIGUNG 且非独立贷款的文档类型，`_stage_suggest` 行为不变
  - 后端 preservation 测试：对所有已有 RecurringTransactionType（rental_income, loan_interest, depreciation, other_income, other_expense, manual），`_generate_transaction_from_recurring` 行为不变
  - 在未修复代码上运行测试
  - **预期结果**: 测试 PASS（确认基线行为已捕获）
  - 当测试编写完成、运行完毕且在未修复代码上通过后，标记任务完成
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. 修复文档分组重构与贷款/保险定期交易缺陷

  - [x] 3.1 前端：移动 LOAN_CONTRACT 分组并更新 i18n
    - 在 `frontend/src/components/documents/DocumentList.tsx` 中，从 `property` 分组的 `types` 数组移除 `DocumentType.LOAN_CONTRACT`
    - 将 `DocumentType.LOAN_CONTRACT` 添加到 `social_insurance` 分组的 `types` 数组
    - 更新 `frontend/src/i18n/locales/zh.json`：`social_insurance` → "保险与贷款"，`deductions` → "税务优惠凭证"
    - 更新 `frontend/src/i18n/locales/de.json`：`social_insurance` → "Versicherung & Kredit"，`deductions` → "Steuerliche Absetzposten"
    - 更新 `frontend/src/i18n/locales/en.json`：`social_insurance` → "Insurance & Loans"，`deductions` → "Tax Deduction Documents"
    - _Bug_Condition: isBugCondition(input) where documentType == "loan_contract" AND getDocumentGroupId == "property"_
    - _Expected_Behavior: LOAN_CONTRACT 归入 social_insurance 分组，分组名称更新_
    - _Preservation: 其他分组的文档类型映射不变_
    - _Requirements: 2.1, 2.2, 3.4_

  - [x] 3.2 后端：新增 RecurringTransactionType 枚举值和更新 CHECK 约束
    - 在 `backend/app/models/recurring_transaction.py` 的 `RecurringTransactionType` 枚举中添加 `INSURANCE_PREMIUM = "insurance_premium"` 和 `LOAN_REPAYMENT = "loan_repayment"`
    - 更新 `check_source_entity_required` 约束，允许 `insurance_premium` 和 `loan_repayment` 类型不要求 property_id 或 loan_id
    - _Bug_Condition: cannotCreateStandaloneLoanRepayment(input) 因 CHECK 约束限制_
    - _Expected_Behavior: insurance_premium 和 loan_repayment 类型可独立存在_
    - _Preservation: 已有 recurring_type 的约束行为不变_
    - _Requirements: 2.4, 2.5, 3.5_

  - [x] 3.3 后端：新增保险合同 suggestion 生成逻辑
    - 在 `backend/app/services/document_pipeline_orchestrator.py` 的 `_stage_suggest` 方法中添加 `VERSICHERUNGSBESTAETIGUNG` 分支
    - 新增 `_build_versicherung_suggestion` 方法，从 OCR 数据提取 `praemie`（保费）、`zahlungsfrequenz`（缴费频率，默认年缴）、保险类型
    - 构建 `import_suggestion`，type 为 `create_insurance_recurring`，包含金额、频率、保险类型
    - 在 `backend/app/tasks/ocr_tasks.py` 中新增 `_build_versicherung_suggestion` 函数和 `create_insurance_recurring_from_suggestion` 函数
    - _Bug_Condition: isBugCondition(input) where documentType == "versicherungsbestaetigung" AND ocrData.praemie IS NOT NULL AND pipelineDoesNotGenerateRecurringSuggestion_
    - _Expected_Behavior: 生成 create_insurance_recurring 类型的 suggestion，包含保费金额和频率_
    - _Preservation: 其他文档类型的 _stage_suggest 行为不变_
    - _Requirements: 2.3, 2.4, 3.3_

  - [x] 3.4 后端：新增独立贷款还款支持
    - 修改 `backend/app/tasks/ocr_tasks.py` 中的 `_build_kreditvertrag_suggestion`，当无 `matched_property_id` 时 suggestion type 改为 `create_loan_repayment`
    - 新增 `create_standalone_loan_repayment` 函数，创建 recurring_type 为 `LOAN_REPAYMENT` 的 RecurringTransaction，不要求 property_id
    - _Bug_Condition: isBugCondition(input) where documentType == "loan_contract" AND matched_property_id IS NULL AND cannotCreateStandaloneLoanRepayment_
    - _Expected_Behavior: 创建不关联房产的独立贷款还款 RecurringTransaction_
    - _Preservation: 有 property_id 的房贷仍走 PropertyLoan + loan_interest 流程_
    - _Requirements: 2.5, 3.3_

  - [x] 3.5 后端：扩展 RecurringTransactionService
    - 在 `backend/app/services/recurring_transaction_service.py` 中添加 `create_insurance_premium_recurring` 方法
    - 添加 `create_loan_repayment_recurring` 方法
    - 更新 `_generate_transaction_from_recurring` 中的 expense_category 映射，支持 INSURANCE_PREMIUM → `ExpenseCategory.INSURANCE`（或 OTHER）和 LOAN_REPAYMENT → `ExpenseCategory.LOAN_INTEREST`（或新增分类）
    - _Bug_Condition: 新增 recurring_type 无对应的 service 方法和交易生成逻辑_
    - _Expected_Behavior: 新类型能正确创建 RecurringTransaction 并生成到期交易_
    - _Preservation: 已有 recurring_type 的 generate_due_transactions 行为不变_
    - _Requirements: 2.3, 2.4, 2.5, 3.5_

  - [x] 3.6 后端：新增 API 端点
    - 在 `backend/app/api/v1/endpoints/documents.py` 中添加 `POST /{document_id}/confirm-insurance-recurring` 端点
    - 添加 `POST /{document_id}/confirm-loan-repayment` 端点（或扩展现有 `confirm-loan` 端点）
    - _Requirements: 2.3, 2.4, 2.5_

  - [x] 3.7 数据库迁移
    - 创建 Alembic 迁移文件，添加 `insurance_premium` 和 `loan_repayment` 到 `recurringtransactiontype` 枚举
    - 更新 `check_source_entity_required` 约束
    - _Requirements: 2.4, 2.5_

  - [x] 3.8 验证 Bug Condition 探索性测试现在通过
    - **Property 1: Expected Behavior** - 文档分组与定期交易生成修复
    - **重要**: 重新运行任务 1 中的同一测试 — 不要编写新测试
    - 任务 1 的测试编码了期望行为
    - 当此测试通过时，确认期望行为已满足
    - 运行任务 1 的 bug condition 探索性测试
    - **预期结果**: 测试 PASS（确认缺陷已修复）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.9 验证 Preservation 测试仍然通过
    - **Property 2: Preservation** - 现有分组与定期交易行为不变
    - **重要**: 重新运行任务 2 中的同一测试 — 不要编写新测试
    - 运行任务 2 的 preservation 属性测试
    - **预期结果**: 测试 PASS（确认无回归）
    - 确认修复后所有测试仍然通过（无回归）

- [x] 4. 检查点 - 确保所有测试通过
  - 运行完整测试套件（后端 pytest + 前端 vitest）
  - 确保所有测试通过，如有问题请询问用户
