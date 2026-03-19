# 需求文档：账号注销与退订功能 (Account Cancellation & Unsubscription)

## 简介

为 Taxja 奥地利税务管理平台添加账号注销与退订功能。用户应能够取消付费订阅（退订）以及永久删除账号（注销）。该功能需符合 GDPR 第 17 条（被遗忘权）和第 20 条（数据可携带权）的要求，确保用户对自身数据拥有完整的控制权。功能涵盖订阅取消、数据导出、账号停用、数据清理以及相关的前端交互界面。

## 术语表

- **Account_Cancellation_Service**: 账号注销服务，负责处理账号停用、数据清理和永久删除的完整流程
- **Subscription_Cancellation_Service**: 退订服务，负责处理付费订阅的取消流程，与 Stripe 支付网关交互
- **Data_Export_Service**: 数据导出服务，负责将用户的全部数据打包导出为可下载的格式
- **Cooling_Off_Period**: 冷静期，账号注销请求提交后到数据永久删除之间的等待时间（30 天）
- **Soft_Delete**: 软删除，将账号标记为已停用但保留数据，在冷静期内可恢复
- **Hard_Delete**: 硬删除，永久删除用户的所有个人数据和关联记录
- **Data_Package**: 数据包，包含用户全部数据的可下载压缩文件（JSON + CSV 格式）
- **Anonymization**: 匿名化，将用户数据中的个人身份信息替换为不可逆的匿名标识
- **Reactivation**: 重新激活，在冷静期内恢复已停用的账号

## 需求

### 需求 1：订阅取消（退订）

**用户故事：** 作为付费用户，我希望能够取消我的付费订阅，以便在不需要高级功能时停止付费。

#### 验收标准

1. WHEN 用户请求取消订阅时，THE Subscription_Cancellation_Service SHALL 调用 Stripe API 设置订阅在当前计费周期结束时取消（cancel_at_period_end = true）
2. WHEN 订阅取消请求成功时，THE Subscription_Cancellation_Service SHALL 更新本地 Subscription 记录的 cancel_at_period_end 字段为 true，并创建审计日志
3. WHILE 用户的订阅处于已取消但未到期状态时，THE Feature_Gate SHALL 继续授予该用户当前 Plan 的全部功能权限，直到 current_period_end 日期
4. WHEN 已取消订阅的计费周期结束时，THE Subscription_Cancellation_Service SHALL 将用户降级为 Free_Tier，并更新 Subscription 状态为 canceled
5. WHEN 用户在订阅取消后、计费周期结束前请求撤销取消时，THE Subscription_Cancellation_Service SHALL 调用 Stripe API 恢复订阅，并将 cancel_at_period_end 重置为 false
6. IF Stripe API 调用失败，THEN THE Subscription_Cancellation_Service SHALL 记录错误日志，保持本地状态不变，并返回用户友好的错误提示

### 需求 2：数据导出（GDPR 数据可携带权）

**用户故事：** 作为用户，我希望在注销账号前能够导出我的全部数据，以便保留个人税务记录的副本。

#### 验收标准

1. WHEN 用户请求数据导出时，THE Data_Export_Service SHALL 生成包含以下内容的 Data_Package：个人信息、全部交易记录（CSV 格式）、税务报告、上传的文档文件、分类修正记录、损失结转记录和房产信息
2. THE Data_Export_Service SHALL 将交易记录导出为 CSV 格式，将结构化数据（个人信息、税务报告、分类修正）导出为 JSON 格式，将文档文件保持原始格式
3. WHEN Data_Package 生成完成时，THE Data_Export_Service SHALL 将压缩文件上传至 MinIO 临时存储桶，并返回有效期为 48 小时的预签名下载链接
4. THE Data_Export_Service SHALL 在导出的 JSON 文件中包含数据字典说明，描述每个字段的含义和数据类型
5. IF 数据导出过程中发生错误，THEN THE Data_Export_Service SHALL 记录错误详情，通知用户导出失败，并提供重试选项
6. THE Data_Export_Service SHALL 对导出的数据包进行 AES-256 加密，使用用户提供的密码作为加密密钥

### 需求 3：账号停用（软删除）

**用户故事：** 作为用户，我希望在提交注销请求后有一段冷静期，以便在改变主意时能够恢复账号。

#### 验收标准

1. WHEN 用户确认注销账号时，THE Account_Cancellation_Service SHALL 将账号状态设置为 deactivated，记录停用时间，并启动 30 天的 Cooling_Off_Period
2. WHEN 账号被停用时，THE Account_Cancellation_Service SHALL 立即取消该用户的活跃订阅（如有），调用 Stripe API 取消订阅并停止后续扣款
3. WHILE 账号处于 deactivated 状态时，THE 认证服务 SHALL 拒绝该用户的登录请求，并提示账号已停用及剩余冷静期天数
4. WHILE 账号处于 deactivated 状态时，THE Account_Cancellation_Service SHALL 保留该用户的全部数据不做任何修改
5. WHEN 用户在 Cooling_Off_Period 内请求重新激活账号时，THE Account_Cancellation_Service SHALL 恢复账号为 active 状态，用户可正常登录并访问 Free_Tier 功能
6. THE Account_Cancellation_Service SHALL 在停用后第 23 天向用户注册邮箱发送提醒邮件，告知账号将在 7 天后被永久删除

### 需求 4：数据永久删除（硬删除）

**用户故事：** 作为用户，我希望在冷静期结束后我的个人数据被彻底删除，以便行使 GDPR 赋予的被遗忘权。

#### 验收标准

