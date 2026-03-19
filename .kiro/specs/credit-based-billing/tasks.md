# 实施计划：Credit-Based Billing（基于 Credit 的计费系统）— 冻结可开工版

## 冻结版执行原则

1. v1 只交付 Credit Billing Foundation，不引入 AI 动态定价。
2. 所有新增模型字段如 status、reservation_id 为 v2 预留，不在 v1 主流程中启用。
3. 同步业务先集成，异步文档链路单独试点。
4. 任何会改变 AI 处理深度或结果质量的逻辑，均不属于本计划范围。

## 概述

将 Taxja 从"按资源类型配额"计费模型迁移为统一的"Credit/Token"计费模型（v1: Credit Billing Foundation）。后端使用 Python/FastAPI/PostgreSQL/SQLAlchemy，前端使用 React 18/TypeScript/Zustand。属性测试使用 Hypothesis 库。

本计划为冻结版，已整合所有架构评审反馈（Ledger status/reservation_id 预留、FIFO top-up 消耗、check_sufficient allow_overage 参数、estimate 接口、FeatureGate 边界明确化、10.3 拆分同步/异步试点、Non-goals 锁定）。

## 任务

- [x] 1. 数据模型与数据库迁移
  - [x] 1.1 扩展 Plan 模型，新增 monthly_credits 和 overage_price_per_credit 字段
    - 在 `backend/app/models/plan.py` 中添加 `monthly_credits = Column(Integer, nullable=False, default=0)` 和 `overage_price_per_credit = Column(Numeric(6, 4), nullable=True)`
    - 创建 Alembic 迁移脚本，为现有 Plan 记录填充默认值（Free=50, Plus=500, Pro=2000）
    - _需求: 13.1, 13.2, 13.3_

  - [x] 1.2 创建 CreditBalance 模型
    - 在 `backend/app/models/credit_balance.py` 中创建 CreditBalance 模型，包含 user_id（unique）、plan_balance、topup_balance、overage_enabled、overage_credits_used、has_unpaid_overage、unpaid_overage_periods、updated_at
    - 添加 CHECK 约束：plan_balance >= 0、topup_balance >= 0、overage_credits_used >= 0、unpaid_overage_periods >= 0
    - 在 User 模型中添加 `credit_balance` relationship
    - _需求: 1.1, 1.3_

  - [x] 1.3 创建 CreditLedger 模型（含 status 和 reservation_id 预留字段）
    - 在 `backend/app/models/credit_ledger.py` 中创建 CreditLedger 模型，包含 CreditOperation、CreditSource、CreditLedgerStatus 枚举
    - CreditLedgerStatus 枚举值：`settled`（v1 默认）、`reserved`（v2 用）、`reversed`（v2 用）、`failed`
    - **failed 状态说明**：v1 中 failed 仅用于明确记录已进入扣费流程但最终未落账成功的异常场景；普通业务异常（如 InsufficientCreditsError 被拒绝）不写 failed ledger，仅当已产生部分持久化副作用时才记录 failed
    - 字段：user_id、operation、operation_detail、status（默认 settled）、credit_amount、source、plan_balance_after、topup_balance_after、is_overage、overage_portion、context_type、context_id、reference_id、reservation_id（v1 始终为 null，v2 预扣链路关联）、reason、pricing_version、created_at
    - 添加 CHECK 约束：credit_amount != 0、plan_balance_after >= 0、topup_balance_after >= 0、overage_portion >= 0
    - 添加复合索引：(user_id, created_at DESC)、(user_id, operation)、(context_type, context_id)、(status)
    - **添加唯一约束**：(user_id, operation=REFUND, reference_id) 上建部分唯一索引（`WHERE operation = 'refund' AND reference_id IS NOT NULL`），确保 refund_key 幂等在数据库层面强制执行，不仅靠代码判断
    - _需求: 2.6, 3.5, 5.5, 5.6_

  - [x] 1.4 创建 CreditCostConfig 模型
    - 在 `backend/app/models/credit_cost_config.py` 中创建 CreditCostConfig 模型
    - 字段：operation（unique）、credit_cost、description、pricing_version、is_active、updated_at
    - _需求: 7.1, 7.4_

  - [x] 1.5 创建 TopupPurchase 和 CreditTopupPackage 模型
    - 在 `backend/app/models/topup_purchase.py` 中创建 TopupPurchase 模型（user_id、credits_purchased、credits_remaining、price_paid、stripe_payment_id、purchased_at、expires_at、is_expired）
    - 在 `backend/app/models/credit_topup_package.py` 中创建 CreditTopupPackage 模型（name、credits、price、stripe_price_id、is_active）
    - _需求: 6.3, 6.6_

  - [x] 1.6 创建 Alembic 迁移脚本
    - 生成包含所有新表（credit_balances、credit_ledger、credit_cost_configs、topup_purchases、credit_topup_packages）和 Plan 扩展字段的迁移
    - 确保 CHECK 约束和索引正确创建
    - _需求: 1.1, 1.3, 2.6, 7.1_

