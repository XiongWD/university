---
change: data-foundation
design-doc: docs/superpowers/specs/2026-06-25-data-foundation-design.md
base-ref: ea5430bea61df1a52017179387b3d763e63c31d2
---

# data-foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行本计划。步骤使用复选框语法进行跟踪（已完成项标记为已勾选）。

**Goal:** 为「人生经济模型模拟器」建立结构化、可扩展、带来源追溯的数据底座层，覆盖六类实体（考生画像/职业/五险一金/城市成本/大学/专业）+ 录取 schema，并暴露查询与纯计算 API，为后续 decision-engine 与 web-ui 提供可信数字底座。

**Architecture:** 方案 B 双模型分层。Domain 层用 Pydantic v2（含嵌套结构，继承 `SourcedRecord` 基类）做 YAML 校验与 API 响应；Table 层用 SQLModel `table=True` 拍平存储；Repository 层集中 Table↔Domain 映射；Loader 负责 YAML→Domain（校验来源字段）→Table（幂等 upsert）；Engine 为纯函数（五险一金 + 2024 个税累进 + 城市成本年化），无 DB 依赖。

**Tech Stack:** Python 3.13 · FastAPI · Pydantic v2（≥2.5）· SQLModel（≥0.0.16）· SQLAlchemy · SQLite · PyYAML · pytest · httpx

## Global Constraints

- Python 版本锁 3.13；依赖下限：`pydantic>=2.5`、`sqlmodel>=0.0.16`（缓解 SQLModel×Pydantic v2 兼容风险）。
- 来源追溯字段（`source`/`as_of`/`confidence`/`note`）从 YAML 种子 → Domain 校验 → SQLite 存储 → API 响应全链路不丢失；任何环节丢失视为缺陷。
- `confidence` 取值范围强制 `[0.0, 1.0]`；手编种子 `confidence ≤ 0.6` 且 `note` 含「待爬虫校准」。
- 所有「区间」字段（薪资三档、租房三档、各成本分项）必须满足 `low ≤ mid ≤ high`（或 `low ≤ high`），倒挂即校验失败。
- 专业薪资强制 P25/P50/P75 三分位，禁用平均值字段。
- 录取 schema 仅定义结构 + 少量示例，不批量入库；本层只做原始字段匹配查询，不做分数筛选/院校推荐（归属 decision-engine）。
- 个税使用 2024 月度累进税率表，起征点 5000，7 档（3/10/20/25/30/35/45%）。
- 合规：全代码库与种子不得出现「保证就业/预测未来收入」措辞；数据标注「基于历史数据模拟」。

## File Structure

```
人生经济模型模拟器/
├── pyproject.toml                       # 依赖声明 + 工具配置
├── app/
│   ├── __init__.py
│   ├── config.py                        # DB 路径 / 种子目录 / API 版本前缀
│   ├── db.py                            # SQLite 引擎 + Session 工厂 + create_all
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                      # SourcedRecord 基类 + CostBand(low,high)
│   │   ├── student.py                   # StudentProfile(Domain)
│   │   ├── career.py                    # Career + SalaryBand
│   │   ├── insurance.py                 # SocialInsurance + 全国基准
│   │   ├── city.py                      # CityCost + RentTiers
│   │   ├── university.py                # University
│   │   ├── major.py                     # Major
│   │   ├── admission.py                 # AdmissionRecord
│   │   └── tables.py                    # 六类 Table SQLModel 拍平定义
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── mappers.py                   # Table↔Domain 映射（六类实体）
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── insurance.py                 # 累进个税 + 企业成本 + 到手工资
│   │   └── cost.py                      # 城市成本年化
│   ├── loader/
│   │   ├── __init__.py
│   │   └── seed_loader.py               # YAML→Domain→Table（幂等 upsert）
│   └── api/
│       ├── __init__.py
│       ├── main.py                      # FastAPI app + /api/v1 前缀 + 启动加载 + /health
│       └── routers/
│           ├── __init__.py
│           ├── careers.py
│           ├── cities.py
│           ├── insurance.py
│           ├── universities.py
│           ├── majors.py
│           └── admissions.py
├── data/seed/                           # YAML 种子（事实来源）
│   ├── cities/ careers/ universities/ majors/ admissions/ insurance/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # tmp DB / TestClient fixtures
│   ├── models/
│   ├── engine/
│   ├── repositories/
│   ├── loader/
│   └── api/
└── README.md
```

