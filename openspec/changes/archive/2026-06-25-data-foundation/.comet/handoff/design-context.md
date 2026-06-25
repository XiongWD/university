# Comet Design Handoff

- Change: data-foundation
- Phase: design
- Mode: compact
- Context hash: 9288109a3559a72011908b94e7df7ae618373660a9770fa9d46ba33e009e74c6

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/data-foundation/proposal.md

- Source: openspec/changes/data-foundation/proposal.md
- Lines: 1-47
- SHA256: 9d339286d12c6cc54929d0617fd4b3eaf9b7c21dc31abbeedc60a93d2cc80146

```md
## Why

人生经济模型模拟器的产品价值在于"把模糊的高考志愿决策变成可追溯的数字决策"。但当前项目零数据基础——没有任何职业、城市、大学、专业数据可供计算，也没有考生画像结构来承载"根据考生情况模拟填报"的核心输入。后续的决策引擎（评分/路径推演）和 Web 前端（精致展示）都依赖一个**结构化、可扩展、带来源追溯**的数据底座。本 change 建立这个底座，让产品从"想法"变成"有真实数字可算"。

数据真实性是产品成败关键（文档原话："产品成败 = 数据真实性，而不是算法"），因此本 change 同时建立**来源追溯机制**：每个数字都带数据来源、采集时间、置信度，为信任与合规（"基于历史数据模拟"而非"预测未来"）打基础。

## What Changes

- 新增**六类核心数据模型**（Python dataclass / Pydantic schema）：
  - 考生画像 `StudentProfile`：总分、省份、偏科分数（数学/英语/语文/文综·理综）、小语种能力、家庭体制资源（体制内/医疗/教育亲属）、性别、兴趣与强项、风险偏好
  - 职业 `Career`：起薪、5 年中位薪资、15 年薪资上限、稳定性、晋升速度、编制属性、关联学科
  - 五险一金 `SocialInsurance`：统一的"总用工成本模型"（企业成本/到手工资公式）+ 全国基准比例，可按城市调参
  - 城市成本 `CityCost`：租房 3 档（单间/一房一厅/合租）、吃饭、通勤、其他、综合月成本、房价均价
  - 大学实力 `University`：层级（985/211/双一流/一本/二本/专科）、就业能力指标、学科评估
  - 专业实力 `Major`：就业密度、薪资分布（P25/P50/P75）、门槛难度、上升空间
- 新增**录取数据 schema**（仅定义结构与少量手编示例，不批量入库——批量历年分数线/位次留给后续爬虫 change）
- 新增 **YAML 种子数据**：覆盖约 7 个代表城市、15 个职业、15–20 个专业，数值参考文档范例量级，全部标注"待爬虫校准"
- 新增 **SQLite 加载层**：YAML 种子首次/按需加载进 SQLite，提供带索引的查询能力
- 新增 **FastAPI 数据访问 API**：按实体提供查询端点，返回结果附带 `source` / `as_of` / `confidence` 来源字段
- 新增**来源追溯约束**：所有数据记录强制带 `source`、`as_of`、`confidence` 字段，加载与 API 层均做校验
- 新增**五险一金成本计算引擎**（纯计算，非决策）：实现"企业成本 = 工资 × (1 + 单位比例)"、"到手 = 工资 - 个人部分 - 个税"公式

## Capabilities

### New Capabilities

- `student-profile-data`: 考生画像数据模型与校验——承载"根据考生情况模拟填报"的输入结构
- `career-data`: 职业数据模型与种子（薪资曲线/稳定性/编制/学科关联）
- `social-insurance-model`: 五险一金统一用工成本模型与计算引擎（企业成本/到手工资）
- `city-cost-data`: 城市生活成本数据模型与种子（租房 3 档/吃饭/通勤/房价）
- `university-data`: 大学实力三维数据模型与种子（层级/就业能力/学科评估）
- `major-data`: 专业实力数据模型与种子（就业密度/薪资分布/门槛/上升空间）
- `admission-data-schema`: 录取数据 schema 定义与示例（仅结构，不批量入库）
- `data-foundation-api`: 数据访问 FastAPI 层 + SQLite 加载层 + 来源追溯约束

### Modified Capabilities

（无——这是项目的首个 change，`openspec/specs/` 当前为空，无既有 spec 被修改。）

## Impact

- **代码**：在仓库根新增 Python 包（如 `app/` 或 `data_foundation/`），含 models、seed（YAML）、loader、api、engine 模块
- **依赖**：新增 Python 依赖——FastAPI、Uvicorn、Pydantic、SQLModel/SQLAlchemy、PyYAML；测试依赖 pytest
- **数据**：新增 `data/seed/*.yaml` 种子目录与 `data/llm_sim.db`（gitignore，首次加载生成）
- **API**：新增本地 FastAPI 服务（如 `localhost:8000`），暴露六类数据查询端点
- **后续依赖**：`decision-engine` change 将消费本层的数据模型与 API；`web-ui` change 将消费本层 API 展示数字
- **合规**：数据组织为"基于历史数据的模拟区间"，不包含任何"保证就业/确切预测未来收入"类字段
```

## openspec/changes/data-foundation/design.md

- Source: openspec/changes/data-foundation/design.md
- Lines: 1-163
- SHA256: 3788f408abf06b895044334152cc0b41b0d8ec35a11966313acc06e13df20126

[TRUNCATED]

```md
## Context

人生经济模型模拟器的核心是"把模糊的高考志愿决策变成可追溯的数字决策"。整个产品分三层独立推进：

```
① data-foundation（本 change）   数据底座：模型 + 种子 + 来源追溯 + 查询 API
② decision-engine（后续 change）  评分模型 + 3 条路径推演 + 城市生存模型
③ web-ui（后续 change）           Vite+React 精致 UI + 路径卡片 + 收入曲线
```

**当前状态**：项目零数据基础。无任何职业/城市/大学/专业数据，无考生画像结构，无后端服务。

**关键约束**：
- 数据真实性是产品成败关键——每个数字必须可追溯到来源（文档原话："产品成败 = 数据真实性"）
- 合规：数据组织为"基于历史数据的模拟区间"，不含"保证就业/预测未来"承诺
- 运行时：Python 3.13 + Node v24，本层只用 Python
- 数据维护：种子数据必须人工可编辑、可 review、可版本化

**干系人**：后续 change（engine/ui）直接消费本层数据模型与 API；家长/学生（最终用户）通过前端间接触达本层。

## Goals / Non-Goals

**Goals:**
- 定义六类数据模型（考生画像/职业/五险一金/城市成本/大学/专业）+ 录取数据 schema
- 提供约 7 城、15 职业、15–20 专业的真实量级种子数据，全部标注来源
- 实现"总用工成本"五险一金计算引擎（企业成本/到手工资公式）
- 提供 YAML 种子 → SQLite 的加载层，支持带索引查询
- 提供 FastAPI 数据访问 API，返回结果附带 `source`/`as_of`/`confidence`
- 每条数据强制带来源字段，加载与 API 层均做校验
- 完整单元测试覆盖模型校验、成本计算、加载逻辑

**Non-Goals:**
- ❌ 爬虫（BOSS/贝壳真实抓取）→ 后续独立 change
- ❌ 决策引擎评分算法、3 条路径推演逻辑 → change ②
- ❌ Web 前端 → change ③
- ❌ 批量历年录取分数线/位次数据入库 → 仅定义 schema + 示例，批量数据走后续 change
- ❌ 全中国所有职业/城市/学校 → 首版用代表样本，结构预留扩展
- ❌ AI 路径解释报告
- ❌ 用户认证、多租户、生产部署（MVP 本地运行即可）

## Decisions

### D1: 数据建模用 Pydantic v2（而非 dataclass / attrs）

**选择**：所有数据模型用 Pydantic v2 BaseModel。

**理由**：
- 强制校验来源字段（`source`/`as_of`/`confidence`）——这是产品信任基石，dataclass 无法在实例化时自动校验
- FastAPI 原生集成 Pydantic，API 响应模型与数据模型统一，零转换
- JSON Schema 自动生成，种子 YAML 校验可直接复用
- 类型注解即文档，与文档里 JSON 字段设计天然对应

**替代方案**：dataclass（轻量但无运行时校验）、attrs（介于两者但不契合 FastAPI）、SQLModel（继承自 Pydantic，会在 D3 考虑）。

### D2: 存储策略——YAML 种子 + SQLite 双层

**选择**：`data/seed/*.yaml`（人工编辑的事实来源）→ 加载层 → SQLite（查询与索引）。

**理由**：
- **YAML 是事实来源（source of truth）**：人工可读、可 review、可 git 版本化、非工程师也能维护。符合"数据维护成本低"目标。
- **SQLite 提供查询能力**：引擎需按"城市+职业+经验"复合查询薪资分布，纯文件遍历在数据量增长后不可接受。
- SQLite 零部署（单文件 `data/llm_sim.db`，gitignore），比 PostgreSQL 轻，MVP 足够；未来数据量大可平滑迁移（查询层抽象隔离）。
- 种子修改后重新加载即更新 DB，幂等。

**替代方案**：纯文件（查询/测试弱）、直接 PostgreSQL（MVP 部署重）、纯 SQLite（种子不可人工 review）。

### D3: ORM 用 SQLModel（而非裸 SQLAlchemy / Tortoise）

**选择**：SQLModel（SQLAlchemy + Pydantic 融合）。

**理由**：
- 同一个类既是 Pydantic 数据模型（校验/序列化）又是 SQLAlchemy 表（持久化）——消除"数据模型"与"表模型"的重复。
- FastAPI 作者所写，三件套天然契合。
- 未来扩展关系（职业↔学科↔城市）时，SQLAlchemy 关系能力完整保留。

**替代方案**：裸 SQLAlchemy（需维护两套模型）、Tortoise ORM（异步生态但社区小）。

### D4: 五险一金计算引擎独立为纯函数模块

**选择**：`app/engine/insurance.py` 提供纯函数 `compute_total_labor_cost()` / `compute_take_home_pay()`。
```

Full source: openspec/changes/data-foundation/design.md

## openspec/changes/data-foundation/tasks.md

- Source: openspec/changes/data-foundation/tasks.md
- Lines: 1-66
- SHA256: 7f5b6fa799e53dab4bd66a52ac0318ef720762ff08188493c31aa2cd4e74a94c

```md
## 1. 项目脚手架

- [ ] 1.1 创建 Python 包结构 `app/{models,engine,loader,api/routers}`、`data/seed/{cities,careers,universities,majors}`、`tests/` 目录与 `__init__.py`
- [ ] 1.2 创建 `pyproject.toml`，声明依赖：fastapi、uvicorn、pydantic v2、sqlmodel、sqlalchemy、pyyaml；dev 依赖 pytest、httpx
- [ ] 1.3 创建 `.gitignore`（忽略 `data/llm_sim.db`、`__pycache__`、`.venv`、`node_modules` 等）
- [ ] 1.4 创建 `app/config.py` 配置模块（数据库路径、种子目录路径、API 版本前缀）

## 2. 数据模型层（app/models）

- [ ] 2.1 实现 `app/models/base.py`：`SourcedRecord` 基类（Pydantic），含 `source`、`as_of`、`confidence`（0–1）、`note` 字段，校验 confidence 取值范围
- [ ] 2.2 实现 `app/models/student.py`：`StudentProfile` 模型（总分/省份/偏科分数含文理两种模式/小语种/家庭体制资源/性别/兴趣/强项/风险偏好三档枚举）
- [ ] 2.3 实现 `app/models/career.py`：`Career` 模型（薪资区间起薪/5年中位/15年上限/稳定性/晋升速度/编制/关联学科），校验区间最低≤最高
- [ ] 2.4 实现 `app/models/insurance.py`：`SocialInsurance` 城市社保模型（各险种个人/单位比例，比例≤1.0 校验）+ 全国基准常量
- [ ] 2.5 实现 `app/models/city.py`：`CityCost` 模型（租房3档区间/吃饭/通勤/其他/综合月成本/房价均价），校验区间
- [ ] 2.6 实现 `app/models/university.py`：`University` 三维模型（层级枚举/就业能力/学科评估列表）
- [ ] 2.7 实现 `app/models/major.py`：`Major` 模型（就业密度/薪资P25-P50-P75三分位/门槛难度/上升空间），强制三分位
- [ ] 2.8 实现 `app/models/admission.py`：`AdmissionRecord` schema（学校/专业/省份/年份/科类/最低分/位次/批次）

## 3. 计算引擎（app/engine）

- [ ] 3.1 实现 `app/engine/insurance.py`：纯函数 `compute_total_labor_cost(salary, insurance)` 返回企业成本（工资×(1+单位比例合计)）
- [ ] 3.2 实现 `compute_take_home_pay(salary, insurance)`：到手 = 工资 - 个人五险一金 - 个税
- [ ] 3.3 实现累进个税计算（2024 税率表），支持多档累进
- [ ] 3.4 实现城市成本年化计算：`compute_annual_cost(city_cost, tuition, accommodation)` = 12×月成本中位 + 学费 + 住宿费

## 4. 数据库与加载层

- [ ] 4.1 实现 `app/db.py`：SQLite 引擎创建 + SQLModel 表定义映射各模型 + Session 工厂
- [ ] 4.2 实现 `app/loader/seed_loader.py`：读取 `data/seed/*.yaml`，按模型校验，校验来源字段完整性
- [ ] 4.3 实现幂等加载（按主键 upsert），重复执行不产生重复
- [ ] 4.4 校验失败时拒绝记录并报告文件与记录标识（不静默跳过）

## 5. 种子数据（data/seed/*.yaml）

- [ ] 5.1 编写 7 个城市成本种子（深圳/北京/上海/郑州/成都/武汉/西安），数值参考文档量级，全部标注 source/as_of/confidence/note"待爬虫校准"
- [ ] 5.2 编写 15 个职业种子（公务员/医生/教师/IT/外贸/跨境电商/国企/日企商务等），含薪资区间
- [ ] 5.3 编写城市社保比例种子（各城五险一金比例配置，含全国基准）
- [ ] 5.4 编写 ≥10 所大学种子（985/211/双一流/一本各样本），学科评估用第四轮并标注
- [ ] 5.5 编写 ≥15 个专业种子（含日语/国贸/历史等文科 + 理工科），薪资强制 P25/P50/P75
- [ ] 5.6 编写录取数据示例（3–5 校 × 2 省），验证 schema 可用

## 6. FastAPI 访问层（app/api）

- [ ] 6.1 实现 `app/api/main.py`：FastAPI 应用 + `/api/v1` 前缀 + 启动时自动加载种子（若 DB 空）
- [ ] 6.2 实现职业 router：`GET /careers`、`GET /careers/{id}`，响应含来源字段
- [ ] 6.3 实现城市 router：`GET /cities`、`GET /cities/{city}/cost`
- [ ] 6.4 实现薪资查询：`GET /careers/{id}/salary?city={city}`
- [ ] 6.5 实现大学 router：`GET /universities` 支持 `?tier=` 筛选
- [ ] 6.6 实现专业 router：`GET /majors`
- [ ] 6.7 实现五险一金计算端点：`POST /insurance/compute`（工资+城市→企业成本/到手）
- [ ] 6.8 实现录取数据查询端点（按省份+分数+科类筛选，空数据集不报错）

## 7. 单元测试（tests）

- [ ] 7.1 测试模型校验：各实体合法构造 + 非法构造（缺字段/区间倒挂/枚举非法）被拒绝
- [ ] 7.2 测试五险一金计算引擎：企业成本、到手工资、个税累进（含高工资跨档）
- [ ] 7.3 测试城市成本年化计算
- [ ] 7.4 测试种子加载：首次加载、幂等重复加载、损坏记录被拒绝
- [ ] 7.5 测试 API 端点：主要查询（含来源字段返回）、按层级筛选、五险一金计算端点
- [ ] 7.6 测试来源追溯全链路：种子→模型→DB→API 响应来源字段不丢失

## 8. 验证与文档

- [ ] 8.1 编写 `README.md`：项目简介、安装（`pip install -e .`）、启动 API（`uvicorn app.api.main:app`）、加载种子、运行测试说明
- [ ] 8.2 端到端验证：启动服务，用文档范例（深圳公务员/郑州成本）查询确认数字与来源正确
- [ ] 8.3 确认合规：全代码库无"保证就业/预测未来收入"措辞，数据均标注"基于历史数据模拟"
```

## openspec/changes/data-foundation/specs/admission-data-schema/spec.md

- Source: openspec/changes/data-foundation/specs/admission-data-schema/spec.md
- Lines: 1-40
- SHA256: be87a639bb654b9f2e3ecc1dcb35c24a9ac94bf228e69b41b7ad3a7cabaa9ea2

```md
## ADDED Requirements

### Requirement: 录取数据 Schema 定义（仅结构，不批量入库）

系统 SHALL 定义 `AdmissionRecord` 数据模型，描述高校历年录取数据结构，用于后续"根据考生分数筛选可报考大学"。字段 MUST 包含：学校、专业、省份、年份、科类（文/理/新高考选科组合）、最低录取分、最低录取位次、平均分、批次（一本/二本/提前批）。

本 change 仅定义 schema 与少量手编示例（3–5 校 × 2 省），不批量入库。批量历年分数线/位次数据归属后续独立 change（爬虫或公开数据集导入）。

模型 SHALL 继承来源追溯基类。

#### Scenario: 构造录取记录示例

- **WHEN** 用合法字段构造一条 AdmissionRecord
- **THEN** 实例化成功，含学校/专业/省份/年份/分数/位次

#### Scenario: 缺关键字段被拒绝

- **WHEN** 构造 AdmissionRecord 时省略省份或年份
- **THEN** 校验失败

### Requirement: 录取数据原始查询接口

系统 MUST 提供录取数据的**原始查询**接口：`GET /api/v1/admissions?province={省}&track={科类}&school={学校}`，仅返回匹配的原始录取记录，不做任何"按考生分数筛选可报考学校"的决策性计算。

**边界**：本层只提供原始数据存取。"根据考生分数筛选可报考大学、计算录取概率"属于决策逻辑，归属 decision-engine（change②）。本层接口 SHALL 只做字段匹配查询（省份/科类/学校等过滤），不做分数区间推断或院校推荐。

#### Scenario: 按省份科类原始查询

- **WHEN** GET /api/v1/admissions?province=河南&track=理科
- **THEN** 返回该省理科的原始录取记录列表（示例数据或空），每条含来源字段，不做分数筛选

#### Scenario: 空数据集查询不报错

- **WHEN** 录取数据表仅有示例数据，用户按某省查询
- **THEN** 接口正常返回（示例匹配或空列表），不抛异常

#### Scenario: schema 验证可用

- **WHEN** 后续 change 批量导入真实录取数据
- **THEN** 本 change 定义的 schema 可直接承接，无需重新建模
```

## openspec/changes/data-foundation/specs/career-data/spec.md

- Source: openspec/changes/data-foundation/specs/career-data/spec.md
- Lines: 1-31
- SHA256: cb25329a3086b666fd48b6e8db883691582dcfd9f16ab528240cc2adab6c2c59

```md
## ADDED Requirements

### Requirement: 职业数据模型定义

系统 SHALL 定义 `Career` 数据模型，字段包含：职业名称、职业类别（公务员/医生/教师/IT/外贸/国企等）、起薪、5 年中位薪资、15 年薪资上限、稳定性（0–1）、晋升速度（慢/中/快）、编制属性（行政编/事业编/企业/无）、关联学科列表。所有薪资字段 MUST 是区间（最低/最高）而非单点值，以反映真实分布。

模型 SHALL 继承来源追溯基类。

#### Scenario: 查询职业薪资曲线

- **WHEN** 查询"公务员-科员"职业
- **THEN** 返回起薪、5 年中位、15 年上限三个薪资区间，以及稳定性与编制属性

#### Scenario: 薪资区间校验

- **WHEN** 某薪资区间最低值大于最高值
- **THEN** 校验失败并报错

### Requirement: 职业种子数据覆盖代表性样本

系统 MUST 提供至少 15 个职业的种子数据，覆盖公务员、医生、教师、IT、外贸、跨境电商、国企、日企商务等类别。每条记录 MUST 标注数据来源（如"公开招聘报告/行业调研"）、采集时间、置信度，并附 `note` 标明"待爬虫校准"。

#### Scenario: 种子数据加载后可查询

- **WHEN** 加载职业种子数据到 SQLite 后查询全部职业
- **THEN** 返回 ≥15 条记录，每条均含完整薪资区间与来源字段

#### Scenario: 缺来源字段的种子被拒绝

- **WHEN** 某条职业种子数据缺少 source 字段
- **THEN** 加载校验失败，拒绝该条并报告具体记录
```

## openspec/changes/data-foundation/specs/city-cost-data/spec.md

- Source: openspec/changes/data-foundation/specs/city-cost-data/spec.md
- Lines: 1-42
- SHA256: 470e22abb10ea0ab4f469886ec64b486bfff9b8b8e6f3baf2009e2d992193aee

```md
## ADDED Requirements

### Requirement: 城市生活成本数据模型

系统 SHALL 定义 `CityCost` 模型，字段包含：城市名、租房均价（拆 3 档：单间/一房一厅/合租，均为区间）、吃饭成本（食堂/外卖均价）、通勤成本、其他（社交/杂费）、综合月生活成本、房价均价。所有成本字段 MUST 支持区间表示以反映真实波动。

模型 SHALL 继承来源追溯基类。

#### Scenario: 查询城市成本明细

- **WHEN** 查询深圳的城市成本
- **THEN** 返回租房 3 档区间、吃饭、通勤、其他及综合月成本

#### Scenario: 区间成本校验

- **WHEN** 某档租房区间最低 > 最高
- **THEN** 校验失败

### Requirement: 城市成本年化计算

系统 MUST 提供年成本计算：`年成本 = 12 × 月综合生活成本 + 学费 + 住宿费`（文档给定）。月综合成本为各分项中位值之和。

#### Scenario: 计算大学生年成本

- **WHEN** 给定深圳月成本区间与学费/住宿费
- **THEN** 输出年成本区间（用月成本中位 ×12 + 学费 + 住宿费）

### Requirement: 代表城市种子数据

系统 MUST 提供至少 7 个代表城市的种子数据，覆盖一线（深圳/北京/上海）与新一线/省会（郑州/成都/武汉/西安）。每条记录 MUST 标注来源（贝壳/58/小红书等）、采集时间、置信度，附"待爬虫校准"。

数值量级 SHALL 参考文档范例（如深圳一房一厅 1800、综合月成本 3500–6000）。

#### Scenario: 种子城市可对比

- **WHEN** 查询深圳与郑州的城市成本
- **THEN** 两者综合月成本差异显著（深圳高于郑州），体现"同专业不同城市生存压力"

#### Scenario: 缺来源城市种子被拒绝

- **WHEN** 某城市种子缺 as_of 字段
- **THEN** 加载失败并报告
```

## openspec/changes/data-foundation/specs/data-foundation-api/spec.md

- Source: openspec/changes/data-foundation/specs/data-foundation-api/spec.md
- Lines: 1-70
- SHA256: 8cb6a1f8e6723a518a0e5b0ba99cc6c6182d89caf8c9c201d97e2a6de4f8be4e

```md
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
```

## openspec/changes/data-foundation/specs/major-data/spec.md

- Source: openspec/changes/data-foundation/specs/major-data/spec.md
- Lines: 1-35
- SHA256: 9e8c305d9533d1a25dd48b9025013924a89ba015e75afdde8af0c13d50a5dbfc

```md
## ADDED Requirements

### Requirement: 专业实力数据模型

系统 SHALL 定义 `Major` 模型，承载文档的"专业评分"输入数据：
- **就业密度**：岗位数量、招聘频率、城市覆盖度
- **薪资分布**：MUST 用 P25（低）/P50（中位）/P75（高）三分位，而非平均值
- **门槛难度**：是否要求英语/数学/证书/考研
- **上升空间**：能否转管理岗/自由职业/跨行业

模型 SHALL 继承来源追溯基类。

#### Scenario: 查询专业薪资分布

- **WHEN** 查询"日语"专业
- **THEN** 返回 P25/P50/P75 三个薪资分位，而非单一平均值

#### Scenario: 门槛要求结构化

- **WHEN** 查询某专业的门槛难度
- **THEN** 返回各门槛项的布尔/枚举（如 requires_english: true）

### Requirement: 专业种子数据

系统 MUST 提供至少 15 个专业种子数据，覆盖文科（含日语/国际经济与贸易/历史等文档重点方向）与理工科。薪资分布 SHALL 标注来源（BOSS/智联等公开报告量级）、采集时间、置信度，附"待爬虫校准"。

#### Scenario: 种子专业含薪资三分位

- **WHEN** 加载专业种子后查询任一专业
- **THEN** 返回完整 P25/P50/P75 与就业密度、门槛、上升空间字段

#### Scenario: 用平均值代替三分位被拒绝

- **WHEN** 某专业种子只填了平均薪资而无 P25/P50/P75
- **THEN** 校验失败（强制三分位分布）
```

## openspec/changes/data-foundation/specs/social-insurance-model/spec.md

- Source: openspec/changes/data-foundation/specs/social-insurance-model/spec.md
- Lines: 1-53
- SHA256: 1b9075580b71de2e57bd9ee04701c95f0b1ec446cccfb56d0ba9c0e7df09a9ce

```md
## ADDED Requirements

### Requirement: 五险一金统一用工成本模型

系统 SHALL 定义 `SocialInsurance` 模型，按文档"总用工成本模型"标准化。模型 MUST 包含五险一金各险种的个人与单位缴纳比例：养老、医疗、失业、工伤、生育、公积金。比例 MUST 支持按城市调参（因为文档指出"城市差异不是结构，而是比例范围"）。

全国基准比例初始化 SHALL 采用文档给定结构：养老 8%/16%、医疗 2%/8–10%、失业 0.3%/0.5%、工伤 0%/0.5%、公积金 5–12%/5–12%。

#### Scenario: 构造城市社保模型

- **WHEN** 用深圳的单位比例集合构造一个城市的 SocialInsurance
- **THEN** 各险种比例可分别读取，合计单位比例可计算

#### Scenario: 比例越界校验

- **WHEN** 某险种比例超过 1.0（100%）
- **THEN** 校验失败

### Requirement: 总用工成本计算引擎

系统 MUST 提供纯函数计算引擎，实现文档给定公式：

```
企业成本 = 工资 × (1 + 五险一金单位部分比例合计)
到手工资 = 工资 - 个人五险一金 - 个税
```

函数 MUST 接受工资与城市社保模型作为输入，输出企业成本与到手工资。个税 SHALL 使用 **2024 年个人所得税完整累进税率表**计算：起征点 5000 元/月，7 档累进税率（3% / 10% / 20% / 25% / 30% / 35% / 45%）。应纳税所得额 = 工资 − 个人五险一金 − 起征点 5000 − 专项附加扣除。引擎 SHALL 预留专项附加扣除参数（首版可选填，默认 0）。

#### Scenario: 计算企业用工成本

- **WHEN** 输入工资 9000、深圳单位比例合计 0.35
- **THEN** 企业成本 = 9000 × 1.35 = 12150

#### Scenario: 计算到手工资

- **WHEN** 输入工资 9000、个人比例 0.12、按 2024 累进税率算个税
- **THEN** 到手 = 9000 - (9000×0.12) - 个税，结果为正且符合税率表

#### Scenario: 个税累进计算正确性

- **WHEN** 输入高工资（如 30000）触发更高税率档
- **THEN** 个税按对应档位累进计算，而非单一比例

#### Scenario: 个税档位边界值

- **WHEN** 应纳税所得额正好处于税率档边界（如 3000、12000 等临界点）
- **THEN** 个税按对应档位正确计算，边界归属无歧义

#### Scenario: 专项附加扣除参数

- **WHEN** 输入工资并传入专项附加扣除金额（如 2000）
- **THEN** 应纳税所得额扣除该金额后再累进计税；不传则默认 0
```

## openspec/changes/data-foundation/specs/student-profile-data/spec.md

- Source: openspec/changes/data-foundation/specs/student-profile-data/spec.md
- Lines: 1-38
- SHA256: 523c2db9a6ff8189cf8648f1e247f9b935ddead3dfa0b9e25cddad16f8d7b340

```md
## ADDED Requirements

### Requirement: 考生画像数据模型定义

系统 SHALL 定义 `StudentProfile` 数据模型，承载"根据考生情况模拟填报志愿"的完整输入结构。模型 MUST 包含以下字段：总分（数值）、省份（决定分数线基准）、偏科科目真实分数（`subject_scores: dict[str,int]`，键为科目名如"数学"/"英语"/"理综"，值为该科高考真实分数）、小语种能力（语种 + 等级如日语 N2/N1）、家庭体制资源（6 个布尔位）、性别、个人兴趣（标签列表）、强项（标签列表）、风险偏好（稳/中/冲三档枚举）。

家庭体制资源 MUST 用 6 个布尔字段表达：`has_govt_resource`（体制内/公务员/事业编）、`has_medical_resource`（医生/医疗系统）、`has_education_resource`（教师/教育系统）、`has_finance_resource`（银行/金融/证券）、`has_law_resource`（法律/司法系统）、`has_business_resource`（企业主/商业/外贸）。

模型 SHALL 继承来源追溯基类，包含 `source`/`as_of`/`confidence` 字段，因为画像输入本身也是需要记录的"数据"。

#### Scenario: 构造完整考生画像

- **WHEN** 用合法字段构造一个 StudentProfile（如总分 450、省份河南、subject_scores={数学:120,英语:75}、has_education_resource=true）
- **THEN** 模型实例化成功，所有必填字段已填充，来源字段存在

#### Scenario: 缺失必填字段被拒绝

- **WHEN** 构造 StudentProfile 时省略省份或总分
- **THEN** 校验失败并抛出明确错误，指出缺失字段

#### Scenario: 风险偏好取值约束

- **WHEN** 风险偏好传入非法值（如 "unknown"）
- **THEN** 校验失败，仅接受稳/中/冲三档之一

### Requirement: 偏科分数支持文理两种模式

系统 MUST 支持两种偏科结构：传统文理分科（语文/数学/英语/文综 或 语文/数学/英语/理综）与新高考选科。模型 SHALL 用足够灵活的结构承载，不丢失任何一科分数。

#### Scenario: 传统理科考生

- **WHEN** 录入语文/数学/英语/理综四科分数
- **THEN** 模型正确存储并可按单科查询

#### Scenario: 新高考选科考生

- **WHEN** 录入语文/数学/英语 + 三门选科分数
- **THEN** 模型正确存储三门选科及其分数
```

## openspec/changes/data-foundation/specs/university-data/spec.md

- Source: openspec/changes/data-foundation/specs/university-data/spec.md
- Lines: 1-36
- SHA256: 8873a380b2104946e7b33dfdae299cbb6b5b9ade46f1ed72e834607df177b178

```md
## ADDED Requirements

### Requirement: 大学三维实力数据模型

系统 SHALL 定义 `University` 模型，承载文档的"三维评分"输入数据：
- **学校层级**（基础层）：985/211/双一流/普通一本/二本/专科
- **就业能力**（核心层）：校招企业层级（是否有央企/大厂）、平均起薪（分城市）、就业率（需做"真实就业率"修正标注）
- **学科实力**（关键差异）：教育部学科评估（A+/A/B 等）、国家重点学科、双一流建设学科

模型 SHALL 继承来源追溯基类。

#### Scenario: 查询大学三维数据

- **WHEN** 查询某 211 大学
- **THEN** 返回层级、就业能力指标、学科评估列表

#### Scenario: 就业率修正标注

- **WHEN** 大学的官方就业率字段存在但可信度存疑
- **THEN** 该字段 confidence 较低且 note 标注"官方数据可能有水分"

### Requirement: 大学种子数据

系统 MUST 提供一定数量（≥10）代表大学种子数据，覆盖各层级（至少含 985/211/双一流/普通一本各样本）。每条 MUST 标注来源（教育部双一流名单/学校就业报告）、采集时间、置信度。

学科评估数据 SHALL 使用教育部第四轮（公开版），并在 note 标注轮次。

#### Scenario: 按层级筛选大学

- **WHEN** 查询所有 211 层级大学
- **THEN** 返回符合条件的大学列表，含学科评估

#### Scenario: 缺层级大学种子被拒绝

- **WHEN** 某大学种子未填层级
- **THEN** 加载失败
```