- [x] 2. 检查点 - 确保数据模型和迁移正确
  - 确保所有测试通过，如有问题请询问用户。

- [x] 3. CreditService 核心实现
  - [x] 3.1 实现 CreditService 基础结构和 get_balance
    - 创建 `backend/app/services/credit_service.py`
    - 实现 `__init__(db, redis_client)`、数据类 `CreditBalanceInfo`（含 `available_without_overage = plan_balance + topup_balance`）、`CreditDeductionResult`、`PeriodEndResult`、`CreditEstimateResult`
    - 实现 `get_balance(user_id)` 方法：返回 plan_balance、topup_balance、total_balance、available_without_overage、overage 状态、预估 overage 费用
    - 实现 Redis 缓存读取逻辑（TTL 5 分钟，cache miss 从 DB 加载）
    - 实现自动创建默认 CreditBalance 记录逻辑（plan_balance = monthly_credits, topup_balance = 0）
    - _需求: 1.1, 1.2, 1.4, 1.5_

  - [x] 3.2 Property 1 属性测试：total_balance 不变量
    - **Property 1: total_balance 不变量**
    - 使用 Hypothesis 验证：对任意 CreditBalance 记录，get_balance 返回的 total_balance 始终等于 plan_balance + topup_balance，且 available_without_overage == plan_balance + topup_balance
    - **验证: 需求 1.2**

  - [x] 3.3 实现 check_and_deduct 扣费方法
    - 实现扣费顺序：plan_balance → topup_balance → overage
    - 快速路径：plan_balance 充足时使用原子 `UPDATE ... WHERE plan_balance >= cost`
    - 慢路径：plan_balance 不足时使用 `SELECT ... FOR UPDATE` 加行锁，计算跨余额分配
    - **Top-up FIFO 消耗**：当需要动用 topup_balance 时，按 `purchased_at ASC` 顺序从 TopupPurchase 记录逐笔扣减 `credits_remaining`
    - 从 CreditCostConfig 查询操作成本
    - **幂等/重复扣费检查**：提取为统一 helper 方法 `has_settled_charge_for_context(user_id, operation, context_type, context_id)` 和 `has_refund_for_key(user_id, refund_key)`，供所有端点和 Celery task 复用，不散落在各处
    - 写入 CreditLedger 记录（status=settled，含 credit_amount、source、balance_after、is_overage、overage_portion、context_type、context_id、pricing_version）
    - 写后删除 Redis 缓存 key
    - 余额不足且 overage 未开启时抛出 InsufficientCreditsError
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 8.1, 8.2, 8.3_

  - [x] 3.4 Property 2 属性测试：扣费分配守恒
    - **Property 2: 扣费分配守恒**
    - 使用 Hypothesis 验证：plan_deducted + topup_deducted + overage_portion == cost × quantity，且严格遵循 plan → topup → overage 顺序
    - **验证: 需求 2.2, 2.3, 2.4**

  - [x] 3.5 Property 3 属性测试：余额不足拒绝
    - **Property 3: 余额不足拒绝**
    - 使用 Hypothesis 验证：plan + topup < cost 且 overage 未开启时，check_and_deduct 抛出 InsufficientCreditsError，余额不变
    - **验证: 需求 2.5**

  - [x] 3.6 Property 14 属性测试：扣费金额等于配置成本
    - **Property 14: 扣费金额等于配置成本**
    - 使用 Hypothesis 验证：实际扣除总量 == CreditCostConfig.credit_cost × quantity，Ledger 的 pricing_version 与配置一致
    - **验证: 需求 2.1, 7.2, 7.3**

  - [x] 3.7 实现 refund_credits 退款方法
    - 实现退款顺序：overage → topup → plan（与扣费相反）
    - **Top-up 退款**：退回 topup 部分时，按 FIFO 反向（最近消耗的 TopupPurchase 优先恢复 credits_remaining）
    - **幂等保证**：支持 `refund_key` 参数，通过 reference_id 做幂等检查——若已存在相同 refund_key 的 REFUND ledger 记录，直接返回当前余额，不重复退款。异步场景（Celery retry / on_failure 重入）必须传 refund_key 防止多退
    - 写入 CreditLedger 记录（operation=REFUND，status=settled，含 reason 字段）
    - 写后删除 Redis 缓存 key
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 3.8 Property 4 属性测试：扣费-退款 round trip
    - **Property 4: 扣费-退款 round trip**
    - 使用 Hypothesis 验证：扣费后退款，plan_balance + topup_balance + overage_credits_used 恢复到扣费前状态
    - **验证: 需求 3.1, 3.2, 3.3, 3.4**

  - [x] 3.9 Property 5 属性测试：退款顺序与扣费相反
    - **Property 5: 退款顺序与扣费相反**
    - 使用 Hypothesis 验证：退款严格遵循 overage → topup → plan 顺序
    - **验证: 需求 3.2, 3.3, 3.4**

  - [x] 3.10 Property 6 属性测试：每次余额变动都有 Ledger 记录
    - **Property 6: 每次余额变动都有 Ledger 记录**
    - 使用 Hypothesis 验证：任何导致 CreditBalance 变化的操作都在 CreditLedger 中新增记录，且 balance_after 与实际余额一致
    - **验证: 需求 2.6, 3.5, 5.5, 5.6, 6.4**

  - [x] 3.11 实现 check_sufficient 方法（含 allow_overage 参数）
    - `check_sufficient(user_id, operation, quantity=1, allow_overage=True) -> bool`
    - `allow_overage=True`（默认）：plan + topup + overage 综合判断
    - `allow_overage=False`：仅检查 plan + topup 自然余额，不考虑 overage
    - 用途：套餐页预估消耗、高风险操作不希望走 overage 时传 False
    - _需求: 9.1, 9.3_

  - [x] 3.12 实现 get_credit_costs 方法
    - 从 CreditCostConfig 查询所有 is_active=true 的操作成本
    - _需求: 7.2, 7.5_

  - [x] 3.13 Property 15 属性测试：成本列表仅返回活跃配置
    - **Property 15: 成本列表仅返回活跃配置**
    - 使用 Hypothesis 验证：get_credit_costs 仅返回 is_active=true 的记录，不遗漏
    - **验证: 需求 7.5, 10.3**

  - [x] 3.14 实现 get_ledger 分页查询方法
    - 按 created_at DESC 排序，支持 limit 和 offset 分页
    - _需求: 10.2_

  - [x] 3.15 Property 18 属性测试：历史分页正确性
    - **Property 18: 历史分页正确性**
    - 使用 Hypothesis 验证：返回记录数 <= limit，按 created_at DESC 排序，offset 跳过正确
    - **验证: 需求 10.2**

  - [x] 3.16 实现 estimate_cost 预估方法
    - `estimate_cost(user_id, operation, quantity=1) -> CreditEstimateResult`
    - v1 为静态查表：从 CreditCostConfig 获取 cost，结合用户余额判断 sufficient / sufficient_without_overage / would_use_overage
    - **⚠️ 纯只读操作：不创建 ledger、不写缓存、不保留/冻结余额、无任何副作用**
    - v2 扩展为动态预估（文档复杂度、处理模式等）
    - _需求: 10.7（新增）_

