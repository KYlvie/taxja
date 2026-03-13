# 实施计划：Saldenliste 报表

## 概述

本计划将 Saldenliste 报表功能拆分为增量式编码任务。从后端服务核心逻辑开始，逐步扩展到 API 端点、前端组件和多语言支持，最终完成集成。每个任务均引用具体需求条款，确保可追溯性。

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLAlchemy / PostgreSQL
- **前端**: React 18 + TypeScript / Vite / i18next
- **测试**: pytest + Hypothesis（属性测试）/ vitest（前端）

## 任务列表

- [x] 1. 实现后端科目体系与核心数据结构
  - [x] 1.1 创建 `backend/app/services/saldenliste_service.py`，定义 `AccountDef` dataclass 和 `KONTENPLAN_EA`、`KONTENPLAN_GMBH` 科目常量
    - 从 `ea_report_service.py` 和 `bilanz_report_service.py` 中的 category 映射关系派生科目定义
    - 实现 `get_account_plan(user_type)` 函数，根据用户类型返回对应科目列表
    - 实现 `_map_transaction_to_konto(transaction, account_plan)` 辅助函数
    - _需求: 1.1, 1.2, 1.3_

  - [x] 1.2 编写属性测试：用户类型决定科目体系（Property 1）
    - 创建 `backend/tests/test_saldenliste_properties.py`
    - **Property 1: 用户类型决定科目体系**
    - EA 用户仅包含 Kontenklasse 4 和 7；GmbH 用户覆盖 0-9
    - **验证: 需求 1.1, 1.2**

  - [x] 1.3 编写属性测试：交易到科目的映射一致性（Property 2）
    - **Property 2: 交易到科目的映射一致性**
    - 有效交易映射到对应科目体系的有效科目编号
    - **验证: 需求 1.3**

  - [x] 1.4 编写属性测试：科目三语标签完整性（Property 11）
    - **Property 11: 科目三语标签完整性**
    - 所有科目的 label_de、label_en、label_zh 均为非空字符串
    - **验证: 需求 8.1**

- [x] 2. 实现 Saldenliste mit VJ 报表核心计算逻辑
  - [x] 2.1 在 `saldenliste_service.py` 中实现余额计算和偏差计算函数
    - 实现 `_compute_yearly_balances(transactions, account_plan)` 计算各科目年度累计余额
    - 实现 `_compute_deviation(current, prior)` 计算偏差（绝对值 + 百分比，上年为零时百分比为 null）
    - 实现 `_group_by_kontenklasse(balances, account_plan)` 按 Kontenklasse 分组并计算小计
    - 实现 `_build_summary_totals(groups, user_type)` 生成汇总行
    - _需求: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 2.2 实现 `generate_saldenliste(db, user, tax_year, language)` 主函数
    - 查询当期和上年交易数据，调用计算函数，组装完整报表响应结构
    - 空数据年份返回零值报表结构
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.5_

  - [x] 2.3 编写属性测试：年度余额计算正确性（Property 3）
    - **Property 3: 年度余额计算正确性**
    - 每个科目 Saldo 等于该年份内所有映射到该科目的交易金额之和
    - **验证: 需求 2.2, 2.3**

  - [x] 2.4 编写属性测试：偏差计算正确性（Property 4）
    - **Property 4: 偏差计算正确性（含除零保护）**
    - 绝对偏差 = current - prior；prior ≠ 0 时百分比 = (current - prior) / prior × 100；prior = 0 时百分比为 null
    - **验证: 需求 2.4, 2.5**

  - [x] 2.5 编写属性测试：Kontenklasse 分组不变量（Property 5）
    - **Property 5: Kontenklasse 分组不变量**
    - 每组内科目具有相同 Kontenklasse，所有科目恰好出现一次
    - **验证: 需求 2.6, 3.4**

  - [x] 2.6 编写属性测试：小计等于组内科目之和（Property 6）
    - **Property 6: 小计等于组内科目之和**
    - 当期小计 = Σ当期 Saldo，上年小计 = Σ上年 Saldo
    - **验证: 需求 2.7, 3.5**

  - [x] 2.7 编写属性测试：Gewinn/Verlust = Ertrag - Aufwand（Property 7）
    - **Property 7: Gewinn/Verlust = Ertrag - Aufwand**
    - 汇总行中 Gewinn/Verlust 等于 Ertrag 合计减去 Aufwand 合计
    - **验证: 需求 2.8, 3.6**

