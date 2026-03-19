# 缺陷修复需求文档

## 简介

Taxja 文档管理模块存在多个关联缺陷，涉及文档分组配置不合理和定期交易生成缺失。具体包括：贷款合同（LOAN_CONTRACT）被错误归入"房产与租赁"组（仅房贷适用）、"抵扣与减免"分组名称不直观、保险合同和贷款合同未能自动生成定期交易。这些问题影响了用户的文档分类管理体验，并导致贷款还款和保险缴费无法被系统自动追踪。

## 缺陷分析

### 当前行为（缺陷）

1.1 WHEN 用户上传贷款合同（LOAN_CONTRACT）时 THEN 系统将其归入"房产与租赁"（property）分组，但贷款合同不一定与房产相关（如消费贷款、车贷、个人贷款等），导致分类不准确且用户难以找到

1.2 WHEN 用户查看"抵扣与减免"（deductions）分组时 THEN 分组名称"抵扣与减免"过于抽象，用户难以直观理解该分组包含捐赠确认、子女照护费、继续教育费、通勤补贴、教会税等税务优惠相关凭证

1.3 WHEN 用户上传保险合同（VERSICHERUNGSBESTAETIGUNG）并完成 OCR 识别后 THEN 系统不会生成保险缴费的定期交易建议，用户必须手动到"定期交易"页面创建，而租赁合同（Mietvertrag）则会自动生成定期收入

1.4 WHEN 用户上传非房贷类贷款合同（如消费贷款）并确认 OCR 建议后 THEN 系统要求必须关联房产（PropertyLoan）才能创建贷款利息定期交易，无法为独立贷款创建还款定期交易

1.5 WHEN 保险合同的 OCR 结果中包含保费金额（Prämie）和缴费周期信息时 THEN 系统不会利用这些数据生成任何定期交易建议，数据被浪费

### 期望行为（正确）

2.1 WHEN 用户上传贷款合同（LOAN_CONTRACT）时 THEN 系统 SHALL 将其归入"社保与保险"（social_insurance）分组并将该分组重命名为"保险与贷款"（中文）/ "Versicherung & Kredit"（德文）/ "Insurance & Loans"（英文），使贷款合同和保险合同归入同一个金融合同类分组

2.2 WHEN 用户查看原"抵扣与减免"（deductions）分组时 THEN 系统 SHALL 将该分组重命名为"税务优惠凭证"（中文）/ "Steuerliche Absetzposten"（德文）/ "Tax Deduction Documents"（英文），使名称更直观地反映该分组包含的可抵扣费用凭证类型

2.3 WHEN 用户上传保险合同（VERSICHERUNGSBESTAETIGUNG）且 OCR 成功提取保费金额（Prämie）后 THEN 系统 SHALL 在 OCR pipeline 中生成保险缴费定期支出建议（import_suggestion），包含保费金额、缴费频率（默认年缴）和保险类型，供用户确认后自动创建 RecurringTransaction

2.4 WHEN 用户确认保险缴费定期交易建议后 THEN 系统 SHALL 创建类型为 INSURANCE_PREMIUM（新增）的 RecurringTransaction，交易类型为 expense，分类为 insurance，并关联源文档（source_document_id）

2.5 WHEN 用户上传非房贷类贷款合同且 OCR 提取到月供金额后 THEN 系统 SHALL 支持创建不关联房产的独立贷款还款定期交易（RecurringTransactionType.LOAN_REPAYMENT，新增类型），交易类型为 expense，分类为 loan_repayment

### 不变行为（回归防护）

3.1 WHEN 用户上传租赁合同（RENTAL_CONTRACT）时 THEN 系统 SHALL CONTINUE TO 将其归入"房产与租赁"分组，并自动生成租金收入的定期交易

3.2 WHEN 用户上传购房合同（PURCHASE_CONTRACT）时 THEN 系统 SHALL CONTINUE TO 将其归入"房产与租赁"分组，并生成房产创建建议

3.3 WHEN 用户上传与房产关联的贷款合同（房贷）时 THEN 系统 SHALL CONTINUE TO 支持创建 PropertyLoan + loan_interest RecurringTransaction 的完整流程

3.4 WHEN 用户查看"工资与雇佣"、"自营/企业"、"房产与租赁"、"税务申报与通知"、"票据发票"、"银行资料"、"其他"等分组时 THEN 系统 SHALL CONTINUE TO 正确显示这些分组及其包含的文档类型，行为不变

3.5 WHEN 已有的定期交易（rental_income、loan_interest、depreciation 等）到期需要生成交易时 THEN 系统 SHALL CONTINUE TO 按照现有 generate_due_transactions 逻辑正确生成和回填交易记录

3.6 WHEN 用户对文档进行搜索、筛选、下载、删除等操作时 THEN 系统 SHALL CONTINUE TO 正常执行这些操作，不受分组重构影响
