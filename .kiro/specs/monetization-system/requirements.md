# 需求文档：变现/收费系统 (Monetization System)

## 简介

为 Taxja 奥地利税务管理平台设计一套循序渐进的变现系统。考虑到平台处于起步阶段，采用 Freemium（免费增值）模式，通过免费层吸引用户、付费层提供高级功能来实现商业化。系统需要支持订阅管理、功能权限控制、用量配额、支付集成和试用期管理。

## 术语表

- **Subscription_Service**: 订阅管理服务，负责用户订阅计划的创建、变更、续费和取消
- **Feature_Gate**: 功能权限网关，根据用户订阅等级控制对特定功能的访问
- **Usage_Tracker**: 用量追踪器，记录和检查用户对受限资源的使用量
- **Payment_Service**: 支付服务，处理与第三方支付网关（Stripe）的交互
- **Plan**: 订阅计划，定义功能权限和用量配额的集合（Free / Plus / Pro）
- **Quota**: 用量配额，某个计划下对特定资源的使用上限（如每月交易数、OCR次数）
- **Trial**: 试用期，新用户注册后可免费体验付费功能的时间窗口
- **Billing_Cycle**: 计费周期，订阅的收费间隔（月付或年付）
- **Webhook_Handler**: Webhook 处理器，接收并处理来自支付网关的异步事件通知
- **Free_Tier**: 免费层，提供基础功能的永久免费计划
- **Plus_Tier**: Plus 层，面向个人纳税人的中级付费计划
- **Pro_Tier**: Pro 层，面向自由职业者和小企业主的高级付费计划
- **Admin_Dashboard**: 后台管理面板，供平台管理员查看收入统计、管理订阅和用户数据的管理界面

## 需求

### 需求 1：订阅计划定义

**用户故事：** 作为平台运营者，我希望定义多个订阅计划（Free / Plus / Pro），以便为不同用户群体提供差异化服务。

#### 验收标准

1. THE Subscription_Service SHALL 支持三个订阅计划：Free（免费）、Plus（€4.90/月 或 €49/年）、Pro（€9.90/月 或 €99/年）
2. THE Subscription_Service SHALL 为每个 Plan 存储以下属性：计划名称、月付价格、年付价格、功能权限列表、用量配额列表
3. WHEN 管理员修改 Plan 的价格或配额时，THE Subscription_Service SHALL 仅对新订阅用户生效，现有用户保持原有条件直到下一个 Billing_Cycle
4. THE Free_Tier SHALL 包含以下功能：每月最多 50 笔手动交易录入、基础税务计算（所得税）、单语言支持（德语）、Dashboard 概览
5. THE Plus_Tier SHALL 包含以下功能：无限交易录入、完整税务计算（所得税 + VAT + SVS）、OCR 文档识别（每月 20 次）、CSV 导入导出、多语言支持、AI 交易分类、税务模拟器
6. THE Pro_Tier SHALL 包含以下功能：Plus 层全部功能、无限 OCR 文档识别、AI 税务助手对话、E1/EA 表格生成、Bilanz 和 Saldenliste 报表、银行账户自动导入（PSD2）、优先客服支持

### 需求 2：功能权限控制

**用户故事：** 作为用户，我希望根据我的订阅等级访问对应的功能，以便获得与付费等级匹配的服务。

#### 验收标准

1. WHEN 用户请求访问某个受限功能时，THE Feature_Gate SHALL 检查该用户当前 Plan 是否包含该功能的访问权限
2. WHEN 用户的 Plan 不包含所请求功能的权限时，THE Feature_Gate SHALL 返回 HTTP 403 状态码，并附带升级提示信息，包含所需的最低 Plan 等级
3. THE Feature_Gate SHALL 作为 FastAPI 依赖注入实现，以便在 API 端点中复用
4. WHEN 用户的订阅状态为过期或已取消时，THE Feature_Gate SHALL 将该用户视为 Free_Tier 用户
5. THE Feature_Gate SHALL 在每次权限检查时从缓存（Redis）读取用户的 Plan 信息，缓存未命中时从数据库加载