- [x] 4. 检查点 - 确保 CreditService 核心逻辑正确
  - 确保所有测试通过，如有问题请询问用户。

- [x] 5. Overage 模式与月度重置
  - [x] 5.1 实现 set_overage_enabled 方法
    - Free 套餐 → 抛出 OverageNotAvailableError
    - unpaid_overage_periods >= 2 → 抛出 OverageSuspendedError
    - Plus/Pro 套餐正常切换 overage_enabled
    - _需求: 4.1, 4.2, 4.7_

  - [x] 5.2 Property 7 属性测试：Free 套餐不支持 overage
    - **Property 7: Free 套餐不支持 overage**
    - 使用 Hypothesis 验证：Free 套餐调用 set_overage_enabled(true) 始终抛出 OverageNotAvailableError
    - **验证: 需求 4.1, 13.2**

  - [x] 5.3 Property 10 属性测试：连续未结清自动禁用 overage
    - **Property 10: 连续未结清自动禁用 overage**
    - 使用 Hypothesis 验证：unpaid_overage_periods >= 2 时 set_overage_enabled(true) 抛出 OverageSuspendedError
    - **验证: 需求 4.7**

  - [x] 5.4 实现 process_period_end 月度重置方法
    - **严格按以下顺序执行（在单个数据库事务内）**：
      1. 结算 overage 费用（overage_credits_used × overage_price_per_credit），通过 Stripe 创建 Invoice（auto_advance=true，metadata 含 `type=overage_settlement`）
      2. 清理过期 topup（逐笔检查 TopupPurchase，`expires_at < now()` 的标记 is_expired=true，从 topup_balance 扣除 credits_remaining）
      3. 重置 plan_balance = monthly_credits
      4. 清零 overage_credits_used = 0
      5. 更新 subscription 周期日期（period_start, period_end）
      6. 写入 Ledger 记录（OVERAGE_SETTLEMENT / TOPUP_EXPIRY / MONTHLY_RESET，均 status=settled）
      7. COMMIT 事务
      8. 删除 Redis 缓存 key（事务外）
    - **Stripe 支付失败处理策略**：完全依赖 Stripe smart retries（自动重试 3-4 次，间隔递增，跨 7-10 天），我方不做额外重试逻辑
    - Stripe webhook `invoice.payment_failed` → 标记 has_unpaid_overage=true，unpaid_overage_periods += 1
    - unpaid_overage_periods >= 2 → 自动禁用 overage 功能（用户仍可使用 plan + topup 余额，不冻结账户）
    - _需求: 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 5.5 Property 9 属性测试：Overage 费用计算
    - **Property 9: Overage 费用计算**
    - 使用 Hypothesis 验证：overage 结算金额 == overage_credits_used × overage_price_per_credit
    - **验证: 需求 4.5, 10.6**

  - [x] 5.6 Property 11 属性测试：月度重置行为
    - **Property 11: 月度重置行为**
    - 使用 Hypothesis 验证：重置后 plan_balance == monthly_credits，overage_credits_used == 0，未过期 topup 不变
    - **验证: 需求 5.1, 5.2, 5.3**

  - [x] 5.7 Property 12 属性测试：Topup 过期清理
    - **Property 12: Topup 过期清理**
    - 使用 Hypothesis 验证：过期的 TopupPurchase 被标记 is_expired=true，topup_balance 扣除对应 credits_remaining
    - **验证: 需求 5.4**

