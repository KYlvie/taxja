# 资产管理系统重新设计

## 为什么要改成"资产管理"？

### 当前问题
- ❌ "房产管理"范围太窄
- ❌ 只关注房地产，忽略其他可折旧资产
- ❌ 不符合实际税务需求

### 奥地利税法中可折旧的资产（AfA - Absetzung für Abnutzung）

#### 1. 不动产（Immobilien）
- **出租房产** - 1.5% 或 2% 年折旧率
- **商业房产** - 2-3% 年折旧率
- **建筑物改造** - 根据使用年限

#### 2. 动产（Bewegliche Wirtschaftsgüter）
- **办公设备**
  - 电脑、笔记本 - 3年（33.33%）
  - 打印机、扫描仪 - 5年（20%）
  - 办公家具 - 10年（10%）
  
- **车辆**
  - 商用车辆 - 8年（12.5%）
  - 特殊车辆 - 根据类型

- **机器设备**
  - 生产设备 - 8-10年
  - 工具 - 5年
  - 专业设备 - 根据行业

- **软件和许可证**
  - 标准软件 - 3年
  - 定制软件 - 4年
  - 许可证 - 根据期限

#### 3. 无形资产（Immaterielle Wirtschaftsgüter）
- **商标和专利** - 根据保护期限
- **商誉（Goodwill）** - 15年
- **客户名单** - 5-10年

#### 4. 小额资产（Geringwertige Wirtschaftsgüter - GWG）
- **€400以下** - 可立即全额抵扣
- **€400-€1000** - 可选择立即抵扣或折旧

## 新的资产管理系统设计

### 资产分类体系

```
资产管理
├── 不动产 🏠
│   ├── 出租房产
│   ├── 商业房产
│   ├── 土地（不可折旧）
│   └── 建筑改造
│
├── 办公设备 💻
│   ├── 电脑和笔记本
│   ├── 打印机和扫描仪
│   ├── 办公家具
│   └── 其他办公设备
│
├── 车辆 🚗
│   ├── 商用车
│   ├── 货车
│   └── 特殊车辆
│
├── 机器设备 ⚙️
│   ├── 生产设备
│   ├── 工具
│   └── 专业设备
│
├── 软件和许可 💿
│   ├── 标准软件
│   ├── 定制软件
│   └── 许可证
│
├── 无形资产 ✨
│   ├── 商标
│   ├── 专利
│   ├── 商誉
│   └── 客户名单
│
└── 小额资产 💰
    └── €400-€1000的资产
```

### 统一的资产表单

```typescript
添加/编辑资产
├── 基本信息
│   ├── 资产名称 *
│   ├── 资产类型 * ⭐
│   │   ├── 不动产
│   │   ├── 办公设备
│   │   ├── 车辆
│   │   ├── 机器设备
│   │   ├── 软件和许可
│   │   ├── 无形资产
│   │   └── 小额资产
│   ├── 子类别 *（根据类型动态显示）
│   └── 描述
│
├── 购买信息
│   ├── 购买日期 *
│   ├── 购买价格 *
│   ├── 增值税（可选）
│   └── 供应商
│
├── 折旧设置 ⭐
│   ├── 折旧方法
│   │   ├── ○ 直线折旧（默认）
│   │   ├── ○ 加速折旧
│   │   └── ○ 立即抵扣（小额资产）
│   ├── 折旧率/年限 *
│   │   └── 自动建议（根据类型）
│   ├── 残值（可选）
│   └── 业务使用比例 * (0-100%)
│
├── 不动产特殊字段（仅不动产类型）
│   ├── 地址
│   ├── 建筑价值 vs 土地价值
│   ├── 建造年份
│   ├── 出租比例
│   └── 租金收入
│
├── 车辆特殊字段（仅车辆类型）
│   ├── 车牌号
│   ├── 品牌型号
│   ├── 里程数
│   └── 私人使用比例
│
├── 软件特殊字段（仅软件类型）
│   ├── 许可证号
│   ├── 许可期限
│   └── 用户数量
│
├── 关联信息
│   ├── 购买发票（文档）
│   ├── 相关交易
│   └── 贷款（如有）
│
└── 状态
    ├── ○ 使用中
    ├── ○ 已出售
    └── ○ 已报废
```

