# 需求文档

## 简介

奥地利税务管理系统是一个自动化税务处理平台，旨在帮助奥地利的职员、房东、个体户和小型企业管理复杂的税务情况。该系统能够自动分类收入和支出、计算税款、生成报税文件，并与 FinanzOnline 系统集成，从而减少对会计的依赖并降低税务处理成本。

## 术语表

- **Tax_System**: 奥地利税务管理系统
- **User**: 使用系统的纳税人（职员、房东、个体户或小型企业主）
- **Income_Transaction**: 收入交易记录
- **Expense_Transaction**: 支出交易记录
- **Income_Category**: 收入类型（工资收入、租赁收入、个体户收入、资本收益）
- **Expense_Category**: 支出类型（可抵扣费用的分类）
- **Tax_Report**: 税务报表
- **FinanzOnline**: 奥地利官方电子报税系统
- **Einkommensteuer**: 所得税
- **Lohnsteuer**: 工资税
- **USt**: 增值税（Umsatzsteuer）
- **Tax_Year**: 纳税年度
- **Deductible_Expense**: 可抵扣费用
- **Tax_Calculation_Engine**: 税款计算引擎
- **Transaction_Classifier**: 交易分类器
- **Export_Module**: 导出模块
- **Validation_Engine**: 验证引擎
- **OCR_Engine**: 光学字符识别引擎
- **Document_Classifier**: 文档分类器
- **Document_Image**: 上传的文档图片（小票、账单、工资单等）
- **Document_Type**: 文档类型（工资单、超市小票、采购账单、租赁账单、银行对账单、房产税单、租赁合同等）
- **Extracted_Data**: 从文档中提取的结构化数据
- **Document_Archive**: 文档存档系统
- **SVS**: 社会保险机构（Sozialversicherung der Selbständigen）
- **GSVG**: 商业社会保险法（Gewerbliches Sozialversicherungsgesetz）
- **Neue_Selbständige**: 新自雇人员
- **Sozialversicherungsbeiträge**: 社会保险缴费
- **Sonderausgaben**: 特殊支出（可抵扣）
- **Kinderabsetzbetrag**: 子女扣除
- **Pendlerpauschale**: 通勤补贴
- **Außergewöhnliche_Belastungen**: 额外负担
- **Pauschalierung**: 平税制
- **Steuerberater**: 税务顾问
- **USP**: 奥地利官方税率表（Umsatzsteuerpauschale）
- **Wohnraum**: 住宅租赁
- **Tax_Configuration**: 税务配置（税率、免税额等参数）
- **Admin_Panel**: 管理员后台
- **Net_Income**: 净到手收入（扣除税款和社保后）
- **Quarterly_Prepayment**: 季度预缴税
- **Kapitalerträge**: 资本收益
- **Property_Type**: 房产类型（住宅或商业）
- **Depreciation_Rate**: 折旧率
- **Compliance_Checklist**: 合规性检查清单
- **Audit_Report**: 审计准备报告
- **Dashboard**: 仪表盘
- **What_If_Simulator**: 模拟器
- **Bank_Import_Module**: 银行导入模块
- **Merchant_Database**: 商家数据库
- **ML_Model**: 机器学习模型
- **Batch_Processing**: 批量处理
- **Confidence_Score**: 置信度评分
- **Two_Factor_Auth**: 双因素认证
- **SVS_Contribution**: SVS 社会保险缴费金额
- **Minimum_Contribution_Base**: 最低缴费基数
- **Maximum_Contribution_Base**: 最高缴费基数
- **Family_Deduction**: 家庭扣除
- **Home_Office_Deduction**: 家庭办公室扣除
- **Commuting_Allowance**: 通勤补贴
- **Flat_Rate_Tax**: 平税制
- **Actual_Accounting**: 实际记账
- **Tax_Comparison_Report**: 税务对比报告
- **VAT_Tolerance_Rule**: 增值税容忍规则
- **Accelerated_Depreciation**: 加速折旧
- **Standard_Depreciation**: 标准折旧
- **Tax_Calendar**: 税务日历
- **Tax_Deadline**: 税务截止日期
- **Language_Setting**: 语言设置
- **PWA**: 渐进式 Web 应用
- **Responsive_Design**: 响应式设计
- **Disclaimer**: 免责声明
- **BMF**: 奥地利联邦财政部（Bundesministerium für Finanzen）
- **XML_Validation**: XML 验证
- **PSD2**: 欧洲支付服务指令第二版
- **MT940**: 银行对账单标准格式
- **Gross_Turnover**: 毛营业额
- **Input_VAT**: 进项增值税
- **Output_VAT**: 销项增值税
- **Verlustvortrag**: 亏损结转
- **Arbeitnehmerveranlagung**: 员工年终税款优化/退税申报
- **Lohnzettel**: 工资税卡
- **Kleines_Pendlerpauschale**: 小通勤补贴（公共交通可用）
- **Großes_Pendlerpauschale**: 大通勤补贴（公共交通不可用）
- **Loss_Carryforward**: 可结转亏损余额
- **Tax_Refund**: 退税金额
- **AES_256**: 高级加密标准 256 位
- **TLS_1_3**: 传输层安全协议 1.3 版
- **AI_Assistant**: AI 税务助手
- **RAG**: 检索增强生成（Retrieval-Augmented Generation）
- **Chat_History**: 聊天记录
- **Knowledge_Base**: AI 知识库

## 需求

### 需求 1: 交易记录管理

**用户故事:** 作为用户，我想要记录所有收入和支出交易，以便系统能够准确计算我的税务情况。

#### 验收标准