- [x] 6. Top-up 充值与套餐变更
  - [x] 6.1 实现 add_topup_credits 充值方法
    - topup_balance += 购买数量
    - 创建 TopupPurchase 记录（expires_at = purchased_at + 12 个月）
    - **注意**：topup_balance 是所有未过期 TopupPurchase.credits_remaining 的聚合值，消耗时按 purchased_at ASC（FIFO）逐笔扣减
    - 写入 TOPUP Ledger 记录
    - 删除 Redis 缓存 key
    - _需求: 6.2, 6.3, 6.4, 6.5_

  - [x] 6.2 Property 13 属性测试：充值增加 topup_balance
    - **Property 13: 充值增加 topup_balance**
    - 使用 Hypothesis 验证：充值后 topup_balance == 充值前 + 购买数量，TopupPurchase.expires_at == purchased_at + 12 个月
    - **验证: 需求 6.2, 6.3**

  - [x] 6.3 实现套餐变更对 overage 的影响逻辑
    - 在 SubscriptionService 的 upgrade/downgrade 流程中集成 CreditService
    - 降级到 Free → 自动关闭 overage，结算已有 overage 费用
    - 升级 → 保留 overage 开关状态
    - _需求: 4.3, 4.4_

  - [x] 6.4 Property 8 属性测试：套餐变更对 overage 的影响
    - **Property 8: 套餐变更对 overage 的影响**
    - 使用 Hypothesis 验证：降级到 Free 时 overage_enabled 变为 false；升级时 overage_enabled 保持不变
    - **验证: 需求 4.3, 4.4**

