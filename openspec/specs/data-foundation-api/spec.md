# data-foundation-api Specification

## Purpose
TBD - created by archiving change data-foundation. Update Purpose after archive.
## Requirements
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

系统 MUST 提供 FastAPI 应用，按实体分组暴露查询端点。除已归档的六类实体端点外，新增**省级分数数据**端点：

- `GET /api/v1/provincial/control-line?province={省}&year={年}&track={科类}` — 省控线查询
- `GET /api/v1/provincial/score-rank?province={省}&year={年}&track={科类}` — 一分一段表查询
- `GET /api/v1/provincial/score-rank/rank?province={省}&year={年}&track={科类}&score={分}` — 分数查累计位次
- `GET /api/v1/provincial/score-rank/score?province={省}&year={年}&track={科类}&rank={位次}` — 位次查分数（就近匹配）

所有响应 MUST 附带来源字段（source/as_of/confidence）。空结果集（不存在的省/年/科类）SHALL 返回空列表或 404，不抛异常。

#### Scenario: 查询省控线

- **WHEN** GET /api/v1/provincial/control-line?province=河南&year=2024&track=理科
- **THEN** 返回该省该年理科的省控线（各批次线），含来源字段

#### Scenario: 分数查位次

- **WHEN** GET /api/v1/provincial/score-rank/rank?province=河南&year=2024&track=理科&score=690
- **THEN** 返回690分对应的累计位次，含来源字段

#### Scenario: 位次查分数

- **WHEN** GET /api/v1/provincial/score-rank/score?province=河南&year=2024&track=理科&rank=300
- **THEN** 返回累计位次约300对应的分数（就近匹配）

#### Scenario: 不存在的省年返回空或404

- **WHEN** 查询一个无数据的省份或年份
- **THEN** 返回空列表或404，不抛服务端异常

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

