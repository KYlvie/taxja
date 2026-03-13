# Getting Started - Monetization System

## 快速开始

### 1. 验证系统安装

运行快速测试脚本：

```bash
python backend/scripts/quick_test.py
```

应该看到所有6项测试通过：
```
✅ PASS - Database Connection
✅ PASS - Plans Exist (3 plans)
✅ PASS - PlanService
✅ PASS - FeatureGateService
✅ PASS - Model Methods
✅ PASS - API Imports

Total: 6/6 tests passed
```

### 2. 启动后端服务器

```bash
cd backend
uvicorn app.main:app --reload
```

服务器将在 http://localhost:8000 启动

### 3. 启动前端开发服务器

```bash
cd frontend
npm run dev
```

前端将在 http://localhost:3000 启动

### 4. 访问功能

#### 用户端功能
- **定价页面**: http://localhost:3000/pricing
- **订阅管理**: http://localhost:3000/subscription
- **支付成功页**: http://localhost:3000/checkout/success

#### API端点

**订阅管理**:
- `GET /api/v1/subscriptions/plans` - 获取所有计划
- `GET /api/v1/subscriptions/current` - 获取当前订阅
- `POST /api/v1/subscriptions/checkout` - 创建支付会话
- `POST /api/v1/subscriptions/upgrade` - 升级计划
- `POST /api/v1/subscriptions/cancel` - 取消订阅

**使用量跟踪**:
- `GET /api/v1/usage/summary` - 获取使用量摘要
- `GET /api/v1/usage/{resource_type}` - 获取特定资源使用量

**管理后台**:
- `GET /api/v1/admin/subscriptions` - 列出所有订阅
- `GET /api/v1/admin/analytics/revenue` - 收入分析（MRR, ARR）
- `POST /api/v1/admin/subscriptions/{user_id}/grant-trial` - 授予试用期
- `PUT /api/v1/admin/subscriptions/{user_id}/change-plan` - 更改用户计划

**Webhook**:
- `POST /api/v1/webhooks/stripe` - Stripe webhook处理

### 5. API文档

访问 http://localhost:8000/docs 查看完整的API文档（Swagger UI）

## 订阅计划

### Free Plan (€0/月)
- 50笔交易/月
- 基础税务计算
- 仅德语支持

### Plus Plan (€4.90/月 或 €49/年)
- 无限交易
- 20次OCR扫描/月
- 完整税务计算
- 多语言支持（德语、英语、中文）
- VAT和SVS计算

### Pro Plan (€9.90/月 或 €99/年)
- 无限交易
- 无限OCR扫描
- AI税务助手
- E1表格生成
- 高级报告
- 优先支持
- API访问

## 功能门控

在代码中使用功能门控：

### 后端（FastAPI）

```python
from app.api.deps import require_feature
from app.services.feature_gate_service import Feature

@router.post("/ocr/scan")
def scan_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_feature(Feature.OCR_SCANNING))
):
    # 只有Plus和Pro用户可以访问
    pass
```

### 前端（React）

```tsx
import { withFeatureGate } from '@/components/subscription/withFeatureGate';

const OCRScanner = () => {
  return <div>OCR扫描功能</div>;
};

export default withFeatureGate(OCRScanner, 'ocr_scanning');
```

## 使用量跟踪

### 后端跟踪使用量

```python
from app.services.usage_tracker_service import UsageTrackerService
from app.models.usage_record import ResourceType

# 增加使用量
usage_service = UsageTrackerService(db)
usage_service.increment_usage(
    user_id=user.id,
    resource_type=ResourceType.TRANSACTIONS
)

# 检查配额
if not usage_service.check_quota_limit(user.id, ResourceType.TRANSACTIONS):
    raise QuotaExceededError("Transaction quota exceeded")
```

### 前端显示使用量

```tsx
import { UsageWidget } from '@/components/subscription/UsageWidget';

<UsageWidget />
```

## Stripe集成（生产环境）

### 1. 配置Stripe

在 `.env` 文件中添加：

```env
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2. 创建Stripe产品

在Stripe Dashboard中创建：
- Plus Plan: €4.90/月 或 €49/年
- Pro Plan: €9.90/月 或 €99/年

### 3. 配置Webhook

在Stripe Dashboard中设置webhook URL：
```
https://your-domain.com/api/v1/webhooks/stripe
```

监听事件：
- `checkout.session.completed`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

## 试用期管理

### 激活14天Pro试用

```python
from app.services.trial_service import TrialService

trial_service = TrialService(db)
subscription = trial_service.activate_trial(user_id)
```

### 检查试用状态

```python
is_trial_active = trial_service.check_trial_status(user_id)
```

## 管理后台

### 授予试用期

```bash
curl -X POST http://localhost:8000/api/v1/admin/subscriptions/123/grant-trial?days=14
```

### 更改用户计划

```bash
curl -X PUT http://localhost:8000/api/v1/admin/subscriptions/123/change-plan \
  -H "Content-Type: application/json" \
  -d '{"plan_type": "pro"}'
```

### 查看收入分析

```bash
curl http://localhost:8000/api/v1/admin/analytics/revenue
```

响应：
```json
{
  "mrr": 1234.50,
  "arr": 14814.00,
  "active_subscriptions": 250,
  "plan_distribution": {
    "free": 150,
    "plus": 75,
    "pro": 25
  }
}
```

## 故障排除

### 问题：数据库连接失败

确保PostgreSQL正在运行：
```bash
docker-compose up -d postgres
```

### 问题：计划数据不存在

运行种子脚本：
```bash
python backend/scripts/seed_plans_sql.py
```

### 问题：Redis连接失败

启动Redis：
```bash
docker-compose up -d redis
```

### 问题：Stripe webhook验证失败

确保在 `.env` 中设置了正确的 `STRIPE_WEBHOOK_SECRET`

## 下一步

1. **配置Stripe测试模式** - 使用测试密钥进行开发
2. **实现前端管理界面** - 创建管理后台UI组件
3. **添加Celery任务** - 配置自动化任务（试用期提醒等）
4. **编写测试** - 添加单元测试和集成测试
5. **部署到生产环境** - 配置生产环境变量和监控

## 支持

如有问题，请查看：
- API文档: http://localhost:8000/docs
- 测试指南: `.kiro/specs/monetization-system/TESTING_GUIDE.md`
- 完成总结: `.kiro/specs/monetization-system/COMPLETION_SUMMARY.md`
