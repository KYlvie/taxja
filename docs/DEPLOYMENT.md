# Taxja 部署指南

## 服务器信息

- IP: `46.62.227.62`
- 用户: `root`
- SSH Key: `C:\Users\yk1e25\taxja-server-nopass`
- 项目路径: `/opt/taxja`
- 域名: `taxja.at`

## 架构

```
nginx (80/443) → backend (8000) → postgres (5432)
                                → redis (6379)
                                → minio (9000)
               → celery-worker  → postgres/redis/minio
               → frontend/dist (静态文件)
```

所有服务通过 Docker Compose 管理，配置文件：
- `docker-compose.server.yml` — 服务定义
- `.env.prod` — 环境变量（API keys、数据库密码等）

---

## 常规部署（无数据库迁移）

适用于：只改了代码（Python/TypeScript/CSS），没有新的 alembic migration 文件。

```bash
# 1. 连接服务器
ssh -i C:\Users\yk1e25\taxja-server-nopass root@46.62.227.62

# 2. 拉取最新代码
cd /opt/taxja && git pull

# 3. 重新构建前端
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build

# 4. 重新构建并重启后端 + Celery
docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build backend celery-worker

# 5. 验证服务状态
docker compose -f docker-compose.server.yml ps
curl -s http://localhost:8000/api/v1/health

# 6. （可选）清除缓存
docker exec taxja-redis redis-cli FLUSHDB
```

---

## 带数据库迁移的部署

适用于：`git pull` 后 `backend/alembic/versions/` 下有新的 migration 文件。

```bash
# 1. 连接服务器
ssh -i C:\Users\yk1e25\taxja-server-nopass root@46.62.227.62

# 2. 拉取最新代码
cd /opt/taxja && git pull

# 3. 重新构建前端
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build

# 4. 重建后端镜像
docker compose -f docker-compose.server.yml --env-file .env.prod build backend celery-worker

# 5. 运行数据库迁移（关键步骤！）
docker compose -f docker-compose.server.yml --env-file .env.prod run --rm backend alembic upgrade head

# 6. 重启服务
docker compose -f docker-compose.server.yml --env-file .env.prod up -d backend celery-worker

# 7. 验证
docker compose -f docker-compose.server.yml ps
curl -s http://localhost:8000/api/v1/health
```

---

## 判断是否需要数据库迁移

```bash
# git pull 后检查是否有新的 migration 文件
git diff HEAD~1 --name-only | grep alembic/versions/
```

如果有输出（新文件），就需要跑迁移。没有输出就不需要。

---

## 只改了前端

如果只改了 `frontend/` 下的文件，不需要重启后端：

```bash
ssh -i C:\Users\yk1e25\taxja-server-nopass root@46.62.227.62
cd /opt/taxja && git pull
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build
# nginx 会自动读取新的 dist 文件，不需要重启
```

---

## 只改了后端

如果只改了 `backend/` 下的 Python 文件，不需要重建前端：

```bash
ssh -i C:\Users\yk1e25\taxja-server-nopass root@46.62.227.62
cd /opt/taxja && git pull
docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build backend celery-worker
```

---

## 故障排查

### 查看日志

```bash
# 后端日志
docker logs taxja-backend --tail 50 -f

# Celery 日志
docker logs taxja-celery-worker --tail 50 -f

# Nginx 日志
docker logs taxja-nginx --tail 50 -f

# 数据库日志
docker logs taxja-postgres --tail 50 -f
```

### 重启单个服务

```bash
docker compose -f docker-compose.server.yml --env-file .env.prod restart backend
docker compose -f docker-compose.server.yml --env-file .env.prod restart celery-worker
docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx
```

### 重启所有服务

```bash
docker compose -f docker-compose.server.yml --env-file .env.prod down
docker compose -f docker-compose.server.yml --env-file .env.prod up -d
```

### 数据库连接

```bash
docker exec -it taxja-postgres psql -U taxja -d taxja
```

### Redis 操作

```bash
# 清除所有缓存
docker exec taxja-redis redis-cli FLUSHDB

# 清除折旧缓存
docker exec taxja-redis redis-cli KEYS "depreciation_schedule:*" | xargs -r docker exec -i taxja-redis redis-cli DEL

# 查看缓存 key
docker exec taxja-redis redis-cli KEYS "*"
```

### 回滚

```bash
cd /opt/taxja
git log --oneline -5          # 查看最近的 commit
git checkout <commit-hash>    # 回滚到指定版本
docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build backend celery-worker
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build
```

如果需要回滚数据库迁移：
```bash
docker compose -f docker-compose.server.yml --env-file .env.prod run --rm backend alembic downgrade -1
```

---

## 新增 Python 依赖

如果 `backend/requirements.txt` 有变化，`--build` 会自动安装新依赖（Dockerfile 里有 `pip install -r requirements.txt`）。

## 新增 npm 依赖

如果 `frontend/package.json` 有变化：

```bash
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm install
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npm run build
```

---

## SSL 证书

Let's Encrypt 证书在 `/etc/letsencrypt/`，nginx 容器挂载了这个目录。

续期：
```bash
certbot renew
docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx
```