- [x] 7. 检查点 - 确保 Overage、月度重置和充值逻辑正确
  - 确保所有测试通过，如有问题请询问用户。

- [x] 8. 并发安全与 FeatureGateService 迁移
  - [x] 8.1 实现并发扣费安全测试
    - 编写测试验证多个并发扣费请求不会导致余额为负
    - 验证快速路径（原子 UPDATE）和慢路径（SELECT FOR UPDATE）的正确性
    - _需求: 8.1, 8.2, 8.3, 8.4_

  - [x] 8.2 Property 16 属性测试：并发扣费余额不为负
    - **Property 16: 并发扣费余额不为负**
    - 使用 Hypothesis 验证：一组并发扣费后 plan_balance >= 0 且 topup_balance >= 0
    - **验证: 需求 8.3**

  - [x] 8.3 迁移 FeatureGateService 到 Credit 模式
    - 修改 `backend/app/services/feature_gate_service.py`
    - `check_feature_access()` 改为委托 `CreditService.check_sufficient()` 检查 credit 是否充足
    - 保留 `check_processing_gate()` 用于系统侧处理级门控（风控/质量控制）
    - 保留旧的 `_FEATURE_MIN_PLAN` 映射作为 fallback（过渡期）
    - **⚠️ 关键边界**：FeatureGateService 只负责用户侧 entitlement / payment sufficiency；自动化深度、risk gating、manual review 继续由处理级 gate 决定，不迁移到 credit 层。例如：用户有足够 credit 可以使用资产识别，但 create_asset_auto 可能因字段不全/重复风险/review_reasons 被系统侧 gate 拒绝。
    - _需求: 9.1, 9.2, 9.3, 9.4_

  - [x] 8.4 Property 17 属性测试：FeatureGateService 委托 CreditService
    - **Property 17: FeatureGateService 委托 CreditService**
    - 使用 Hypothesis 验证：FeatureGateService.check_feature_access 返回值与 CreditService.check_sufficient 一致
    - **验证: 需求 9.1, 9.3, 9.4**

- [x] 9. 检查点 - 确保并发安全和功能门控迁移正确
  - 确保所有测试通过，如有问题请询问用户。

- [x] 10. Credit API 端点
  - [x] 10.1 创建 Pydantic schemas
    - 在 `backend/app/schemas/credit.py` 中创建请求/响应 schemas：CreditBalanceResponse（含 available_without_overage）、CreditLedgerResponse、CreditCostResponse、TopupCheckoutRequest、TopupCheckoutResponse、OverageUpdateRequest、OverageEstimateResponse、CreditEstimateRequest、CreditEstimateResponse
    - _需求: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.2 实现 Credit API 端点
    - 创建 `backend/app/api/v1/endpoints/credits.py`
    - `GET /credits/balance` — 返回 plan_balance、topup_balance、total_balance、available_without_overage、overage 状态、预估 overage 费用
    - `GET /credits/history` — 返回分页 CreditLedger 记录（支持 limit、offset 参数）
    - `GET /credits/costs` — 返回所有活跃操作的 credit 成本列表
    - `POST /credits/topup` — 创建 Stripe Checkout Session（或 dev mode 直接充值）
    - `PUT /credits/overage` — 调用 set_overage_enabled 更新 overage 开关
    - `GET /credits/overage/estimate` — 返回当前周期 overage 预估费用
    - `POST /credits/estimate` — 预估操作成本（输入 operation + quantity，输出 cost、sufficient、sufficient_without_overage、would_use_overage）
    - 在 `backend/app/api/v1/endpoints/__init__.py` 或路由注册处挂载 credits router
    - _需求: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 11. Celery 后台任务与 Stripe Webhook
  - [x] 11.1 创建月度重置 Celery 任务
    - 在 `backend/app/tasks/credit_tasks.py` 中创建 `process_period_end_batch` 任务
    - 查询所有 period_end <= now() 的用户，逐个调用 `CreditService.process_period_end`
    - 配置 Celery Beat 定时调度（每日检查）
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 11.2 创建 Stripe webhook 处理
    - 处理 `checkout.session.completed` 事件 → 调用 `add_topup_credits`
    - 处理 `invoice.paid` 事件 → **仅当 invoice metadata 含 `type=overage_settlement` 时**才重置 has_unpaid_overage=false 和 unpaid_overage_periods=0，恢复 overage 功能；普通订阅付款成功不应错误清空 overage 欠费状态
    - 处理 `invoice.payment_failed` 事件 → **仅当 invoice metadata 含 `type=overage_settlement` 时**才标记 has_unpaid_overage=true，unpaid_overage_periods += 1
    - **注意**：不做额外重试逻辑，完全依赖 Stripe smart retries
    - _需求: 4.6, 4.8, 6.2_

