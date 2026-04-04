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

## 容器重启规则

每次修改代码后，必须根据改动范围重启对应的容器。**重要：backend/celery 重启后 Docker 会分配新 IP，必须同时重启 nginx，否则 nginx 会连旧 IP 导致 502。**

| 改动范围 | 需要重启的容器 |
|----------|---------------|
| 只改了 `frontend/` | 重新 build 前端（`npx vite build`），重启 nginx |
| 只改了 `backend/app/` (非 tasks/) | backend + nginx |
| 改了 `backend/app/tasks/` 或 Celery 相关 | backend + celery-worker + nginx |
| 改了 `backend/alembic/versions/` | 先跑 migration，再重启 backend + celery-worker + nginx |
| 改了 `backend/requirements.txt` | 需要 `--build` 重建镜像，重启 backend + celery-worker + nginx |
| 改了 `.env.prod` (API keys 等) | backend + celery-worker + nginx |
| 改了 `nginx.conf` | 只需重启 nginx |
| postgres/redis/minio 配置变更 | 重启对应容器 + 所有依赖它的容器 + nginx |

> **为什么总要重启 nginx？** nginx 启动时解析 `server backend:8000` 的 DNS 并缓存结果。backend 容器重建后 Docker 分配新 IP，nginx 仍连旧 IP → `connect() failed (111: Connection refused)` → 502。重启 nginx 刷新 DNS 即可。

> **为什么 celery-worker 也要重启？** celery-worker 和 backend 跑的是同一套 Python 代码。OCR、AI 分类、pipeline 处理都在 celery 里执行。如果只重启 backend 不重启 celery，上传文件的处理逻辑还是旧代码。

> **前端 build 注意事项：** `npm run build` 会先跑 `tsc` 类型检查，如果有 TS 类型错误会失败。可以用 `npx vite build` 跳过类型检查直接构建。

---

## 常规部署（无数据库迁移）

适用于：只改了代码（Python/TypeScript/CSS），没有新的 alembic migration 文件。

```bash
# 1. 连接服务器
ssh -i C:\Users\yk1e25\taxja-server-nopass root@46.62.227.62

# 2. 拉取最新代码
cd /opt/taxja && git pull

# 3. 重新构建前端（跳过 tsc 类型检查）
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npx vite build

# 4. 重新构建并重启后端 + Celery + Nginx
docker compose -f docker-compose.server.yml --env-file .env.prod up -d --build backend celery-worker
docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx

# 5. 验证服务状态
docker compose -f docker-compose.server.yml ps
curl -s http://localhost:8000/api/v1/health
# 通过 nginx 验证（确认代理正常）
curl -s -o /dev/null -w '%{http_code}' http://localhost/api/v1/health

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

# 3. 重新构建前端（跳过 tsc 类型检查）
docker run --rm -v $(pwd)/frontend:/app -w /app node:18-alpine npx vite build

# 4. 重建后端镜像
docker compose -f docker-compose.server.yml --env-file .env.prod build backend celery-worker

# 5. 运行数据库迁移（关键步骤！）
docker compose -f docker-compose.server.yml --env-file .env.prod run --rm backend alembic upgrade head

# 6. 重启服务（包括 nginx！）
docker compose -f docker-compose.server.yml --env-file .env.prod up -d backend celery-worker
docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx

# 7. 验证
docker compose -f docker-compose.server.yml ps
curl -s http://localhost:8000/api/v1/health
curl -s -o /dev/null -w '%{http_code}' http://localhost/api/v1/health
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
docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx
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

---

## 常见踩坑

### 1. 部署后 502 Bad Gateway
**原因**：重启了 backend/celery 但没重启 nginx，nginx 缓存了旧容器 IP。
**修复**：`docker compose -f docker-compose.server.yml --env-file .env.prod restart nginx`

### 2. 文档上传后全部识别为 "other"
**原因**：`.env.prod` 中的 LLM API key（Groq/OpenAI/Anthropic）过期或无效，AI 分类全部 401 失败，fallback 到 regex。
**排查**：`docker logs taxja-celery-worker --tail 50 2>&1 | grep 401`
**修复**：更新 `.env.prod` 中的 API key，重启 backend + celery-worker + nginx。

### 3. Alembic migration 失败 (KeyError)
**原因**：migration 链断裂（分叉或 revision ID 不匹配）。
**排查**：检查 `backend/alembic/versions/` 下是否有多个文件的 `down_revision` 指向同一个父级。
**修复**：修复 migration 链使其线性，确保每个 `revision` ID 与下游 `down_revision` 一致。

### 4. 前端 `npm run build` 失败
**原因**：TypeScript 类型检查错误（`tsc` 报错）。
**修复**：用 `npx vite build` 跳过类型检查直接构建。
