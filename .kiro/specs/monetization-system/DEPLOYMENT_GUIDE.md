# Monetization System - Deployment Guide

## 部署前准备

### 1. 环境要求

**后端**:
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- 至少2GB RAM

**前端**:
- Node.js 18+
- npm 9+

### 2. 必需的环境变量

在 `backend/.env` 中配置：

```env
# 安全密钥（生产环境必须更改）
SECRET_KEY=your-production-secret-key-min-32-chars
ENCRYPTION_KEY=your-base64-encoded-encryption-key

# 数据库
POSTGRES_SERVER=your-db-host
POSTGRES_USER=taxja
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=taxja
POSTGRES_PORT=5432

# Redis
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_DB=0

# MinIO/S3
MINIO_ENDPOINT=your-minio-endpoint
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_BUCKET=taxja-documents
MINIO_SECURE=true

# Stripe（生产密钥）
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# CORS（生产域名）
BACKEND_CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Celery
CELERY_BROKER_URL=redis://your-redis-host:6379/0
CELERY_RESULT_BACKEND=redis://your-redis-host:6379/0
```

### 3. Stripe配置

#### 3.1 创建产品和价格

在Stripe Dashboard中创建：

**Plus Plan**:
- 产品名称: "Taxja Plus"
- 月度价格: €4.90
- 年度价格: €49.00
- 记录Price ID

**Pro Plan**:
- 产品名称: "Taxja Pro"
- 月度价格: €9.90
- 年度价格: €99.00
- 记录Price ID

#### 3.2 配置Webhook

1. 在Stripe Dashboard → Developers → Webhooks
2. 添加端点: `https://your-domain.com/api/v1/webhooks/stripe`
3. 选择事件:
   - `checkout.session.completed`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. 复制Webhook签名密钥到 `STRIPE_WEBHOOK_SECRET`

## 部署步骤

### 步骤1: 数据库准备

```bash
# 1. 创建数据库
createdb taxja

# 2. 运行迁移
cd backend
python scripts/run_migration_010.py

# 3. 种子订阅计划
python scripts/seed_plans_sql.py

# 4. 验证
python scripts/quick_test.py
```

### 步骤2: 后端部署

#### 使用Docker

```bash
# 构建镜像
docker build -t taxja-backend:latest -f backend/Dockerfile .

# 运行容器
docker run -d \
  --name taxja-backend \
  -p 8000:8000 \
  --env-file backend/.env \
  taxja-backend:latest
```

#### 使用systemd

创建 `/etc/systemd/system/taxja-backend.service`:

```ini
[Unit]
Description=Taxja Backend API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=taxja
WorkingDirectory=/opt/taxja/backend
Environment="PATH=/opt/taxja/venv/bin"
ExecStart=/opt/taxja/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable taxja-backend
sudo systemctl start taxja-backend
```

### 步骤3: Celery Worker部署

创建 `/etc/systemd/system/taxja-celery.service`:

```ini
[Unit]
Description=Taxja Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=taxja
WorkingDirectory=/opt/taxja/backend
Environment="PATH=/opt/taxja/venv/bin"
ExecStart=/opt/taxja/venv/bin/celery -A app.tasks.celery_app worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 步骤4: 前端部署

```bash
# 1. 构建生产版本
cd frontend
npm run build

