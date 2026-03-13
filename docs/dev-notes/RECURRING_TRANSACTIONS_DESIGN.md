# 定期交易自动化系统设计

## 问题描述

用户提出的关键问题：
1. 租金收入是否自动添加到系统？
2. 贷款利息是否自动扣除？
3. 如果租金突然停止怎么办？
4. 如果房产卖掉了怎么办？

## 解决方案概述

实现一个完整的定期交易（Recurring Transactions）系统，自动生成租金收入、贷款利息等定期交易，并智能处理房产状态变化。

## 核心组件

### 1. RecurringTransaction 模型

**文件**: `backend/app/models/recurring_transaction.py`

**功能**:
- 存储定期交易配置
- 支持多种频率：月度、季度、年度、周度、双周
- 支持多种类型：
  - `RENTAL_INCOME` - 租金收入
  - `LOAN_INTEREST` - 贷款利息
  - `DEPRECIATION` - 折旧
  - `MANUAL` - 用户自定义

**关键字段**:
- `property_id` - 关联房产
- `loan_id` - 关联贷款
- `amount` - 金额
- `frequency` - 频率
- `start_date` / `end_date` - 起止日期
- `is_active` - 是否激活
- `last_generated_date` - 上次生成日期
- `next_generation_date` - 下次生成日期

### 2. RecurringTransactionService 服务

**文件**: `backend/app/services/recurring_transaction_service.py`

**核心方法**:

#### 创建定期交易
```python
# 创建租金收入定期交易
create_rental_income_recurring(
    user_id, property_id, monthly_rent, 
    start_date, end_date, day_of_month
)

# 创建贷款利息定期交易
create_loan_interest_recurring(
    user_id, loan_id, monthly_interest,
    start_date, end_date, day_of_month
)
```

#### 管理定期交易
```python
pause_recurring_transaction(recurring_id)  # 暂停
resume_recurring_transaction(recurring_id)  # 恢复
stop_recurring_transaction(recurring_id, end_date)  # 停止
```

#### 自动生成交易
```python
generate_due_transactions(target_date)  # 生成到期的交易
```

#### 智能处理房产状态变化
```python
auto_pause_for_sold_property(property_id)  # 房产卖出时自动暂停
```

### 3. Celery 定时任务

**文件**: `backend/app/tasks/recurring_tasks.py`

**任务**:

#### 每日生成交易任务
```python
@shared_task(name="generate_recurring_transactions")
def generate_recurring_transactions_task():
    """每天午夜运行，生成所有到期的定期交易"""
```

#### 房产状态检查任务
```python
@shared_task(name="check_property_status_changes")
def check_property_status_changes_task():
    """每天检查房产状态变化，自动暂停已售房产的定期交易"""
```

## 使用场景

### 场景 1: 新增租赁房产

**流程**:
1. 用户添加房产信息（地址、购买价格等）
2. 用户设置租金金额和租赁开始日期
3. 系统自动创建 `RecurringTransaction`:
   - Type: `RENTAL_INCOME`
   - Amount: 月租金
   - Frequency: `MONTHLY`
   - Start date: 租赁开始日期
   - Day of month: 每月收租日（如1号）

**结果**:
- 每月自动生成租金收入交易
- 自动关联到对应房产
- 自动分类为 `rental_income`

### 场景 2: 房产贷款

**流程**:
1. 用户添加房产贷款信息
2. 系统计算月度利息金额
3. 自动创建 `RecurringTransaction`:
   - Type: `LOAN_INTEREST`
   - Amount: 月利息
   - Frequency: `MONTHLY`
   - Linked to: PropertyLoan

**结果**:
- 每月自动生成贷款利息支出交易
- 自动标记为可抵扣（`is_deductible=True`）
- 关联到房产和贷款记录

### 场景 3: 租金停止（租客搬走）

**用户操作**:
```
方式 1: 暂停定期交易
- 用户点击"暂停租金收入"
- 系统调用 pause_recurring_transaction()
- 状态变为 is_active=False
- 可以随时恢复

方式 2: 设置结束日期
- 用户设置租赁结束日期
- 系统调用 stop_recurring_transaction(end_date)
- 系统在结束日期后自动停止生成
```

**系统行为**:
- 不再生成新的租金收入交易
- 历史交易保留
- 可以查看暂停原因和时间

### 场景 4: 房产卖出

**流程**:
1. 用户将房产状态改为 `SOLD`
2. 用户设置 `sale_date`
3. 系统自动触发:
   ```python
   auto_pause_for_sold_property(property_id)
   ```
4. 所有关联的定期交易自动暂停:
   - 租金收入
   - 贷款利息（如果贷款已还清）
   - 折旧

**结果**:
- 所有定期交易标记为 `is_active=False`
- 添加备注："Auto-paused: Property sold on YYYY-MM-DD"
- 设置 `end_date` 为卖出日期
- 不影响历史交易记录

### 场景 5: 房产重新出租

**流程**:
1. 用户将房产状态改回 `ACTIVE`
2. 用户创建新的租金收入定期交易
3. 设置新的租金金额和开始日期

**或者**:
1. 用户找到之前暂停的定期交易
2. 更新金额（如果租金变化）
3. 调用 `resume_recurring_transaction()`

## 数据库迁移

需要创建迁移文件：