**分解决策**：模型按实体分文件；Repository 集中映射逻辑单独可测；Engine 拆为 insurance/cost 两个纯函数模块；API 按实体分 router。TDD 顺序：models/engine（纯单元测试）→ db/repository → loader → seeds → api → 集成。

---

### Task 1: 项目脚手架与配置

**Files:** Create: `pyproject.toml`, `app/__init__.py`, `app/config.py`, 各包 `__init__.py`, `tests/__init__.py`

**Interfaces:** Produces `app.config.settings`（`db_path`/`seed_dir`/`api_prefix`/`db_url`）。

- [x] **Step 1: 创建 `pyproject.toml`**（fastapi/uvicorn/pydantic>=2.5/sqlmodel>=0.0.16/sqlalchemy/pyyaml + dev pytest/httpx；pytest 配置 pythonpath=["."]）
- [x] **Step 2: 创建 `app/config.py`**（Settings 类 + PROJECT_ROOT/DATA_DIR/SEED_DIR/DB_PATH 常量 + db_url 属性）
- [x] **Step 3: 创建所有空 `__init__.py`**（app/ 及子包、tests/）
- [x] **Step 4: 安装并验证导入** — Run `pip install -e ".[dev]"`；`python -c "from app.config import settings; print(settings.db_url)"` 无报错
- [x] **Step 5: 验证 pytest 可运行** — Run `pytest -q` 退出码 0/5 无收集错误
- [x] **Step 6: Commit** — `chore: 搭建 data-foundation 包结构与配置`

---

### Task 2: SourcedRecord 基类与 CostBand

**Files:** Create `app/models/base.py`; Test `tests/models/test_base.py`

**Interfaces:** `SourcedRecord`（source/as_of/confidence∈[0,1]/note）；`CostBand(low,high)` 强制 low≤high。

- [x] **Step 1: 写失败测试** — 合法构造、confidence>1 拒绝、CostBand 合法/倒挂拒绝
- [x] **Step 2: 运行确认失败** — `pytest tests/models/test_base.py -q` ModuleNotFoundError
- [x] **Step 3: 写实现** — BaseModel + field_validator(confidence) + model_validator(CostBand low≤high)
- [x] **Step 4: 运行确认通过** — 4 测试 PASS
- [x] **Step 5: Commit** — `feat(models): SourcedRecord 基类与 CostBand 区间校验`

---

### Task 3: StudentProfile 考生画像模型

**Files:** Create `app/models/student.py`; Test `tests/models/test_student.py`

**Interfaces:** 消费 `SourcedRecord`；产出 `StudentProfile`（province/total_score/subject_scores:dict/MinorLanguage|None/FamilyResources 6 布尔位/gender/interests/strengths/RiskPreference 枚举 稳/中/冲）。

- [x] **Step 1: 写失败测试** — 传统理综、新高考 6 科、缺 province 拒绝、非法 risk_preference 拒绝、minor_language 可选
- [x] **Step 2: 运行确认失败**
- [x] **Step 3: 写实现** — RiskPreference(str,Enum)/MinorLanguage/FamilyResources(6 bool)/StudentProfile(SourcedRecord)
- [x] **Step 4: 运行确认通过** — 5 测试 PASS
- [x] **Step 5: Commit** — `feat(models): StudentProfile 考生画像（6 家庭资源布尔位）`

---

### Task 4: Career 职业模型（含 SalaryBand）

**Files:** Create `app/models/career.py`; Test `tests/models/test_career.py`

**Interfaces:** `SalaryBand(low,mid,high)` 强制 low≤mid≤high；`Career(SourcedRecord)`（name/category/entry_salary/mid_salary_5y/ceil_salary_15y/stability∈[0,1]/promotion_speed/establishment_type/related_majors）。枚举 PromotionSpeed(慢/中/快)、EstablishmentType(行政编/事业编/企业/无)。