1. THE Tax_System SHALL 允许用户创建 Income_Transaction 记录，包含日期、金额、描述和来源
2. THE Tax_System SHALL 允许用户创建 Expense_Transaction 记录，包含日期、金额、描述和类型
3. WHEN 用户创建交易记录时，THE Tax_System SHALL 验证必填字段的完整性
4. WHEN 用户创建交易记录时，THE Tax_System SHALL 验证金额为正数且格式正确
5. THE Tax_System SHALL 允许用户编辑已存在的交易记录
6. THE Tax_System SHALL 允许用户删除交易记录
7. THE Tax_System SHALL 为每个交易记录生成唯一标识符

### 需求 2: 自动交易分类

**用户故事:** 作为用户，我想要系统自动分类我的收入和支出，以便节省手动分类的时间。

#### 验收标准

1. WHEN 用户创建 Income_Transaction 时，THE Transaction_Classifier SHALL 自动识别 Income_Category（工资收入、租赁收入或个体户收入）
2. WHEN 用户创建 Expense_Transaction 时，THE Transaction_Classifier SHALL 自动识别 Expense_Category
3. THE Transaction_Classifier SHALL 基于交易描述、金额模式和历史数据进行分类
4. WHEN 自动分类完成时，THE Tax_System SHALL 允许用户手动调整分类结果
5. WHEN 用户手动调整分类时，THE Transaction_Classifier SHALL 学习该调整以改进未来分类准确性
6. THE Tax_System SHALL 为每个 Expense_Category 标记是否为 Deductible_Expense

### 需求 3: 所得税计算

**用户故事:** 作为用户，我想要系统自动计算我的所得税，以便了解我需要缴纳的税款。

#### 验收标准

1. WHEN 用户请求税款计算时，THE Tax_Calculation_Engine SHALL 汇总指定 Tax_Year 的所有收入
2. THE Tax_Calculation_Engine SHALL 应用 2026 年奥地利所得税累进税率，根据 USP 2026 年税率表（通胀调整 1.7333%）
3. THE Tax_Calculation_Engine SHALL 应用免税额 €13,539（2026 年官方 USP 确认值）
4. THE Tax_Calculation_Engine SHALL 应用以下 2026 年完整税级（根据 USP 官方表）：
   - €0 – €13,539：0%
   - €13,539 – €21,992：20%
   - €21,992 – €36,458：30%
   - €36,458 – €70,365：40%
   - €70,365 – €104,859：48%
   - €104,859 – €1,000,000：50%
   - €1,000,000 以上：55%
5. THE Tax_Calculation_Engine SHALL 从总收入中扣除所有 Deductible_Expense 和 Sonderausgaben
6. THE Tax_Calculation_Engine SHALL 自动将已缴 SVS_Contribution 作为 Sonderausgaben 抵扣项
7. WHEN 应税收入小于或等于免税额时，THE Tax_Calculation_Engine SHALL 返回税款为 €0
8. THE Tax_Calculation_Engine SHALL 分别计算工资收入、租赁收入、个体户收入和 Kapitalerträge 的税款
9. THE Tax_Calculation_Engine SHALL 返回详细的税款计算明细，包括各税率档次的应税金额
10. THE Tax_Calculation_Engine SHALL 从 Tax_Configuration 读取税率表，支持管理员通过 Admin_Panel 更新
11. THE Tax_System SHALL 明确显示"根据 USP 2026 年税率表计算"
12. THE Admin_Panel SHALL 允许管理员更新税率表、免税额和税级配置

### 需求 4: 增值税计算

**用户故事:** 作为个体户或小型企业主，我想要系统计算我的增值税义务，以便正确申报和缴纳增值税。

#### 验收标准

1. WHERE 用户年 Gross_Turnover 超过 €55,000，THE Tax_Calculation_Engine SHALL 计算增值税义务
2. THE Tax_Calculation_Engine SHALL 应用标准增值税率 20%
3. THE Tax_Calculation_Engine SHALL 应用住宅租赁（Wohnraum）增值税率 10%（或可选择豁免）
4. THE Tax_Calculation_Engine SHALL 应用商业租赁增值税率 20%
5. THE Tax_System SHALL 要求用户标记 Property_Type（住宅或商业）以应用正确的增值税率
6. WHEN 用户年 Gross_Turnover 不超过 €55,000 时，THE Tax_System SHALL 提示用户符合小企业免税条件
7. WHEN 用户年 Gross_Turnover 超过 €55,000 但不超过 €60,500 时，THE Tax_System SHALL 应用 VAT_Tolerance_Rule：提示"当年仍可免税，但次年自动取消免税资格"
8. WHEN 用户符合小企业免税条件或触发 VAT_Tolerance_Rule 时，THE Tax_System SHALL 建议"考虑咨询 Steuerberater 是否主动纳税以抵扣进项税"
9. THE Tax_Calculation_Engine SHALL 计算 Output_VAT（收入中的增值税）
10. THE Tax_Calculation_Engine SHALL 计算 Input_VAT（可抵扣支出中的增值税）
11. THE Tax_Calculation_Engine SHALL 计算应缴增值税（Output_VAT 减去 Input_VAT）
12. THE Tax_System SHALL 生成季度增值税报表
13. THE Tax_System SHALL 在用户 Gross_Turnover 接近 €55,000 时提前预警

### 需求 5: 租赁收入费用抵扣

**用户故事:** 作为房东，我想要系统识别并计算可抵扣的租赁相关费用，以便减少我的应税收入。

#### 验收标准

