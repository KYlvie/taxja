# 需求文档：合同上传与自动识别

## 简介

本功能优化 Taxja 平台的合同管理流程。当前系统已具备 OCR 文档识别能力，能识别购房合同（Kaufvertrag）和租赁合同（Mietvertrag），并自动生成房产记录或周期性交易建议。本次改进聚焦于：引导用户在添加合同时上传实际文件，上传后自动识别合同类型并创建相应记录，同时确保数据一致性不会因自动化流程而混乱。

## 术语表

- **OCR_Pipeline**: 文档光学字符识别处理管道，负责从上传的文件中提取文本和结构化数据
- **Document_Classifier**: 文档分类器，根据 OCR 提取的文本内容判断文档类型
- **Contract_Recognition_Service**: 合同识别服务，负责识别合同类型并生成导入建议
- **Import_Suggestion**: 导入建议，OCR 识别合同后生成的结构化数据建议（如房产信息、周期性交易）
- **Property_Detail_Page**: 房产详情页面，展示房产信息和关联合同
- **Document_Upload_Page**: 文档上传页面，用户上传文件的主要入口
- **Recurring_Transaction**: 周期性交易，由合同自动生成的定期收支记录
- **Confidence_Score**: 置信度分数，OCR 识别结果的可信程度（0.00-1.00）
- **Kaufvertrag**: 购房合同（奥地利房产购买合同）
- **Mietvertrag**: 租赁合同（奥地利租赁合同）
- **Kreditvertrag**: 贷款合同

## 需求

### 需求 1：合同上传引导提示

**用户故事：** 作为纳税人，我希望在房产详情页添加合同时，系统能引导我上传实际合同文件，以确保合同记录有文件支撑。

#### 验收标准

1. WHEN 用户在 Property_Detail_Page 点击"添加租赁合同"按钮, THE Property_Detail_Page SHALL 跳转到 Document_Upload_Page 并预设文档类型为 rental_contract
2. WHEN 用户在 Property_Detail_Page 点击"添加购房合同"按钮, THE Property_Detail_Page SHALL 跳转到 Document_Upload_Page 并预设文档类型为 purchase_contract
3. THE Property_Detail_Page SHALL 在合同区域显示提示文字，说明合同需通过上传文件方式添加（税务局要求书面合同）
4. WHEN Document_Upload_Page 接收到预设的文档类型参数, THE Document_Upload_Page SHALL 在上传区域显示对应的合同类型标签

### 需求 2：合同类型自动识别

**用户故事：** 作为纳税人，我希望上传合同文件后系统能自动识别合同类型，减少手动分类的工作量。

#### 验收标准

1. WHEN 用户上传一份文件, THE OCR_Pipeline SHALL 在处理完成后自动判断文档是否为合同类型（Kaufvertrag、Mietvertrag 或 Kreditvertrag）
2. WHEN OCR_Pipeline 识别文档为 Kaufvertrag, THE Document_Classifier SHALL 将文档类型设置为 purchase_contract 并提取购房金额、地址、购买日期等关键字段
3. WHEN OCR_Pipeline 识别文档为 Mietvertrag, THE Document_Classifier SHALL 将文档类型设置为 rental_contract 并提取月租金额、租赁地址、租赁起止日期等关键字段
4. WHEN OCR_Pipeline 识别文档为 Kreditvertrag, THE Document_Classifier SHALL 将文档类型设置为 loan_contract 并提取贷款金额、利率、还款周期等关键字段
5. IF OCR_Pipeline 的 Confidence_Score 低于 0.5, THEN THE Contract_Recognition_Service SHALL 将文档标记为"需人工确认"状态，不自动创建任何记录

### 需求 3：合同识别后自动生成导入建议

**用户故事：** 作为纳税人，我希望系统识别合同后能自动生成对应的房产或交易记录建议，让我一键确认即可完成数据录入。

#### 验收标准

1. WHEN OCR_Pipeline 成功识别一份 Kaufvertrag, THE Contract_Recognition_Service SHALL 生成一条包含房产地址、购买价格、建筑价值、土地价值的 Import_Suggestion
2. WHEN OCR_Pipeline 成功识别一份 Mietvertrag, THE Contract_Recognition_Service SHALL 生成一条包含租赁地址、月租金额、租赁起止日期的 Import_Suggestion，并同时生成一条 Recurring_Transaction 建议
3. WHEN OCR_Pipeline 成功识别一份 Kreditvertrag, THE Contract_Recognition_Service SHALL 生成一条包含贷款金额、年利率、月还款额的 Import_Suggestion
4. THE Contract_Recognition_Service SHALL 在生成 Import_Suggestion 前检查是否已存在相同地址的房产记录，避免重复创建
5. IF 系统中已存在相同地址的房产记录, THEN THE Contract_Recognition_Service SHALL 将 Import_Suggestion 标记为"关联到已有房产"而非"创建新房产"

