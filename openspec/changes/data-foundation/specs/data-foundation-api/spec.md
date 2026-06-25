## ADDED Requirements

### Requirement: YAML 种子加载到 SQLite

系统 MUST 提供 YAML 种子数据加载层，将 `data/seed/*.yaml` 中的六类数据加载进 SQLite。加载 MUST 幂等（重复执行不产生重复记录，按主键 upsert）。加载前 MUST 校验每条记录的来源字段完整性（source/as_of/confidence），校验失败的记录 SHALL 被拒绝并报告。

#### Scenario: 首次加载种子

- **WHEN** 数据库为空时执行加载
- **THEN** 六类数据全部写入，数量符合各实体种子规模

#### Scenario: 重复加载幂等

- **WHEN** 再次执行加载
- **THEN** 记录总数不变，无重复，已修改的种子值被更新

#### Scenario: 损坏种子被拒绝

- **WHEN** 某 YAML 记录缺 source 字段
- **THEN** 加载中止该记录，报告文件与记录标识

### Requirement: FastAPI 数据访问端点

系统 MUST 提供 FastAPI 应用，按实体分组暴露查询端点（至少）：
- `GET /api/v1/careers` 与 `GET /api/v1/careers/{id}`
- `GET /api/v1/cities` 与 `GET /api/v1/cities/{city}/cost`
- `GET /api/v1/careers/{id}/salary?city={city}`
- `GET /api/v1/universities`（支持按层级筛选）
- `GET /api/v1/majors`
- `POST /api/v1/insurance/compute`（输入工资+城市，返回企业成本/到手）

所有响应 MUST 附带来源字段（source/as_of/confidence）。

#### Scenario: 查询职业详情

- **WHEN** GET /api/v1/careers/{id}
- **THEN** 返回 200 与该职业完整数据，含来源字段

#### Scenario: 按层级筛选大学

- **WHEN** GET /api/v1/universities?tier=211
- **THEN** 仅返回 211 层级大学

#### Scenario: 计算五险一金成本

- **WHEN** POST /api/v1/insurance/compute，body 含工资与城市
- **THEN** 返回企业成本与到手工资，按该城市比例计算

### Requirement: 来源追溯贯穿全链路

系统 MUST 保证来源追溯字段（source/as_of/confidence/note）从 YAML 种子 → 模型校验 → SQLite 存储 → API 响应全链路不丢失。任何环节丢弃来源字段视为缺陷。

#### Scenario: API 响应保留来源

- **WHEN** 调用任一数据查询端点
- **THEN** 响应 JSON 含 source/as_of/confidence 字段，值与种子一致

#### Scenario: 缺来源记录无法入库

- **WHEN** 加载层遇到缺 confidence 的记录
- **THEN** 拒绝入库并报告

### Requirement: 单元测试覆盖核心逻辑

系统 MUST 提供单元测试，覆盖：模型校验（各实体合法/非法构造）、五险一金计算引擎（企业成本/到手/个税累进）、城市成本年化计算、种子加载（幂等/校验拒绝）、API 端点（主要查询与计算）。

#### Scenario: 测试套件可独立运行

- **WHEN** 执行 pytest
- **THEN** 所有测试通过，覆盖上述逻辑，无跳过的核心测试