1. THE Tax_System SHALL 识别以下租赁相关 Deductible_Expense：维护费、管理费、贷款利息、折旧、保险费、物业税
2. WHEN 用户记录租赁相关支出时，THE Tax_System SHALL 自动标记为 Deductible_Expense
3. THE Tax_Calculation_Engine SHALL 从租赁收入中扣除所有租赁相关 Deductible_Expense
4. THE Tax_System SHALL 计算房产 Standard_Depreciation，Depreciation_Rate 为 1.5%（66.6 年）
5. WHERE 2026 年可申请 Accelerated_Depreciation，THE Tax_System SHALL 提供最高 4.5% 前几年的折旧选项
6. THE Tax_System SHALL 根据 Property_Type（住宅或商业）自动推荐最优折旧方案
7. WHEN 计算折旧时，THE Tax_System SHALL 要求用户提供房产购买价格和购买日期
8. THE Tax_System SHALL 生成租赁收入和支出的详细报表
9. THE Tax_System SHALL 区分住宅租赁（Wohnraum）和商业租赁的增值税处理
10. THE Tax_System SHALL 要求用户输入 Property_Type 以应用正确的增值税率和折旧规则
11. WHEN 用户选择住宅租赁时，THE Tax_System SHALL 提供 10% 增值税或豁免选项
12. WHEN 用户选择商业租赁时，THE Tax_System SHALL 自动应用 20% 增值税率

### 需求 6: 个体户费用抵扣

**用户故事:** 作为个体户，我想要系统识别并计算可抵扣的业务相关费用，以便减少我的应税收入。

#### 验收标准

1. THE Tax_System SHALL 识别以下业务相关 Deductible_Expense：办公用品、设备、差旅费、营销费用、专业服务费、保险费
2. WHEN 用户记录业务相关支出时，THE Tax_System SHALL 自动标记为 Deductible_Expense
3. THE Tax_Calculation_Engine SHALL 从个体户收入中扣除所有业务相关 Deductible_Expense
4. WHERE 用户使用家庭办公室，THE Tax_System SHALL 计算家庭办公室费用抵扣比例
5. THE Tax_System SHALL 验证费用抵扣的合理性，并在可疑情况下提示用户
6. THE Tax_System SHALL 生成个体户收入和支出的详细报表

### 需求 7: 税务报表生成

**用户故事:** 作为用户，我想要系统生成报税所需的所有文件和报表，以便提交给税务机关或会计。

#### 验收标准

1. THE Tax_System SHALL 生成年度所得税报表（Einkommensteuererklärung）
2. WHERE 适用，THE Tax_System SHALL 生成增值税报表（Umsatzsteuererklärung）
3. THE Tax_System SHALL 生成收入和支出汇总表
4. THE Tax_System SHALL 生成可抵扣费用明细表
5. THE Export_Module SHALL 支持导出为 PDF 格式
6. THE Export_Module SHALL 支持导出为 CSV 格式
7. THE Export_Module SHALL 支持导出为 FinanzOnline 兼容的 XML 格式
8. WHEN 生成报表时，THE Tax_System SHALL 包含所有必需的纳税人信息和计算明细

### 需求 8: FinanzOnline 集成

**用户故事:** 作为用户，我想要系统能够与 FinanzOnline 集成，以便直接电子申报税务。

#### 验收标准

1. THE Tax_System SHALL 生成符合 FinanzOnline 格式要求的 XML 文件
2. THE Validation_Engine SHALL 验证生成的 XML 文件符合 FinanzOnline 架构定义
3. THE Tax_System SHALL 生成 XML 文件并提供详细的 FinanzOnline 上传指引（注：目前无公开 API，需手动上传）
4. THE Tax_System SHALL 提供 BMF 测试账号申请指引，用于 XML_Validation
5. THE Tax_System SHALL 提醒用户报税截止日期（6 月 30 日）
6. WHEN 报税截止日期临近时，THE Tax_System SHALL 发送通知给用户
7. THE Tax_System SHALL 在 Tax_Calendar 中显示所有重要 Tax_Deadline

### 需求 9: 数据验证和完整性

**用户故事:** 作为用户，我想要系统验证我的数据完整性和准确性，以便避免报税错误。

#### 验收标准

1. THE Validation_Engine SHALL 验证所有交易记录的日期在有效的 Tax_Year 范围内
2. THE Validation_Engine SHALL 验证所有金额字段为正数且精度为两位小数
3. THE Validation_Engine SHALL 检查是否存在重复的交易记录
4. WHEN 用户生成税务报表时，THE Validation_Engine SHALL 检查必需信息的完整性
5. IF 发现数据不完整或不一致，THEN THE Tax_System SHALL 显示详细的错误消息和修复建议
6. THE Tax_System SHALL 在用户提交报表前执行最终验证检查
7. THE Validation_Engine SHALL 验证可抵扣费用是否符合奥地利税法规定

### 需求 10: 多年度数据管理

**用户故事:** 作为用户，我想要系统管理多个纳税年度的数据，以便查看历史记录和趋势。

#### 验收标准

1. THE Tax_System SHALL 允许用户在不同 Tax_Year 之间切换
2. THE Tax_System SHALL 为每个 Tax_Year 独立存储交易记录和税务计算结果
3. THE Tax_System SHALL 允许用户查看历史 Tax_Year 的税务报表
4. THE Tax_System SHALL 提供跨年度的收入和支出趋势分析
5. WHEN 新的 Tax_Year 开始时，THE Tax_System SHALL 自动创建新的年度数据空间
6. THE Tax_System SHALL 允许用户导入上一年度的数据作为参考

### 需求 11: 用户配置和个人信息管理

**用户故事:** 作为用户，我想要配置我的个人信息和税务身份，以便系统能够准确计算我的税务情况。

#### 验收标准

1. THE Tax_System SHALL 允许用户输入个人信息：姓名、地址、税号
2. THE Tax_System SHALL 允许用户选择适用的身份类型：职员、房东、个体户或组合
3. WHERE 用户是个体户，THE Tax_System SHALL 允许用户输入企业信息和增值税号
4. WHERE 用户是房东，THE Tax_System SHALL 允许用户输入房产信息
5. THE Tax_System SHALL 加密存储敏感的个人信息
6. THE Tax_System SHALL 允许用户随时更新个人信息
7. WHEN 个人信息变更时，THE Tax_System SHALL 验证新信息的有效性

### 需求 12: 数据导入功能