- [x] **Step 1: 写失败测试** — 合法、SalaryBand 倒挂拒绝、stability>1 拒绝、非法 establishment 拒绝
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(models): Career 职业模型（SalaryBand 三档区间校验）`

---

### Task 5: SocialInsurance 五险一金模型 + 全国基准

**Files:** Create `app/models/insurance.py`; Test `tests/models/test_insurance.py`

**Interfaces:** `RatePair(employee,employer)` 各 [0,1]；`InsuranceRates`（pension/medical/unemployment/work_injury/maternity/housing_fund）；`SocialInsurance(SourcedRecord)`（city/rates）；常量 `NATIONAL_BASELINE_RATES`（养老8/16、医疗2/9、失业0.3/0.5、工伤0/0.5、生育0/0、公积金8/8）。

- [x] **Step 1: 写失败测试** — RatePair 合法/越界拒绝、SocialInsurance 合计、基准单位比例合计 0.2~0.6
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(models): SocialInsurance 五险一金模型 + 全国基准比例`

---

### Task 6: CityCost 城市成本模型（含 RentTiers）

**Files:** Create `app/models/city.py`; Test `tests/models/test_city.py`

**Interfaces:** 消费 `CostBand`；`RentTiers(single,one_bed,shared)`；`CityCost(SourcedRecord)`（city/rent/food/commute/other/monthly_total/house_price_avg）。

- [x] **Step 1: 写失败测试** — 合法、rent 倒挂拒绝
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(models): CityCost 城市成本模型（租房三档区间）`

---

### Task 7: University 大学三维模型

**Files:** Create `app/models/university.py`; Test `tests/models/test_university.py`

**Interfaces:** 枚举 UniversityTier(985/211/双一流/一本/二本/专科)；`EmploymentAbility(campus_tier/avg_entry_salary/employment_rate)`；`Discipline(name,grade)`；`University(SourcedRecord)`。

- [x] **Step 1: 写失败测试** — 合法、非法 tier 拒绝、低 confidence 就业率存疑标注
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(models): University 大学三维模型`

---

### Task 8: Major 专业三分位模型

**Files:** Create `app/models/major.py`; Test `tests/models/test_major.py`

**Interfaces:** `EmploymentDensity(jobs/frequency/city_coverage)`；`SalaryQuantile(p25,p50,p75)` 三者皆必填；`Barriers/Upside`；`Major(SourcedRecord)` 用 `ConfigDict(extra="forbid")` 拒绝 avg 等平均值字段。

- [x] **Step 1: 写失败测试** — 合法、缺 p75 拒绝、avg 字段被拒
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(models): Major 专业模型（强制 P25/P50/P75 三分位）`

---

### Task 9: AdmissionRecord 录取 schema

**Files:** Create `app/models/admission.py`; Test `tests/models/test_admission.py`

**Interfaces:** 枚举 Batch(一本/二本/提前批)；`AdmissionRecord(SourcedRecord)`（school/major/province/year/track 自由字符串/min_score/min_rank/avg_score/batch）。仅 schema + 示例。

- [x] **Step 1: 写失败测试** — 合法、缺 province/year 拒绝、新高考选科自由字符串
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(models): AdmissionRecord 录取 schema`

---

### Task 10: Engine — 个税累进 + 五险一金计算

**Files:** Create `app/engine/insurance.py`; Test `tests/engine/test_insurance.py`

**Interfaces:** 常量 `TAX_BRACKETS_2024`（7 档，速算扣除 0/210/1410/2660/4410/7160/15160）；`progressive_tax(taxable)`；`compute_total_labor_cost(salary,insurance)`；`compute_take_home_pay(salary,insurance,special_deduction=0)`。单位/个人比例合计用 model_fields 遍历，避免硬编码字段名。