- [x] 3. 实现 Periodensaldenliste 报表核心计算逻辑
  - [x] 3.1 在 `saldenliste_service.py` 中实现月度余额计算函数
    - 实现 `_compute_monthly_balances(transactions, account_plan)` 计算各科目月度金额
    - 扩展 `_group_by_kontenklasse` 支持月度数据分组和月度小计
    - 实现 `generate_periodensaldenliste(db, user, tax_year, language)` 主函数
    - 空数据年份返回零值报表结构
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.5_

  - [x] 3.2 编写属性测试：月度金额计算正确性（Property 8）
    - **Property 8: 月度金额计算正确性**
    - 每个科目每月金额等于该月内所有映射到该科目的交易金额之和
    - **验证: 需求 3.2**

  - [x] 3.3 编写属性测试：年度合计一致性（Property 9）
    - **Property 9: 年度合计一致性**
    - Gesamt 等于该科目 12 个月金额之和
    - **验证: 需求 3.3, 3.7**

- [x] 4. 检查点 - 后端核心逻辑验证
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 5. 新增后端 API 端点
  - [x] 5.1 在 `backend/app/api/v1/endpoints/reports.py` 中新增两个 POST 端点
    - `POST /api/v1/reports/saldenliste` 调用 `generate_saldenliste`
    - `POST /api/v1/reports/periodensaldenliste` 调用 `generate_periodensaldenliste`
    - 复用现有 `ReportRequest` schema 和 `get_current_user` 认证依赖
    - _需求: 4.1, 4.2, 4.3, 4.4_

  - [x] 5.2 编写属性测试：用户数据隔离（Property 10）
    - **Property 10: 用户数据隔离**
    - 用户 A 的报表不包含用户 B 的交易数据
    - **验证: 需求 4.4**

  - [x] 5.3 编写单元测试：API 端点和边界情况
    - 创建 `backend/tests/test_saldenliste_service.py`
    - 测试端点认证要求、空数据年份返回零值、语言参数切换
    - _需求: 4.1, 4.2, 4.3, 4.5_

- [x] 6. 扩展前端 reportService 和 TypeScript 类型定义
  - [x] 6.1 在 `frontend/src/services/reportService.ts` 中新增类型定义和 API 方法
    - 添加 `SaldenlisteReport`、`PeriodensaldenlisteReport` 等 TypeScript 接口
    - 添加 `generateSaldenliste(taxYear, language)` 方法
    - 添加 `generatePeriodensaldenliste(taxYear, language)` 方法
    - _需求: 4.1, 4.2_

- [x] 7. 实现 Saldenliste mit VJ 前端组件
  - [x] 7.1 创建 `frontend/src/components/reports/SaldenlisteReport.tsx` 和对应 CSS
    - 年份选择器（下拉框，最近 5 年）
    - 按 Kontenklasse 分组的可折叠表格
    - 列：科目编号、科目名称、当期 Saldo、上年 Saldo、Abweichung（绝对值）、Abweichung（%）
    - 每组小计行 + 底部汇总行（Aktiva/Passiva/Ertrag/Aufwand/Gewinn-Verlust）
    - 正偏差百分比绿色、负偏差百分比红色
    - 使用 `useTranslation` 支持 i18n
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 8. 实现 Periodensaldenliste 前端组件
  - [x] 8.1 创建 `frontend/src/components/reports/PeriodensaldenlisteReport.tsx` 和对应 CSS
    - 年份选择器
    - 按 Kontenklasse 分组的可折叠宽表格（14 列）
    - 列：科目编号、科目名称、1月-12月、年度合计
    - 支持水平滚动（`overflow-x: auto`）
    - 每组月度小计行 + 底部汇总行
    - 使用 `useTranslation` 支持 i18n
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 9. 集成到 ReportsPage 标签页导航
  - [x] 9.1 修改 `frontend/src/pages/ReportsPage.tsx`
    - 在 `TabType` 中新增 `'saldenliste' | 'periodensaldenliste'`
    - 在现有标签页（ea/bilanz/taxform）之后、generate/audit/export 之前插入两个新标签页
    - 对所有用户类型显示这两个标签页
    - _需求: 7.1, 7.2, 7.3, 7.4_

- [x] 10. 添加 i18n 多语言翻译键值
  - [x] 10.1 更新 `frontend/src/i18n/locales/de.json`、`en.json`、`zh.json`
    - 添加两个新标签页的翻译键
    - 添加报表组件中使用的所有标签翻译（列标题、汇总行标签、月份名称等）
    - _需求: 8.1, 8.2, 8.3, 8.4_

- [x] 11. 最终检查点 - 全部测试通过
  - 确保所有后端测试（属性测试 + 单元测试）和前端构建通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选项，可跳过以加速 MVP 交付
- 每个任务引用具体需求条款，确保可追溯性
- 属性测试使用 Hypothesis 库验证通用正确性属性
- 检查点任务确保增量验证