**用户故事:** 作为用户，我想要从银行对账单或其他来源导入交易数据，以便减少手动输入工作。

#### 验收标准

1. THE Tax_System SHALL 支持从 CSV 文件导入交易记录
2. THE Bank_Import_Module SHALL 支持从奥地利主流银行导入数据：Raiffeisen、Erste Bank、Sparkasse
3. THE Bank_Import_Module SHALL 支持 MT940 格式银行对账单
4. WHERE 银行支持 PSD2 API，THE Bank_Import_Module SHALL 支持直接导入
5. WHEN 导入数据时，THE Tax_System SHALL 映射文件列到系统字段
6. WHEN 导入数据时，THE Transaction_Classifier SHALL 自动分类导入的交易
7. THE Tax_System SHALL 在导入前预览数据并允许用户确认
8. IF 导入数据包含错误或不完整记录，THEN THE Tax_System SHALL 显示错误报告并允许用户修正
9. THE Tax_System SHALL 检测并防止重复导入相同的交易记录
10. THE Bank_Import_Module SHALL 识别银行对账单中的常见交易类型

### 需求 13: 税务规则更新机制

**用户故事:** 作为用户，我想要系统能够适应税法变化，以便始终使用最新的税率和规则。

#### 验收标准

1. THE Tax_System SHALL 为每个 Tax_Year 维护独立的税率和规则配置
2. THE Tax_System SHALL 允许管理员更新税率、免税额和其他税务参数
3. WHEN 税务规则更新时，THE Tax_System SHALL 仅影响当前和未来的 Tax_Year
4. THE Tax_System SHALL 保留历史 Tax_Year 的税务规则以确保历史计算的准确性
5. THE Tax_System SHALL 在用户界面显示当前使用的税率和规则
6. WHERE 税法发生重大变化，THE Tax_System SHALL 通知用户并提供更新说明

### 需求 14: 报表和数据导出的往返一致性

**用户故事:** 作为用户，我想要确保导出和导入的数据保持一致，以便在不同系统间安全迁移数据。

#### 验收标准

1. THE Export_Module SHALL 导出完整的交易数据为 CSV 格式
2. THE Tax_System SHALL 能够导入之前导出的 CSV 文件
3. FOR ALL 有效的交易数据集，导出然后导入然后再导出 SHALL 产生相同的数据（往返属性）
4. THE Export_Module SHALL 在导出文件中包含所有必要的元数据和分类信息
5. WHEN 导入之前导出的数据时，THE Tax_System SHALL 保留所有交易分类和计算结果
6. THE Validation_Engine SHALL 验证导入数据的完整性和格式正确性

### 需求 15: FinanzOnline XML 格式的往返验证

**用户故事:** 作为开发者，我想要确保生成的 FinanzOnline XML 格式正确，以便避免提交失败。

#### 验收标准

1. THE Export_Module SHALL 生成符合 FinanzOnline 架构的 XML 文件
2. THE Validation_Engine SHALL 解析生成的 XML 文件并验证其结构
3. THE Tax_System SHALL 提供 XML 格式化工具，将 Tax_Report 转换为可读的 XML 格式
4. FOR ALL 有效的 Tax_Report，解析 XML 然后格式化然后再解析 SHALL 产生等效的 Tax_Report（往返属性）
5. IF XML 生成失败或格式不正确，THEN THE Tax_System SHALL 返回详细的错误信息
6. THE Validation_Engine SHALL 使用官方 FinanzOnline 架构定义文件进行验证

### 需求 16: 税款计算的不变性属性

**用户故事:** 作为用户，我想要确保税款计算的准确性和一致性，以便信任系统的计算结果。

#### 验收标准

1. FOR ALL 交易记录集合，无论添加顺序如何，THE Tax_Calculation_Engine SHALL 计算出相同的总税款（交换律）
2. WHEN 用户修改交易分类但不改变金额时，THE Tax_Calculation_Engine SHALL 重新计算税款并反映分类变化的影响
3. FOR ALL Tax_Year，总收入 SHALL 等于所有 Income_Transaction 金额之和（不变性）
4. FOR ALL Tax_Year，总可抵扣费用 SHALL 小于或等于总支出（不变性）
5. WHEN 应税收入为负数时，THE Tax_Calculation_Engine SHALL 返回税款为 €0
6. THE Tax_Calculation_Engine SHALL 确保计算结果精度为两位小数

### 需求 17: 数据安全和隐私

**用户故事:** 作为用户，我想要我的财务和税务数据得到安全保护，以便保护我的隐私。

#### 验收标准

1. THE Tax_System SHALL 加密存储所有用户数据
2. THE Tax_System SHALL 使用 AES_256 加密存储数据（at rest）和 TLS_1_3 传输加密（in transit）
3. THE Tax_System SHALL 要求用户身份验证才能访问系统
3. THE Tax_System SHALL 提供 Two_Factor_Auth（双因素认证）
4. THE Tax_System SHALL 在用户会话超时后自动登出
5. THE Tax_System SHALL 记录所有数据访问和修改的审计日志
6. THE Tax_System SHALL 允许用户导出所有个人数据（一键操作）
7. THE Tax_System SHALL 允许用户永久删除所有个人数据（一键操作）
8. THE Tax_System SHALL 遵守 GDPR 和奥地利数据保护法规
9. THE Tax_System SHALL 在每页底部显示 Disclaimer："本系统仅供参考，不构成税务咨询。最终报税以 FinanzOnline 为准，建议复杂情况咨询 Steuerberater。开发者不承担任何税务责任。"
10. WHEN 用户首次启动系统时，THE Tax_System SHALL 弹窗显示完整 Disclaimer，用户必须同意才能使用
11. THE Tax_System SHALL 明确说明不提供"税务顾问服务"（符合 Steuerberatungsgesetz 限制）

### 需求 18: 错误处理和恢复

