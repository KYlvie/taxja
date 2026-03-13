# 需求文档：Saldenliste 报表

## 简介

为 Taxja 系统新增两种奥地利标准会计报表：**Saldenliste mit Vorjahresvergleich（余额表含上年对比）** 和 **Periodensaldenliste（期间余额表）**。两种报表均适用于所有用户类型（个人用户和 GmbH 用户），报表框架结构统一，仅科目内容因用户类型而异。个人用户（employee、self_employed、landlord、mixed）使用 EA-Rechnung 科目体系（主要为 Kontenklasse 4 收入 + 7 支出），GmbH 用户使用完整 Kontenklassen 0-9（资产、负债、权益、收入、支出）。

## 术语表

- **Saldenliste_Service**: 后端服务模块，负责生成 Saldenliste mit VJ 和 Periodensaldenliste 报表数据
- **Report_API**: 后端 API 端点，接收报表请求并返回报表数据
- **Saldenliste_Component**: 前端 React 组件，负责渲染 Saldenliste mit VJ 报表
- **Periodensaldenliste_Component**: 前端 React 组件，负责渲染 Periodensaldenliste 报表
- **Report_Service_Client**: 前端 API 客户端服务，负责与后端报表端点通信
- **ReportsPage**: 前端报表页面，包含标签页导航
- **Kontenklasse**: 奥地利标准科目分类（0-9），用于对科目进行分组
- **Saldo**: 科目余额，即某一期间内该科目的累计金额
- **Vorjahr (VJ)**: 上年同期，用于对比分析
- **Abweichung**: 偏差，当期与上年同期之间的差异（绝对值和百分比）
- **Aktiva**: 资产类科目合计
- **Passiva**: 负债及权益类科目合计
- **Ertrag**: 收入类科目合计
- **Aufwand**: 支出类科目合计
- **Gewinn/Verlust**: 利润或亏损（Ertrag - Aufwand）
- **EA_User**: 个人用户类型（employee、self_employed、landlord、mixed），使用 EA-Rechnung 科目体系
- **GmbH_User**: GmbH 公司用户类型，使用完整 Kontenklassen 0-9 科目体系

## 需求

### 需求 1：按用户类型确定科目体系

**用户故事：** 作为用户，我希望系统根据我的用户类型自动选择正确的科目体系，以便报表内容与我的会计需求匹配。

#### 验收标准

1. WHILE 当前用户的 user_type 为 employee、self_employed、landlord 或 mixed 时，THE Saldenliste_Service SHALL 使用 EA-Rechnung 科目体系（Kontenklasse 4 收入 + Kontenklasse 7 支出）生成报表数据
2. WHILE 当前用户的 user_type 为 gmbh 时，THE Saldenliste_Service SHALL 使用完整 Kontenklassen 0-9 科目体系（0 资产、1 负债、2 权益、3 存货、4 收入、5 材料费用、6 人工费用、7 其他经营费用、8 财务收支、9 结转）生成报表数据
3. THE Saldenliste_Service SHALL 将每笔交易根据其 income_category 或 expense_category 映射到对应的 Kontenklasse 和科目编号

### 需求 2：Saldenliste mit Vorjahresvergleich（余额表含上年对比）

**用户故事：** 作为用户，我希望查看当期各科目累计余额并与上年同期对比，以便分析财务变化趋势。

#### 验收标准

1. WHEN 用户请求生成 Saldenliste mit VJ 报表时，THE Report_API SHALL 接受 tax_year 和 language 参数并返回结构化报表数据
2. THE Saldenliste_Service SHALL 计算指定 tax_year 内每个科目的累计 Saldo（余额）
3. THE Saldenliste_Service SHALL 计算上年（tax_year - 1）同期每个科目的累计 Saldo
4. THE Saldenliste_Service SHALL 计算每个科目的 Abweichung（偏差），包含绝对值（当期 Saldo - 上年 Saldo）和百分比（偏差 / 上年 Saldo × 100）
5. IF 上年 Saldo 为零，THEN THE Saldenliste_Service SHALL 将百分比偏差设为 null 而非执行除零运算
6. THE Saldenliste_Service SHALL 按 Kontenklasse（0-9）对科目进行分组
7. THE Saldenliste_Service SHALL 为每个 Kontenklasse 计算小计（当期小计、上年小计、偏差小计）
8. THE Saldenliste_Service SHALL 在报表底部生成汇总行：Aktiva 合计、Passiva 合计、Ertrag 合计、Aufwand 合计、Gewinn/Verlust（Ertrag - Aufwand）

### 需求 3：Periodensaldenliste（期间余额表）

**用户故事：** 作为用户，我希望查看各科目按月份分列的金额，以便进行月度趋势分析。

#### 验收标准

