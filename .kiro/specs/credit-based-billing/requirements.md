# 需求文档：Credit-Based Billing（基于 Credit 的计费系统）

## 简介

本文档定义 Taxja 从"按资源类型配额"计费模型迁移到统一"Credit/Token"计费模型（v1）的功能需求。v1 聚焦于 Credit 账务基础设施，包括双余额管理、扣费/退款、Overage 模式、Top-up 充值、月度重置、全局成本配置、并发安全和前端展示改版。

## 术语表

- **CreditService**: 核心 Credit 管理服务，负责余额查询、扣费、退款、充值、月度重置等操作
- **CreditBalance**: 用户 Credit 余额记录，包含 plan_balance 和 topup_balance 双余额
- **CreditLedger**: Credit 变动审计日志表，记录所有 credit 增减操作
- **CreditCostConfig**: 全局操作 credit 成本配置表，独立于 Plan
- **Plan_Balance**: 套餐赠送的月度 Credit 余额，每个计费周期重置，不累积
- **Topup_Balance**: 用户通过 Stripe 一次性支付购买的 Credit 余额，有效期 12 个月，不随月度周期清零
- **Overage**: 超额使用模式，Plus/Pro 套餐可开启，余额耗尽后按单价继续使用，周期结束通过 Stripe Invoice 结算
- **Overage_Credits_Used**: 当前计费周期内已使用的 overage credit 数量
- **TopupPurchase**: Top-up 购买记录，追踪每笔充值的剩余额度和过期时间
- **CreditTopupPackage**: 预定义的 Credit 充值套餐包
- **InsufficientCreditsError**: 余额不足且 overage 未开启时抛出的错误
- **OverageNotAvailableError**: Free 套餐用户尝试开启 overage 时抛出的错误
- **OverageSuspendedError**: 连续 2 个周期未结清 overage 欠款时抛出的错误
- **Pricing_Version**: 定价规则版本号，用于追溯扣费时使用的成本配置
- **Processing_Gate**: 系统侧处理级门控（风控/质量控制），与计费无关

## 需求

### 需求 1: Credit 余额管理

**用户故事:** 作为 Taxja 用户，我希望拥有统一的 Credit 余额，以便通过消耗 Credit 使用所有平台功能，而不受套餐功能锁定限制。

#### 验收标准

1. THE CreditService SHALL 为每个用户维护 plan_balance 和 topup_balance 两个独立余额
2. WHEN 用户查询余额时，THE CreditService SHALL 返回 plan_balance、topup_balance、total_balance（plan + topup 之和）、overage 状态和预估 overage 费用
3. THE CreditBalance SHALL 对 plan_balance 和 topup_balance 施加 CHECK 约束确保值大于等于 0
4. WHEN 用户无 CreditBalance 记录时，THE CreditService SHALL 自动创建一条默认记录（plan_balance 等于套餐 monthly_credits，topup_balance 为 0）
5. THE CreditService SHALL 通过 Redis 缓存余额数据（TTL 5 分钟），cache miss 时从数据库加载

### 需求 2: Credit 扣费

**用户故事:** 作为 Taxja 用户，我希望在使用平台功能时自动扣除对应的 Credit，以便按实际使用量付费。

#### 验收标准

1. WHEN 用户执行一个消耗 Credit 的操作时，THE CreditService SHALL 从全局 CreditCostConfig 查询该操作的 credit 成本
2. WHEN 扣费时 plan_balance 充足，THE CreditService SHALL 仅从 plan_balance 扣除，使用原子 UPDATE ... WHERE plan_balance >= cost 操作
3. WHEN plan_balance 不足但 plan_balance + topup_balance 充足时，THE CreditService SHALL 先扣完 plan_balance 剩余部分，再从 topup_balance 扣除差额
4. WHEN plan_balance 和 topup_balance 均不足且 overage 已开启时，THE CreditService SHALL 先扣完 plan_balance 和 topup_balance，剩余部分计入 overage_credits_used
5. IF plan_balance 和 topup_balance 均不足且 overage 未开启，THEN THE CreditService SHALL 抛出 InsufficientCreditsError 并返回 HTTP 402
6. WHEN 扣费成功时，THE CreditService SHALL 写入一条 CreditLedger 记录，包含 credit_amount（负数）、source、plan_balance_after、topup_balance_after、is_overage、overage_portion、context_type、context_id 和 pricing_version
7. WHEN 扣费成功时，THE CreditService SHALL 删除该用户的 Redis 缓存 key（写后删除策略）