**用户故事:** 作为用户，我想要系统能够优雅地处理错误，以便在出现问题时不会丢失数据。

#### 验收标准

1. IF 系统遇到意外错误，THEN THE Tax_System SHALL 显示用户友好的错误消息
2. IF 数据保存失败，THEN THE Tax_System SHALL 保留用户输入并允许重试
3. THE Tax_System SHALL 自动保存用户的工作进度
4. THE Tax_System SHALL 提供数据备份和恢复功能
5. IF 导入数据失败，THEN THE Tax_System SHALL 回滚所有更改并保持数据一致性
6. THE Tax_System SHALL 记录所有错误到日志文件以便故障排查
7. WHEN 系统检测到数据损坏时，THE Tax_System SHALL 尝试从备份恢复数据

### 需求 19: 文档智能识别和 OCR 处理

**用户故事:** 作为用户，我想要上传文档照片并让系统自动识别内容，以便快速录入交易数据并保存税务证据。

#### 验收标准

1. THE Tax_System SHALL 接受用户上传的 Document_Image，支持 JPG、PNG 和 PDF 格式
2. WHEN 用户上传 Document_Image 时，THE OCR_Engine SHALL 提取文档中的文本内容
3. THE OCR_Engine SHALL 识别德语和英语文本
4. THE OCR_Engine SHALL 提取关键信息：日期、金额、商家名称、项目明细和增值税金额
5. WHEN 超市小票识别完成时，THE OCR_Engine SHALL 识别 Document_Type 包括：工资单、超市小票、采购账单、租赁账单、银行对账单、房产税单、租赁合同、Lohnzettel（工资税卡）、SVS 缴费通知单
6. THE Tax_System SHALL 支持 Batch_Processing，允许用户批量上传多个 Document_Image
7. WHEN 批量上传时，THE Tax_System SHALL 使用 ML_Model 智能分组（如一堆超市小票自动按月汇总）
8. THE Tax_System SHALL 将原始 Document_Image 存储到 Document_Archive 作为电子存档
9. THE Tax_System SHALL 为每个存档的 Document_Image 生成唯一标识符并关联到相应的交易记录

### 需求 20: 工资单智能识别

**用户故事:** 作为职员，我想要上传工资单照片并让系统自动识别，以便快速创建收入记录。

#### 验收标准

1. WHEN THE Document_Classifier 识别 Document_Type 为工资单时，THE Tax_System SHALL 提取工资金额、发放日期、雇主名称和税前税后金额
2. WHEN 工资单识别完成时，THE Tax_System SHALL 询问用户："这是工资单吗？是否设定为固定月收入？"
3. WHEN 用户确认后，THE Tax_System SHALL 自动创建 Income_Transaction 记录，分类为工资收入
4. WHERE 用户选择设定为固定月收入，THE Tax_System SHALL 为后续月份自动生成预期收入记录
5. THE Tax_System SHALL 显示 Extracted_Data 供用户审核和修改
6. THE Tax_System SHALL 将工资单 Document_Image 关联到创建的 Income_Transaction

### 需求 21: 超市小票智能识别

**用户故事:** 作为个体户，我想要上传超市购物小票并让系统智能判断哪些项目可以抵扣，以便准确计算业务成本。

#### 验收标准

1. WHEN THE Document_Classifier 识别 Document_Type 为超市小票时，THE Tax_System SHALL 提取购物日期、总金额、商家名称和项目明细
2. WHEN 超市小票识别完成时，THE Tax_System SHALL 询问用户："这是个体户采购吗？需要抵扣税款计算为成本吗？"
3. THE Tax_System SHALL 分析项目明细并智能判断哪些项目可能用于业务用途
4. THE Tax_System SHALL 显示可抵扣建议，标记哪些项目可以抵扣、哪些不能抵扣，并说明理由
5. THE Tax_System SHALL 允许用户调整可抵扣项目的选择
6. WHEN 用户确认后，THE Tax_System SHALL 创建 Expense_Transaction 记录，仅包含可抵扣的项目金额
7. THE Tax_System SHALL 将超市小票 Document_Image 关联到创建的 Expense_Transaction

### 需求 22: 采购账单智能识别

**用户故事:** 作为个体户或房东，我想要上传采购账单并让系统自动识别为业务费用，以便快速录入可抵扣支出。

#### 验收标准

1. WHEN THE Document_Classifier 识别 Document_Type 为采购账单时，THE Tax_System SHALL 提取账单日期、总金额、供应商名称、项目明细和增值税金额
2. THE Document_Classifier SHALL 判断账单类型（办公用品、设备、维护费用、专业服务等）
3. WHEN 采购账单识别完成时，THE Tax_System SHALL 显示识别结果和建议的 Expense_Category
4. THE Tax_System SHALL 询问用户确认："这是业务费用吗？建议分类为 [类别]，可抵扣。请确认。"
5. THE Tax_System SHALL 显示提取的增值税金额，用于进项税抵扣计算
6. WHEN 用户确认后，THE Tax_System SHALL 创建 Expense_Transaction 记录，标记为 Deductible_Expense
7. THE Tax_System SHALL 将采购账单 Document_Image 关联到创建的 Expense_Transaction

### 需求 23: OCR 识别结果的用户确认机制

**用户故事:** 作为用户，我想要在系统自动识别后能够审核和确认数据，以便确保税务数据的准确性和合规性。

#### 验收标准

1. WHEN OCR 处理完成时，THE Tax_System SHALL 显示 Extracted_Data 的所有字段供用户审核
2. THE Tax_System SHALL 高亮显示 OCR_Engine 识别置信度较低的字段
3. THE Tax_System SHALL 允许用户编辑任何 Extracted_Data 字段
4. THE Tax_System SHALL 要求用户明确确认 Document_Type 和交易分类
5. THE Tax_System SHALL 在用户确认前不创建任何交易记录
6. WHEN 用户确认数据后，THE Tax_System SHALL 记录该确认操作和时间戳
7. THE Tax_System SHALL 允许用户稍后返回查看和修改已确认的数据

