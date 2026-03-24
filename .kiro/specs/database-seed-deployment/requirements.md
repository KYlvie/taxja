# 需求文档：数据库种子数据部署系统

## 简介

构建一个完整的数据库种子数据初始化系统，使本地开发环境可以从空数据库一键启动到可用状态。当前项目尚未正式运营，不需要增量迁移补丁的方式来维护种子数据。该系统将所有配置/引用数据整合为一个统一的种子数据模块，与 Alembic 迁移配合工作，在 `docker-compose up` 后自动完成数据库初始化和种子数据填充。

## 术语表

- **Seed_System**: 数据库种子数据初始化系统，负责在空数据库上填充所有配置和引用数据
- **Reference_Data**: 应用运行所必需的配置/引用数据，包括订阅计划、税务配置、积分成本配置、积分充值包等
- **Seed_Runner**: 种子数据执行器，负责检测数据库状态并执行种子数据填充
- **Seed_Registry**: 种子数据注册表，集中管理所有种子数据模块的注册和执行顺序
- **Alembic**: 数据库 schema 迁移工具，管理表结构变更
- **Docker_Compose**: 容器编排工具，用于本地开发环境的服务启动

## 需求

### 需求 1：统一种子数据模块

**用户故事：** 作为开发者，我希望所有引用数据集中在一个种子数据模块中管理，以便新环境部署时不需要手动运行多个脚本。

#### 验收标准

1. THE Seed_System SHALL 将所有 Reference_Data（plans、tax_configurations、credit_cost_configs、credit_topup_packages）整合到一个统一的 Python 种子数据模块中
2. THE Seed_Registry SHALL 以声明式方式注册每个数据表的种子数据函数及其执行顺序
3. THE Seed_System SHALL 使用 SQLAlchemy ORM 模型（而非原始 SQL）来插入种子数据，以确保与 schema 变更保持同步
4. WHEN 新的 Reference_Data 表需要种子数据时，THE Seed_Registry SHALL 支持通过添加新的种子函数来扩展，无需修改已有代码

### 需求 2：幂等种子数据执行

**用户故事：** 作为开发者，我希望种子数据脚本可以安全地重复执行，以便在任何时候运行都不会产生重复数据或错误。

#### 验收标准

1. WHEN Seed_Runner 执行种子数据填充时，THE Seed_Runner SHALL 检查每条记录是否已存在，仅插入缺失的记录
2. WHEN 种子数据已存在于数据库中时，THE Seed_Runner SHALL 更新已有记录以匹配最新的种子数据定义（upsert 语义）
3. WHEN Seed_Runner 被重复执行多次时，THE Seed_System SHALL 产生与执行一次相同的数据库状态（幂等性）
4. THE Seed_Runner SHALL 在执行完成后输出每个表的操作摘要（插入数量、更新数量、跳过数量）

### 需求 3：自动化初始化流程

**用户故事：** 作为开发者，我希望 `docker-compose up` 后数据库自动完成迁移和种子数据填充，以便无需手动执行任何额外步骤。

#### 验收标准

1. WHEN Docker_Compose 启动 backend 服务时，THE Seed_System SHALL 在应用启动前自动执行 Alembic 迁移（`alembic upgrade head`）
2. WHEN Alembic 迁移完成后，THE Seed_System SHALL 自动执行种子数据填充
3. WHEN 数据库已包含最新的 schema 和种子数据时，THE Seed_System SHALL 在 5 秒内完成检查并跳过，不影响启动速度
4. IF 迁移或种子数据填充过程中发生错误，THEN THE Seed_System SHALL 记录详细错误信息并以非零退出码终止，阻止应用启动

### 需求 4：CLI 命令支持

**用户故事：** 作为开发者，我希望可以通过命令行手动触发种子数据操作，以便在调试或重置数据库时灵活使用。

#### 验收标准

1. THE Seed_System SHALL 提供一个 CLI 命令（如 `python -m app.db.seed`）用于手动执行种子数据填充
2. THE Seed_System SHALL 提供一个 `--reset` 选项，用于清空所有 Reference_Data 表后重新填充
3. THE Seed_System SHALL 提供一个 `--dry-run` 选项，用于预览将要执行的操作而不实际修改数据库
4. THE Seed_System SHALL 提供一个 `--table` 选项，用于仅对指定的表执行种子数据填充

### 需求 5：Docker 入口脚本集成

**用户故事：** 作为开发者，我希望 Docker 容器启动时自动完成数据库初始化，以便 `docker-compose up` 一条命令即可获得完全可用的开发环境。

#### 验收标准

1. THE Seed_System SHALL 提供一个 Docker 入口脚本（entrypoint），在启动 uvicorn 之前执行迁移和种子数据填充
2. WHEN 环境变量 `AUTO_SEED` 设置为 `true` 时，THE Seed_System SHALL 在容器启动时自动执行种子数据填充
3. WHEN 环境变量 `AUTO_SEED` 未设置或设置为 `false` 时，THE Seed_System SHALL 跳过自动种子数据填充，仅执行迁移
4. THE Docker_Compose 配置 SHALL 在开发环境中默认启用 `AUTO_SEED=true`

### 需求 6：种子数据完整性验证

**用户故事：** 作为开发者，我希望系统能验证种子数据的完整性，以便在数据缺失时及时发现问题。

#### 验收标准

1. THE Seed_System SHALL 提供一个验证命令，检查所有 Reference_Data 表是否包含预期的种子数据
2. WHEN 验证发现缺失的种子数据时，THE Seed_System SHALL 输出缺失数据的详细列表
3. WHEN 应用启动时，THE Seed_System SHALL 执行轻量级验证，检查关键 Reference_Data 表是否为空
4. IF 关键 Reference_Data 表（plans、tax_configurations）为空，THEN THE Seed_System SHALL 在日志中输出警告信息

### 需求 7：向后兼容现有脚本

**用户故事：** 作为开发者，我希望新系统与现有的种子脚本保持向后兼容，以便过渡期间两种方式都可以使用。

#### 验收标准

1. THE Seed_System SHALL 保留现有的 `db_seed.sql`、`seed_tax_config.py`、`seed_plans_sql.py` 文件，标记为已废弃
2. THE Seed_System SHALL 确保新种子数据模块产生的数据与现有脚本产生的数据一致
3. WHEN 现有种子脚本已被新系统完全替代后，THE Seed_System SHALL 在废弃文件中添加指向新系统的引导注释

### 需求 8：Makefile 集成

**用户故事：** 作为开发者，我希望通过 Makefile 命令快速操作种子数据，以便与现有的开发工作流保持一致。

#### 验收标准

1. THE Makefile SHALL 提供 `make seed` 命令用于执行种子数据填充
2. THE Makefile SHALL 提供 `make seed-reset` 命令用于重置并重新填充种子数据
3. THE Makefile SHALL 提供 `make seed-verify` 命令用于验证种子数据完整性
4. THE Makefile SHALL 提供 `make fresh` 命令用于从空数据库执行完整初始化（迁移 + 种子数据）
