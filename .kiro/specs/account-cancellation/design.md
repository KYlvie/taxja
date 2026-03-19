# 技术设计：账号注销与退订功能

## 概述

基于现有的分层架构（API → Services → Models），新增账号注销与退订功能。核心变更包括：User 模型新增账号状态字段、三个新服务（AccountCancellationService、DataExportService、扩展 SubscriptionService）、Celery 定时清理任务、前端多步骤注销流程。

## 数据模型变更

### User 模型扩展 (`backend/app/models/user.py`)

新增字段：
```python
# 账号状态: active, deactivated, deletion_pending
account_status = Column(String(20), nullable=False, default="active", index=True)
deactivated_at = Column(DateTime, nullable=True)          # 停用时间
scheduled_deletion_at = Column(DateTime, nullable=True)    # 计划删除时间
deletion_retry_count = Column(Integer, nullable=False, default=0)  # 硬删除重试次数
cancellation_reason = Column(String(500), nullable=True)   # 注销原因
```

### AccountDeletionLog 新模型 (`backend/app/models/account_deletion_log.py`)

硬删除完成后的合规审计记录：
```python
class AccountDeletionLog(Base):
    __tablename__ = "account_deletion_logs"
    id = Column(Integer, primary_key=True)
    anonymous_user_hash = Column(String(64), nullable=False)  # SHA-256(user_id + salt)
    deleted_at = Column(DateTime, nullable=False)
    data_types_deleted = Column(JSON)       # ["transactions", "documents", ...]
    deletion_method = Column(String(20))    # "scheduled" | "admin_manual"
    initiated_by = Column(String(20))       # "user" | "admin" | "system"
```

### Alembic 迁移 (`backend/alembic/versions/011_add_account_cancellation_fields.py`)

- User 表新增 account_status、deactivated_at、scheduled_deletion_at、deletion_retry_count、cancellation_reason
- 新建 account_deletion_logs 表
- 添加 account_status 索引

## 后端服务设计

### AccountCancellationService (`backend/app/services/account_cancellation_service.py`)

核心方法：
- `get_cancellation_impact(user_id) -> dict` — 返回注销影响摘要（数据数量、订阅信息）
- `deactivate_account(user_id, password, reason) -> dict` — 验证密码后软删除，取消活跃订阅，设置 scheduled_deletion_at = now + 30天
- `reactivate_account(user_id) -> dict` — 冷静期内恢复账号为 active
- `hard_delete_account(user_id, initiated_by) -> dict` — 按顺序删除：MinIO 文档 → 数据库关联记录 → 匿名化支付/审计记录 → Redis 缓存 → 创建 AccountDeletionLog
- `send_deletion_reminder(user_id)` — 第 23 天发送提醒邮件

删除顺序（hard_delete_account）：
1. 查询用户所有 Document，调用 StorageService.delete_file 删除 MinIO 文件
2. 删除数据库记录（利用 cascade="all, delete-orphan" 关系）
3. 匿名化 PaymentEvent（set user_id=NULL）和 AuditLog
4. 清除 Redis 缓存 keys: `user:{id}:*`, `session:{id}:*`
5. 删除 User 记录
6. 创建 AccountDeletionLog

### DataExportService (`backend/app/services/data_export_service.py`)

核心方法：
- `export_user_data(user_id, encryption_password) -> str` — 生成加密数据包，返回 MinIO 预签名下载链接（48h 有效）

导出流程：
1. 查询用户全部数据（transactions, documents, tax_reports, corrections, loss_carryforwards, properties, property_loans）
2. 交易记录 → CSV，结构化数据 → JSON（含数据字典），文档 → 原始文件
3. 打包为 ZIP，使用 pyzipper 进行 AES-256 加密
4. 上传至 MinIO `data-exports/` 桶，生成 48h 预签名 URL

### SubscriptionService 扩展

现有 `cancel_subscription` 和 `reactivate_subscription` 已满足需求 1 的大部分逻辑。需要：
- 在 `cancel_subscription` 中增加 Stripe API 调用（当前只更新本地状态）
- 确保 `reactivate_subscription` 重置 `cancel_at_period_end`

## API 端点设计

### 账号管理端点 (`backend/app/api/v1/endpoints/account.py`)