### 需求 3：用量配额管理

**用户故事：** 作为用户，我希望了解我的功能使用情况和剩余配额，以便合理规划使用或决定是否升级。

#### 验收标准

1. THE Usage_Tracker SHALL 追踪以下资源的使用量：每月交易录入数、每月 OCR 识别次数、每月 AI 助手对话次数
2. WHEN 用户的某项资源使用量达到 Quota 上限时，THE Usage_Tracker SHALL 拒绝该操作并返回配额超限提示，包含当前使用量、配额上限和配额重置日期
3. WHEN 用户的某项资源使用量达到 Quota 的 80% 时，THE Usage_Tracker SHALL 在 API 响应头中附加配额预警信息
4. THE Usage_Tracker SHALL 在每个 Billing_Cycle 开始时重置所有用量计数器
5. WHEN 用户升级 Plan 时，THE Usage_Tracker SHALL 立即应用新 Plan 的 Quota 上限，无需等待下一个 Billing_Cycle
6. THE Usage_Tracker SHALL 提供 API 端点，返回用户当前各项资源的使用量、配额上限和重置日期

### 需求 4：支付集成

**用户故事：** 作为用户，我希望通过安全的支付方式订阅付费计划，以便方便地完成付款。

#### 验收标准

1. THE Payment_Service SHALL 集成 Stripe 作为支付网关，支持信用卡和 SEPA 直接扣款两种支付方式
2. WHEN 用户选择订阅付费 Plan 时，THE Payment_Service SHALL 创建 Stripe Checkout Session 并返回支付页面 URL
3. WHEN Stripe 发送 Webhook 事件时，THE Webhook_Handler SHALL 验证事件签名的有效性后再处理事件
4. WHEN 收到 `checkout.session.completed` 事件时，THE Webhook_Handler SHALL 激活用户的订阅并更新 Plan 等级
5. WHEN 收到 `invoice.payment_failed` 事件时，THE Webhook_Handler SHALL 将用户订阅标记为 `past_due` 状态，并保留 7 天宽限期
6. WHEN 宽限期结束且支付仍未成功时，THE Subscription_Service SHALL 将用户降级为 Free_Tier
7. THE Payment_Service SHALL 支持月付和年付两种 Billing_Cycle，年付享受约 17% 的折扣
8. IF Stripe API 调用失败，THEN THE Payment_Service SHALL 记录错误日志并返回用户友好的错误提示，包含重试建议

### 需求 5：试用期管理

**用户故事：** 作为新用户，我希望在注册后免费体验付费功能，以便在决定付费前充分了解平台价值。

#### 验收标准

1. WHEN 新用户完成注册时，THE Subscription_Service SHALL 自动为该用户激活 14 天的 Pro_Tier 试用期
2. WHILE 用户处于试用期内，THE Feature_Gate SHALL 授予该用户 Pro_Tier 的全部功能权限
3. WHEN 试用期剩余 3 天时，THE Subscription_Service SHALL 通过应用内通知提醒用户试用即将到期
4. WHEN 试用期结束且用户未订阅付费 Plan 时，THE Subscription_Service SHALL 将用户降级为 Free_Tier
5. THE Subscription_Service SHALL 确保每个用户仅能享受一次试用期，通过用户记录中的 `trial_used` 标志控制

### 需求 6：订阅生命周期管理

**用户故事：** 作为用户，我希望能够灵活管理我的订阅（升级、降级、取消），以便根据需求调整服务等级。

#### 验收标准

1. WHEN 用户请求升级 Plan 时，THE Subscription_Service SHALL 立即生效新 Plan，并按剩余天数比例计算差价（proration）
2. WHEN 用户请求降级 Plan 时，THE Subscription_Service SHALL 在当前 Billing_Cycle 结束后生效新 Plan
3. WHEN 用户请求取消订阅时，THE Subscription_Service SHALL 保留付费功能直到当前 Billing_Cycle 结束
4. THE Subscription_Service SHALL 为每次订阅变更创建审计日志记录，包含变更时间、变更类型、原 Plan 和新 Plan
5. WHEN 用户在取消后的 30 天内请求重新订阅时，THE Subscription_Service SHALL 恢复用户之前的数据和设置