### 资产列表视图

```
资产管理
├── 顶部统计卡片
│   ├── 总资产价值：€125,450
│   ├── 年度折旧：€8,320
│   ├── 累计折旧：€32,100
│   └── 剩余价值：€93,350
│
├── 筛选和分类
│   ├── 按类型
│   │   ├── 全部 (15)
│   │   ├── 🏠 不动产 (2)
│   │   ├── 💻 办公设备 (8)
│   │   ├── 🚗 车辆 (1)
│   │   ├── ⚙️ 机器设备 (3)
│   │   └── 💿 软件 (1)
│   ├── 按状态
│   │   ├── 使用中
│   │   ├── 已出售
│   │   └── 已报废
│   └── 搜索
│
└── 资产卡片列表
    ├── 🏠 出租房产 - Thenneberg 51
    │   ├── 购买价格：€85,000
    │   ├── 年折旧：€1,275 (1.5%)
    │   ├── 累计折旧：€5,100
    │   ├── 剩余价值：€79,900
    │   ├── 使用年限：4年 / 67年
    │   └── [查看详情] [编辑] [出售]
    │
    ├── 💻 MacBook Pro 2023
    │   ├── 购买价格：€2,500
    │   ├── 年折旧：€833 (33.33%)
    │   ├── 累计折旧：€1,666
    │   ├── 剩余价值：€834
    │   ├── 使用年限：2年 / 3年
    │   └── [查看详情] [编辑] [报废]
    │
    └── 🚗 商用车 - VW Transporter
        ├── 购买价格：€28,000
        ├── 年折旧：€3,500 (12.5%)
        ├── 累计折旧：€7,000
        ├── 剩余价值：€21,000
        ├── 使用年限：2年 / 8年
        ├── 业务使用：80%
        └── [查看详情] [编辑] [出售]
```

### 资产详情页面

```
资产详情 - MacBook Pro 2023
├── 基本信息卡片
│   ├── 类型：办公设备 > 电脑和笔记本
│   ├── 购买日期：2023-01-15
│   ├── 购买价格：€2,500
│   ├── 供应商：Apple Store
│   └── 状态：使用中 ✓
│
├── 折旧信息卡片
│   ├── 折旧方法：直线折旧
│   ├── 折旧年限：3年
│   ├── 年折旧率：33.33%
│   ├── 业务使用比例：100%
│   ├── 年度折旧：€833.33
│   ├── 累计折旧：€1,666.67
│   ├── 剩余价值：€833.33
│   └── 完全折旧日期：2026-01-15
│
├── 折旧时间线
│   ├── 2023 | €833.33 | 剩余 €1,666.67
│   ├── 2024 | €833.33 | 剩余 €833.33
│   └── 2025 | €833.33 | 剩余 €0.00
│
├── 关联文档
│   └── 📄 购买发票.pdf
│
├── 关联交易
│   └── 2023-01-15 | 购买 MacBook Pro | -€2,500
│
└── 操作按钮
    ├── [编辑资产]
    ├── [标记为已出售]
    ├── [标记为已报废]
    └── [生成折旧报告]
```

## 智能功能

### 1. OCR自动识别资产类型

```python
# 识别购买发票
if "MacBook" in text or "laptop" in text:
    asset_type = "办公设备"
    sub_category = "电脑和笔记本"
    suggested_depreciation_years = 3
    
elif "车辆" in text or "KFZ" in text:
    asset_type = "车辆"
    sub_category = "商用车"
    suggested_depreciation_years = 8
    
elif "房产" in text or "Immobilie" in text:
    asset_type = "不动产"
    sub_category = "出租房产"
    suggested_depreciation_rate = 1.5  # %
```

### 2. 自动折旧计算

```python
# 每月自动计算折旧
def calculate_monthly_depreciation(asset):
    if asset.depreciation_method == "straight_line":
        annual_depreciation = asset.purchase_price / asset.useful_life_years
        monthly_depreciation = annual_depreciation / 12
        
        # 考虑业务使用比例
        business_depreciation = monthly_depreciation * (asset.business_use_percentage / 100)
        
        return business_depreciation
```

### 3. 折旧提醒