### 需求 3: Credit 退款

**用户故事:** 作为 Taxja 用户，我希望在操作处理失败时自动退回已扣除的 Credit，以便不因系统故障而损失额度。

#### 验收标准

1. WHEN 操作处理失败时，THE CreditService SHALL 调用 refund_credits 退回已扣除的 credit
2. WHEN 退款时原始扣费包含 overage 部分，THE CreditService SHALL 优先退回 overage 部分（减少 overage_credits_used）
3. WHEN 退款时原始扣费包含 topup 部分，THE CreditService SHALL 在退回 overage 后退回 topup_balance
4. WHEN 退款时原始扣费包含 plan 部分，THE CreditService SHALL 最后退回 plan_balance
5. WHEN 退款成功时，THE CreditService SHALL 写入一条 CreditLedger 记录，operation 为 REFUND，包含 reason 字段说明退款原因
6. WHEN 退款成功时，THE CreditService SHALL 删除该用户的 Redis 缓存 key
7. WHEN 提供 refund_key 参数时，THE CreditService SHALL 通过 reference_id 做幂等检查，若已存在相同 refund_key 的 REFUND ledger 记录则直接返回当前余额，不重复退款

### 需求 4: Overage 模式

**用户故事:** 作为 Plus/Pro 套餐用户，我希望在 Credit 耗尽后仍能继续使用平台功能，以便不因额度不足而中断工作流。

#### 验收标准

1. IF Free 套餐用户尝试开启 overage，THEN THE CreditService SHALL 抛出 OverageNotAvailableError
2. WHEN Plus 或 Pro 套餐用户请求开启 overage 时，THE CreditService SHALL 将 overage_enabled 设为 true
3. WHEN 用户套餐从 Plus/Pro 降级到 Free 时，THE CreditService SHALL 自动关闭 overage 并结算已有 overage 费用
4. WHEN 用户套餐升级时，THE CreditService SHALL 保留 overage 开关的当前状态
5. WHEN 计费周期结束且 overage_credits_used 大于 0 时，THE CreditService SHALL 计算 overage 费用（overage_credits_used × overage_price_per_credit）并通过 Stripe 创建 Invoice
6. IF Stripe Invoice 支付失败，THEN THE CreditService SHALL 标记 has_unpaid_overage 为 true 并将 unpaid_overage_periods 加 1
7. IF unpaid_overage_periods 大于等于 2，THEN THE CreditService SHALL 自动禁用 overage 功能并抛出 OverageSuspendedError
8. WHEN 用户通过 Stripe webhook（invoice.paid）结清欠款时，THE CreditService SHALL 仅当该 invoice metadata 含 type=overage_settlement 时才重置 has_unpaid_overage 和 unpaid_overage_periods 并恢复 overage 功能；普通订阅付款成功不应错误清空 overage 欠费状态

### 需求 5: 月度重置

**用户故事:** 作为 Taxja 用户，我希望每个计费周期自动获得套餐赠送的 Credit 额度，以便持续使用平台服务。

#### 验收标准

1. WHEN 计费周期结束时，THE CreditService SHALL 将 plan_balance 重置为套餐的 monthly_credits 值
2. WHEN 计费周期结束时，THE CreditService SHALL 保留 topup_balance 不变（不随月度周期清零）
3. WHEN 计费周期结束时，THE CreditService SHALL 将 overage_credits_used 重置为 0
4. WHEN 计费周期结束时，THE CreditService SHALL 清理超过 12 个月有效期的 topup_balance 部分，并将对应 TopupPurchase 标记为 is_expired
5. WHEN 月度重置完成时，THE CreditService SHALL 写入一条 CreditLedger 记录，operation 为 MONTHLY_RESET
6. WHEN 有 topup 过期清理时，THE CreditService SHALL 写入一条 CreditLedger 记录，operation 为 TOPUP_EXPIRY
7. WHILE 用户有未结清 overage 欠款时，THE CreditService SHALL 照常重置 plan_balance（不影响用户正常使用）