### 需求 24: 文档存档和检索

**用户故事:** 作为用户，我想要系统保存所有上传的文档原始照片，以便在税务审计时提供证据。

#### 验收标准

1. THE Document_Archive SHALL 永久存储所有上传的 Document_Image 原始文件
2. THE Tax_System SHALL 为每个交易记录显示关联的 Document_Image 缩略图
3. THE Tax_System SHALL 允许用户点击缩略图查看完整的 Document_Image
4. THE Tax_System SHALL 允许用户下载原始 Document_Image 文件
5. THE Tax_System SHALL 在生成税务报表时包含相关 Document_Image 的引用列表
6. THE Tax_System SHALL 允许用户按日期、Document_Type 或金额搜索存档的文档
7. THE Tax_System SHALL 在用户删除交易记录时保留关联的 Document_Image，并标记为已删除交易的存档

### 需求 25: OCR 识别质量和错误处理

**用户故事:** 作为用户，我想要系统在 OCR 识别失败或质量不佳时给出清晰的反馈，以便我知道如何改进。

#### 验收标准

1. IF OCR_Engine 无法识别 Document_Image 中的文本，THEN THE Tax_System SHALL 提示用户："无法识别文档内容，请确保照片清晰且光线充足"
2. IF OCR_Engine 识别 Confidence_Score 低于 60%，THEN THE Tax_System SHALL 弹出"推荐手动输入或重拍"模板
3. WHEN Confidence_Score 低于 60% 时，THE Tax_System SHALL 提供清晰的重拍指引和最佳实践
4. THE Tax_System SHALL 为每个提取的字段显示 Confidence_Score
5. IF Document_Image 格式不支持，THEN THE Tax_System SHALL 返回错误消息并列出支持的格式
6. IF Document_Image 文件大小超过 10MB，THEN THE Tax_System SHALL 提示用户压缩图片
7. THE Tax_System SHALL 允许用户重新上传 Document_Image 以改进识别结果
8. THE Tax_System SHALL 提供手动输入选项，当 OCR 识别完全失败时

### 需求 26: 奥地利常见文档格式识别

**用户故事:** 作为奥地利用户，我想要系统能够识别奥地利常见的文档格式，以便提高识别准确性。

#### 验收标准

1. THE OCR_Engine SHALL 识别奥地利主要超市的小票格式（Billa、Spar、Hofer、Lidl、Merkur）
2. THE OCR_Engine SHALL 识别奥地利常见的增值税标注格式（20% USt、10% USt）
3. THE Document_Classifier SHALL 识别奥地利工资单的标准格式和术语（Brutto、Netto、Lohnsteuer、Sozialversicherung）
4. THE OCR_Engine SHALL 识别奥地利日期格式（DD.MM.YYYY）
5. THE OCR_Engine SHALL 识别欧元货币符号和金额格式（€1.234,56）
6. THE Tax_System SHALL 维护 Merchant_Database（奥地利常见商家和供应商数据库），用于改进识别准确性
7. THE ML_Model SHALL 持续学习用户的常用供应商和商家，自动改进识别结果
8. THE Tax_System SHALL 允许用户自定义商家学习，将新商家添加到个人 Merchant_Database

### 需求 27: OCR 数据提取的往返验证

**用户故事:** 作为开发者，我想要确保 OCR 提取的数据能够正确存储和检索，以便保证数据完整性。

#### 验收标准

1. THE Tax_System SHALL 将 Extracted_Data 序列化为结构化格式存储
2. THE Tax_System SHALL 能够从存储中检索 Extracted_Data 并重新显示
3. FOR ALL 有效的 Extracted_Data，存储然后检索然后再存储 SHALL 产生相同的数据（往返属性）
4. THE Tax_System SHALL 保留 OCR_Engine 的原始输出和用户修改后的最终数据
5. THE Tax_System SHALL 记录用户对 Extracted_Data 的所有修改历史
6. THE Tax_System SHALL 允许用户查看 OCR 原始识别结果和当前数据的对比

### 需求 28: 社会保险（SVS/GSVG）计算模块

**用户故事:** 作为个体户或新自雇人员，我想要系统自动计算社会保险缴费，以便了解实际到手收入和可抵扣金额。

#### 验收标准

1. THE Tax_System SHALL 根据用户类型（职员/个体户/新自雇）自动计算 Sozialversicherungsbeiträge
2. THE Tax_Calculation_Engine SHALL 动态计算实际 SVS 费率（随基数自动调整）：养老保险 18.5%、医疗保险 6.8%、事故保险固定 €12.95/月、补充养老 1.53%
3. THE Tax_Calculation_Engine SHALL 根据实际收入基数动态计算 SVS 费率，而非固定百分比
4. WHERE 用户是个体户（GSVG）且年收入超过 €6,613.20，THE Tax_System SHALL 按 Minimum_Contribution_Base €551.10/月计算最低缴费
5. THE Tax_System SHALL 应用 Maximum_Contribution_Base €8,085/月
6. WHERE 用户是 Neue_Selbständige，THE Tax_System SHALL 应用最低缴费 €160.81/月特殊规则
7. THE Tax_Calculation_Engine SHALL 将已缴 SVS_Contribution 自动作为 Sonderausgaben 抵扣项目
8. THE Tax_System SHALL 生成"SVS 缴费预测表 + 季度预缴提醒"
9. THE Tax_System SHALL 显示 Net_Income（收入 - 税 - 社保）
10. THE Tax_System SHALL 在 Dashboard 显示年度社保缴费总额和可抵扣金额

### 需求 29: 家庭与特殊扣除

**用户故事:** 作为有家庭的纳税人，我想要系统自动应用家庭相关扣除，以便减少税负。

#### 验收标准