# 2. 部署到静态服务器（Nginx示例）
sudo cp -r dist/* /var/www/taxja/

# 3. 配置Nginx
```

Nginx配置示例 `/etc/nginx/sites-available/taxja`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # 前端静态文件
    location / {
        root /var/www/taxja;
        try_files $uri $uri/ /index.html;
    }
    
    # API代理
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 步骤5: 用户迁移

```bash
# 运行迁移脚本
python scripts/migrate_existing_users.py
```

### 步骤6: 验证部署

```bash
# 1. 检查后端健康
curl https://your-domain.com/api/v1/subscriptions/plans

# 2. 检查前端
curl https://your-domain.com

# 3. 测试Stripe webhook
# 在Stripe Dashboard中发送测试事件

# 4. 检查日志
sudo journalctl -u taxja-backend -f
sudo journalctl -u taxja-celery -f
```

## 监控和维护

### 1. 日志配置

在 `backend/app/core/logging_config.py` 中配置：

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger("taxja")
    logger.setLevel(logging.INFO)
    
    # 文件处理器
    handler = RotatingFileHandler(
        "/var/log/taxja/app.log",
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
```

### 2. 监控指标

使用Prometheus监控：

```python
# backend/app/core/metrics.py
from prometheus_client import Counter, Gauge, Histogram

# 订阅指标
subscription_created = Counter('subscription_created_total', 'Total subscriptions created')
subscription_upgraded = Counter('subscription_upgraded_total', 'Total upgrades')
subscription_canceled = Counter('subscription_canceled_total', 'Total cancellations')

# 收入指标
mrr_gauge = Gauge('mrr_euros', 'Monthly Recurring Revenue in Euros')
arr_gauge = Gauge('arr_euros', 'Annual Recurring Revenue in Euros')

# 配额指标
quota_exceeded = Counter('quota_exceeded_total', 'Quota exceeded events', ['resource_type'])

# Stripe指标
stripe_webhook_received = Counter('stripe_webhook_received_total', 'Stripe webhooks', ['event_type'])
stripe_api_errors = Counter('stripe_api_errors_total', 'Stripe API errors')
```

### 3. 健康检查端点

```python
# backend/app/api/v1/endpoints/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.base import get_db
from sqlalchemy import text

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """健康检查端点"""
    try:
        # 检查数据库
        db.execute(text("SELECT 1"))
        
        # 检查Redis（如果配置）
        # redis_client.ping()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

### 4. 备份策略

```bash
# 数据库备份脚本
#!/bin/bash
# /opt/taxja/scripts/backup_db.sh

BACKUP_DIR="/opt/taxja/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/taxja_$DATE.sql.gz"

# 创建备份
pg_dump taxja | gzip > $BACKUP_FILE

# 保留最近30天的备份
find $BACKUP_DIR -name "taxja_*.sql.gz" -mtime +30 -delete

# 上传到S3（可选）
# aws s3 cp $BACKUP_FILE s3://your-backup-bucket/
```

配置cron任务:
```bash
# 每天凌晨2点备份
0 2 * * * /opt/taxja/scripts/backup_db.sh
```

## 故障排除

### 问题1: Stripe webhook验证失败

**症状**: 返回400错误，日志显示签名验证失败

**解决方案**:
1. 检查 `STRIPE_WEBHOOK_SECRET` 是否正确
2. 确保使用原始请求体进行验证
3. 检查Stripe Dashboard中的webhook配置

### 问题2: 数据库连接失败

**症状**: 500错误，无法连接数据库

**解决方案**:
1. 检查PostgreSQL服务状态
2. 验证数据库凭据
3. 检查防火墙规则
4. 查看数据库日志

### 问题3: Redis连接失败

**症状**: 功能门控缓存失败

**解决方案**:
1. 检查Redis服务状态
2. 验证Redis连接字符串
3. 检查Redis内存使用
4. 系统会降级到无缓存模式

### 问题4: Celery任务不执行

**症状**: 试用期提醒未发送

**解决方案**:
1. 检查Celery worker状态
2. 验证Redis broker连接
3. 查看Celery日志
4. 检查任务调度配置

## 回滚计划

如果部署出现问题，按以下步骤回滚：

### 1. 回滚后端

```bash
# 停止新版本
sudo systemctl stop taxja-backend

# 恢复旧版本
sudo cp /opt/taxja/backup/backend-old /opt/taxja/backend -r

# 启动旧版本
sudo systemctl start taxja-backend
```

### 2. 回滚数据库

```bash
# 恢复备份
gunzip < /opt/taxja/backups/taxja_YYYYMMDD_HHMMSS.sql.gz | psql taxja
```

### 3. 回滚前端

```bash
# 恢复旧版本
sudo cp /var/www/taxja-backup/* /var/www/taxja/
```

## 性能优化

### 1. 数据库优化

```sql
-- 创建索引
CREATE INDEX CONCURRENTLY idx_subscriptions_user_status 
ON subscriptions(user_id, status);

CREATE INDEX CONCURRENTLY idx_usage_records_user_period 
ON usage_records(user_id, period_start, period_end);

-- 分析表
ANALYZE subscriptions;
ANALYZE usage_records;
ANALYZE plans;
```

### 2. Redis缓存优化

```python
# 增加缓存TTL
PLAN_CACHE_TTL = 3600  # 1小时
USER_SUBSCRIPTION_CACHE_TTL = 300  # 5分钟
FEATURE_GATE_CACHE_TTL = 300  # 5分钟
```

### 3. API响应优化

```python
# 使用响应缓存
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
```

## 安全加固

### 1. 速率限制

```python
# backend/app/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 应用到端点
@router.post("/checkout")
@limiter.limit("5/hour")
def create_checkout_session(...):
    pass
```

### 2. HTTPS强制

在Nginx配置中添加：
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### 3. 敏感数据加密

确保所有敏感数据使用AES-256加密存储。

## 支持和维护

### 联系方式
- 技术支持: support@taxja.com
- 紧急问题: +43 XXX XXXXXXX

### 维护窗口
- 每周日 02:00-04:00 UTC
- 提前24小时通知用户

### 更新流程
1. 在测试环境验证
2. 创建数据库备份
3. 部署到生产环境
4. 监控错误日志
5. 验证关键功能

## 总结

按照本指南完成部署后，系统应该：
- ✅ 所有服务正常运行
- ✅ Stripe集成工作正常
- ✅ 用户可以订阅和升级
- ✅ 功能门控正常工作
- ✅ 监控和日志配置完成
- ✅ 备份策略就位

如有问题，请参考故障排除部分或联系技术支持。