```python
# backend/alembic/versions/012_add_recurring_transactions.py

def upgrade():
    # Create RecurrenceFrequency enum
    op.execute("""
        CREATE TYPE recurrencefrequency AS ENUM (
            'monthly', 'quarterly', 'annually', 'weekly', 'biweekly'
        )
    """)
    
    # Create RecurringTransactionType enum
    op.execute("""
        CREATE TYPE recurringtransactiontype AS ENUM (
            'rental_income', 'loan_interest', 'depreciation', 'manual'
        )
    """)
    
    # Create recurring_transactions table
    op.create_table(
        'recurring_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), ForeignKey('users.id'), nullable=False),
        sa.Column('recurring_type', sa.Enum(...), nullable=False),
        sa.Column('property_id', UUID(), ForeignKey('properties.id'), nullable=True),
        sa.Column('loan_id', sa.Integer(), ForeignKey('property_loans.id'), nullable=True),
        # ... 其他字段
    )
```

## Celery Beat 配置

在 `backend/app/core/celery_app.py` 或配置文件中添加：

```python
from celery.schedules import crontab

beat_schedule = {
    'generate-recurring-transactions-daily': {
        'task': 'generate_recurring_transactions',
        'schedule': crontab(hour=0, minute=5),  # 每天 00:05 运行
    },
    'check-property-status-changes-daily': {
        'task': 'check_property_status_changes',
        'schedule': crontab(hour=1, minute=0),  # 每天 01:00 运行
    },
}
```

## API 端点设计

### 创建定期交易
```
POST /api/v1/recurring-transactions/rental-income
POST /api/v1/recurring-transactions/loan-interest
```

### 管理定期交易
```
GET /api/v1/recurring-transactions  # 列表
GET /api/v1/recurring-transactions/{id}  # 详情
PUT /api/v1/recurring-transactions/{id}  # 更新
DELETE /api/v1/recurring-transactions/{id}  # 删除

POST /api/v1/recurring-transactions/{id}/pause  # 暂停
POST /api/v1/recurring-transactions/{id}/resume  # 恢复
POST /api/v1/recurring-transactions/{id}/stop  # 停止
```

### 查询
```
GET /api/v1/properties/{id}/recurring-transactions  # 房产的定期交易
GET /api/v1/recurring-transactions/upcoming  # 即将生成的交易
```

## 前端 UI 设计

### 房产详情页

**定期交易卡片**:
```
┌─────────────────────────────────────┐
│ 📅 定期交易                          │
├─────────────────────────────────────┤
│ 💰 租金收入                          │
│    €1,200.00 / 月                   │
│    下次生成: 2026-04-01             │
│    [暂停] [编辑]                     │
├─────────────────────────────────────┤
│ 💳 贷款利息                          │
│    €450.00 / 月                     │
│    下次生成: 2026-04-01             │
│    [暂停] [编辑]                     │
├─────────────────────────────────────┤
│ [+ 添加定期交易]                     │
└─────────────────────────────────────┘
```

### 交易列表页

**自动生成标记**:
```
2026-03-01  租金收入 - Musterstraße 1  €1,200.00  🤖 自动生成
2026-03-01  贷款利息 - Bank Austria    €450.00   🤖 自动生成
```

### 房产卖出确认对话框

```
┌─────────────────────────────────────┐
│ ⚠️  确认卖出房产                     │
├─────────────────────────────────────┤
│ 卖出此房产将自动停止以下定期交易：   │
│                                     │
│ • 租金收入 (€1,200/月)              │
│ • 贷款利息 (€450/月)                │
│                                     │
│ 卖出日期: [2026-03-15]              │
│                                     │
│ [取消] [确认卖出]                    │
└─────────────────────────────────────┘
```

## 优势

### 1. 自动化
- 无需手动每月输入租金收入
- 无需手动记录贷款利息
- 减少人为错误

### 2. 智能化
- 房产卖出自动停止相关交易
- 房产状态变化自动处理
- 支持暂停/恢复灵活管理

### 3. 可追溯
- 所有自动生成的交易都有标记
- 保留完整的历史记录
- 可以查看定期交易的配置历史

### 4. 灵活性
- 支持多种频率（月/季/年）
- 支持自定义开始/结束日期
- 支持手动暂停/恢复
- 支持金额调整

## 实施步骤

1. ✅ 创建 `RecurringTransaction` 模型
2. ✅ 创建 `RecurringTransactionService` 服务
3. ✅ 创建 Celery 定时任务
4. ⏳ 创建数据库迁移
5. ⏳ 添加 API 端点
6. ⏳ 更新 User 模型添加关系
7. ⏳ 配置 Celery Beat 调度
8. ⏳ 前端 UI 实现
9. ⏳ 编写测试
10. ⏳ 文档和用户指南

## 注意事项

### 税务合规
- 自动生成的交易仍需用户审核
- 系统标记为"自动生成"以便识别
- 用户可以编辑或删除自动生成的交易

### 数据一致性
- 定期交易与实际交易分开存储
- 定期交易只是"模板"，不影响实际账目
- 只有生成的 Transaction 才计入税务计算

### 性能考虑
- Celery 任务异步执行，不阻塞主应用
- 批量生成交易使用事务
- 定期清理过期的定期交易配置

## 未来扩展

1. **智能提醒**
   - 租金未收到提醒
   - 定期交易异常检测

2. **批量操作**
   - 批量暂停/恢复
   - 批量调整金额

3. **高级规则**
   - 租金自动涨幅（如每年+2%）
   - 贷款还款计划自动调整

4. **报表功能**
   - 定期交易统计
   - 现金流预测
