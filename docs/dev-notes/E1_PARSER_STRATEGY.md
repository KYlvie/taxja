# E1表单解析器策略

## 支持的格式

### ✅ 标准E1表单格式（2023-2025年）
- 官方E1表单（Einkommensteuererklärung）
- 从FinanzOnline导出的E1表单
- 手工填写的E1表单PDF
- 特征：包含"E 1-PDF-YYYY"标识

### ⏳ Steuerberechnung格式（未来支持）
- 税务软件生成的计算结果
- 特征：包含"Steuerberechnung für YYYY"
- 数据集中在单页
- 需要专门的解析器

## 格式检测逻辑

```python
def detect_e1_format(text: str) -> str:
    """
    Detect E1 form format
    Returns: 'standard_e1' | 'steuerberechnung' | 'unknown'
    """
    if 'E 1-PDF-' in text or 'Einkommensteuererklärung für' in text[:500]:
        return 'standard_e1'
    elif 'Steuerberechnung für' in text[:500]:
        return 'steuerberechnung'
    else:
        return 'unknown'
```

## 当前实现状态

### ✅ 已实现
- 标准E1表单基础解析
- KZ值提取
- 个人信息提取
- 收入/费用分类

### 🚧 增强中
- 详细的就业费用提取
- 租赁物业详细信息
- 税务计算结果提取
- 2023-2025年格式适配

### ⏳ 计划中
- Steuerberechnung格式支持
- 多年度数据对比
- 自动数据验证

## 用户指南

### 支持的文件类型

✅ **推荐使用**：
1. 从FinanzOnline导出的E1表单PDF
2. 填写完整的官方E1表单
3. 包含E1b（租赁详情）的完整申报包

❌ **暂不支持**：
1. 税务软件生成的Steuerberechnung文件
2. 扫描件或图片（OCR质量可能不佳）
3. 不完整的表单

### 如何获取支持的E1表单

1. **FinanzOnline导出**（推荐）
   - 登录 finanzonline.bmf.gv.at
   - 选择相应年度的申报
   - 导出为PDF

2. **手工填写**
   - 下载官方E1表单模板
   - 使用PDF编辑器填写
   - 保存为PDF

3. **税务顾问提供**
   - 要求提供标准E1表单格式
   - 不是Steuerberechnung格式

## 测试文件

### 可用于测试
- `backend/Einkommensteuererklärung für 2022.pdf` - 2020年数据，标准格式 ✅

### 不适用于当前版本
- `backend/Einkommensteuererklärung für 2023.PDF` - Steuerberechnung格式 ⏳

## 版本规划

### v1.0（当前）
- 支持标准E1表单（2020-2025年）
- 基础数据提取
- 交易创建

### v1.1（计划）
- 增强的详细数据提取
- 租赁物业详情
- 税务计算结果

### v2.0（未来）
- Steuerberechnung格式支持
- 多格式自动检测
- 智能数据验证

## 建议

对于2023年及以后的申报：
1. 使用标准E1表单格式
2. 如果只有Steuerberechnung文件，可以手动输入数据
3. 或等待v2.0版本支持

---

**结论**：当前版本专注于标准E1表单格式（2023-2025年），这是最通用和官方的格式。
