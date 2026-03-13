# Taxja 快速测试指南

## 🎉 系统已就绪！

所有服务都在运行，所有问题都已修复。现在可以开始测试了！

## 🌐 访问地址

### 前端应用
**URL**: http://localhost:5173

打开浏览器访问此地址开始使用应用。

### API 文档
**URL**: http://localhost:8000/api/v1/docs

在这里可以测试所有 API 端点。

## 🧪 测试场景

### 1. 用户注册和登录

#### 注册新用户
1. 访问 http://localhost:5173
2. 点击"注册"或"Register"
3. 填写信息：
   - 邮箱：任意有效邮箱
   - 密码：至少 8 个字符
   - 姓名：任意名称
   - 用户类型：选择一个（员工、自雇、房东等）
4. 提交注册

#### 登录
1. 使用注册的邮箱和密码登录
2. 应该能看到仪表板

### 2. 交易管理

#### 添加收入交易
1. 登录后，进入"交易"或"Transactions"页面
2. 点击"添加交易"
3. 选择类型：收入
4. 填写金额、日期、描述
5. 保存

#### 添加支出交易
1. 同样在交易页面
2. 选择类型：支出
3. 填写详细信息
4. 系统会自动分类（AI 分类）

### 3. 文档上传和 OCR

#### 上传收据
1. 进入"文档"或"Documents"页面
2. 点击"上传文档"
3. 选择图片或 PDF 文件
4. 系统会自动进行 OCR 识别
5. 查看提取的信息

### 4. 房产管理

#### 添加房产
1. 进入"房产"或"Properties"页面
2. 点击"添加房产"
3. 填写房产信息：
   - 地址
   - 购买价格
   - 购买日期
   - 房产类型（出租/自住/混合）
4. 保存

#### 查看折旧
1. 在房产列表中查看
2. 系统会自动计算年度折旧
3. 可以查看折旧进度

### 5. 税务计算

#### 查看税务摘要
1. 进入"仪表板"或"Dashboard"
2. 查看当前年度的税务摘要
3. 包括：
   - 总收入
   - 总支出
   - 应纳税额
   - 可抵扣项目

#### 生成税务报告
1. 进入"报告"或"Reports"页面
2. 选择年度
3. 生成报告
4. 可以下载 PDF 或导出数据

## 🔧 API 测试（使用 Swagger UI）

访问 http://localhost:8000/api/v1/docs

### 测试认证端点

#### 1. 注册用户
```
POST /api/v1/auth/register
Body:
{
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "name": "New User",
  "user_type": "employee"
}
```

#### 2. 登录
```
POST /api/v1/auth/login
Body (form-data):
username: newuser@example.com
password: SecurePass123!
```

复制返回的 `access_token`

#### 3. 使用 Token
1. 点击页面右上角的"Authorize"按钮
2. 输入：`Bearer <your_access_token>`
3. 点击"Authorize"
4. 现在可以测试需要认证的端点了

### 测试交易端点

#### 创建交易
```
POST /api/v1/transactions/
Body:
{
  "amount": 1500.00,
  "date": "2026-03-08",
  "description": "Salary March 2026",
  "transaction_type": "income",
  "category": "employment_income"
}
```

#### 获取交易列表
```
GET /api/v1/transactions/?year=2026
```

### 测试文档端点

#### 上传文档
```
POST /api/v1/documents/upload
Body (multipart/form-data):
file: [选择文件]
document_type: receipt
```

#### 获取文档列表
```
GET /api/v1/documents/
```

### 测试房产端点

#### 创建房产
```
POST /api/v1/properties/
Body:
{
  "address": "Teststraße 123, 1010 Wien",
  "purchase_price": 300000.00,
  "land_value": 50000.00,
  "purchase_date": "2020-01-15",
  "property_type": "rental"
}
```

#### 获取房产列表
```
GET /api/v1/properties/
```

## 🧪 运行自动化测试

### 后端测试

#### 运行所有测试
```bash
cd backend
pytest -v
```

#### 运行备份测试
```bash
cd backend
pytest tests/test_backup_*.py -v
```

#### 运行带覆盖率的测试
```bash
cd backend
pytest --cov=app --cov-report=html
```

查看覆盖率报告：打开 `backend/htmlcov/index.html`

### 前端测试

```bash
cd frontend
npm run test
```

## 📊 监控和日志

### 查看后端日志
在 Kiro 中使用：
```
getProcessOutput terminalId=4 lines=50
```

### 查看前端日志
在 Kiro 中使用：
```
getProcessOutput terminalId=5 lines=50
```

### 查看数据库
```bash
docker exec -it taxja-postgres psql -U taxja -d taxja
```

常用 SQL 查询：
```sql
-- 查看所有用户
SELECT id, email, name, user_type FROM users;

-- 查看所有交易
SELECT id, amount, date, description, transaction_type FROM transactions;

-- 查看所有房产
SELECT id, address, purchase_price, property_type FROM properties;
```

### 查看 MinIO 存储
访问 http://localhost:9001
- 用户名：minioadmin
- 密码：minioadmin

## 🐛 常见问题

### 前端无法连接后端
**检查**：
1. 后端是否在运行：`curl http://localhost:8000/api/v1/docs`
2. CORS 配置是否正确（已配置）

### 注册失败
**检查**：
1. 邮箱格式是否正确
2. 密码是否足够强（至少 8 个字符）
3. 查看后端日志获取详细错误

### 文档上传失败
**检查**：
1. MinIO 是否在运行：`docker ps | grep minio`
2. 文件大小是否超过限制
3. 文件格式是否支持

### 数据库错误
**检查**：
1. PostgreSQL 是否在运行：`docker ps | grep postgres`
2. 数据库迁移是否完成：`cd backend && alembic current`
3. 如需重置：`docker-compose down -v && docker-compose up -d`

## 🎯 测试重点

### 核心功能
- ✅ 用户注册和登录
- ✅ 交易创建和分类
- ✅ 文档上传和 OCR
- ✅ 房产管理和折旧计算
- ✅ 税务计算和报告生成

### 新功能（备份系统）
- 📝 备份任务（如果已添加 API 端点）
- 📝 备份列表查询
- 📝 备份恢复功能

### 性能测试
- 📝 大量交易的加载速度
- 📝 OCR 处理时间
- 📝 报告生成速度

## 📝 测试反馈

测试时如果发现问题，请记录：
1. 问题描述
2. 重现步骤
3. 预期行为
4. 实际行为
5. 错误信息（如果有）
6. 浏览器控制台日志
7. 后端日志

## 🚀 下一步

1. **功能测试**：测试所有核心功能
2. **性能测试**：测试大数据量下的性能
3. **安全测试**：测试认证和授权
4. **集成测试**：测试端到端流程
5. **用户体验测试**：测试界面和交互

祝测试顺利！🎊
