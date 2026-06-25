---
comet_change: data-foundation
role: technical-design
canonical_spec: openspec
---

# Design Doc: data-foundation

人生经济模型模拟器三层架构的**数据底座层**。本设计基于 OpenSpec 产物（proposal/design/specs）经 brainstorming 确认后定稿。

## 1. 背景与目标

产品是面向高考生及家长的「人生经济模型模拟器」，把模糊的高考志愿决策变成可追溯的数字决策。分三层独立推进：

```
① data-foundation（本 change）   数据底座：模型 + 种子 + 来源追溯 + 查询 API + 纯计算
② decision-engine（后续 change）  评分模型 + 3 条路径推演 + 城市生存模型
③ web-ui（后续 change）           Vite+React 精致 UI + 路径卡片 + 收入曲线
```

**本层目标**：建立结构化、可扩展、带来源追溯的数据底座，覆盖六类实体，为 engine 和 ui 提供可信的"数字底座"。

**严格边界**：data-foundation 只做"查询 / 存取 / 纯计算"（五险一金、年成本、个税）。所有"根据考生画像评分 / 筛选可报大学 / 推演路径"的决策逻辑归属 decision-engine。

## 2. 技术栈

Python 3.13 · FastAPI · Pydantic v2 · SQLModel · SQLite · PyYAML · pytest · httpx

## 3. 分层架构（方案 B：双模型 + 映射层）

经 brainstorming 对比三个方案后选定方案 B。核心理由：数据天然有嵌套结构（薪资三档区间、租房三档、学科评估列表），SQLModel 单模型处理嵌套需拍平（丢类型）或 JSON 列（丢查询）；纯 Pydantic+JSON 查询能力弱。方案 B 让各层各司其职。

```
┌─────────────────────────────────────────────────────────────┐
│                    data-foundation 分层                      │
└─────────────────────────────────────────────────────────────┘

  YAML 种子 (事实来源)          FastAPI 请求
  data/seed/*.yaml                  │
       │                            ▼
       ▼                      ┌──────────┐
  ┌──────────┐    校验写入    │ api 层   │  routers/ (按实体分组)
  │ loader   │──────────────▶│          │  响应带 source/as_of/confidence
  │          │  Domain 校验   └────┬─────┘
  └──────────┘                     │ 读取
       │ Domain 模型校验            ▼
       ▼                      ┌──────────┐
  ┌──────────┐                │repository│  Table↔Domain 映射
  │ Domain   │◀───────────────│          │  (CareerRow↔CareerRead)
  │ (Pydantic│   重组嵌套      └────┬─────┘
  │  含嵌套)  │                     │ SQL
  └──────────┘                     ▼
                              ┌──────────┐
                              │ SQLite   │  Table 模型 (SQLModel, 拍平)
                              │ llm_sim  │  careers/cities/...
                              └──────────┘

  ┌──────────┐
  │ engine   │  纯函数计算（无 DB 依赖）
  │ insurance│  compute_total_labor_cost / compute_take_home_pay
  └──────────┘
```

### 各层职责

| 层 | 位置 | 模型类型 | 职责 |
|----|------|----------|------|
| Domain | `app/models/` | Pydantic v2（含嵌套） | YAML 校验 + API 响应。继承 SourcedRecord 基类。保留嵌套结构（薪资三档、租房三档、学科评估列表）|
| Table | 同 models 文件 | SQLModel `table=True` | 字段拍平存储。纯持久化，不做业务。易索引。|
| Repository | `app/repositories/` | — | Table Row ↔ Domain Read 映射。集中重组嵌套/拍平逻辑，可独立测试。|
| Loader | `app/loader/` | — | YAML → Domain（校验来源字段）→ Table Row（幂等 upsert）。|
| Engine | `app/engine/` | 纯函数 | 五险一金、年成本、个税累进计算。输入 Domain 模型，输出数值。无 DB 依赖。|

## 4. 数据模型设计

### 4.1 来源追溯基类 `SourcedRecord`（所有实体继承）