- [x] 12. 数据迁移脚本
  - [x] 12.1 创建用户数据迁移 Alembic 脚本
    - 为所有现有用户创建 CreditBalance 记录（plan_balance = plan.monthly_credits，topup_balance = 0，overage_enabled = false）
    - 为每个用户写入 MIGRATION Ledger 记录（status=settled）
    - 创建 CreditCostConfig 初始数据（ocr_scan=5, ai_conversation=10, transaction_entry=1, bank_import=3, e1_generation=20, tax_calc=2）
    - 创建 CreditTopupPackage 初始数据（小包 100/€4.99、中包 300/€12.99、大包 1000/€39.99）
    - 保留旧 UsageRecord 表和 Plan 的 quotas/features 字段不删除
    - _需求: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 12.2 Property 19 属性测试：迁移后状态正确性
    - **Property 19: 迁移后状态正确性**
    - 使用 Hypothesis 验证：迁移后 plan_balance == monthly_credits，topup_balance == 0，overage_enabled == false，存在 MIGRATION Ledger 记录
    - **验证: 需求 12.1, 12.2, 12.3**

- [x] 13. 检查点 - 确保 API、Webhook、迁移全部正确
  - 确保所有测试通过，如有问题请询问用户。

- [x] 14. 业务端点扣费集成 — 同步端点试点
  - [x] 14.1 同步端点扣费集成（AI 对话、税务计算、交易录入）
    - 在 AI 对话端点中调用 `check_and_deduct("ai_conversation")`，失败时调用 `refund_credits`
    - 在交易录入端点中调用 `check_and_deduct("transaction_entry")`
    - 在银行导入端点中调用 `check_and_deduct("bank_import")`
    - 在税务计算端点中调用 `check_and_deduct("tax_calc")`
    - 在 E1 生成端点中调用 `check_and_deduct("e1_generation")`，失败时调用 `refund_credits`
    - 扣费成功后在响应头中添加 `X-Credits-Remaining`（返回 `available_without_overage` 即 plan_balance + topup_balance 自然余额，不混入 overage 额度）
    - **这些都是同步短操作，"先扣后退"模式适用**
    - _需求: 2.1, 2.5, 3.1_

- [x] 15. 业务端点扣费集成 — 文档/OCR 异步扣费试点
  - [x] 15.1 文档上传/OCR 异步扣费集成
    - 在 OCR 上传端点（`backend/app/api/v1/endpoints/documents.py`）中调用 `check_and_deduct("ocr_scan")`
    - **异步链路特殊处理**：
      - 上传时同步扣费（用户等待期间完成）
      - 后台 Celery 任务处理 OCR
      - 任务失败/超时/部分失败时，在 Celery task 的 on_failure 回调中调用 `refund_credits(reason="ocr_processing_failed", refund_key="refund:{doc_id}")`
      - **幂等防护**：refund_credits 通过 refund_key 做幂等检查，Celery retry / on_failure 重入不会重复退款
      - 确保 Celery task retry 不会重复扣费（通过 context_type="document" + context_id=doc_id 做幂等检查）
    - **v1 限制**：不做多段扣费（整个文档处理视为一次操作），不区分 OCR 成功但分类失败的情况（v2 引入事件级计费后细化）
    - 扣费成功后在响应头中添加 `X-Credits-Remaining`（返回 `available_without_overage`，与同步端点一致）
    - _需求: 2.1, 2.5, 3.1_

- [x] 16. 检查点 - 确保业务端点扣费集成正确
  - 确保所有测试通过，如有问题请询问用户。

