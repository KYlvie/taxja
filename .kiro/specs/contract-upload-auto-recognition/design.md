# 技术设计：合同上传与自动识别

## 概述

本设计基于现有的 `DocumentPipelineOrchestrator` 架构进行增量改进。系统已具备 Kaufvertrag 和 Mietvertrag 的自动识别和记录创建能力，本次改进聚焦于三个方面：

1. 前端引导优化：从房产页跳转上传时携带上下文参数
2. 后端 Kreditvertrag 处理：补全贷款合同的识别和自动创建流程
3. 数据一致性增强：防重复、地址匹配警告

## 现有架构分析

### 已有能力（无需重建）
- `DocumentPipelineOrchestrator._stage_suggest()` 已处理 Kaufvertrag → 自动创建 Property，Mietvertrag → 自动创建 RecurringTransaction
- `confirm_property_from_ocr` / `confirm_recurring_from_ocr` / `dismiss_import_suggestion` 端点已存在
- 前端 `DocumentsPage` 已有确认/忽略建议的 UI 和 OCR 字段编辑功能
- `documentService` 已有 `confirmProperty`、`confirmRecurring`、`dismissSuggestion` 方法
- `PropertyLoan` 模型已有 `loan_contract_document_id` 字段
- `DocumentType.LOAN_CONTRACT` 枚举已存在

### 需要新增/修改的部分

#### 1. 前端：房产页 → 上传页的上下文传递

当前 `PropertyDetail.tsx` 的"添加合同"按钮链接到 `/documents`，不携带任何上下文。

改进方案：
- 链接改为 `/documents?property_id={id}&type=rental_contract`（或 `purchase_contract`）
- `DocumentsPage` 读取 URL 参数，在上传区域显示上下文提示
- 上传完成后，后端 OCR pipeline 可利用 `property_id` 参数自动关联

涉及文件：
- `frontend/src/components/properties/PropertyDetail.tsx` — 修改链接 URL
- `frontend/src/pages/DocumentsPage.tsx` — 读取 query params，显示上下文提示
- `frontend/src/components/documents/DocumentUpload.tsx` — 传递 property_id 到上传请求

#### 2. 后端：上传端点接收 property_id 参数

`POST /documents/upload` 新增可选 `property_id` query 参数，存入 `document.ocr_result` 的 `_upload_context` 字段，供 pipeline 使用。

涉及文件：
- `backend/app/api/v1/endpoints/documents.py` — upload_document 新增参数

#### 3. 后端：Kreditvertrag 识别与处理

在 `DocumentPipelineOrchestrator._stage_suggest()` 中新增 `LOAN_CONTRACT` 分支：

```python
elif db_type == DBDocumentType.LOAN_CONTRACT:
    suggestion = self._build_kreditvertrag_suggestion(document, result)
    if suggestion:
        result.suggestions.append(suggestion)
```

新增方法：
- `_build_kreditvertrag_suggestion()` — 从 OCR 数据提取贷款金额、利率、月还款额
- `_validate_kreditvertrag()` — 验证必填字段

新增端点：
- `POST /documents/{id}/confirm-loan` — 创建 PropertyLoan + RecurringTransaction(loan_interest)

涉及文件：
- `backend/app/services/document_pipeline_orchestrator.py` — 新增 Kreditvertrag 处理
- `backend/app/api/v1/endpoints/documents.py` — 新增 confirm-loan 端点
- `backend/app/tasks/ocr_tasks.py` — 新增 `_build_kreditvertrag_suggestion` 和 `create_loan_from_suggestion`

#### 4. 前端：Kreditvertrag 建议确认 UI

在 `DocumentsPage` 的文档详情视图中，当 `import_suggestion.type === 'create_loan'` 时显示贷款建议卡片和确认按钮。

涉及文件：
- `frontend/src/pages/DocumentsPage.tsx` — 新增贷款建议确认按钮
- `frontend/src/services/documentService.ts` — 新增 `confirmLoan` 方法

#### 5. 数据一致性：property_id 上下文传递到 pipeline

当上传时携带 `property_id`，pipeline 在生成建议时：
- Mietvertrag：直接关联到指定房产，跳过地址匹配
- Kreditvertrag：直接关联到指定房产
- 如果 OCR 识别的地址与指定房产地址不匹配，在建议中添加 `address_mismatch_warning`

涉及文件：
- `backend/app/services/document_pipeline_orchestrator.py` — 读取 `_upload_context`
- `backend/app/tasks/ocr_tasks.py` — `_build_mietvertrag_suggestion` 使用 context property_id

## 数据流

```
用户在房产页点击"添加合同"
  → 跳转 /documents?property_id=xxx&type=rental_contract
  → DocumentsPage 显示上下文提示
  → 用户上传文件
  → POST /documents/upload?property_id=xxx
  → document.ocr_result._upload_context = {property_id: xxx}
  → OCR Pipeline 处理
  → _stage_suggest 读取 _upload_context
  → 生成 import_suggestion（已关联 property_id）
  → 前端显示建议卡片
  → 用户确认 → 创建记录并关联
```

## 不需要新增的数据库表/字段

- `PropertyLoan.loan_contract_document_id` 已存在
- `RecurringTransaction.source_document_id` 已存在
- `Property.kaufvertrag_document_id` / `mietvertrag_document_id` 已存在
- `DocumentType.LOAN_CONTRACT` 已存在
- 无需新增数据库迁移
