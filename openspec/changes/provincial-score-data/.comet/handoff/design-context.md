# Comet Design Handoff

- Change: provincial-score-data
- Phase: design
- Mode: compact
- Context hash: f591a9f3e7c380c12d6751adc419c3fa1bc05d28605a1042f76403ac76b06b84

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/provincial-score-data/proposal.md

- Source: openspec/changes/provincial-score-data/proposal.md
- Lines: 1-34
- SHA256: 97e61b5232af2eae9c7f5ebb560e84235bf6eec98b7c5c82a28e10d2e204d16f

```md
## Why

产品的核心价值是"真实志愿填报流程"——用户打开产品第一件事就是输入分数筛选可报学校。而高考录取本质是**按位次录取**，不是按分数：同一分数在不同年份含金量不同（试卷难度波动），但位次相对稳定。因此做"位次法志愿筛选"必须先有**省控线**（决定能否报对应批次）和**一分一段表**（分数↔位次映射）这两组省级基础数据。

当前 `admission-data-schema`（已归档）只定义了院校录取记录的 schema 与示例，**缺少这两组决定位次法能否成立的核心数据**。本 change 建立省级分数数据底座，是后续志愿筛选引擎（change⑤）的硬前置依赖。

## What Changes

- 新增**省控线** `ProvincialControlLine` 数据模型：省份、年份、科类（河南=文/理，广东=物理类/历史类）、各批次线（特殊类型招生线、一本线、二本线、专科线）。决定"分数能否报对应批次"。
- 新增**一分一段表** `ScoreRankTable` 数据模型：省份、年份、科类、分数→累计位次的映射（1 分一档，官方精度）。位次法核心数据，用于"今年分数→今年位次"换算。
- 新增**公开数据集导入器**：从公开高考数据集（GitHub 结构化数据集 / 省考试院公开 PDF 转结构化）导入河南、广东两省近 3 年省控线与一分一段表。
- 扩展**查询 API**：按省份/年份/科类查询省控线与一分一段表，支持"给定分数查位次"与"给定位次查分数"双向查询。
- 复用 data-foundation 的 **SourcedRecord 来源追溯基类**，所有数据带来源（数据集名/发布年）、采集时间、置信度。
- 覆盖**两种高考模式**：河南传统文理分科 + 广东新高考 3+1+2（物理类/历史类）。

## Capabilities

### New Capabilities

- `provincial-control-line`: 省控线数据模型与查询（各批次分数线，决定批次门槛）
- `score-rank-table`: 一分一段表数据模型与查询（分数↔位次双向映射，位次法基础）
- `provincial-data-import`: 公开数据集导入器（河南/广东近3年，含来源追溯）

### Modified Capabilities

- `data-foundation-api`: 扩展 FastAPI 访问层，新增省控线与一分一段表查询端点（复用已归档的 data-foundation-api 能力的查询机制）

## Impact

- **代码**：在 `app/models/` 新增 provincial.py（省控线+一分一段表 Domain/Table）；在 `app/repositories/mappers.py` 扩展映射；在 `app/api/routers/` 新增 provincial.py router；在 `app/loader/` 扩展种子/导入器
- **数据**：新增 `data/seed/provincial/*.yaml` 种子（河南/广东近3年省控线+一分一段表）+ 公开数据集导入脚本
- **依赖**：复用现有 pydantic/sqlmodel/fastapi；导入器可能新增数据处理依赖（如 PDF 解析，若数据源为 PDF）
- **后续依赖**：change ④b（院校录取数据）需对照省控线定批次；change⑤（志愿引擎）依赖一分一段表做位次换算
- **合规**：数据标注"基于历史数据模拟"，省控线/一分一段表为官方公开数据，confidence 可较高（≥0.8）
```

## openspec/changes/provincial-score-data/design.md

- Source: openspec/changes/provincial-score-data/design.md
- Lines: 1-72
- SHA256: 7e14f0560c5c0374e55627116bf07ba3cea921f97b915d704cfe68e64dea9728

```md
## Context

承接已归档的 data-foundation（6 实体模型 + SourcedRecord 基类 + FastAPI/SQLite/Loader 架构）。本 change 是"真实志愿填报流程"的第一块拼图——建立位次法所需的省级基础数据。

高考录取规则核心：**按位次录取**。位次 = 该分数在全省同科类考生中的累计排名。因此志愿筛选需要：
1. 省控线（分数过线才能报对应批次）
2. 一分一段表（分数↔位次映射，做"今年分→位次"和"位次稳定性修正"）

两种高考模式需同时支持：
- 河南：传统文理分科（科类=文科/理科）
- 广东：新高考 3+1+2（科类=物理类/历史类，且后续院校专业组有科目要求）

## Goals / Non-Goals

**Goals:**
- 省控线 + 一分一段表两个数据模型，支持河南/广东两种模式
- 公开数据集导入（近3年），全部带来源追溯
- 双向查询 API（分数→位次、位次→分数、省控线查询）
- 复用 data-foundation 架构（SourcedRecord/SQLModel/Loader/FastAPI）

**Non-Goals:**
- ❌ 爬虫（实时抓取阳光高考/考试院）→ 后续可选 change
- ❌ 院校录取数据（专业组/录取明细）→ change ④b
- ❌ 志愿筛选引擎（位次换算/冲稳保/表生成）→ change⑤
- ❌ Web 前端 → change③
- ❌ 全国31省 → 仅河南+广东两省
- ❌ 位次稳定性修正算法（等效位次换算）→ change⑤ 引擎职责，本层只提供原始数据

## Decisions

### D1: 一分一段表存储为"分段记录"而非单条大 JSON

**选择**：一分一段表存为多条 `ScoreRankEntry`（每条=一个分数段：分数、该分人数、累计位次），每省每年每科类一组。

**理由**：
- 查询"某分数的位次"用 SQL 索引直接命中，比解析 JSON 快且可索引。
- "位次→分数"反向查询用 ORDER BY + 范围查询，JSON 做不到。
- 数据量可控：一分一段表约 300-700 条/省/年/科类（分数从满分到 0），3 年×2 省×2 科类 ≈ 3600-8400 条，SQLite 轻松承载。

**替代方案**：单条 JSON 字段存整表（查询弱、难索引），被否。

### D2: 复用 data-foundation 的 SourcedRecord + Repository 双模型架构

**选择**：直接复用已归档 data-foundation 的架构模式——Domain(Pydantic 嵌套) + Table(SQLModel 拍平) + Repository 映射 + Loader 幂等 upsert。

**理由**：架构已验证（94 测试），无需重新设计；SourcedRecord 来源追溯是产品信任基石，新数据必须继承。新增模型按相同模式加入即可。

### D3: 科类用统一的自由字符串字段承载两种模式

**选择**：科类字段用 `track: str`，值为"文科"/"理科"（河南）或"物理类"/"历史类"（广东），不做强枚举。

**理由**：两种高考模式科类命名不同，且未来可能扩展（3+3 模式省份）。强枚举会限制扩展；自由字符串配合查询参数过滤足够。与已归档 admission-data-schema 的 track 字段一致。

### D4: 数据导入器与种子 Loader 分离

**选择**：`app/loader/seed_loader.py` 继续负责 YAML 种子（手编/已清洗）；新增 `app/loader/dataset_importer.py` 负责从公开数据集（CSV/JSON/PDF）解析并入库。两者都走 Repository upsert，保证幂等。

**理由**：种子是"可版本化、可 review 的事实来源"；数据集导入是"批量、可能脏"的来源。职责分离便于分别测试与维护。导入器需做数据清洗（去重、类型转换、缺失校验）。

## Risks / Trade-offs

- **[公开数据集质量参差]** GitHub 高考数据集可能过时或有错 → 缓解：每条带 source/as_of/confidence；省控线/一分一段表为官方公开数据，confidence 可设≥0.8；导入器做合理性校验（如位次应随分数递减）。
- **[一分一段表数据量大]** 每省每年数千条 → 缓解：D1 分段记录+索引，SQLite 足够；按省/年/科类分区查询。
- **[PDF 解析复杂]** 若数据源为考试院 PDF → 缓解：优先选已结构化的数据集（CSV/JSON）；PDF 作为最后选项，且 PDF 解析单独成模块。
- **[两种模式字段差异]** 河南/广东科类与批次命名可能不同 → 缓解：D3 自由字符串；批次用统一枚举（一本/二本/专科/特殊类型）但允许部分省无某批次（如新高考省份合并本科批次）。
- **[合规：数据时效性]** 省控线/一分一段表每年更新 → 缓解：as_of 记录数据所属年份；导入器支持增量更新；标注"历史数据，非当年实时"。

## Open Questions

1. 广东新高考已合并一本/二本为"本科批"——省控线模型是否需支持"本科批"这种合并批次？建议是（batch 枚举加"本科批"，按省差异存在）。
2. 一分一段表是否包含"累计人数"和"该分人数"两个字段？建议都含（位次法用累计，分析竞争密度用该分人数）。
3. 特殊类型招生线（原一本线参考）在广东如何表达？建议统一用"特殊类型招生控制线"字段，各省命名差异在 note 标注。
```

## openspec/changes/provincial-score-data/tasks.md

- Source: openspec/changes/provincial-score-data/tasks.md
- Lines: 1-47
- SHA256: 687e3b95530d8ef6d957a920ac95adf4e8abc04faecb28488b60ce741bb0aa5e

```md
## 1. 数据模型层（app/models）

- [ ] 1.1 实现 `app/models/provincial.py`：`ProvincialControlLine` 模型（省份/年份/科类 track + 批次线集合 special_line/first_batch/second_batch/undergrad_batch/junior_college，各批次可选），继承 SourcedRecord，校验分数非负、必填字段
- [ ] 1.2 实现 `ScoreRankTable`（表头：省份/年份/科类 + 来源）与 `ScoreRankEntry`（score/count_at/cumulative_rank），含累计位次单调性校验（高分位次小）
- [ ] 1.3 扩展 `app/models/tables.py`：新增 `ProvincialControlLineRow`、`ScoreRankTableRow`、`ScoreRankEntryRow`（SQLModel 拍平，含来源字段 + _check_sourced 校验）

## 2. Repository 映射

- [ ] 2.1 在 `app/repositories/mappers.py` 新增省级数据的 `*_to_row` / `*_to_domain` 映射（provincial_control_line、score_rank_table、score_rank_entry 三类）
- [ ] 2.2 测试映射往返（roundtrip）不丢字段、来源完整

## 3. 数据查询逻辑（位次法双向查询）

- [ ] 3.1 实现分数→累计位次查询（按省/年/科类 + 分数精确匹配）
- [ ] 3.2 实现位次→分数查询（就近匹配：精确位次不存在时取最接近的分数段）
- [ ] 3.3 单元测试双向查询（含就近匹配场景）

## 4. 数据集导入器（app/loader/dataset_importer.py）

- [ ] 4.1 实现公开数据集（CSV/JSON）解析省控线与一分一段表
- [ ] 4.2 实现数据清洗（类型转换、去重、缺失剔除）
- [ ] 4.3 实现幂等导入（复用 Repository upsert）+ 来源标注（数据集名/年份/confidence）
- [ ] 4.4 实现合理性校验（省控线分数非负、一分一段表位次单调性），校验失败拒绝并报告
- [ ] 4.5 测试导入（合法导入、脏数据拒绝、增量更新、幂等）

## 5. 种子数据（data/seed/provincial/）

- [ ] 5.1 编写河南近3年（如2022-2024）省控线种子（文科+理科，一本/二本/专科线）
- [ ] 5.2 编写广东近3年省控线种子（物理类+历史类，特殊类型招生线+本科批）
- [ ] 5.3 编写河南近3年一分一段表种子（文科+理科，每省每年≥100分数段，位次单调）
- [ ] 5.4 编写广东近3年一分一段表种子（物理类+历史类，位次单调）
- [ ] 5.5 扩展 seed_loader 注册省级数据 SEED_SPECS + 加载校验测试（规模达标、位次单调性、来源完整、官方数据 confidence≥0.8）

## 6. FastAPI 端点（app/api/routers/provincial.py）

- [ ] 6.1 实现 `GET /api/v1/provincial/control-line`（省控线查询，含来源字段）
- [ ] 6.2 实现 `GET /api/v1/provincial/score-rank`（一分一段表查询）
- [ ] 6.3 实现 `GET /api/v1/provincial/score-rank/rank`（分数查累计位次）
- [ ] 6.4 实现 `GET /api/v1/provincial/score-rank/score`（位次查分数就近匹配）
- [ ] 6.5 注册 router 到 main.py + 启动加载省级种子
- [ ] 6.6 API 端点测试（各查询返回来源字段、空结果不报错）

## 7. 验证与文档

- [ ] 7.1 单元测试：模型校验（省控线批次可选/一分一段表位次单调性）、双向查询、导入清洗
- [ ] 7.2 端到端验证：河南690分查位次、广东本科批查询、来源字段全链路
- [ ] 7.3 更新 README 增加省级数据端点说明 + 合规检查（无预测措辞，标注历史数据）
```

## openspec/changes/provincial-score-data/specs/data-foundation-api/spec.md

- Source: openspec/changes/provincial-score-data/specs/data-foundation-api/spec.md
- Lines: 1-32
- SHA256: e8011d41c13dc80729980273fe6dd0d4bb0f45a90061f921c4f2f6712cb0ff9d

```md
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
```

## openspec/changes/provincial-score-data/specs/provincial-control-line/spec.md

- Source: openspec/changes/provincial-score-data/specs/provincial-control-line/spec.md
- Lines: 1-41
- SHA256: 60e47ba9cb20979effa42305249cd179ee8f94d884ffb278de5976d846d5a4b4

```md
## ADDED Requirements

### Requirement: 省控线数据模型定义

系统 SHALL 定义 `ProvincialControlLine` 数据模型，承载各省份各批次录取控制分数线。字段 MUST 包含：省份、年份、科类（track 自由字符串，支持"文科"/"理科"/"物理类"/"历史类"）、批次控制线集合（special_line 特殊类型招生控制线、first_batch 一本线、second_batch 二本线、undergrad_batch 本科批[新高考合并批次]、junior_college 专科线）。各省仅需填其适用的批次线（如广东新高考无一本/二本，用本科批）。

模型 SHALL 继承来源追溯基类（source/as_of/confidence/note）。省控线为官方公开数据，confidence 建议 ≥ 0.8。

#### Scenario: 构造河南传统文理科控线

- **WHEN** 构造 ProvincialControlLine（省份河南、年份2024、科类理科、一本线514、二本线400）
- **THEN** 实例化成功，各批次线可读取，来源字段存在

#### Scenario: 构造广东新高考省控线

- **WHEN** 构造 ProvincialControlLine（省份广东、年份2024、科类物理类、特殊类型招生线539、本科批442）
- **THEN** 实例化成功，本科批存在，一本/二本字段可为空

#### Scenario: 缺省份或年份被拒绝

- **WHEN** 构造省控线时省略省份或年份
- **THEN** 校验失败并报错

#### Scenario: 分数为负被拒绝

- **WHEN** 某批次线填负数（如 -1）
- **THEN** 校验失败

### Requirement: 省控线种子数据覆盖两省三年

系统 MUST 提供河南与广东两省近 3 年（如 2022-2024）的省控线种子数据，覆盖河南文科/理科与广东物理类/历史类。每条 MUST 标注来源（数据集名/官方发布）、as_of（数据所属年份）、confidence（官方数据≥0.8）。

#### Scenario: 种子省控线可查询

- **WHEN** 加载种子后查询河南2024理科省控线
- **THEN** 返回完整批次线（一本/二本/专科等），含来源字段

#### Scenario: 两省批次结构差异体现

- **WHEN** 查询河南2024 vs 广东2024 省控线
- **THEN** 河南有一本/二本线，广东有本科批（无一本二本），结构差异正确反映
```

## openspec/changes/provincial-score-data/specs/provincial-data-import/spec.md

- Source: openspec/changes/provincial-score-data/specs/provincial-data-import/spec.md
- Lines: 1-39
- SHA256: eb06c7a56b473beba44de699a4a8b425b67836f4d46e9c9bdc8e4f7e25689b3e

```md
## ADDED Requirements

### Requirement: 公开数据集导入器

系统 MUST 提供数据导入器 `dataset_importer`，从公开高考数据集（CSV/JSON 结构化格式）解析并入库省控线与一分一段表。导入 SHALL 复用 Repository 的幂等 upsert 机制（重复导入不产生重复记录）。

导入器 MUST 对导入数据做合理性校验：
- 省控线：分数非负、必填字段（省/年/科类）存在
- 一分一段表：累计位次单调性（高分位次小）
- 校验失败的记录 SHALL 被拒绝并报告（文件、记录标识、原因），不静默跳过

#### Scenario: 导入 CSV 省控线

- **WHEN** 用合法 CSV 数据集导入河南2024省控线
- **THEN** 数据入库，幂等（再次导入数量不变），每条带来源字段

#### Scenario: 导入失败数据被拒绝

- **WHEN** 导入的一分一段表数据存在位次单调性违反
- **THEN** 导入器拒绝并报告具体记录，不静默跳过

#### Scenario: 增量更新

- **WHEN** 数据集新增 2025 年数据后再次导入
- **THEN** 仅新增 2025 年记录，历史记录不变

### Requirement: 数据清洗与来源标注

导入器 MUST 对原始数据集做清洗：类型转换（字符串→数值）、去重（按省/年/科类主键）、缺失关键字段剔除。每条导入记录 MUST 标注来源（数据集名称/版本）、as_of（数据所属年份）、confidence（公开数据集建议 0.7-0.9）。

#### Scenario: 脏数据清洗

- **WHEN** 原始数据集含重复行或类型错误（如分数为字符串"514"）
- **THEN** 导入器清洗后入库（重复去重、类型转换），数据合法

#### Scenario: 来源标注完整

- **WHEN** 导入任意省控线/一分一段表记录
- **THEN** 入库记录含 source（数据集名）、as_of（年份）、confidence 字段
```

## openspec/changes/provincial-score-data/specs/score-rank-table/spec.md

- Source: openspec/changes/provincial-score-data/specs/score-rank-table/spec.md
- Lines: 1-65
- SHA256: e2affc510bc02c50b144f06e0a36d249906b41f6aca6cea67210056bb526a34b

```md
## ADDED Requirements

### Requirement: 一分一段表数据模型定义

系统 SHALL 定义一分一段表模型，承载"分数→位次"映射（位次法核心数据）。模型 SHALL 由两部分组成：
- `ScoreRankTable`：表头（省份、年份、科类 track、来源追溯）
- `ScoreRankEntry`：分段记录（score 该分数、count_at 该分人数、cumulative_rank 累计位次），属于某表头

一分一段表 MUST 同时包含"该分人数"与"累计位次"两个字段（累计位次用于位次法换算，该分人数用于分析竞争密度）。

分段记录 SHALL 满足不变量：累计位次随分数递减而递增（高分位次小、低分位次大）。

ScoreRankTable SHALL 继承来源追溯基类。

#### Scenario: 构造一分一段表

- **WHEN** 构造 ScoreRankTable（河南、2024、理科）含多条 ScoreRankEntry（如 700分→累计位次50，690分→累计位次300）
- **THEN** 实例化成功，按分数可查对应累计位次

#### Scenario: 累计位次单调性校验

- **WHEN** 一组 entries 中存在"高分累计位次 > 低分累计位次"的反常数据（如 700分累计位次500 > 690分累计位次300）
- **THEN** 校验失败（违反位次单调性）

#### Scenario: 双字段完整

- **WHEN** 某 entry 缺 count_at 或 cumulative_rank
- **THEN** 校验失败

### Requirement: 分数位次双向查询

系统 MUST 支持基于一分一段表的**双向查询**：
- 给定分数 → 查累计位次（"我这个分数排第几"）
- 给定位次 → 查对应分数（"第N名大概多少分"）

位次查询 SHALL 支持精确匹配与就近匹配（精确位次不存在时取最接近的分数段）。

#### Scenario: 分数查位次

- **WHEN** 查询河南2024理科690分的累计位次
- **THEN** 返回该分数对应的累计位次（如300）

#### Scenario: 位次查分数

- **WHEN** 查询河南2024理科累计位次约300对应的分数
- **THEN** 返回最接近的分数（如690）

#### Scenario: 查询不存在的分数就近匹配

- **WHEN** 查询一个一分一段表中无精确记录的分数
- **THEN** 返回最接近的分数段位次，不报错

### Requirement: 一分一段表种子覆盖两省三年

系统 MUST 提供河南与广东两省近 3 年、文/理与物理/历史类的一分一段表种子。每条 entry MUST 通过位次单调性校验。种子量级参考真实（每省每年每科类约 300-700 个分数段）。

#### Scenario: 种子一分一段表可加载并通过单调性校验

- **WHEN** 加载一分一段表种子
- **THEN** 所有 entries 通过累计位次单调性校验，无反常数据

#### Scenario: 种子规模达标

- **WHEN** 查询河南2024理科一分一段表
- **THEN** 返回 ≥ 100 个分数段（覆盖主要分数区间）
```