### 需求 6: Top-up 充值

**用户故事:** 作为 Taxja 用户，我希望能够购买额外的 Credit 充值包，以便在套餐额度不足时补充使用。

#### 验收标准

1. WHEN 用户选择充值包并发起支付时，THE CreditService SHALL 通过 Stripe 创建一次性支付的 Checkout Session
2. WHEN Stripe webhook 确认支付成功（checkout.session.completed）时，THE CreditService SHALL 将购买的 credit 数量加到 topup_balance
3. WHEN 充值成功时，THE CreditService SHALL 创建一条 TopupPurchase 记录，expires_at 设为购买时间加 12 个月
4. WHEN 充值成功时，THE CreditService SHALL 写入一条 CreditLedger 记录，operation 为 TOPUP，source 为 topup
5. WHEN 充值成功时，THE CreditService SHALL 删除该用户的 Redis 缓存 key
6. THE CreditTopupPackage SHALL 存储预定义的充值包信息，包含名称、credit 数量、价格和 Stripe price ID

### 需求 7: 全局 Credit 成本配置

**用户故事:** 作为系统管理员，我希望通过全局配置表管理各操作的 Credit 成本，以便独立于套餐进行调价和版本管理。

#### 验收标准

1. THE CreditCostConfig SHALL 存储每个操作的 credit 成本，包含 operation 名称、credit_cost、description、pricing_version 和 is_active 字段
2. WHEN CreditService 执行扣费时，THE CreditService SHALL 从 CreditCostConfig 查询当前 is_active 的操作成本
3. WHEN 扣费记录写入 CreditLedger 时，THE CreditService SHALL 记录当时使用的 pricing_version
4. THE CreditCostConfig SHALL 确保 operation 字段唯一，防止同一操作出现重复配置
5. WHEN 用户请求操作成本列表时，THE Credit_API SHALL 返回所有 is_active 的操作及其 credit 成本

### 需求 8: 并发安全

**用户故事:** 作为 Taxja 用户，我希望在多个操作同时扣费时余额计算准确，以便不会出现余额变为负数或重复扣费的情况。

#### 验收标准

1. WHEN plan_balance 充足时，THE CreditService SHALL 使用单条原子 UPDATE ... WHERE plan_balance >= cost 语句完成扣费
2. WHEN plan_balance 不足需要跨余额扣除时，THE CreditService SHALL 使用 SELECT ... FOR UPDATE 加行锁后在事务内完成计算和更新
3. THE CreditService SHALL 在数据库事务内完成所有扣费操作，确保余额更新和 Ledger 写入的原子性
4. WHEN 数据库写操作成功后，THE CreditService SHALL 删除 Redis 缓存 key（写后删除），读取时从数据库重新加载

### 需求 9: 功能门控迁移

**用户故事:** 作为 Taxja 用户，我希望所有平台功能通过 Credit 消耗来控制访问，而不再受套餐层级的功能锁定限制。

#### 验收标准

1. WHEN 用户尝试使用某功能时，THE FeatureGateService SHALL 通过 CreditService.check_sufficient 检查用户是否有足够 credit（plan + topup + overage 综合判断）
2. THE FeatureGateService SHALL 保留系统侧处理级门控（Processing_Gate），用于风控和质量控制，与计费逻辑分离。FeatureGateService 只负责用户侧 entitlement / payment sufficiency；自动化深度、risk gating、manual review 继续由处理级 gate 决定，不迁移到 credit 层
3. WHEN 用户 credit 充足或 overage 已开启时，THE FeatureGateService SHALL 允许用户访问该功能
4. IF 用户 credit 不足且 overage 未开启，THEN THE FeatureGateService SHALL 拒绝访问并返回余额不足提示

