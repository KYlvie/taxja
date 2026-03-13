# Taxja 本地启动指南（不使用 Docker）

## 前提条件

你需要在本地安装以下软件：

### 必需软件

1. **Python 3.11+**
   - 下载: https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"

2. **Node.js 18+**
   - 下载: https://nodejs.org/
   - 选择 LTS 版本

3. **PostgreSQL 15+**
   - 下载: https://www.postgresql.org/download/windows/
   - 或使用 Chocolatey: `choco install postgresql`

4. **Redis 7+**
   - Windows 版本: https://github.com/microsoftarchive/redis/releases
   - 或使用 WSL2 安装 Redis

### 可选软件（用于 OCR 功能）

5. **Tesseract OCR**
   - 下载: https://github.com/UB-Mannheim/tesseract/wiki
   - 安装后添加到 PATH

---

## 简化方案：只运行前端（查看界面）

如果你只想快速看看界面效果，可以只启动前端，使用模拟数据。

### 步骤 1: 启动前端

```bash
cd frontend
npm run dev
```

### 步骤 2: 访问

打开浏览器访问: http://localhost:5173

**注意**: 这种方式只能看到界面，无法使用实际功能（因为没有后端）。

---

## 完整方案：运行前端 + 后端

### 步骤 1: 安装并启动 PostgreSQL

#### 使用 Chocolatey（推荐）

```bash
# 安装 Chocolatey（如果还没有）
# 以管理员身份运行 PowerShell，然后执行：
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 安装 PostgreSQL
choco install postgresql

# 启动 PostgreSQL 服务
net start postgresql-x64-15
```

#### 手动安装

1. 下载并安装 PostgreSQL: https://www.postgresql.org/download/windows/
2. 安装时记住密码（默认用户是 postgres）
3. 安装完成后，PostgreSQL 会自动启动

#### 创建数据库

```bash
# 打开 PowerShell，连接到 PostgreSQL
psql -U postgres

# 在 psql 中执行：
CREATE DATABASE taxja;
CREATE USER taxja WITH PASSWORD 'taxja_password';
GRANT ALL PRIVILEGES ON DATABASE taxja TO taxja;
\q
```

---

### 步骤 2: 安装并启动 Redis（可选）

Redis 用于缓存，不是必需的。如果不安装，系统仍然可以运行。

#### 使用 WSL2（推荐）

```bash
# 在 WSL2 中安装 Redis
sudo apt update
sudo apt install redis-server

# 启动 Redis
sudo service redis-server start
```

#### 使用 Windows 版本

1. 下载: https://github.com/microsoftarchive/redis/releases
2. 解压并运行 `redis-server.exe`

---

### 步骤 3: 配置后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件
@"
SECRET_KEY=dev-secret-key-change-in-production
ENCRYPTION_KEY=dev-encryption-key-change-in-production
POSTGRES_SERVER=localhost
POSTGRES_USER=taxja
POSTGRES_PASSWORD=taxja_password
POSTGRES_DB=taxja
POSTGRES_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
"@ | Out-File -FilePath .env -Encoding utf8

# 运行数据库迁移
alembic upgrade head

# 加载演示数据
python scripts/seed_demo.py
```

---

### 步骤 4: 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

后端会在 http://localhost:8000 运行

**保持这个终端窗口打开**

---

### 步骤 5: 启动前端

**打开新的终端窗口**：

```bash
cd frontend
npm run dev
```

前端会在 http://localhost:5173 运行

**保持这个终端窗口打开**

---

### 步骤 6: 访问应用

打开浏览器访问: http://localhost:5173

使用演示账号登录：
- **邮箱**: employee@demo.taxja.at
- **密码**: Demo2026!

---

## 功能限制说明

### 不安装 Redis

- ✅ 所有核心功能正常
- ⚠️ 性能可能稍慢（没有缓存）
- ⚠️ 会话管理使用内存存储

### 不安装 MinIO

- ✅ 所有功能正常
- ⚠️ 文档上传会失败
- ⚠️ OCR 功能无法使用

### 不安装 Tesseract

- ✅ 所有功能正常
- ⚠️ OCR 文档识别无法使用
- ✅ 可以手动输入交易数据

---

## 最小化配置（只需 PostgreSQL）

如果你只想快速测试核心功能，只需要：

1. **安装 PostgreSQL**
2. **启动后端**
3. **启动前端**

其他服务（Redis、MinIO、Tesseract）都是可选的。

---

## 常见问题

### ❌ 问题 1: PostgreSQL 连接失败

**错误**: `could not connect to server`

**解决方案**:
```bash
# 检查 PostgreSQL 是否运行
Get-Service postgresql*

# 如果没有运行，启动它
net start postgresql-x64-15
```

---

### ❌ 问题 2: 端口被占用

**错误**: `Address already in use`

**解决方案**:
```bash
# 查看哪个进程占用了端口
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# 停止占用端口的进程
taskkill /PID <进程ID> /F
```

---

### ❌ 问题 3: Python 依赖安装失败

**错误**: `error: Microsoft Visual C++ 14.0 is required`

**解决方案**:
```bash
# 安装 Visual C++ Build Tools
# 下载: https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

---

## 推荐配置

### 开发环境

- ✅ PostgreSQL（必需）
- ✅ Redis（推荐，提升性能）
- ⚠️ MinIO（可选，用于文档存储）
- ⚠️ Tesseract（可选，用于 OCR）

### 快速测试

- ✅ PostgreSQL（必需）
- ⚠️ 其他都可选

---

## 停止服务

### 停止后端
在后端终端按 `Ctrl + C`

### 停止前端
在前端终端按 `Ctrl + C`

### 停止 PostgreSQL
```bash
net stop postgresql-x64-15
```

---

## 总结

**最简单的方式仍然是使用 Docker**，因为它会自动处理所有依赖。

但如果你不想使用 Docker，按照上面的步骤，只需要：
1. 安装 PostgreSQL
2. 启动后端
3. 启动前端

就可以看到系统运行了！

---

**需要帮助？随时问我！** 😊
