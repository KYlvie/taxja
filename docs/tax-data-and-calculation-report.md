# Taxja 税务数据与计算逻辑完整报告

> 本文档完整记录 Taxja 系统中存储的所有税务数据（按年份）以及所有税务计算逻辑。
> 数据来源：`backend/app/models/tax_configuration.py` 中的 `get_20XX_tax_config()` 函数。
> 最后更新：2026-03-16

---

## 目录

1. [数据库税务配置模型](#1-数据库税务配置模型)
2. [所得税税率档次对比表 (2022–2026)](#2-所得税税率档次对比表-20222026)
3. [免税额与关键阈值对比表](#3-免税额与关键阈值对比表)
4. [增值税 (USt) 配置对比表](#4-增值税-ust-配置对比表)
5. [SVS 社保配置对比表](#5-svs-社保配置对比表)
6. [扣除项配置对比表](#6-扣除项配置对比表)
7. [所得税计算逻辑 (Einkommensteuer)](#7-所得税计算逻辑-einkommensteuer)
8. [增值税计算逻辑 (Umsatzsteuer)](#8-增值税计算逻辑-umsatzsteuer)
9. [SVS 社保计算逻辑](#9-svs-社保计算逻辑)
10. [KESt 资本利得税计算逻辑](#10-kest-资本利得税计算逻辑)
11. [ImmoESt 房产利得税计算逻辑](#11-immoest-房产利得税计算逻辑)
12. [扣除项计算逻辑 (Absetzbeträge & Werbungskosten)](#12-扣除项计算逻辑)
13. [自雇人士专项计算逻辑](#13-自雇人士专项计算逻辑)
14. [AfA 折旧计算逻辑](#14-afa-折旧计算逻辑)
15. [员工退税计算逻辑 (Arbeitnehmerveranlagung)](#15-员工退税计算逻辑)
16. [亏损结转逻辑 (Verlustvortrag)](#16-亏损结转逻辑)
17. [税务计算引擎总调度](#17-税务计算引擎总调度)
18. [源文件索引](#18-源文件索引)

---

## 1. 数据库税务配置模型

**模型**: `TaxConfiguration` (`backend/app/models/tax_configuration.py`)
**表名**: `tax_configurations`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 主键 |
| `tax_year` | Integer UNIQUE | 税务年度 |
| `tax_brackets` | JSON | 累进税率档次数组 |
| `exemption_amount` | Numeric(12,2) | 免税额 (Freibetrag) |
| `vat_rates` | JSON | 增值税配置 |
| `svs_rates` | JSON | SVS 社保配置 |
| `deduction_config` | JSON | 扣除项配置 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

**数据播种**: `backend/app/db/seed_tax_config.py` → 调用 `get_2022..2026_tax_config()` 写入数据库。

---

## 2. 所得税税率档次对比表 (2022–2026)

奥地利采用 7 档累进税率，自 2023 年起每年按冷进程 (Kalte Progression) 调整档次边界。

### 2022 年

| 档次 | 收入区间 (€) | 税率 |
|------|-------------|------|
| 1 | 0 – 11,000 | 0% |
| 2 | 11,000 – 18,000 | 20% |
| 3 | 18,000 – 31,000 | 32.5% |
| 4 | 31,000 – 60,000 | 42% |
| 5 | 60,000 – 90,000 | 48% |
| 6 | 90,000 – 1,000,000 | 50% |
| 7 | 1,000,000+ | 55% |

> 备注：2022 年第二档从 35% 降至 20%（生态社会税改）；第三档 32.5%（过渡年）。

### 2023 年

| 档次 | 收入区间 (€) | 税率 |
|------|-------------|------|
| 1 | 0 – 11,693 | 0% |
| 2 | 11,693 – 19,134 | 20% |
| 3 | 19,134 – 32,075 | 30% |
| 4 | 32,075 – 62,080 | 41% |
| 5 | 62,080 – 93,120 | 48% |
| 6 | 93,120 – 1,000,000 | 50% |
| 7 | 1,000,000+ | 55% |

> 备注：首次冷进程调整。通胀率 5.2%，前两档上调 6.3%，其余 3.47%。第三档税率降至 30%，第四档降至 41%。

### 2024 年

| 档次 | 收入区间 (€) | 税率 |
|------|-------------|------|
| 1 | 0 – 12,816 | 0% |
| 2 | 12,816 – 20,818 | 20% |
| 3 | 20,818 – 34,513 | 30% |
| 4 | 34,513 – 66,612 | 40% |
| 5 | 66,612 – 99,266 | 48% |
| 6 | 99,266 – 1,000,000 | 50% |
| 7 | 1,000,000+ | 55% |

> 备注：通胀率 9.9%。第四档税率从 41% 降至 40%（此后稳定）。

### 2025 年

| 档次 | 收入区间 (€) | 税率 |
|------|-------------|------|
| 1 | 0 – 13,308 | 0% |
| 2 | 13,308 – 21,617 | 20% |
| 3 | 21,617 – 35,836 | 30% |
| 4 | 35,836 – 69,166 | 40% |
| 5 | 69,166 – 103,072 | 48% |
| 6 | 103,072 – 1,000,000 | 50% |
| 7 | 1,000,000+ | 55% |

> 备注：通胀率 5.0%，档次按 3.8333% 调整。

### 2026 年

| 档次 | 收入区间 (€) | 税率 |
|------|-------------|------|
| 1 | 0 – 13,539 | 0% |
| 2 | 13,539 – 21,992 | 20% |
| 3 | 21,992 – 36,458 | 30% |
| 4 | 36,458 – 70,365 | 40% |
| 5 | 70,365 – 104,859 | 48% |
| 6 | 104,859 – 1,000,000 | 50% |
| 7 | 1,000,000+ | 55% |

> 来源：USP 2026 官方税率表。



---

## 3. 免税额与关键阈值对比表

| 年份 | 免税额 (€) | 小企业阈值 (€) | 容差阈值 (€) |
|------|-----------|---------------|-------------|
| 2022 | 11,000.00 | 35,000 (净额) | 38,500 |
| 2023 | 11,693.00 | 35,000 (净额) | 38,500 |
| 2024 | 12,816.00 | 35,000 (净额) | 38,500 |
| 2025 | 13,308.00 | 55,000 (毛额) | 60,500 |
| 2026 | 13,539.00 | 55,000 (毛额) | 60,500 |

> 备注：2025 年起 Kleinunternehmerregelung 阈值从 €35,000 净额提高到 €55,000 毛额。

---

## 4. 增值税 (USt) 配置对比表

| 年份 | 标准税率 | 住宅租赁税率 | 小企业阈值 (€) | 容差阈值 (€) |
|------|---------|-------------|---------------|-------------|
| 2022 | 20% | 10% | 35,000 | 38,500 |
| 2023 | 20% | 10% | 35,000 | 38,500 |
| 2024 | 20% | 10% | 35,000 | 38,500 |
| 2025 | 20% | 10% | 55,000 | 60,500 |
| 2026 | 20% | 10% | 55,000 | 60,500 |

**增值税税率类别**:
- **标准税率 20%**: 大多数商品和服务
- **优惠税率 10%**: 住宅租赁、住宿、食品、书籍、公共交通
- **优惠税率 13%**: 活体动植物、艺术活动、电影/马戏、体育赛事门票

---

## 5. SVS 社保配置对比表

SVS (Sozialversicherungsanstalt der Selbständigen) 适用于自雇人士。

| 参数 | 2022 | 2023 | 2024 | 2025 | 2026 |
|------|------|------|------|------|------|
| 养老保险 (Pension) | 18.5% | 18.5% | 18.5% | 18.5% | 18.5% |
| 医疗保险 (Health) | 6.8% | 6.8% | 6.8% | 6.8% | 6.8% |
| 意外保险 (固定/月) | €10.09 | €10.42 | €10.97 | €11.35 | €12.95 |
| 补充养老 (Supplementary) | 1.53% | 1.53% | 1.53% | 1.53% | 1.53% |
| GSVG 最低基数/月 | €485.85 | €485.85 | €500.91 | €500.91 | €551.10 |
| GSVG 最低年收入 | €5,830.20 | €5,830.20 | €6,010.92 | €6,010.92 | €6,613.20 |
| 新自雇最低/月 | €141.79 | €141.79 | €146.18 | €146.18 | €160.81 |
| 最高基数/月 | €6,615 | €6,615 | €6,825 | €7,525 | €8,085 |

> 备注：百分比费率稳定（GSVG §§27-27a），固定金额每年按 Aufwertungszahl 调整。

---

## 6. 扣除项配置对比表

### 6.1 常用年度税务参数

> 注意：本表仅列出各项参数的年度金额，不代表税法分类。具体分类见下方说明。

| 参数 | 类型 | 2022 | 2023 | 2024 | 2025 | 2026 |
|------|------|------|------|------|------|------|
| 居家办公 (Telearbeitspauschale) | 收入扣除 | €300 | €300 | €300 | €300 | €300 |
| 子女扣除/月 (Kinderabsetzbetrag) | 参考值* | €58.40 | €61.80 | €67.80 | €70.90 | €70.90 |
| 工资成本定额 (Werbungskostenpauschale) | 收入扣除 | €132 | €132 | €132 | €132 | €132 |
| 特殊支出定额 (Sonderausgabenpauschale) | 收入扣除 | €60 | €60 | €60 | €60 | €60 |
| 交通抵扣 (Verkehrsabsetzbetrag) | 税额抵扣 | €400 | €421 | €463 | €487 | €496 |
| 单亲/唯一收入者 (AEAB/AVAB 1孩) | 税额抵扣 | €494 | €520 | €572 | €601 | €612 |

> *Kinderabsetzbetrag 通过 Familienbeihilfe 自动发放，不进入税务申报的 income_deductions 或 tax_credits。

### 6.2 家庭奖金 (Familienbonus Plus)

| 年份 | 18岁以下/年 | 18-24岁/年 |
|------|------------|-----------|
| 2022 | €2,000.16 | €650.16 |
| 2023 | €2,000.16 | €650.16 |
| 2024 | €2,000.16 | €700.08 |
| 2025 | €2,000.16 | €700.08 |
| 2026 | €2,000.16 | €700.08 |

### 6.3 唯一收入者/单亲抵扣 (AVAB/AEAB)

| 年份 | 1孩 | 2孩 | 每增加1孩 |
|------|-----|-----|----------|
| 2022 | €494 | €669 | €220 |
| 2023 | €520 | €704 | €232 |
| 2024 | €572 | €774 | €255 |
| 2025 | €601 | €813 | €268 |
| 2026 | €612 | €828 | €273 |

### 6.4 交通抵扣附加 (Zuschlag zum Verkehrsabsetzbetrag)

低收入员工可获得额外交通抵扣，在收入区间内线性递减。

| 年份 | 全额 | 收入下限 | 收入上限 |
|------|------|---------|---------|
| 2022 | €684 | €15,500 | €24,500 |
| 2023 | €684 | €16,832 | €25,774 |
| 2024 | €752 | €18,499 | €28,326 |
| 2025 | €790 | €19,424 | €29,743 |
| 2026 | €804 | €19,761 | €30,259 |

### 6.5 退休人员抵扣 (Pensionistenabsetzbetrag)

| 年份 | 普通全额 | 收入下限 | 收入上限 | 增强全额 | 增强收入下限 |
|------|---------|---------|---------|---------|-------------|
| 2022 | €868 | €17,000 | €25,000 | €1,214 | €19,930 |
| 2023 | €868 | €18,410 | €26,826 | €1,278 | €20,967 |
| 2024 | €954 | €20,233 | €29,482 | €1,405 | €23,043 |
| 2025 | €1,002 | €21,245 | €30,957 | €1,476 | €24,196 |
| 2026 | €1,020 | €21,614 | €31,494 | €1,502 | €24,616 |

### 6.6 通勤补贴 (Pendlerpauschale)

**小通勤补贴 (Kleines Pendlerpauschale)** — 有公共交通可用:

| 距离 | 月额 |
|------|------|
| 20-40km | €58 |
| 40-60km | €113 |
| 60km+ | €168 |

**大通勤补贴 (Großes Pendlerpauschale)** — 无公共交通:

| 距离 | 月额 |
|------|------|
| 2-20km | €31 |
| 20-40km | €123 |
| 40-60km | €214 |
| 60km+ | €306 |

**Pendlereuro**: €2-6/km/年（2026年为€6/km）

### 6.7 子女多付款 (Kindermehrbetrag)

| 年份 | 金额 |
|------|------|
| 2022 | €550 |
| 2023 | €550 |
| 2024 | €700 |
| 2025 | €700 |
| 2026 | €700 |

### 6.8 赡养费抵扣 (Unterhaltsabsetzbetrag)

| 年份 | 第1孩/月 | 第2孩/月 | 第3+孩/月 |
|------|---------|---------|----------|
| 2022 | €29.20 | €43.80 | €58.40 |
| 2023 | €31.00 | €47.00 | €62.00 |
| 2024 | €35.00 | €52.00 | €69.00 |
| 2025 | €37.00 | €55.00 | €73.00 |
| 2026 | €38.00 | €56.00 | €75.00 |



---

## 7. 所得税计算逻辑 (Einkommensteuer)

**源文件**: `backend/app/services/income_tax_calculator.py`

### 7.1 核心类

```
IncomeTaxCalculator(tax_config: Dict)
```

从 `TaxConfiguration` 加载 `tax_brackets` 和 `exemption_amount`。

### 7.2 累进税计算

```python
calculate_progressive_tax(taxable_income, tax_year) → IncomeTaxResult
```

**算法**:
1. 遍历每个税率档次
2. 计算该档次内的应税金额 = `min(剩余收入, 档次宽度)`
3. 该档税额 = 应税金额 × 税率
4. 累加总税额，减少剩余收入
5. 有效税率 = 总税额 / 应税收入

**税率归一化**: 如果 `rate > 1`，自动除以 100（兼容百分比和小数两种格式）。

### 7.3 免税额应用

```python
apply_exemption(gross_income) → taxable_income
```

`应税收入 = max(0, 毛收入 - 免税额)`

### 7.4 亏损结转集成

```python
calculate_tax_with_loss_carryforward(gross_income, tax_year, loss_applied, remaining_loss)
```

流程: 毛收入 → 减免税额 → 减亏损结转 → 累进税计算

### 7.5 返回结构

```python
@dataclass
class IncomeTaxResult:
    total_tax: Decimal           # 总税额
    breakdown: List[TaxBracketResult]  # 每档明细
    effective_rate: Decimal       # 有效税率
    taxable_income: Decimal       # 应税收入
    loss_carryforward_applied: Optional[Decimal]
    remaining_loss_balance: Optional[Decimal]
```

---

## 8. 增值税计算逻辑 (Umsatzsteuer)

**源文件**: `backend/app/services/vat_calculator.py`

### 8.1 核心类

```
VATCalculator(vat_config: Optional[Dict])
```

### 8.2 税率确定

```python
determine_vat_rate(category, description, property_type, vat_opted_in) → (rate, VATRateType)
```

**优先级**:
1. 房产类型：住宅租赁 → 10%（需 opt-in），商业 → 20%
2. 类别匹配：`rental/groceries/accommodation` → 10%，`art/culture/sports_event` → 13%
3. 描述关键词匹配：德语/英语关键词 → 10% 或 13%
4. 默认：标准 20%

**10% 关键词**: miete, wohnung, lebensmittel, buch, zeitung, unterkunft, airbnb, nahverkehr, oebb...
**13% 关键词**: kunst, film, kino, sport, theater, blumen, brennholz, tier...

### 8.3 增值税计算

```python
calculate_vat_liability(gross_turnover, transactions, property_type) → VATResult
```

**流程**:
1. 检查小企业豁免 (Kleinunternehmerregelung)
   - 营业额 ≤ 阈值 → 豁免
   - 营业额 ≤ 容差阈值 → 本年豁免，下年取消
   - 营业额 > 容差阈值 → 需缴纳增值税
2. 逐笔交易计算：`VAT = gross × rate / (1 + rate)`
3. 收入交易 → 销项税 (Output VAT)
4. 支出交易 → 进项税 (Input VAT)
5. 净增值税 = 销项税 - 进项税

### 8.4 小企业豁免规则

```python
check_small_business_exemption(gross_turnover) → bool
apply_tolerance_rule(gross_turnover) → (applies, warning)
```

- 2025 年起：阈值 €55,000 毛额，容差 €60,500（10% 超额，5年内仅一次）
- 2024 年及之前：阈值 €35,000 净额，容差 €38,500

---

## 9. SVS 社保计算逻辑

**源文件**: `backend/app/services/svs_calculator.py`

### 9.1 核心类

```
SVSCalculator(svs_config: Optional[Dict])
```

### 9.2 用户类型

| 类型 | 说明 |
|------|------|
| `EMPLOYEE` | 雇员（雇主代扣，本计算器返回 0） |
| `GSVG` | 商业自雇 (Gewerbetreibende) |
| `NEUE_SELBSTAENDIGE` | 新自雇/自由职业者 |

### 9.3 GSVG 计算

```python
_calculate_gsvg(monthly_income, annual_income) → SVSResult
```

**规则**:
1. 年收入 < 最低年收入 (€6,613.20 for 2026) → 无需缴纳
2. 缴费基数 = `max(月收入, 最低基数)` 且 `min(缴费基数, 最高基数)`
3. 养老 = 基数 × 18.5%
4. 医疗 = 基数 × 6.8%
5. 意外 = 固定金额/月 (€12.95 for 2026)
6. 补充养老 = 基数 × 1.53%
7. 月总额 = 养老 + 医疗 + 意外 + 补充养老
8. 年总额 = 月总额 × 12

### 9.4 新自雇计算

```python
_calculate_neue_selbstaendige(monthly_income, annual_income) → SVSResult
```

**规则**:
1. 缴费基数 = `min(月收入, 最高基数)`（无最低收入要求）
2. 同 GSVG 计算各项
3. 如果月总额 < 最低缴费 (€160.81 for 2026) → 适用最低缴费

### 9.5 季度预缴

```python
calculate_quarterly_prepayment(annual_income, user_type) → Decimal
```

季度预缴 = 年总额 / 4

---

## 10. KESt 资本利得税计算逻辑

**源文件**: `backend/app/services/kest_calculator.py`

### 10.1 税率

| 收入类型 | 税率 | 说明 |
|---------|------|------|
| `BANK_INTEREST` | 25% | 银行存款利息 |
| `DIVIDENDS` | 27.5% | 股息 |
| `SECURITIES_GAINS` | 27.5% | 股票/基金/ETF 收益 |
| `CRYPTO` | 27.5% | 加密货币（2021.03.01 起） |
| `BOND_INTEREST` | 27.5% | 债券利息 |
| `FUND_DISTRIBUTIONS` | 27.5% | 基金分配 |
| `GMBH_SHARES` | 27.5% | GmbH 股份出售 |
| `OTHER` | 27.5% | 其他资本收入 |

> 备注：KESt 税率稳定，不受冷进程调整影响。

### 10.2 计算逻辑

```python
calculate_kest(items: List[Dict]) → KEStResult
```

**流程**:
1. 逐项计算：税额 = 毛额 × 适用税率
2. 已代扣 (withheld) 的项目记入已扣税额
3. 剩余应缴 = 总税额 - 已代扣税额
4. 净收入 = 总毛额 - 总税额

**返回结构**:
```python
@dataclass
class KEStResult:
    total_gross: Decimal          # 总毛额
    total_tax: Decimal            # 总税额
    total_already_withheld: Decimal  # 已代扣
    remaining_tax_due: Decimal    # 剩余应缴
    net_income: Decimal           # 净收入
    line_items: List[KEStLineItem]  # 逐项明细
```

---

## 11. ImmoESt 房产利得税计算逻辑

**源文件**: `backend/app/services/immoest_calculator.py`

### 11.1 基本税率

| 类型 | 税率 | 说明 |
|------|------|------|
| 标准 | 30% | 售价 - 购入价 - 改良费 - 出售费 = 收益 × 30% |
| 旧房产（2002.03.31前购入） | 14% | 售价 × 14%（未重新分区） |
| 旧房产（重新分区） | 18% | 售价 × 18%（60% × 30%） |
| 重新分区附加费 | 30% | 2025.07.01 起，2024.12.31 后重新分区的土地 |

### 11.2 免税类型

| 免税类型 | 条件 |
|---------|------|
| **Hauptwohnsitzbefreiung** | 主要住所：连续居住 ≥2 年，或过去 10 年中 ≥5 年 |
| **Herstellerbefreiung** | 自建房产且从未用于收入产生 |

### 11.3 计算逻辑

```python
calculate_immoest(sale_price, acquisition_cost, acquisition_date, ...) → ImmoEStResult
```

**流程**:
1. 检查免税 → 如适用，返回免税结果
2. 检查旧房产（购入日期 ≤ 2002.03.31）
   - 未重新分区：售价 × 14%
   - 已重新分区：售价 × 18%
3. 新房产：收益 = 售价 - 购入价 - 改良费 - 出售费
4. 税额 = 收益 × 30%
5. 重新分区附加费（如适用）= 收益 × 30%
6. 总税 = 税额 + 附加费



---

## 12. 扣除项计算逻辑

**源文件**: `backend/app/services/deduction_calculator.py`

### 12.1 核心类

```
DeductionCalculator(deduction_config: Optional[Dict])
```

### 12.2 通勤补贴 (Pendlerpauschale + Pendlereuro)

```python
calculate_commuting_allowance(distance_km, public_transport_available, working_days) → DeductionResult
```

**规则**:
1. 有公共交通 → 小通勤补贴 (Kleines)，最低 20km
2. 无公共交通 → 大通勤补贴 (Großes)，最低 2km
3. 根据距离查表获取月额
4. Pendlerpauschale 年额 = 月额 × 12 → **收入扣除项** (Werbungskosten/Freibetrag，减少应税收入)
5. Pendlereuro = 距离(km) × €6/年 (2026) → **税额抵扣项** (Absetzbetrag，直接减少税额)

> ⚠️ 重要区分：Pendlerpauschale 和 Pendlereuro 在税法上属于不同类别。
> - Pendlerpauschale 是 Freibetrag（减税基），归入 `income_deductions`
> - Pendlereuro 是 Absetzbetrag（减税额），归入 `tax_credits`
> - BMF 明确："Der Pendlereuro ist ein Absetzbetrag und reduziert somit direkt die Steuerlast。"
> - 代码中 `amount` 仅返回 Pendlerpauschale，Pendlereuro 存于 `breakdown['pendler_euro']` 供引擎单独处理

### 12.3 居家办公 (Telearbeitspauschale)

```python
calculate_home_office_deduction(telearbeit_days, employer_pauschale) → DeductionResult
```

**法定精确计算** (2025 年起, BMF 规则):
- €3.00/天，最多 100 天/年 → 年上限 €300
- 如雇主已支付免税 Telearbeitspauschale → 仅可扣除差额
- 精确公式：`deductible = max(0, min(days, 100) × 3 - employer_paid)`

**产品兼容策略**:
- 如历史记录缺少 `telearbeit_days`（值为 None），系统按兼容策略临时回退为固定 €300
- 这不是法理上的正常计算方式，仅用于旧数据迁移过渡
- `telearbeit_days = 0` 时明确返回 €0（用户显式声明无居家办公天数）

### 12.4 家庭扣除 — Kinderabsetzbetrag（仅供参考，不进入主税算）

```python
calculate_family_deductions(family_info) → DeductionResult
```

计算公式：月额 × 12 × 子女数

> ⚠️ **Informational / Reference Only**
> Kinderabsetzbetrag 与 Familienbeihilfe 关联，由税务局自动发放。
> 它**不进入** `income_deductions`（不减税基），也**不进入** `tax_credits`（不减税额）。
> 代码中仅存入 `breakdown['kinderabsetzbetrag_info']` 供前端展示参考，
> 不参与任何实际税额计算。BMF 明确将其与 Familienbeihilfe 挂钩，
> 而非作为普通 Werbungskosten 或 Absetzbetrag 处理。

### 12.5 家庭奖金 (Familienbonus Plus)

```python
calculate_familienbonus(family_info) → DeductionResult
```

- 18 岁以下：€2,000.16/年/孩
- 18-24 岁：€700.08/年/孩 (2024 年起)
- 这是 **Absetzbetrag**（直接从税额中扣除，非收入扣除）

### 12.6 唯一收入者抵扣 (AVAB/AEAB)

```python
calculate_alleinverdiener(family_info) → DeductionResult
```

- 条件：唯一收入者或单亲 + 至少 1 个孩子
- 1 孩 = 基础额，2 孩 = 2 孩额，3+ 孩 = 2 孩额 + 每增加 1 孩额 × (n-2)
- 这是 **Absetzbetrag**

### 12.7 交通抵扣附加 (Zuschlag zum Verkehrsabsetzbetrag)

```python
calculate_zuschlag_verkehrsabsetzbetrag(annual_income) → DeductionResult
```

- 收入 ≤ 下限 → 全额
- 收入 ≥ 上限 → €0
- 中间 → 线性递减：`全额 × (1 - (收入-下限)/(上限-下限))`

### 12.8 退休人员抵扣 (Pensionistenabsetzbetrag)

```python
calculate_pensionisten_absetzbetrag(pension_income, is_single) → DeductionResult
```

- 单身退休人员 → 增强额 (Erhöhter)
- 非单身 → 普通额
- 同样线性递减逻辑

### 12.9 特殊支出定额 (Sonderausgabenpauschale)

```python
calculate_sonderausgabenpauschale() → DeductionResult
```

固定 €60/年，自动适用于所有纳税人。

### 12.10 员工扣除

```python
calculate_employee_deductions(actual_werbungskosten) → DeductionResult
```

- 如实际工资成本 > €132 → 不适用定额
- 否则 → 适用 Werbungskostenpauschale €132
- Verkehrsabsetzbetrag 作为 Absetzbetrag 存入 breakdown

### 12.11 总扣除汇总

```python
calculate_total_deductions(...) → DeductionResult
```

**返回值说明**:
- `amount` = 收入扣除总额（减少应税收入）
- `breakdown` 中包含 Absetzbeträge（减少税额，由引擎单独处理）

**收入扣除项** (减少应税收入):
- Pendlerpauschale（通勤补贴基值，不含 Pendlereuro）
- Telearbeitspauschale（居家办公）
- Werbungskostenpauschale
- Sonderausgabenpauschale (€60)

**税额抵扣项** (Absetzbeträge，减少税额):
- Verkehrsabsetzbetrag
- Zuschlag zum Verkehrsabsetzbetrag
- Pendlereuro（通勤公里补贴，€6/km/年）
- Familienbonus Plus
- AVAB/AEAB（唯一收入者/单亲抵扣）
- Pensionistenabsetzbetrag

> ⚠️ 注意：Alleinerzieherabsetzbetrag (AEAB) 是 Absetzbetrag（税额抵扣），不是收入扣除项。
> BMF 明确将其归类为 §33 Abs 4 EStG 的 Absetzbetrag。

---

## 13. 自雇人士专项计算逻辑

**源文件**: `backend/app/services/self_employed_tax_service.py`

### 13.1 利润免税额 (Gewinnfreibetrag, §10 EStG)

```python
calculate_gewinnfreibetrag(profit, qualifying_investment, config) → GewinnfreibetragResult
```

#### 基础免税额 (Grundfreibetrag)

- 利润的 15%，最高 €4,950（= 15% × €33,000）
- 无需投资证明
- 自动适用

#### 投资免税额 (Investitionsbedingter Freibetrag)

利润超过 €33,000 的部分，按递减税率计算：

| 利润区间 | 税率 | 最大免税额 |
|---------|------|----------|
| €33,000 – €208,000 | 13% | €22,750 |
| €208,000 – €383,000 | 7% | €12,250 |
| €383,000 – €580,000 | 4.5% | €8,865 |
| €580,000+ | 0% | — |

- 需要购买合格固定资产或证券
- 实际免税额 = min(计算额, 实际投资额)
- 每人每年总上限：€46,400

### 13.2 基础定额扣除 (Basispauschalierung, §17 EStG)

```python
calculate_basispauschalierung(gross_turnover, profession_type, svs, ...) → BasispauschalierungResult
```

**规则**:
- 营业额上限：€220,000 (2022-2024) / €320,000 (2025) / €420,000 (2026)
- 一般行业：12% (2022-2024) / 13.5% (2025) / 15% (2026)
- 咨询/写作：6%（所有年份）
- 利润 = 营业额 - 定额费用 - SVS - 其他可扣除项
- 仍可扣除 Grundfreibetrag，但不可扣除投资免税额

### 13.3 小企业状态判定

```python
determine_kleinunternehmer_status(gross_turnover, has_input_vat, prev_exceeded, config) → KleinunternehmerStatus
```

**流程**:
1. 营业额 ≤ 阈值 → 豁免（如有大量进项税，建议自愿注册）
2. 阈值 < 营业额 ≤ 容差 且 上年未超 → 本年豁免，下年取消
3. 营业额 > 容差 → 需缴增值税
4. 营业额 > €100,000 → 月度 UVA；否则季度 UVA

### 13.4 费用方法对比

```python
compare_expense_methods(turnover, actual_expenses, profession, svs, investment, config) → ExpenseMethodComparison
```

对比 Basispauschalierung vs 实际费用追踪，推荐更节税的方法。

### 13.5 自雇配置按年变化

| 参数 | 2022 | 2023 | 2024 | 2025 | 2026 |
|------|------|------|------|------|------|
| 定额营业额上限 | €220,000 | €220,000 | €220,000 | €320,000 | €420,000 |
| 一般定额率 | 12% | 12% | 12% | 13.5% | 15% |
| 咨询定额率 | 6% | 6% | 6% | 6% | 6% |
| 小企业阈值 | €35,000 | €35,000 | €35,000 | €55,000 | €55,000 |
| 小企业容差 | €38,500 | €38,500 | €38,500 | €60,500 | €60,500 |
| Grundfreibetrag 率 | 15% | 15% | 15% | 15% | 15% |
| Grundfreibetrag 上限 | €4,950 | €4,950 | €4,950 | €4,950 | €4,950 |
| 总免税额上限 | €46,400 | €46,400 | €46,400 | €46,400 | €46,400 |

---

## 14. AfA 折旧计算逻辑

**源文件**: `backend/app/services/afa_calculator.py`

### 14.1 基础折旧率

| 建筑类型 | 年折旧率 | 法律依据 |
|---------|---------|---------|
| 住宅 (Wohngebäude) | 1.5% | §16 Abs 1 Z 8 / §8 Abs 1 EStG |
| 商业 (Betriebsgebäude) | 2.5% | §8 Abs 1 EStG |

> 备注：2016 年改革后，旧的 1915 年前/后区分不再适用。

### 14.2 加速折旧 (Beschleunigte AfA)

**一般加速折旧** (§8 Abs 1a EStG, KonStG 2020):
适用于 2020.06.30 后竣工的建筑。

| 年份 | 住宅有效率 | 商业有效率 |
|------|----------|----------|
| 第1年 | 4.5% (3×) | 7.5% (3×) |
| 第2年 | 3.0% (2×) | 5.0% (2×) |
| 第3年+ | 1.5% | 2.5% |

**生态标准扩展加速** (BMF erweiterte beschleunigte AfA):
适用于 2024-2026 年竣工且符合 klimaaktiv 标准的住宅建筑。

| 年份 | 有效率 |
|------|-------|
| 第1-3年 | 4.5% (3×) |
| 第4年+ | 1.5% |

### 14.3 计算逻辑

```python
calculate_annual_depreciation(property, year) → Decimal
```

**流程**:
1. 自住房产 → 不可折旧
2. 检查是否在该年拥有
3. 获取截至上年的累计折旧
4. 计算可折旧价值（考虑混合用途的出租比例）
5. 检查是否已完全折旧
6. 确定有效折旧率（含加速折旧）
7. 计算年折旧额
8. 按月份比例调整（部分年份）
9. 确保不超过建筑价值

### 14.4 累计折旧

```python
get_accumulated_depreciation(property_id, up_to_year) → Decimal
```

从购入年到指定年，逐年数学计算累计折旧（考虑加速折旧、部分年份、建筑价值上限）。

### 14.5 空置警告

无租金收入的出租房产会触发分级警告：
- ≤6 个月：信息级 — 记录出租努力
- 7-12 个月：警告级 — 税务局可能质疑出租意图
- >12 个月：错误级 — 折旧抵扣有风险，建议重新分类

---

## 15. 员工退税计算逻辑

**源文件**: `backend/app/services/employee_refund_calculator.py`

### 15.1 核心类

```
EmployeeRefundCalculator(tax_config, deduction_config)
```

### 15.2 退税计算

```python
calculate_refund(lohnzettel, family_info, user, ...) → RefundResult
```

**Arbeitnehmerveranlagung 流程**:

**Step 1: 收入扣除 (Income Deductions → 减少应税收入)**
- 1a. Werbungskostenpauschale €132（或实际 Werbungskosten，取较高者）
- 1b. Pendlerpauschale 基值（月额 × 12，仅 Freibetrag 部分）
- 1c. Telearbeitspauschale（€3/天 × 天数 - 雇主已付）
- 1d. 社保缴费 (SVS/SV-Beiträge)
- 1e. Sonderausgabenpauschale €60（§18 Abs 2 EStG，减收入项）
- 1f. 其他额外收入扣除

**Step 2: 累进税计算**
- 应税收入 = 毛收入 - Step 1 总扣除
- 按年度税率档次计算 tax_before_credits

**Step 3: 税额抵扣 (Absetzbeträge → 直接减少税额)**
- 3a. Verkehrsabsetzbetrag（所有雇员）
- 3b. Zuschlag zum Verkehrsabsetzbetrag（低收入附加）
- 3c. Pendlereuro（距离 × €6/年，Absetzbetrag）
- 3d. Familienbonus Plus
- 3e. AVAB/AEAB（唯一收入者/单亲抵扣）

**Step 4: 最终税额**
- actual_tax = max(0, tax_before_credits - total_tax_credits)

**Step 5: 退税/补缴**
- refund = withheld_tax - actual_tax
- 正数 = 退税，负数 = 补缴

### 15.3 基于交易的退税估算

```python
calculate_refund_from_transactions(transactions, user, family_info) → RefundResult
```

从交易记录自动汇总收入和支出，计算退税。

### 15.4 退税潜力估算

```python
estimate_refund_potential(annual_income, ...) → Dict
```

快速估算退税潜力，无需完整 Lohnzettel。

---

## 16. 亏损结转逻辑

**源文件**: `backend/app/services/loss_carryforward_service.py`

### 16.1 核心功能

- 多年亏损跟踪
- FIFO（先进先出）应用顺序
- 亏损记录、应用、余额查询

### 16.2 规则

- 自雇/企业亏损可无限期结转
- 每年最多抵扣当年利润的 75%（Verlustvortragsgrenze）
- 按 FIFO 顺序消耗最早的亏损

---

## 17. 税务计算引擎总调度

**源文件**: `backend/app/services/tax_calculation_engine.py`

### 17.1 统一调度

税务计算引擎是所有计算器的统一入口，协调以下模块：

```
TaxCalculationEngine
├── IncomeTaxCalculator      # 所得税
├── VATCalculator            # 增值税
├── SVSCalculator            # 社保
├── DeductionCalculator      # 扣除项
├── AfACalculator            # 折旧
├── KEStCalculator           # 资本利得税
├── ImmoEStCalculator        # 房产利得税
├── SelfEmployedTaxService   # 自雇专项
├── EmployeeRefundCalculator # 员工退税
└── LossCarryforwardService  # 亏损结转
```

### 17.2 计算流程

1. 加载年度 TaxConfiguration
2. 初始化各计算器（传入年度配置）
3. 根据用户类型（雇员/自雇/房东）选择计算路径
4. 汇总所有税种结果
5. 生成税务报告

---

## 18. 源文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/models/tax_configuration.py` | 税务配置模型 + 2022-2026 年度数据 |
| `backend/app/db/seed_tax_config.py` | 数据库播种脚本 |
| `backend/app/services/income_tax_calculator.py` | 所得税累进计算 |
| `backend/app/services/vat_calculator.py` | 增值税计算 |
| `backend/app/services/svs_calculator.py` | SVS 社保计算 |
| `backend/app/services/kest_calculator.py` | KESt 资本利得税 |
| `backend/app/services/immoest_calculator.py` | ImmoESt 房产利得税 |
| `backend/app/services/deduction_calculator.py` | 扣除项计算 |
| `backend/app/services/self_employed_tax_service.py` | 自雇专项 (Gewinnfreibetrag, Basispauschalierung) |
| `backend/app/services/afa_calculator.py` | AfA 折旧计算 |
| `backend/app/services/employee_refund_calculator.py` | 员工退税 (Arbeitnehmerveranlagung) |
| `backend/app/services/loss_carryforward_service.py` | 亏损结转 |
| `backend/app/services/tax_calculation_engine.py` | 税务计算引擎总调度 |