### 需求 10: Credit API 端点

**用户故事:** 作为前端开发者，我希望有完整的 Credit API 端点，以便前端能够查询余额、查看历史、管理 overage 和发起充值。

#### 验收标准

1. WHEN 前端请求 GET /credits/balance 时，THE Credit_API SHALL 返回用户的 plan_balance、topup_balance、total_balance、overage 状态和预估 overage 费用
2. WHEN 前端请求 GET /credits/history 时，THE Credit_API SHALL 返回分页的 CreditLedger 记录列表
3. WHEN 前端请求 GET /credits/costs 时，THE Credit_API SHALL 返回所有活跃操作的 credit 成本列表
4. WHEN 前端请求 POST /credits/topup 时，THE Credit_API SHALL 创建 Stripe Checkout Session 并返回 session_id 和重定向 URL
5. WHEN 前端请求 PUT /credits/overage 时，THE Credit_API SHALL 调用 CreditService.set_overage_enabled 更新 overage 开关状态
6. WHEN 前端请求 GET /credits/overage/estimate 时，THE Credit_API SHALL 返回当前周期的 overage 预估费用
7. WHEN 前端请求 POST /credits/estimate 时，THE Credit_API SHALL 返回操作的预估成本、是否充足、仅自然余额是否充足、是否会动用 overage

### 需求 11: 前端 Credit 展示

**用户故事:** 作为 Taxja 用户，我希望在前端界面清晰地看到我的 Credit 余额、使用情况和 overage 状态，以便了解自己的消费情况。

#### 验收标准

1. THE 前端 SHALL 在 SubscriptionStatus 组件中显示统一的 Credit 进度条，分别展示 plan_balance 和 topup_balance
2. THE 前端 SHALL 提供 Overage 开关（toggle），显示 overage 单价，并在有未结清欠款时展示警告信息
3. THE 前端 SHALL 提供 Credit 历史页面，展示分页的 credit 变动记录
4. THE 前端 SHALL 提供 Credit 充值入口，展示可用的充值包及价格
5. THE 前端套餐页 SHALL 展示每个套餐的月度 Credit 额度、overage 单价和操作成本参考表

### 需求 12: 数据迁移

**用户故事:** 作为系统管理员，我希望将现有用户平滑迁移到 Credit 计费模型，以便用户无感知地过渡到新系统。

#### 验收标准

1. WHEN 执行迁移时，THE 迁移脚本 SHALL 为所有现有用户创建 CreditBalance 记录，plan_balance 设为套餐的 monthly_credits（直接给满额）
2. WHEN 执行迁移时，THE 迁移脚本 SHALL 将所有用户的 topup_balance 设为 0，overage_enabled 设为 false
3. WHEN 迁移完成时，THE 迁移脚本 SHALL 为每个用户写入一条 CreditLedger 记录，operation 为 MIGRATION
4. WHEN 执行迁移时，THE 迁移脚本 SHALL 创建全局 CreditCostConfig 初始数据
5. THE 迁移 SHALL 保留旧 UsageRecord 表和 Plan 的 quotas、features JSONB 字段不删除，确保向后兼容
6. WHILE 过渡期内，THE API SHALL 同时返回 credit 信息和旧格式数据

### 需求 13: 套餐配置

**用户故事:** 作为系统管理员，我希望为每个套餐配置月度 Credit 额度和 overage 单价，以便支持差异化的计费策略。

#### 验收标准

1. THE Plan 模型 SHALL 包含 monthly_credits 字段（整数，默认 0）和 overage_price_per_credit 字段（Decimal，可为 null）
2. WHEN overage_price_per_credit 为 null 时，THE CreditService SHALL 视该套餐不支持 overage
3. THE Plan 配置 SHALL 支持 Free（50 credits/月，无 overage）、Plus（500 credits/月，€0.04/credit overage）、Pro（2000 credits/月，€0.03/credit overage）三种套餐