1. WHEN Cooling_Off_Period（30 天）结束且用户未请求重新激活时，THE Account_Cancellation_Service SHALL 执行 Hard_Delete 流程
2. THE Account_Cancellation_Service SHALL 在 Hard_Delete 流程中删除以下数据：用户个人信息（姓名、邮箱、税号、地址）、全部交易记录、全部上传文档（包括 MinIO 中的文件）、税务报告、分类修正记录、损失结转记录、房产和贷款信息、聊天消息记录、通知记录、定期交易规则、用量记录
3. THE Account_Cancellation_Service SHALL 保留匿名化的统计数据用于平台分析，包括：匿名化的支付事件记录（移除 user_id，保留金额和事件类型）和匿名化的审计日志
4. THE Account_Cancellation_Service SHALL 从 MinIO 存储中删除该用户的全部文档文件，确保文件级别的彻底清理
5. THE Account_Cancellation_Service SHALL 清除 Redis 中与该用户相关的全部缓存数据（会话、Plan 信息、用量计数）
6. WHEN Hard_Delete 流程完成时，THE Account_Cancellation_Service SHALL 创建一条不可逆的删除确认记录，仅包含匿名化的用户标识和删除时间戳，用于合规审计
7. IF Hard_Delete 流程中某个步骤失败，THEN THE Account_Cancellation_Service SHALL 记录失败详情，标记该账号为 deletion_pending 状态，并在下一次定时任务中重试

### 需求 5：注销确认与安全验证

**用户故事：** 作为用户，我希望注销流程有充分的确认步骤，以防止误操作导致数据丢失。

#### 验收标准

1. WHEN 用户发起注销请求时，THE Account_Cancellation_Service SHALL 要求用户输入当前密码进行身份验证
2. WHEN 身份验证通过后，THE Account_Cancellation_Service SHALL 向用户展示注销影响摘要，包含：将被删除的数据类型和数量、活跃订阅的剩余天数和退款信息、冷静期说明、数据导出建议
3. WHEN 用户确认注销时，THE Account_Cancellation_Service SHALL 要求用户手动输入"DELETE"（或对应语言的确认词）作为最终确认
4. WHEN 用户启用了双因素认证时，THE Account_Cancellation_Service SHALL 在密码验证后额外要求输入双因素验证码
5. THE Account_Cancellation_Service SHALL 在注销确认后向用户注册邮箱发送注销确认邮件，包含冷静期说明和重新激活链接

### 需求 6：定时清理任务

**用户故事：** 作为平台运营者，我希望系统自动执行过期账号的数据清理，以便确保 GDPR 合规并释放存储资源。

#### 验收标准

1. THE Account_Cancellation_Service SHALL 通过 Celery 定时任务每日执行一次过期账号检查
2. WHEN 定时任务发现 deactivated 状态超过 30 天的账号时，THE Account_Cancellation_Service SHALL 对该账号执行 Hard_Delete 流程
3. THE Account_Cancellation_Service SHALL 在定时任务执行后生成清理报告，包含：检查的账号数量、执行删除的账号数量、删除失败的账号数量及原因
4. WHEN 定时任务发现 deletion_pending 状态的账号时，THE Account_Cancellation_Service SHALL 重试 Hard_Delete 流程，最多重试 3 次
5. IF 某个账号的 Hard_Delete 重试 3 次均失败，THEN THE Account_Cancellation_Service SHALL 向管理员发送告警通知，要求人工介入处理

### 需求 7：前端注销与退订界面

**用户故事：** 作为用户，我希望在设置页面中找到清晰的注销和退订入口，以便方便地管理我的账号和订阅。

#### 验收标准

1. THE 前端应用 SHALL 在用户设置页面的"账号管理"区域提供"取消订阅"和"注销账号"两个独立入口
2. WHEN 用户点击"取消订阅"时，THE 前端应用 SHALL 展示当前订阅信息（Plan 名称、到期日期、已付金额），并提供确认取消按钮和取消原因选择（可选）
3. WHEN 用户点击"注销账号"时，THE 前端应用 SHALL 引导用户完成多步骤注销流程：步骤一展示注销影响摘要、步骤二提供数据导出选项、步骤三要求密码验证和最终确认
4. WHEN 注销流程中用户选择导出数据时，THE 前端应用 SHALL 调用 Data_Export_Service 生成数据包，并在下载链接就绪后通知用户
5. THE 前端应用 SHALL 支持德语、英语和中文三种语言的注销和退订相关文案
6. WHEN 用户的账号处于 deactivated 状态时，THE 前端应用 SHALL 在登录页面展示账号已停用提示，并提供"重新激活账号"按钮
7. WHEN 用户成功取消订阅后，THE 前端应用 SHALL 展示确认信息，包含订阅到期日期和降级后可用功能说明

### 需求 8：管理员账号管理

**用户故事：** 作为平台管理员，我希望能够查看和管理用户的注销请求，以便处理特殊情况和监控注销趋势。

#### 验收标准

1. THE Admin_Dashboard SHALL 在用户管理页面展示账号状态筛选器，支持按 active、deactivated、deletion_pending 状态筛选用户
2. WHEN 管理员查看已停用账号列表时，THE Admin_Dashboard SHALL 展示每个账号的停用日期、冷静期剩余天数和计划删除日期
3. WHEN 管理员请求手动触发某个账号的 Hard_Delete 时，THE Account_Cancellation_Service SHALL 跳过冷静期立即执行删除流程，并记录管理员操作审计日志
4. THE Admin_Dashboard SHALL 展示注销统计数据，包含：每月注销请求数、注销原因分布、冷静期内重新激活率、平均用户生命周期
5. WHEN 管理员请求手动重新激活某个已停用账号时，THE Account_Cancellation_Service SHALL 恢复该账号为 active 状态，并记录管理员操作审计日志