- [x] **Step 1: 写失败测试** — 3%档(2920→87.6)、边界3000归3%档、20%档(21400→2870)、零/负→0、企业成本公式、到手为正且等于公式、专项扣除使到手更高、7档存在
- [x] **Step 2-4: 失败→实现→通过** — 8 测试 PASS
- [x] **Step 5: Commit** — `feat(engine): 五险一金企业成本/到手工资 + 2024 七档累进个税`

---

### Task 11: Engine — 城市成本年化

**Files:** Create `app/engine/cost.py`; Test `tests/engine/test_cost.py`

**Interfaces:** `compute_annual_cost(city_cost,tuition,accommodation)->CostBand`（12×月综合成本中位 + 学费 + 住宿；中位法单值 low==high）。

- [x] **Step 1: 写失败测试** — 年成本 = 12×((low+high)/2)+学费+住宿
- [x] **Step 2-4: 失败→实现→通过**
- [x] **Step 5: Commit** — `feat(engine): 城市成本年化计算`

---

### Task 12: DB 层 — SQLite 引擎 + Table 模型

**Files:** Create `app/models/tables.py`（六类 Row 拍平）、`app/db.py`; Test `tests/test_db.py`

**Interfaces:** `StudentRow/CareerRow/SocialInsuranceRow/CityCostRow/UniversityRow/MajorRow/AdmissionRow`（table=True，主键 id + 拍平字段 + 来源字段，嵌套对象存 JSON 字符串）；`get_engine()/init_db()/get_session()`。

- [x] **Step 1: 写失败测试** — init_db 建表、插入 CareerRow 取得 id
- [x] **Step 2-4: 失败→实现→通过** — 含完整 Table 定义
- [x] **Step 5: Commit** — `feat(db): SQLite 引擎 + 六类 Table 拍平模型 + Session`

---

### Task 13: Repository — Table↔Domain 映射

**Files:** Create `app/repositories/mappers.py`; Test `tests/repositories/test_mappers.py`

**Interfaces:** 六类各 `*_to_row(domain)->Row` 与 `*_to_domain(row)->Domain`。JSON 字段 json.dumps/loads。

- [x] **Step 1: 写失败测试** — career 往返 roundtrip（to_row→to_domain 字段不丢，含 source）
- [x] **Step 2-4: 失败→实现→通过**（career 完整 + 其余实体同模式）
- [x] **Step 5: Commit** — `feat(repositories): 六类实体 Table↔Domain 映射层`

---

### Task 14: Seed Loader — YAML→Domain→Table（幂等 upsert）

**Files:** Create `app/loader/seed_loader.py`; Test `tests/loader/test_seed_loader.py`

**Interfaces:** `SeedLoadError`（含文件名+记录标识+原因）；`load_all_seeds(seed_dir,session)->dict`；`is_db_empty(session)`。校验失败由 Pydantic ValidationError 捕获包装为 SeedLoadError，不静默跳过。

- [x] **Step 1: 写失败测试** — 幂等（二次加载数量不变）、缺 source 记录被拒（SeedLoadError）
- [x] **Step 2-4: 失败→实现→通过** — **移除 placeholder 行**，只实现 load_all_seeds 主入口
- [x] **Step 5: Commit** — `feat(loader): YAML 种子加载（Domain 校验 + 幂等 upsert + 拒绝损坏记录）`

---

### Task 15: 种子 YAML 数据

**Files:** Create `data/seed/{cities,careers,insurance,universities,majors,admissions}/*.yaml`; Test `tests/loader/test_seed_data.py`

**规模与合规：** cities≥7(深/北/上/郑州/成都/武汉/西安)、careers≥15、universities≥10、majors≥15、admissions 3-5校×2省。每条 source/as_of/confidence≤0.6/note"待爬虫校准"。学科评估第四轮。薪资 P25/P50/P75。

- [x] **Step 1: 写加载校验测试** — 规模达标 + 每条有来源 + 手编 confidence≤0.6 + note 含待爬虫校准
- [x] **Step 2: 运行确认失败**
- [x] **Step 3: 编写种子 YAML** — 量级对齐文档范例（深圳一房一厅 1800、综合月成本 3500-6000）
- [x] **Step 4: 运行确认通过**
- [x] **Step 5: Commit** — `feat(data): 六类种子 YAML（合规标注 + 文档量级）`