1. THE Tax_System SHALL 自动应用单身/单亲/子女扣除（Kinderabsetzbetrag）
2. THE Tax_System SHALL 自动计算 Commuting_Allowance（Pendlerpauschale）：
   - 根据通勤距离（20/40/60km 分级）、公共交通可用性计算基础金额（€58-€306/月）
   - 加上 Pendlereuro（€6/km/年）
   - 区分"小通勤补贴"（Kleines Pendlerpauschale）和"大通勤补贴"（Großes Pendlerpauschale）
3. THE Tax_System SHALL 自动应用 Home_Office_Deduction 平额扣除 €300/年
4. WHEN 用户输入大病费用时，THE Tax_System SHALL 智能提示可能符合 Außergewöhnliche_Belastungen 条件
5. THE Tax_System SHALL 根据用户家庭状况自动计算所有适用的 Family_Deduction
6. THE Tax_System SHALL 要求用户输入家庭成员信息以计算扣除
7. THE Tax_System SHALL 验证扣除金额符合奥地利税法规定

### 需求 30: 预缴税与资本收入

**用户故事:** 作为个体户或房东，我想要系统估算季度预缴税款，以便提前准备资金。

#### 验收标准

1. THE Tax_System SHALL 自动估算 Quarterly_Prepayment（Einkommensteuer-Vorauszahlungen）
2. THE Tax_Calculation_Engine SHALL 支持 Kapitalerträge 27.5% 平税计算
3. THE Tax_System SHALL 支持租赁以外的其他 Income_Category
4. THE Tax_System SHALL 生成季度预缴提醒和金额建议
5. THE Tax_System SHALL 在 Tax_Calendar 中显示季度预缴 Tax_Deadline
6. THE Tax_System SHALL 根据当前年度收入趋势预测全年税款

### 需求 31: 小企业平税制（Pauschalierung）选项

**用户故事:** 作为小企业主，我想要比较实际记账和平税制的节税效果，以便选择最优方案。

#### 验收标准

1. WHERE 用户利润不超过 €33,000，THE Tax_System SHALL 自动计算 15% 基本免税额（最高 €4,950）
2. THE Tax_System SHALL 支持 6%/12% 营业额 Flat_Rate_Tax 选项
3. THE Tax_System SHALL 允许用户切换 Actual_Accounting 和 Flat_Rate_Tax 模式
4. THE Tax_System SHALL 生成 Tax_Comparison_Report，双轨计算对比节税效果
5. THE Tax_System SHALL 显示推荐方案和理由
6. THE Tax_System SHALL 说明每种方案的优缺点和适用条件

### 需求 32: 审计就绪检查清单

**用户故事:** 作为用户，我想要生成税务审计准备报告，以便应对可能的税务检查。

#### 验收标准

1. THE Tax_System SHALL 生成 Audit_Report（税务审计准备报告）
2. THE Audit_Report SHALL 包含所有 Document_Image 引用和存档位置
3. THE Audit_Report SHALL 列出所有可抵扣项目的理由说明
4. THE Audit_Report SHALL 提供 Compliance_Checklist
5. THE Audit_Report SHALL 标记可能存在风险的项目并提供建议
6. THE Tax_System SHALL 验证所有交易记录都有对应的 Document_Image 支持

### 需求 33: 多语言支持

**用户故事:** 作为国际用户，我想要使用中文、英文或德文界面，以便更好地理解和使用系统。

#### 验收标准

1. THE Tax_System SHALL 支持德语、英语、中文三种 Language_Setting
2. THE Tax_System SHALL 允许用户随时切换 Language_Setting
3. THE Tax_System SHALL 为所有税务术语提供多语言对照
4. THE OCR_Engine SHALL 识别德语和英语文本
5. THE Export_Module SHALL 支持多语言报表生成
6. WHEN 用户首次访问时，THE Tax_System SHALL 根据浏览器设置自动选择默认 Language_Setting

### 需求 34: 仪表盘与税务模拟器

**用户故事:** 作为用户，我想要在首页看到税务概览和节税建议，以便快速了解我的税务状况。

#### 验收标准

1. THE Dashboard SHALL 显示"2026 年预计税款 €X（已缴 €Y，还需 €Z）"
2. THE Dashboard SHALL 显示"节税建议 Top 3"
3. THE Dashboard SHALL 显示"节税潜力估算（平税制可省 €X）"
4. THE What_If_Simulator SHALL 允许用户改动一笔支出，实时显示税款变化
4. THE Dashboard SHALL 显示年度收入/支出趋势图
5. THE Dashboard SHALL 显示 Tax_Calendar 和重要 Tax_Deadline 提醒
6. THE Dashboard SHALL 显示 Net_Income（收入 - 税 - 社保）
7. THE Dashboard SHALL 显示当前 Gross_Turnover 和增值税免税额距离

### 需求 35: 移动端和响应式设计

**用户故事:** 作为移动用户，我想要在手机上使用系统，以便随时随地拍照上传小票。

#### 验收标准

1. THE Tax_System SHALL 提供 Responsive_Design Web 界面
2. THE Tax_System SHALL 支持 PWA（Progressive Web App）
3. THE Tax_System SHALL 在移动端优化拍照上传功能
4. THE Tax_System SHALL 支持离线查看已保存的数据
5. THE Tax_System SHALL 提供移动端优化的 OCR 拍照界面
6. THE Tax_System SHALL 在移动端提供简化的 Dashboard 视图

### 需求 36: 亏损结转（Verlustvortrag）与结余管理

**用户故事:** 作为个体户或小型企业主，我想要系统自动处理以前年度的亏损结转，以便减少未来税负。

#### 验收标准