- [x] 17. 前端 Credit 展示改版
  - [x] 17.1 扩展 subscriptionStore 支持 Credit 数据
    - 在 `frontend/src/stores/subscriptionStore.ts` 中新增 credit 相关状态和 actions
    - 新增类型：CreditBalance（含 available_without_overage）、CreditLedgerEntry、CreditCost、TopupPackage
    - 新增 actions：fetchCreditBalance、fetchCreditHistory、fetchCreditCosts、createTopupCheckout、toggleOverage、fetchOverageEstimate、estimateCost
    - _需求: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 17.2 改版 SubscriptionStatus 组件为 Credit 展示
    - 修改 `frontend/src/components/subscription/SubscriptionStatus.tsx`
    - 替换按资源使用量条为统一 Credit 进度条（分别显示 plan_balance 和 topup_balance）
    - 新增 Overage 开关（toggle）+ 单价显示 + 未结清警告
    - 显示本周期 overage 使用量和预估费用
    - **新增"预计能做什么"辅助文案**：根据当前余额和 CreditCostConfig，显示"约等于还能处理 N 次 OCR / N 次 AI 对话"等轻量提示，帮助用户理解 credit 的实际价值。文案需标注"该提示为按当前标准成本表的近似估算，不代表最终实际消耗"
    - _需求: 11.1, 11.2_

  - [x] 17.3 创建 CreditHistory 页面
    - 创建 `frontend/src/pages/CreditHistoryPage.tsx`
    - 展示分页的 credit 变动记录列表（操作类型、金额、时间、关联实体）
    - 支持按操作类型筛选
    - _需求: 11.3_

  - [x] 17.4 创建 Credit 充值组件
    - 创建 `frontend/src/components/subscription/CreditTopup.tsx`
    - 展示可用充值包（名称、credit 数量、价格）
    - 点击后调用 createTopupCheckout 跳转 Stripe Checkout
    - _需求: 11.4_

  - [x] 17.5 改版套餐页展示 Credit 信息
    - 修改套餐页（PricingPage 或相关组件）展示月度 Credit 额度、overage 单价
    - 添加操作成本参考表（OCR=5, AI=10, 交易=1, 银行导入=3, E1=20, 税务计算=2）
    - _需求: 11.5_

- [x] 18. API 过渡期兼容
  - [x] 18.1 在订阅 API 响应中同时返回 credit 信息
    - 修改 `backend/app/api/v1/endpoints/subscriptions.py` 的 `GET /subscriptions/current` 响应，附加 credit_balance 信息
    - 保留旧格式 usage 数据（过渡期兼容）
    - _需求: 12.6_

- [x] 19. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## v1 明确不做的事项（Non-goals）

以下功能明确不在 v1 范围内，实施时不要越界：

1. **不按文档复杂度动态定价** — 所有操作按 CreditCostConfig 静态配置扣费，不区分文档页数、图片数量、字段复杂度
2. **不支持 Auto / High 处理模式差异扣费** — 不引入 processing_mode 概念，所有处理走统一成本
3. **不支持 reservation-based settlement** — 采用"先扣后退"模式，不实现 reserve → settle → release 三段式（但 Ledger 已预留 status 和 reservation_id 字段供 v2 使用）
4. **不按实际 token / vision API 调用回写真实成本** — 不追踪 AI provider 的实际消耗，成本为固定值
5. **不针对单个后台任务做多段扣费** — 每次操作扣费一次，不拆分为多个计费事件
6. **不改变 AI 处理深度** — 仅改计费模型，OCR/AI/分类等处理逻辑和结果质量不变
7. **不支持 Plan 级 credit_cost override** — 所有套餐共享全局 CreditCostConfig
8. **成本配置不区分 provider path** — 不区分 Tesseract vs Cloud Vision、本地 AI vs OpenAI 等不同处理路径的成本差异

## 备注

- 标记 `*` 的任务为可选属性测试任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点确保增量验证，及时发现问题
- 属性测试使用 Hypothesis 库验证通用正确性属性
- v2（AI Processing Pricing Model）的预留接口已在 v1 数据模型中包含（status、reservation_id、pricing_version、context_type/context_id 等），无需额外任务
- **任务 14（同步扣费）和 15（异步扣费）已拆分**：同步短操作先上线验证，文档/OCR 异步链路单独试点，降低风险
- **Top-up FIFO 规则**：消耗按 purchased_at ASC，过期清理逐笔从 TopupPurchase.credits_remaining 计算
- **Stripe 失败策略**：完全依赖 Stripe smart retries，不做额外重试；连续 2 周期未结清自动禁用 overage，不冻结账户
