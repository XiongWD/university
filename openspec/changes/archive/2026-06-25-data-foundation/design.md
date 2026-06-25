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

**理由**：
- 纯函数易测试（输入工资+比例→输出成本），无副作用。
- 文档要求"标准化公式"且"城市差异只是比例范围"——把比例作为参数注入，引擎本身固定。
- 这是"计算"而非"决策"，放在数据层（提供能力）而非引擎层（做路径推演）。后续 engine 可调用本引擎算"到手收入"。

**公式**（文档给定）：
```
企业成本 = 工资 × (1 + 五险一金单位部分比例合计)
到手工资 = 工资 - 个人五险一金 - 个税
```

### D5: 来源追溯作为模型基类约束

**选择**：定义 `SourcedRecord` 基类（Pydantic），含 `source: str`、`as_of: date`、`confidence: float`（0–1）、`note: str | None`。所有种子记录继承。

**理由**：
- 信任是产品核心壁垒，来源不能是"可选字段"——校验在模型层强制，加载层与 API 层双重保证。
- `confidence` 量化"这个数字有多可信"（手编种子低、官方数据高），前端可据此显示标注。
- 单点定义，六类实体自动获得追溯能力。

### D6: 包结构

```
人生经济模型模拟器/
├── app/
│   ├── __init__.py
│   ├── models/              # Pydantic + SQLModel 数据模型
│   │   ├── base.py          # SourcedRecord 基类
│   │   ├── student.py       # StudentProfile
│   │   ├── career.py
│   │   ├── insurance.py
│   │   ├── city.py
│   │   ├── university.py
│   │   ├── major.py
│   │   └── admission.py     # 仅 schema
│   ├── engine/              # 纯计算引擎
│   │   └── insurance.py     # 五险一金计算
│   ├── loader/              # YAML → SQLite
│   │   └── seed_loader.py
│   ├── db.py                # SQLite 引擎与 Session
│   └── api/                 # FastAPI 路由
│       ├── main.py
│       └── routers/
├── data/
│   └── seed/                # YAML 种子（事实来源）
│       ├── cities/
│       ├── careers/
│       ├── universities/
│       └── majors/
├── tests/
├── data/llm_sim.db          # gitignore，加载生成
└── pyproject.toml
```

**理由**：`models` / `engine` / `loader` / `api` 分层清晰，每层可独立测试；`data/seed` 与代码分离，符合"种子可人工维护"目标。

### D7: API 设计——按实体分组，统一来源返回

**选择**：每个实体一个 router，返回响应统一用 Pydantic 包装（数据 + 来源）。例：
```
GET /api/v1/careers/{id}              → Career + source 字段
GET /api/v1/cities/{city}/cost        → CityCost
GET /api/v1/careers/{id}/salary?city=深圳 → 薪资分布 + 该城五险一金
GET /api/v1/insurance/compute         → POST 工资+城市，返回企业成本/到手
```

**理由**：RESTful 按实体分组，与前端组件天然对应；查询参数化（城市/经验）支撑 engine 复用。

## Risks / Trade-offs

- **[种子数据失真]** 手编数据可能偏离真实市场 → 缓解：每个数字标注 `confidence`（手编 ≤0.6）与 `note: "待爬虫校准"`；`as_of` 记录编制日期；后续爬虫 change 替换时按 `source` 字段比对。
- **[种子数据维护成本随规模爆炸]** 城市×职业×经验组合爆炸 → 缓解：D2 用 YAML 模板化（职业定义薪资曲线比例，城市定义基数），引擎组合计算而非全量预存；首版限定 7 城/15 职业。
- **[SQLite 并发与迁移]** 未来生产可能需 PG → 缓解：查询层抽象（Repository 模式），SQLModel 可切换引擎；MVP 单机无并发问题。
- **[合规风险：被误解为"预测未来收入"]** → 缓解：所有薪资字段命名含"预期/历史区间"，API 响应与前端标注"基于历史数据模拟"；不出现"保证/确切"措辞（见 proposal 合规项）。
- **[录取数据 schema 定义后长期空置]** 仅 schema 无数据可能导致后续 engine 无从消费 → 缓解：本 change 提供少量手编示例（3–5 校×2 省），验证 schema 可用；批量入库明确归属后续 change。
- **[Pydantic v2 与 SQLModel 版本耦合]** SQLModel 对 Pydantic v2 支持需确认 → 缓解：锁定兼容版本组合，CI 验证。

## Open Questions

1. **省份-分数线映射粒度**：录取数据 schema 中"省份"是否需细化到文理科分开？建议是（高考分文理/新高考选科），待 tasks 阶段细化。
2. **个税计算精度**：到手工资公式含个税，首版是否实现完整累进税率表？建议实现（公式固定、易测），用 2024 税率表。
3. **大学学科评估数据来源**：教育部第五轮学科评估未完全公开，是否用第四轮（公开）+ 标注？建议第四轮 + `note`。