1. THE Tax_System SHALL 自动携带前年度亏损至当前 Tax_Year
2. THE Tax_Calculation_Engine SHALL 在计算应税收入前先抵扣可结转亏损
3. THE Tax_System SHALL 显示"可结转亏损余额"和"本年已使用亏损金额"
4. THE Tax_System SHALL 支持手动输入历史亏损（兼容旧数据迁移）
5. WHEN 亏损结转后税款为负时，THE Tax_System SHALL 自动返回 €0 并记录剩余可结转金额
6. THE Tax_System SHALL 在 Dashboard 显示多年度亏损结转趋势
7. THE Tax_System SHALL 提醒用户亏损结转的时效限制（如适用）

### 需求 37: 员工年终税款优化（Arbeitnehmerveranlagung）

**用户故事:** 作为普通职员，我想要系统检查 Lohnsteuer 是否多缴并建议退税。

#### 验收标准

1. THE Tax_System SHALL 支持上传 Lohnzettel（工资税卡）
2. THE OCR_Engine SHALL 识别 Lohnzettel 中的已预扣 Lohnsteuer 和 Sozialversicherung
3. THE Tax_Calculation_Engine SHALL 对比已预扣 Lohnsteuer 与实际应缴所得税
4. THE Tax_System SHALL 显示"预计退税金额"或"需补缴金额"
5. THE Tax_System SHALL 自动应用职工可用的扣除（Pendlerpauschale、Home Office、Sonderausgaben 等）
6. THE Tax_System SHALL 生成 Arbeitnehmerveranlagung 申报建议
7. THE Tax_System SHALL 在 Dashboard 显著提示"您可能有 €X 退税"

### 需求 38: AI 税务助手

**用户故事:** 作为用户，我想要一个内置的线上 AI 助手，以便随时问税务问题而不用翻阅复杂文档或找会计。

#### 验收标准

1. THE Tax_System SHALL 在 Dashboard、每页右下角和侧边栏提供"问 Taxja AI" 聊天按钮（支持移动端一键弹出）
2. WHEN 用户输入问题时，THE AI_Assistant SHALL 使用 RAG（Retrieval-Augmented Generation）技术，结合用户本年度交易数据、已上传 Document_Image 和最新奥地利税法（2026 USP 表）给出回答
3. THE AI_Assistant SHALL 支持德语、英语、中文三种语言（自动检测浏览器语言）
4. EVERY 回答 MUST 以醒目免责声明结尾："⚠️ 本回答仅供一般性参考，不构成税务咨询或正式建议。请以 FinanzOnline 最终结果为准，复杂情况请咨询 Steuerberater。"
5. THE AI_Assistant SHALL 能智能回答以下类别问题：
   - OCR 识别结果解释（"这张超市小票哪些项目可抵扣？"）
   - SVS 缴费、所得税税级、家庭扣除、通勤补贴计算
   - "What-if" 模拟（"如果我再买一台设备，税能省多少？"）
   - 平税制 vs 实际记账对比建议
6. WHEN 用户在聊天中上传 Document_Image 时，THE AI_Assistant SHALL 自动调用 OCR_Engine 并分析可抵扣金额 + 理由
7. THE AI_Assistant SHALL 保存用户所有聊天记录（可搜索、可删除、可导出 PDF）
8. THE Validation_Engine SHALL 严格限制 AI 不能给出具体报税金额或"保证退税 X 欧元"的承诺（防止违反 Steuerberatungsgesetz）
9. THE Tax_System SHALL 使用加密通道传输聊天内容，并遵守 GDPR（用户可一键删除全部聊天记录）
10. WHEN 税法更新时，THE Admin_Panel SHALL 允许管理员一键刷新 AI 知识库

## 总结

本需求文档定义了奥地利税务管理系统的全面功能，涵盖交易管理、自动分类、税款计算（所得税、增值税、社会保险）、报表生成、FinanzOnline 集成、文档智能识别（OCR）、数据验证、安全性、多语言支持、移动端支持和 AI 税务助手等方面。

核心功能亮点：

1. 税法准确性：基于 USP 2026 年官方税率表，完整税级门槛（€0-€13,539: 0% 至 €1,000,000 以上: 55%），支持管理员后台更新税率配置
2. 社会保险计算：完整的 SVS/GSVG 计算模块，动态计算实际费率（随基数自动调整），自动计算缴费并作为可抵扣项目
3. 增值税智能处理：€55,000 免税额 + 10% 容忍规则，区分住宅/商业租赁的不同税率
4. OCR 智能识别：支持批量上传、智能分组、ML 持续学习，识别奥地利常见文档格式（包括 Lohnzettel 和 SVS 缴费通知单）
5. 平税制对比：双轨计算实际记账 vs 平税制，帮助用户选择最优方案
6. 审计就绪：完整的文档存档、审计报告生成、合规性检查清单
7. 亏损结转管理（需求 36）：自动携带前年度亏损，在计算应税收入前先抵扣，显示多年度趋势
8. 员工退税优化（需求 37）：识别 Lohnzettel，对比已预扣税款与实际应缴税款，显示预计退税金额
9. AI 税务助手（需求 38）：内置 RAG 驱动的多语言 AI 助手，实时回答税务问题、解释 OCR 结果、提供 What-if 模拟建议，所有回答附带免责声明确保合规
10. 通勤补贴详细计算：根据通勤距离（20/40/60km 分级）、公共交通可用性计算基础金额（€58-€306/月），加上 Pendlereuro（€6/km/年），区分小通勤补贴和大通勤补贴
11. 强化数据安全：使用 AES_256 加密存储数据（at rest）和 TLS_1_3 传输加密（in transit）
12. 用户体验：仪表盘（含节税潜力估算）、What-if 模拟器、多语言支持、移动端 PWA

系统旨在为奥地利的职员、房东、个体户和小型企业提供全面的税务自动化解决方案，减少对 Steuerberater 的依赖并降低税务处理成本。所有功能均符合奥地利税法和 Steuerberatungsgesetz 限制，明确定位为"税务工具"而非"税务咨询服务"。