```
POST /api/v1/account/cancellation-impact    → 获取注销影响摘要
POST /api/v1/account/deactivate             → 停用账号（需密码验证）
POST /api/v1/account/reactivate             → 重新激活账号
POST /api/v1/account/export-data            → 请求数据导出
GET  /api/v1/account/export-status/{task_id} → 查询导出状态
```

### 管理员端点扩展 (`backend/app/api/v1/endpoints/admin.py`)

```
GET    /api/v1/admin/users?status=deactivated  → 按状态筛选用户
POST   /api/v1/admin/users/{id}/hard-delete    → 手动触发硬删除
POST   /api/v1/admin/users/{id}/reactivate     → 手动重新激活
GET    /api/v1/admin/cancellation-stats         → 注销统计数据
```

### 认证端点修改 (`backend/app/api/v1/endpoints/auth.py`)

login 端点增加 account_status 检查：
- `deactivated` → 返回 403 + 剩余冷静期天数 + reactivation 提示
- `deletion_pending` → 返回 403 + 账号已计划删除

## Pydantic Schemas (`backend/app/schemas/account.py`)

```python
class DeactivateAccountRequest(BaseModel):
    password: str
    reason: Optional[str] = None
    two_factor_code: Optional[str] = None
    confirmation_word: str  # 必须为 "DELETE"

class CancellationImpactResponse(BaseModel):
    transaction_count: int
    document_count: int
    tax_report_count: int
    property_count: int
    has_active_subscription: bool
    subscription_days_remaining: Optional[int]
    cooling_off_days: int = 30

class DataExportRequest(BaseModel):
    encryption_password: str  # 用于 AES-256 加密数据包

class DataExportStatusResponse(BaseModel):
    status: str  # "pending" | "processing" | "ready" | "failed"
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
```

## Celery 定时任务 (`backend/app/tasks/account_cleanup_tasks.py`)

```python
@celery_app.task
def cleanup_expired_accounts():
    """每日执行：检查过期停用账号并执行硬删除"""
    # 1. 查找 account_status='deactivated' 且 scheduled_deletion_at < now
    # 2. 对每个账号执行 hard_delete_account
    # 3. 查找 account_status='deletion_pending' 且 retry_count < 3，重试
    # 4. retry_count >= 3 的发送管理员告警
    # 5. 生成清理报告

@celery_app.task
def send_deletion_reminders():
    """每日执行：向第 23 天的停用账号发送提醒邮件"""

# Celery Beat 配置
CELERYBEAT_SCHEDULE = {
    'cleanup-expired-accounts': {
        'task': 'app.tasks.account_cleanup_tasks.cleanup_expired_accounts',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨 2 点
    },
    'send-deletion-reminders': {
        'task': 'app.tasks.account_cleanup_tasks.send_deletion_reminders',
        'schedule': crontab(hour=9, minute=0),  # 每天上午 9 点
    },
}
```

## 前端设计

### 账号管理组件 (`frontend/src/components/account/`)

- `AccountManagementSection.tsx` — 设置页中的账号管理区域，包含退订和注销入口
- `CancelSubscriptionModal.tsx` — 退订确认弹窗（显示订阅信息、到期日、取消原因选择）
- `DeleteAccountWizard.tsx` — 多步骤注销向导：
  - Step 1: 注销影响摘要（调用 cancellation-impact API）
  - Step 2: 数据导出选项（可选，调用 export-data API）
  - Step 3: 密码验证 + 输入 "DELETE" 确认
- `DeactivatedAccountBanner.tsx` — 登录页停用提示 + 重新激活按钮

### Zustand Store (`frontend/src/stores/accountStore.ts`)

```typescript
interface AccountStore {
  cancellationImpact: CancellationImpact | null;
  exportStatus: ExportStatus | null;
  fetchCancellationImpact: () => Promise<void>;
  deactivateAccount: (data: DeactivateRequest) => Promise<void>;
  reactivateAccount: () => Promise<void>;
  requestDataExport: (password: string) => Promise<void>;
  pollExportStatus: (taskId: string) => Promise<void>;
}
```

### API 服务 (`frontend/src/services/accountService.ts`)

封装所有账号管理 API 调用。

### i18n 翻译

在 de.json、en.json、zh.json 中新增 `account` 命名空间，包含所有注销/退订相关文案。

## 依赖

- `pyzipper` — Python AES-256 加密 ZIP（需添加到 requirements.txt）
- 现有依赖：boto3（MinIO）、redis、celery、stripe（已在 monetization 中引入）

## 任务列表