1. WHEN 用户请求生成 Periodensaldenliste 报表时，THE Report_API SHALL 接受 tax_year 和 language 参数并返回结构化报表数据
2. THE Saldenliste_Service SHALL 计算指定 tax_year 内每个科目在每个月份（1-12月）的金额
3. THE Saldenliste_Service SHALL 为每个科目计算年度合计（Gesamt），即 12 个月金额之和
4. THE Saldenliste_Service SHALL 按 Kontenklasse 对科目进行分组
5. THE Saldenliste_Service SHALL 为每个 Kontenklasse 计算每月小计和年度小计
6. THE Saldenliste_Service SHALL 在报表底部生成汇总行：Aktiva 合计、Passiva 合计、Ertrag 合计、Aufwand 合计、Gewinn/Verlust（Ertrag - Aufwand）
7. FOR ALL 科目，年度合计（Gesamt）SHALL 等于该科目 12 个月金额之和（一致性校验）

### 需求 4：后端 API 端点

**用户故事：** 作为前端开发者，我希望有清晰的 API 端点来获取两种 Saldenliste 报表数据，以便在前端渲染报表。

#### 验收标准

1. THE Report_API SHALL 提供 POST /api/v1/reports/saldenliste 端点用于生成 Saldenliste mit VJ 报表
2. THE Report_API SHALL 提供 POST /api/v1/reports/periodensaldenliste 端点用于生成 Periodensaldenliste 报表
3. THE Report_API SHALL 要求用户认证后才能访问报表端点
4. THE Report_API SHALL 仅返回当前认证用户的报表数据
5. WHEN 指定 tax_year 内无交易数据时，THE Report_API SHALL 返回空报表结构（所有金额为零），而非返回错误

### 需求 5：Saldenliste mit VJ 前端组件

**用户故事：** 作为用户，我希望在报表页面以表格形式查看余额表含上年对比，以便直观了解各科目的财务变化。

#### 验收标准

1. THE Saldenliste_Component SHALL 以表格形式展示报表数据，列包含：科目编号、科目名称、当期 Saldo、上年 Saldo、Abweichung（绝对值）、Abweichung（百分比）
2. THE Saldenliste_Component SHALL 按 Kontenklasse 分组显示，每组带有可折叠的标题行和小计行
3. THE Saldenliste_Component SHALL 在表格底部显示汇总行（Aktiva、Passiva、Ertrag、Aufwand、Gewinn/Verlust）
4. THE Saldenliste_Component SHALL 提供年份选择器，允许用户切换查看不同年份的报表
5. THE Saldenliste_Component SHALL 支持 i18n 多语言显示（德语、英语、中文）
6. WHEN Abweichung 百分比为正值时，THE Saldenliste_Component SHALL 以绿色显示该值
7. WHEN Abweichung 百分比为负值时，THE Saldenliste_Component SHALL 以红色显示该值

### 需求 6：Periodensaldenliste 前端组件

**用户故事：** 作为用户，我希望在报表页面以月度分列表格查看期间余额表，以便分析各科目的月度趋势。

#### 验收标准

1. THE Periodensaldenliste_Component SHALL 以表格形式展示报表数据，列包含：科目编号、科目名称、1月至12月各月金额、年度合计（Gesamt）
2. THE Periodensaldenliste_Component SHALL 按 Kontenklasse 分组显示，每组带有可折叠的标题行和小计行
3. THE Periodensaldenliste_Component SHALL 在表格底部显示汇总行（Aktiva、Passiva、Ertrag、Aufwand、Gewinn/Verlust）
4. THE Periodensaldenliste_Component SHALL 提供年份选择器，允许用户切换查看不同年份的报表
5. THE Periodensaldenliste_Component SHALL 支持 i18n 多语言显示（德语、英语、中文）
6. THE Periodensaldenliste_Component SHALL 支持水平滚动以适应 14 列（科目编号 + 科目名称 + 12月 + 合计）的宽表格

### 需求 7：报表页面标签页集成

**用户故事：** 作为用户，我希望在报表页面通过标签页快速切换到新的 Saldenliste 报表，以便方便地访问所有报表类型。

#### 验收标准

1. THE ReportsPage SHALL 新增 "Saldenliste" 标签页用于显示 Saldenliste mit VJ 报表
2. THE ReportsPage SHALL 新增 "Periodensaldenliste" 标签页用于显示 Periodensaldenliste 报表
3. THE ReportsPage SHALL 对所有用户类型（EA_User 和 GmbH_User）显示这两个新标签页
4. THE ReportsPage SHALL 将新标签页放置在现有报表标签页（EA/Bilanz）之后、生成/审计/导出标签页之前

### 需求 8：多语言支持

**用户故事：** 作为用户，我希望新报表的所有标签和内容支持德语、英语和中文，以便我使用自己熟悉的语言查看报表。

#### 验收标准

1. THE Saldenliste_Service SHALL 为每个科目名称和分组标签提供德语（de）、英语（en）和中文（zh）三种语言版本
2. THE Saldenliste_Component SHALL 根据用户当前语言设置显示对应语言的科目名称和标签
3. THE Periodensaldenliste_Component SHALL 根据用户当前语言设置显示对应语言的科目名称和标签
4. THE ReportsPage SHALL 在 i18n 翻译文件中添加两个新标签页的翻译键值