---

### Task 16: FastAPI 访问层

**Files:** Create `app/api/main.py` + 6 routers; Test `tests/api/test_api.py`, `tests/conftest.py`

**Interfaces:** careers/cities/universities(??tier=)/majors/admissions(原始查询)/insurance/compute/health。启动 lifespan 自动加载种子。

- [x] **Step 1: 写 conftest + 失败测试** — health、careers 含 source、career 详情、tier 筛选、insurance compute、admissions 空不报错、city cost
- [x] **Step 2: 运行确认失败**
- [x] **Step 3: 写 routers** — 每实体 router + main.py lifespan
- [x] **Step 4: 修复 get_session 为 FastAPI 依赖** — 新增 get_session_dep generator，router 用 Depends(get_session_dep)
- [x] **Step 5: 运行确认通过** — 7 测试 PASS
- [x] **Step 6: Commit** — `feat(api): FastAPI 六实体查询端点 + 五险一金计算 + 启动自动加载`

---

### Task 17: 来源追溯全链路集成测试

**Files:** Test `tests/test_provenance_chain.py`

- [x] **Step 1: 写集成测试** — 种子 source/confidence 经 API 返回不丢；手编种子 confidence≤0.6 且 note 含待爬虫校准
- [x] **Step 2: 运行确认通过**
- [x] **Step 3: Commit** — `test: 来源追溯全链路集成测试`

---

### Task 18: README + 端到端验证 + 合规检查

**Files:** Create `README.md`; Test `tests/test_compliance.py`

- [x] **Step 1: 写合规测试** — 无"保证就业/预测未来收入"措辞；种子含待爬虫校准
- [x] **Step 2: 写 README** — 安装/加载/启动/测试/架构 + 声明"基于历史数据模拟"
- [x] **Step 3: 端到端验证** — insurance/compute(9000,全国基准)企业成本≈12060；深圳成本对齐范例
- [x] **Step 4: 运行合规测试通过**
- [x] **Step 5: 全量回归** — `pytest -q` 全 PASS
- [x] **Step 6: Commit** — `docs: README + 端到端验证 + 合规检查`

---

## Self-Review

**1. Spec 覆盖核对：** 8 个 spec 与 tasks.md 全部映射到 Task 1–18（详见下表）。无遗漏 capability。

| Spec / tasks 条目 | 覆盖任务 |
|---|---|
| student-profile-data | Task 3 |
| career-data | Task 4 + 15 |
| social-insurance-model | Task 5 + 10 |
| city-cost-data | Task 6 + 11 + 15 |
| university-data | Task 7 + 15 + 16 |
| major-data | Task 8 + 15 |
| admission-data-schema | Task 9 + 16 |
| data-foundation-api | Task 14 + 16 + 17 |
| tasks §1 脚手架 | Task 1 |
| tasks §4 DB+加载 | Task 12 + 14 |
| tasks §7-8 测试/文档 | 各任务内嵌 + 17 + 18 |

**2. 占位符扫描：** Task 14 的 `load_yaml_file` 含 placeholder 行——实现时只实现 `load_all_seeds` 主入口，移除 placeholder。

**3. 类型一致性：** 枚举值（稳/中/冲、慢/中/快、行政编/事业编/企业/无、985/211/双一流/一本/二本/专科、一本/二本/提前批）在模型/mapper/种子 YAML 中一致；SalaryBand(low,mid,high) vs CostBand(low,high) 区分明确；Repository 与 engine 函数签名跨层一致。

**4. 关键计算已验证：** 2024 个税月度累进表（7档，速算扣除 0/210/1410/2660/4410/7160/15160）。9000 工资 → 企业成本 12150 匹配 spec；2920→87.6(3%档)；21400→2870(20%档)；边界 3000 归 3%档（taxable≤upper）。

**5. 潜在风险：** SQLModel×Pydantic v2 锁版本；get_session 双用途（with + Depends）用 get_session_dep 解决；个税边界 3000/12000 归低档与速算扣除连续性一致。
