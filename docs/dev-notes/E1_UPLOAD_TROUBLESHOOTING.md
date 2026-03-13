# E1表单上传问题排查

## 问题现象

从截图看到：
- 识别置信度：75%（偏低）
- 税务年度：2023（但你说上传的是2020年的）
- 纳税人和税号：空
- KZ值不正确：
  - KZ 245: €11,383.33（应该是€38,987.70）
  - KZ 370: €2.11（应该是€-18,771.31）
  - KZ 572: €10,513.51（这个KZ不应该存在）

## 根本原因

1. **你上传的文件可能不是完整的E1 PDF**
   - 可能是截图或扫描件
   - 可能是部分页面
   - 可能是压缩或低质量的PDF

2. **数据只是预览，还没有导入**
   - 截图显示的是预览界面
   - 需要点击"✅ 导入数据并创建交易"按钮才会真正创建交易记录
   - 数据库中没有E1表单的记录证实了这一点

## 解决方案

### 方案1：使用正确的PDF文件

1. 确保上传的是**完整的E1 PDF文件**（不是截图）
2. 文件应该包含所有页面（至少3页）
3. 文件名应该包含年份信息

**测试文件位置**：
- `backend/Einkommensteuererklärung für 2022.pdf`（实际是2020年数据）

### 方案2：通过API直接测试

使用我们的测试脚本直接测试解析器：

```bash
cd backend
python test_enhanced_e1_parser.py
```

这会显示从PDF中提取的所有数据。

### 方案3：手动上传并导入

1. 访问 http://localhost:5173/documents
2. 点击"导入 E1 所得税申报表"标签
3. 上传完整的E1 PDF文件
4. 等待预览加载
5. **检查预览数据是否正确**
6. 如果正确，点击"✅ 导入数据并创建交易"
7. 如果不正确，说明PDF识别有问题

## 验证步骤

### 1. 检查上传的文件

```bash
# 在项目根目录
ls -la *.pdf
```

确保有正确的E1 PDF文件。

### 2. 测试解析器

```bash
cd backend
python test_enhanced_e1_parser.py
```

应该看到：
- Tax Year: 2020
- Employment (KZ 245): €38,987.70
- Rental (KZ 350): €-18,771.31
- Tax calculation results

### 3. 检查数据库

```bash
cd backend
python check_e1_docs.py
```

如果导入成功，应该看到E1相关的文档记录。

### 4. 检查交易记录

```python
# backend/check_transactions.py
import psycopg2

conn = psycopg2.connect('postgresql://taxja:taxja_password@localhost:5432/taxja')
cur = conn.cursor()
cur.execute("""
    SELECT id, type, amount, description, import_source, transaction_date 
    FROM transactions 
    WHERE import_source = 'e1_import' 
    ORDER BY id DESC 
    LIMIT 10
""")

for row in cur.fetchall():
    print(f'ID: {row[0]}, Type: {row[1]}, Amount: €{row[2]}, Desc: {row[3]}, Date: {row[5]}')

cur.close()
conn.close()
```

## 预期结果

成功导入后应该创建多条交易记录：

1. **就业收入** - €38,987.70
2. **租赁收入** - 根据详细数据拆分
3. **租赁费用** - €18,771.31（总费用）
4. 可能还有其他详细的费用项目

## 常见问题

### Q: 为什么预览数据不对？
A: 可能原因：
- PDF质量问题
- 不是完整的E1表单
- OCR识别错误
- 上传了错误的文件

### Q: 如何确认是否导入成功？
A: 检查：
1. 前端显示"✅ 导入成功"消息
2. 显示创建的交易数量
3. 交易列表中出现新记录
4. 数据库中有e1_import来源的交易

### Q: 可以重新上传吗？
A: 可以，但建议：
1. 先删除错误的预览
2. 确保使用正确的PDF文件
3. 重新上传并检查预览
4. 确认数据正确后再导入

## 下一步

1. **找到正确的E1 PDF文件**
2. **重新上传**
3. **仔细检查预览数据**
4. **确认无误后点击导入**
5. **验证交易记录是否创建**

如果问题仍然存在，请提供：
- 上传的文件名
- 预览界面的完整截图
- 后端日志（Terminal ID: 8）