```python
source: str          # 数据来源（"教育部学科评估第四轮"/"贝壳租房2024"）
as_of: date          # 数据采集/发布日期
confidence: float    # 0.0–1.0（手编种子≤0.6，官方数据≥0.8）
note: str | None     # 备注（"待爬虫校准"/"官方可能有水分"）
```

来源追溯贯穿全链路：YAML 种子 → Domain 校验（Pydantic 强制）→ SQLite 存储 → API 响应。任何环节丢失来源字段视为缺陷。

### 4.2 六类实体 + 录取 schema

**① StudentProfile（考生画像）** — 模拟填报的核心输入

```python
province: str                        # 省份（分数线基准）
total_score: int                     # 高考总分
subject_scores: dict[str, int]       # 真实科目分数 {数学:120, 英语:75, 理综:200}
minor_language: {lang, level} | None # 小语种（日语/N2）
family_resources: {                  # 6 个布尔位
  has_govt_resource: bool,           #   体制内/公务员/事业编
  has_medical_resource: bool,        #   医生/医疗系统
  has_education_resource: bool,      #   教师/教育系统
  has_finance_resource: bool,        #   银行/金融/证券
  has_law_resource: bool,            #   法律/司法系统
  has_business_resource: bool}       #   企业主/商业/外贸
gender: str
interests: list[str]
strengths: list[str]
risk_preference: enum                # 稳/中/冲
```

**② Career（职业）** — 含嵌套薪资区间

```python
SalaryBand: {low: int, mid: int, high: int}   # 区间（非单点）
name, category                               # 名称/类别(公务员/IT/外贸/国企...)
entry_salary: SalaryBand                     # 起薪区间
mid_salary_5y: SalaryBand                    # 5 年中位
ceil_salary_15y: SalaryBand                  # 15 年上限
stability: float                             # 0–1
promotion_speed: enum                        # 慢/中/快
establishment_type: enum                     # 行政编/事业编/企业/无
related_majors: list[str]
```

**③ SocialInsurance（五险一金）** — 按城市

```python
city: str
rates: {养老/医疗/失业/工伤/生育/公积金 各 {employee: float, employer: float}}  # 比例 0–1
# + TAX_BRACKETS_2024 常量（7 档累进，起征点 5000）
```

**④ CityCost（城市成本）** — 含嵌套租房三档

```python
RentTiers: {single: Band, one_bed: Band, shared: Band}  # 租房 3 档区间
city: str
rent: RentTiers
food: Band; commute: Band; other: Band        # 吃饭/通勤/其他(区间)
monthly_total: Band                            # 综合月成本
house_price_avg: int                           # 房价均价
```

**⑤ University（大学三维）**

```python
tier: enum                       # 985/211/双一流/一本/二本/专科
employment_ability: {            # 就业能力
  campus_tier, avg_entry_salary, employment_rate}
disciplines: list[{name, grade}] # 学科评估（A+/A/B...）
```

**⑥ Major（专业三分位）**

```python
employment_density: {jobs, frequency, city_coverage}  # 就业密度
salary: {p25: int, p50: int, p75: int}                # 强制三分位，禁平均值
barriers: {english, math, certificate, postgrad}      # 门槛
upside: {management, freelance, cross_industry}       # 上升空间
```

**+ AdmissionRecord（仅 schema，不批量入库）**

```python
school, major, province, year, track(文/理/选科), min_score, min_rank, avg_score, batch
```

## 5. 计算引擎（纯函数）

### 5.1 五险一金（文档给定公式）

```python
compute_total_labor_cost(salary: int, insurance: SocialInsurance) -> int:
    employer_rate = sum(各险种 employer 比例)
    return salary * (1 + employer_rate)          # 企业成本

compute_take_home_pay(salary, insurance, special_deduction=0) -> int:
    personal = salary * sum(各险种 employee 比例)
    taxable = salary - personal - 5000 - special_deduction
    tax = progressive_tax(taxable)               # 2024 七档累进
    return salary - personal - tax               # 到手工资
```

### 5.2 城市成本年化