```
提醒：
- MacBook Pro 将在2025年完全折旧
- 商用车已使用2年，建议检查维护记录
- 出租房产本月折旧：€106.25
```

## 数据库设计

### Assets 表（新建或重命名 properties）

```sql
CREATE TABLE assets (
    id UUID PRIMARY KEY,
    user_id INT NOT NULL,
    
    -- 基本信息
    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,  -- real_estate, office_equipment, vehicle, machinery, software, intangible, small_asset
    sub_category VARCHAR(100),
    description TEXT,
    
    -- 购买信息
    purchase_date DATE NOT NULL,
    purchase_price DECIMAL(12,2) NOT NULL,
    vat_amount DECIMAL(12,2),
    supplier VARCHAR(255),
    
    -- 折旧设置
    depreciation_method VARCHAR(50) DEFAULT 'straight_line',  -- straight_line, accelerated, immediate
    depreciation_rate DECIMAL(5,2),  -- 百分比
    useful_life_years INT,
    salvage_value DECIMAL(12,2) DEFAULT 0,
    business_use_percentage DECIMAL(5,2) DEFAULT 100,
    
    -- 不动产特殊字段
    address TEXT,
    building_value DECIMAL(12,2),
    land_value DECIMAL(12,2),
    construction_year INT,
    rental_percentage DECIMAL(5,2),
    
    -- 车辆特殊字段
    license_plate VARCHAR(50),
    vehicle_make_model VARCHAR(255),
    mileage INT,
    private_use_percentage DECIMAL(5,2),
    
    -- 软件特殊字段
    license_number VARCHAR(255),
    license_expiry_date DATE,
    number_of_users INT,
    
    -- 计算字段
    accumulated_depreciation DECIMAL(12,2) DEFAULT 0,
    current_value DECIMAL(12,2),
    last_depreciation_date DATE,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',  -- active, sold, disposed
    sale_date DATE,
    sale_price DECIMAL(12,2),
    
    -- 关联
    document_id INT,
    loan_id INT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 迁移策略

### 从 properties 到 assets

```sql
-- 1. 重命名表
ALTER TABLE properties RENAME TO assets;

-- 2. 添加新字段
ALTER TABLE assets ADD COLUMN asset_type VARCHAR(50) DEFAULT 'real_estate';
ALTER TABLE assets ADD COLUMN sub_category VARCHAR(100) DEFAULT 'rental_property';
-- ... 其他新字段

-- 3. 更新现有数据
UPDATE assets SET 
    asset_type = 'real_estate',
    sub_category = 'rental_property',
    name = CONCAT(street, ', ', city),
    purchase_price = purchase_price,
    depreciation_rate = depreciation_rate,
    building_value = building_value,
    land_value = land_value;
```

## 用户界面改进

### 导航菜单
```
旧：🏠 房产
新：💼 资产
```

### 快捷操作面板
```
旧：🏠 管理房产
新：💼 管理资产
    - 查看所有资产
    - 添加新资产
    - 折旧报告
```

### 仪表板统计
```
资产概览
├── 总资产价值：€125,450
├── 本年度折旧：€8,320
├── 不动产：2项 | €85,000
├── 办公设备：8项 | €12,500
├── 车辆：1项 | €28,000
└── 其他：4项 | €5,950
```

## 优势总结

### 用户角度
✅ 管理所有可折旧资产，不只是房产
✅ 自动计算折旧，减少手动工作
✅ 清晰的资产分类和追踪
✅ 符合奥地利税法要求

### 税务角度
✅ 完整的折旧记录
✅ 准确的税务抵扣计算
✅ 符合AfA规定
✅ 便于年度报税

### 业务角度
✅ 资产全生命周期管理
✅ 投资回报分析
✅ 资产价值追踪
✅ 更专业的财务管理

## 实施建议

### 阶段1：数据模型扩展
1. 创建新的 Asset 模型
2. 保留 Property 作为兼容
3. 添加资产类型枚举

### 阶段2：UI改造
1. 重命名"房产"为"资产"
2. 添加资产类型选择
3. 动态表单字段

### 阶段3：功能增强
1. 自动折旧计算
2. OCR资产识别
3. 折旧报告生成

### 阶段4：数据迁移
1. 迁移现有房产数据
2. 验证数据完整性
3. 更新文档

要开始实施吗？
