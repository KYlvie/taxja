# E1表单解析器 - 亏损结转功能已添加 ✅

## 更新内容

为了支持所有用户类型（员工、房东、自雇人士、小企业主），已添加完整的亏损结转（Loss Carryforward）数据提取和处理功能。

## 新增字段

### E1FormData 数据类

添加了7个亏损结转相关字段：

```python
# Loss carryforward (Verlustvortrag)
kz_462: Optional[Decimal] = None  # 前年度未使用亏损总额
kz_332: Optional[Decimal] = None  # 本年使用的经营亏损
kz_346: Optional[Decimal] = None  # 本年使用的投资亏损
kz_372: Optional[Decimal] = None  # 本年使用的非经营亏损
kz_341: Optional[Decimal] = None  # 本年新产生的经营亏损
kz_342: Optional[Decimal] = None  # 本年新产生的投资亏损
kz_371: Optional[Decimal] = None  # 本年新产生的非经营亏损
```

## 功能说明

### 1. 数据提取（E1FormExtractor）

**新增方法：`_extract_loss_carryforward()`**

从E1表单中提取亏损结转数据：
- 第13节：Wartetastenregelungen（等待规则）
- 第25.3节：Verlustabzug（亏损扣除）

**提取的KZ字段：**
- **KZ 462** - 前年度未使用亏损总额
- **KZ 332** - 本年使用的经营亏损（自己企业）
- **KZ 346** - 本年使用的投资亏损
- **KZ 372** - 本年使用的非经营亏损
- **KZ 341** - 本年新产生的经营亏损
- **KZ 342** - 本年新产生的投资亏损
- **KZ 371** - 本年新产生的非经营亏损

### 2. 数据处理（E1FormImportService）

**新增方法：`_process_loss_carryforward()`**

处理亏损结转数据并创建数据库记录：

1. **计算亏损使用情况**
   - 汇总本年使用的所有亏损（KZ 332 + 346 + 372）

2. **记录新产生的亏损**
   - 汇总本年新产生的亏损（KZ 341 + 342 + 371）
   - 创建或更新`LossCarryforward`数据库记录

3. **计算剩余余额**
   - 剩余 = 前年度亏损 - 本年使用 + 本年新增

4. **返回详细信息**
   ```json
   {
     "prior_year_losses": 10000.00,
     "losses_used_this_year": 5000.00,
     "new_losses_this_year": 3000.00,
     "remaining_balance": 8000.00,
     "details": [
       {
         "type": "business_loss_used",
         "kz": "332",
         "amount": 5000.00,
         "description": "Verrechenbare Verluste - eigener Betrieb"
       }
     ]
   }
   ```

## 使用场景

### 场景1：小企业主有亏损年份

**2023年：**
- 营业收入：€30,000
- 营业支出：€45,000
- 净亏损：€-15,000
- **KZ 341** = €15,000（新产生的亏损）

**系统处理：**
- 创建`LossCarryforward`记录
- `loss_year` = 2023
- `loss_amount` = €15,000
- `remaining_amount` = €15,000

### 场景2：使用前年度亏损

**2024年：**
- 营业收入：€50,000
- 前年度亏损：€15,000（从2023年）
- **KZ 462** = €15,000（前年度亏损）
- **KZ 332** = €15,000（本年使用）

**系统处理：**
- 更新2023年的`LossCarryforward`记录
- `used_amount` = €15,000
- `remaining_amount` = €0
- 应税收入减少€15,000

### 场景3：部分使用亏损

**2024年：**
- 营业收入：€20,000
- 前年度亏损：€30,000
- **KZ 462** = €30,000
- **KZ 332** = €20,000（只能使用€20,000）

**系统处理：**
- 更新`LossCarryforward`记录
- `used_amount` = €20,000
- `remaining_amount` = €10,000（可结转到2025年）

## 数据库集成

亏损数据自动保存到`loss_carryforwards`表：

```sql
CREATE TABLE loss_carryforwards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    loss_year INTEGER NOT NULL,
    loss_amount NUMERIC(12, 2) NOT NULL,
    used_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    remaining_amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, loss_year)
);
```

## API响应示例

导入E1表单后的响应包含亏损结转信息：

```json
{
  "tax_year": 2023,
  "taxpayer_name": "Zhang Fenghong",
  "steuernummer": "03 627/7572",
  "transactions_created": 2,
  "loss_carryforward": {
    "prior_year_losses": null,
    "losses_used_this_year": null,
    "new_losses_this_year": 15000.00,
    "remaining_balance": 15000.00,
    "details": [
      {
        "type": "new_business_loss",
        "kz": "341",
        "amount": 15000.00,
        "description": "Nicht ausgleichsfähige Verluste - eigener Betrieb"
      }
    ]
  }
}
```

## 支持的用户类型

### ✅ 员工（Employee）
- 通常没有亏损
- 系统正常处理收入和扣除

### ✅ 房东（Landlord）
- 租赁亏损通过E1b表单处理
- 可能有KZ 371（非经营亏损）

### ✅ 自雇人士（Self-Employed）
- 可能有KZ 341（经营亏损）
- 亏损可结转7年

### ✅ 小企业主（Small Business Owner）
- 可能有KZ 341（经营亏损）
- 可能有KZ 342（投资亏损）
- 完整的亏损跟踪和结转

## 税务规划优势

1. **多年税务优化**
   - 自动跟踪亏损余额
   - 计算未来年度可用亏损

2. **准确的税务计算**
   - 系统自动应用亏损抵扣
   - 减少应税收入

3. **合规性**
   - 符合奥地利税法
   - 7年亏损结转期限

4. **透明度**
   - 详细的亏损使用记录
   - 清晰的余额追踪

## 测试建议

1. **测试有亏损的企业主**
   - 上传包含KZ 341的E1表单
   - 验证`LossCarryforward`记录创建

2. **测试亏损使用**
   - 上传包含KZ 462和KZ 332的E1表单
   - 验证亏损余额更新

3. **测试多年场景**
   - 导入多年的E1表单
   - 验证亏损结转链

## 下一步

现在E1解析器已经完整支持：
- ✅ 所有收入类型
- ✅ 所有扣除项
- ✅ 租赁详情
- ✅ 税务计算
- ✅ 亏损结转

可以测试完整的导入流程了！