```python
compute_annual_cost(city_cost, tuition, accommodation) -> Band:
    monthly_mid = (monthly_total.low + monthly_total.high) / 2
    return 12 * monthly_mid + tuition + accommodation
```

## 6. API 设计（按实体分组）

```
GET  /api/v1/careers[?category=]           # 职业列表
GET  /api/v1/careers/{id}                  # 职业详情（薪资三档区间）
GET  /api/v1/cities                        # 城市列表
GET  /api/v1/cities/{city}/cost            # 城市成本明细
POST /api/v1/insurance/compute             # 五险一金计算（工资+城市→企业成本/到手）
GET  /api/v1/universities[?tier=211]       # 大学（按层级筛选）
GET  /api/v1/majors                        # 专业（P25/P50/P75）
GET  /api/v1/admissions[?province=&track=] # 录取数据（仅原始查询，筛选归 engine②）
GET  /api/v1/health                        # 健康检查 + 种子加载状态
```

所有响应继承 SourcedRecord，来源字段天然出现在 JSON。启动时若 DB 空则自动加载种子。

## 7. 包结构

```
人生经济模型模拟器/
├── app/
│   ├── __init__.py
│   ├── config.py                  # DB 路径、种子目录、API 版本前缀
│   ├── models/                    # Domain (Pydantic) + Table (SQLModel)
│   │   ├── base.py                # SourcedRecord 基类
│   │   ├── student.py / career.py / insurance.py
│   │   ├── city.py / university.py / major.py / admission.py
│   ├── repositories/              # Table↔Domain 映射
│   ├── engine/                    # 纯计算
│   │   └── insurance.py
│   ├── loader/                    # YAML → Domain → SQLite
│   │   └── seed_loader.py
│   ├── db.py                      # SQLite 引擎 + Session
│   └── api/
│       ├── main.py
│       └── routers/
├── data/seed/                     # YAML 种子（事实来源）
│   ├── cities/ careers/ universities/ majors/ admissions/
├── tests/
├── data/llm_sim.db                # gitignore
└── pyproject.toml
```

## 8. 测试策略

| 层 | 测试内容 |
|----|----------|
| models | 各实体合法构造；非法构造被拒（缺字段/区间倒挂/枚举非法/confidence>1）；嵌套对象完整 |
| engine | 企业成本公式；到手工资（低/中/高跨档）；个税 7 档边界值；年成本公式 |
| loader | YAML→Domain→Table 全流程；幂等重复加载；损坏记录被拒并报告 |
| api | GET 各端点返回来源字段；?tier= 筛选；POST /insurance/compute 计算正确 |
| 追溯链路 | 种子→模型→DB→响应来源字段全链路不丢失 |

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 种子数据失真 | confidence≤0.6 手编 + note"待爬虫校准" + as_of 日期；后续爬虫按 source 比对替换 |
| 嵌套对象拍平丢类型 | 方案 B：Domain 保嵌套，Table 仅存储，Repository 重组 |
| SQLModel×Pydantic v2 兼容 | 锁定 pydantic≥2.5 + sqlmodel≥0.0.16，CI 验证 |
| 合规（被误解为预测） | 字段命名"预期/历史区间"，标注"基于历史数据模拟"，无"保证/预测"措辞 |
| 数据组合爆炸 | YAML 模板化：职业存薪资比例曲线，城市存基数，引擎组合计算 |

## 10. Spec Patch 回写

brainstorming 确认后已回写以下 delta spec：
1. `student-profile-data/spec.md`：偏科改 `subject_scores` 真实分数；家庭资源改 6 布尔位
2. `admission-data-schema/spec.md`：移除"按分数筛选"决策查询，改为"仅原始录取数据查询"
3. `social-insurance-model/spec.md`：明确 2024 累进税率表 7 档 + 起征点 5000 + 专项扣除接口

## 11. 待解决问题（implementation 阶段细化，不阻塞设计）

- 录取数据 schema 的"科类"是否需细化到新高考选科组合（建议支持，track 字段用自由字符串）
- 学科评估数据用第四轮（公开）+ note 标注轮次
