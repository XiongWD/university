## MODIFIED Requirements

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
