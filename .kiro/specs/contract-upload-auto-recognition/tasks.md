# 实施任务：合同上传与自动识别

## 任务列表

### Task 1: 房产页上传链接携带上下文参数
- [x] 修改 `PropertyDetail.tsx` 中"添加租赁合同"按钮的链接，从 `/documents` 改为 `/documents?property_id={property.id}&type=rental_contract`
- [x] 在房产详情页购房合同区域（如果 `kaufvertrag_document_id` 为空），添加"上传购房合同"链接，指向 `/documents?property_id={property.id}&type=purchase_contract`
- [x] 确保空状态提示中的"上传租赁合同"链接也携带 `property_id` 参数

**涉及文件**: `frontend/src/components/properties/PropertyDetail.tsx`
**对应需求**: 需求 1（验收标准 1, 2, 3）

### Task 2: 文档上传页读取上下文参数并显示提示
- [x] `DocumentsPage.tsx` 使用 `useSearchParams` 读取 `property_id` 和 `type` 参数
- [x] 当存在 `property_id` 参数时，在上传区域上方显示上下文提示卡片（如"正在为房产 XXX 上传租赁合同"）
- [x] 将 `property_id` 传递给 `DocumentUpload` 组件
- [x] `DocumentUpload.tsx` 在上传请求中将 `property_id` 作为 query 参数传递
- [x] 添加 i18n 翻译键（zh/en/de）

**涉及文件**: `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/components/documents/DocumentUpload.tsx`, `frontend/src/i18n/locales/zh.json`, `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/de.json`
**对应需求**: 需求 1（验收标准 4）, 需求 5（验收标准 3）

### Task 3: 后端上传端点接收 property_id 参数
- [x] `upload_document` 端点新增可选 `property_id: Optional[str] = Query(None)` 参数
- [x] 上传时将 `property_id` 存入 `document.ocr_result` 的 `_upload_context` 字段：`{"_upload_context": {"property_id": property_id}}`
- [x] `batch_upload_documents` 端点同样支持 `property_id` 参数

**涉及文件**: `backend/app/api/v1/endpoints/documents.py`
**对应需求**: 需求 5（验收标准 3）

### Task 4: Pipeline 利用 upload_context 进行房产关联
- [x] `_build_mietvertrag_suggestion` 读取 `document.ocr_result._upload_context.property_id`，如果存在则直接使用该 property_id 而非地址匹配
- [x] 如果 `_upload_context.property_id` 存在但 OCR 识别的地址与该房产地址不匹配，在 suggestion 中添加 `address_mismatch_warning: true`
- [x] `_build_kaufvertrag_suggestion` 同样读取 `_upload_context`，如果存在 property_id 则将 Kaufvertrag 关联到已有房产而非创建新房产

**涉及文件**: `backend/app/tasks/ocr_tasks.py`, `backend/app/services/document_pipeline_orchestrator.py`
**对应需求**: 需求 5（验收标准 3, 4）, 需求 3（验收标准 4, 5）

### Task 5: Kreditvertrag 验证与建议生成（后端）
- [x] 在 `DocumentPipelineOrchestrator._stage_suggest()` 中新增 `LOAN_CONTRACT` 分支，调用 `_build_kreditvertrag_suggestion()`
- [x] 实现 `_validate_kreditvertrag()` 方法：验证贷款金额、利率、月还款额等必填字段
- [x] 实现 `_build_kreditvertrag_suggestion()` 方法：从 OCR 数据构建 `import_suggestion`，type 为 `create_loan`，包含 loan_amount、interest_rate、monthly_payment、lender_name、start_date、end_date
- [x] 如果 `_upload_context.property_id` 存在，自动关联到该房产
- [x] 如果缺少关键字段（贷款金额或利率），将 suggestion 标记为 `status: "needs_input"` 并列出缺失字段

**涉及文件**: `backend/app/services/document_pipeline_orchestrator.py`
**对应需求**: 需求 2（验收标准 4）, 需求 3（验收标准 3）, 需求 7（验收标准 1, 4）

### Task 6: Kreditvertrag 确认端点（后端）
- [x] 新增 `POST /documents/{id}/confirm-loan` 端点
- [x] 从 `document.ocr_result.import_suggestion` 读取贷款数据
- [x] 创建 `PropertyLoan` 记录，设置 `loan_contract_document_id = document_id`
- [x] 创建 `RecurringTransaction`（type=loan_interest），金额为月利息（loan_amount × interest_rate / 12），设置 `source_document_id = document_id`，`loan_id = new_loan.id`
- [x] 生成历史到期交易（调用 `RecurringTransactionService.generate_due_transactions`）
- [x] 将 suggestion 标记为 `status: "confirmed"`
- [x] 在 `ocr_tasks.py` 中实现 `create_loan_from_suggestion()` 辅助函数

**涉及文件**: `backend/app/api/v1/endpoints/documents.py`, `backend/app/tasks/ocr_tasks.py`
**对应需求**: 需求 7（验收标准 2, 3）, 需求 4（验收标准 2, 5）

### Task 7: 前端 Kreditvertrag 建议确认 UI
- [x] `documentService.ts` 新增 `confirmLoan(id: number)` 方法，调用 `POST /documents/{id}/confirm-loan`
- [x] `DocumentsPage.tsx` 文档详情视图中，当 `import_suggestion.type === 'create_loan'` 时显示贷款建议卡片
- [x] 卡片显示：贷款金额、利率、月还款额、贷款人、起止日期
- [x] 提供"确认创建贷款"和"忽略建议"按钮
- [x] 如果 suggestion 有 `missing_fields`，显示缺失字段提示
- [x] 添加 i18n 翻译键（zh/en/de）

**涉及文件**: `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/services/documentService.ts`, `frontend/src/i18n/locales/zh.json`, `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/de.json`
**对应需求**: 需求 4（验收标准 1, 2, 3）, 需求 7（验收标准 4）

### Task 8: 地址不匹配警告 UI
- [x] 当 `import_suggestion.address_mismatch_warning === true` 时，在建议卡片中显示黄色警告提示
- [x] 警告内容：OCR 识别的地址与目标房产地址不一致，用户可选择继续关联或取消
- [x] 添加 i18n 翻译键（zh/en/de）

**涉及文件**: `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/i18n/locales/zh.json`, `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/de.json`
**对应需求**: 需求 5（验收标准 4）

### Task 9: 数据一致性保护增强
- [x] 在 `_build_kreditvertrag_suggestion` 中检查是否已存在相同 `loan_contract_document_id` 的 PropertyLoan，避免重复创建
- [x] 在 `confirm-loan` 端点中检查 suggestion status，如果已是 `confirmed` 则返回已确认信息
- [x] 确保 Kreditvertrag pipeline 处理失败时正确设置 `processed_at` 和 `confidence_score = 0.0`

**涉及文件**: `backend/app/services/document_pipeline_orchestrator.py`, `backend/app/api/v1/endpoints/documents.py`
**对应需求**: 需求 6（验收标准 1, 2, 5）