### 需求 4：导入建议的用户确认流程

**用户故事：** 作为纳税人，我希望在系统自动识别合同后能预览和确认生成的记录，避免错误数据进入系统。

#### 验收标准

1. WHEN OCR_Pipeline 生成 Import_Suggestion, THE Document_Upload_Page SHALL 在文档详情中展示导入建议卡片，包含识别出的关键字段
2. WHEN 用户点击"确认导入"按钮, THE Contract_Recognition_Service SHALL 根据 Import_Suggestion 创建对应的房产记录或 Recurring_Transaction
3. WHEN 用户点击"忽略建议"按钮, THE Contract_Recognition_Service SHALL 标记该 Import_Suggestion 为已忽略，不创建任何记录
4. THE Document_Upload_Page SHALL 允许用户在确认前编辑 Import_Suggestion 中的关键字段（金额、日期、地址）
5. WHEN 用户确认导入 Mietvertrag 的建议, THE Contract_Recognition_Service SHALL 同时创建 Recurring_Transaction 并将 source_document_id 设置为该合同文档的 ID

### 需求 5：合同与房产的自动关联

**用户故事：** 作为纳税人，我希望上传的合同能自动关联到对应的房产，无需手动绑定。

#### 验收标准

1. WHEN 用户确认 Kaufvertrag 的 Import_Suggestion 并创建房产, THE Contract_Recognition_Service SHALL 自动将该文档 ID 设置为房产的 kaufvertrag_document_id
2. WHEN 用户确认 Mietvertrag 的 Import_Suggestion, THE Contract_Recognition_Service SHALL 自动将该文档 ID 设置为对应房产的 mietvertrag_document_id
3. WHEN 用户从 Property_Detail_Page 跳转上传合同且 URL 中携带 property_id 参数, THE Contract_Recognition_Service SHALL 在生成 Import_Suggestion 时自动关联到该房产
4. IF 合同上传时携带了 property_id 参数但 OCR 识别的地址与该房产地址不匹配, THEN THE Contract_Recognition_Service SHALL 在 Import_Suggestion 中显示地址不匹配警告，由用户决定是否继续关联

### 需求 6：数据一致性保护

**用户故事：** 作为纳税人，我希望自动识别流程不会导致系统数据混乱，所有自动创建的记录都可追溯和撤销。

#### 验收标准

1. THE Contract_Recognition_Service SHALL 确保每份合同文档只能生成一次 Import_Suggestion，避免重复处理
2. WHEN 用户确认 Import_Suggestion 创建记录后, THE Contract_Recognition_Service SHALL 将该 Import_Suggestion 标记为"已确认"，防止重复确认
3. THE Contract_Recognition_Service SHALL 在创建房产或 Recurring_Transaction 时使用数据库事务，确保所有关联记录要么全部创建成功，要么全部回滚
4. WHEN 自动创建的 Recurring_Transaction 关联了 source_document_id, THE Property_Detail_Page SHALL 在该交易卡片上显示"合同关联"标识，表明该交易由合同自动生成
5. IF OCR_Pipeline 处理过程中发生错误, THEN THE OCR_Pipeline SHALL 将文档标记为已处理（processed_at 非空）并设置 Confidence_Score 为 0.0，防止前端无限轮询

### 需求 7：贷款合同识别与处理

**用户故事：** 作为纳税人，我希望上传贷款合同后系统能识别并生成贷款利息的周期性支出记录，用于税务抵扣计算。

#### 验收标准

1. WHEN OCR_Pipeline 识别文档为 Kreditvertrag, THE Contract_Recognition_Service SHALL 提取贷款金额、年利率、贷款期限、月还款额等关键字段
2. WHEN 用户确认 Kreditvertrag 的 Import_Suggestion, THE Contract_Recognition_Service SHALL 创建一条类型为 loan_interest 的 Recurring_Transaction，金额为月利息支出
3. WHEN Kreditvertrag 关联到某个房产, THE Contract_Recognition_Service SHALL 将贷款记录关联到该房产的 PropertyLoan 模型
4. IF Kreditvertrag 中未包含足够的关键字段（贷款金额或利率缺失）, THEN THE Contract_Recognition_Service SHALL 在 Import_Suggestion 中标记缺失字段并要求用户手动补充
