# Taxja 快速启动指南

## 当前状态
✅ Docker 基础设施已启动 (PostgreSQL, Redis, MinIO)
✅ Python 虚拟环境已创建
✅ 大部分依赖已安装
✅ 前端依赖已安装

## 立即启动（3步）

### 1. 完成后端依赖安装
打开 PowerShell，运行：
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt --no-build-isolation
```

### 2. 运行数据库迁移
```powershell
# 确保还在 backend 目录，虚拟环境已激活
alembic upgrade head
```

### 3. 启动服务
运行自动启动脚本：
```powershell
# 回到项目根目录
cd ..
.\start-services.ps1
```

或者手动启动（两个终端）：

**终端 1 - 后端：**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**终端 2 - 前端：**
```powershell
cd frontend
npm run dev
```

## 访问地址
- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- MinIO: http://localhost:9001 (minioadmin/minioadmin)

## 开发优势
- ✅ 代码修改立即生效（热重载）
- ✅ 无需重新构建 Docker 镜像
- ✅ 方便调试和测试
- ✅ 快速迭代开发

## 停止服务
- 关闭 PowerShell 窗口
- 或按 Ctrl+C

## 停止基础设施
```powershell
docker-compose stop postgres redis minio
```

## 故障排除

### 端口被占用
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### 数据库连接失败
```powershell
docker-compose restart postgres
```

### 重新开始
```powershell
docker-compose down -v
docker-compose up -d postgres redis minio
```

## 下一步
1. 查看 API 文档了解可用接口
2. 测试前端功能
3. 开始开发新功能
4. 运行测试: `pytest` (后端) 或 `npm test` (前端)