### 需求 7：前端订阅界面

**用户故事：** 作为用户，我希望在界面上清晰地看到各计划的对比和我的订阅状态，以便做出明智的订阅决策。

#### 验收标准

1. THE 前端应用 SHALL 在定价页面展示三个 Plan 的功能对比表，包含价格、功能列表和推荐标签
2. WHEN 用户访问受限功能时，THE 前端应用 SHALL 展示升级提示弹窗，说明所需 Plan 等级和升级按钮
3. THE 前端应用 SHALL 在用户设置页面展示当前订阅状态，包含 Plan 名称、到期日期、用量统计和管理按钮
4. WHEN 用户点击订阅按钮时，THE 前端应用 SHALL 跳转到 Stripe Checkout 支付页面
5. WHEN 支付完成后，THE 前端应用 SHALL 自动刷新用户的订阅状态并展示成功提示
6. THE 前端应用 SHALL 支持德语、英语和中文三种语言的订阅相关文案

### 需求 8：数据模型扩展

**用户故事：** 作为开发者，我希望数据库模型能够支撑订阅和支付功能，以便可靠地存储和查询相关数据。

#### 验收标准

1. THE 数据库 SHALL 包含 `subscriptions` 表，存储用户订阅记录，包含字段：user_id、plan_type、status、stripe_subscription_id、current_period_start、current_period_end、cancel_at_period_end
2. THE 数据库 SHALL 包含 `plans` 表，存储计划定义，包含字段：name、monthly_price、yearly_price、features（JSON）、quotas（JSON）
3. THE 数据库 SHALL 包含 `usage_records` 表，存储用量记录，包含字段：user_id、resource_type、count、period_start、period_end
4. THE 数据库 SHALL 包含 `payment_events` 表，存储支付事件日志，包含字段：stripe_event_id、event_type、user_id、payload（JSON）、processed_at
5. THE User 模型 SHALL 扩展以下字段：subscription_id（外键）、trial_used（布尔值）、trial_end_date（日期时间）
6. THE 数据库 SHALL 通过 Alembic 迁移脚本创建上述表结构，确保与现有数据库兼容


### 需求 9：后台管理面板

**用户故事：** 作为平台管理员，我希望通过后台管理面板查看收入统计和管理订阅数据，以便监控平台运营状况并及时做出调整。

#### 验收标准

1. THE Admin_Dashboard SHALL 展示关键收入指标，包含月度经常性收入（MRR）、年度经常性收入（ARR）、流失率（Churn Rate）和转化率（Conversion Rate）
2. THE Admin_Dashboard SHALL 展示订阅数据概览，包含各 Plan 的活跃订阅数、试用期用户数和总付费用户数
3. WHEN 管理员查看用户列表时，THE Admin_Dashboard SHALL 展示每个用户的当前 Plan、订阅状态、订阅开始日期和到期日期
4. WHEN 管理员请求调整某个 Plan 的价格或功能配置时，THE Admin_Dashboard SHALL 调用 Subscription_Service 更新 Plan 定义，并记录变更日志
5. THE Admin_Dashboard SHALL 提供支付事件日志查看功能，支持按事件类型、用户和时间范围筛选 payment_events 记录
6. WHEN 管理员请求手动调整用户订阅状态时，THE Admin_Dashboard SHALL 支持以下操作：赠送试用期、升级或降级用户 Plan、延长订阅有效期
7. THE Admin_Dashboard SHALL 提供收入报表功能，支持按日、周、月维度查看收入趋势图表
8. THE Admin_Dashboard SHALL 仅允许具有管理员角色（role = admin）的用户访问，非管理员用户访问时返回 HTTP 403 状态码
