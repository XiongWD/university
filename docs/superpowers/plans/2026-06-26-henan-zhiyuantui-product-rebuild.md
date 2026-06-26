# 河南志愿推产品重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目重构为“河南志愿推”，只面向河南考生，统一志愿推荐、目标评估和大学费用能力，支持河南 2026 规则、历史录取、专业组、计划、费用、就业信号和 48 志愿草案。

**Architecture:** 新增河南专用数据模型与导入层，建立本地可追溯数据库；重构 advisory 引擎为“资格过滤 → 批次线 → 位次风险 → 专业/就业/费用排序 → 冲稳保分桶 → 48 志愿草案”；合并费用页到推荐和目标评估；新增目标评估联动选择院校/专业/专业组。

**Tech Stack:** Python/FastAPI/Pydantic/SQLModel/pytest/YAML/CSV，React/TypeScript/Vite/Playwright。

## Global Constraints

- 产品名固定为“河南志愿推”。
- 仅支持河南考生；`source_province` 固定为 `河南`。
- 河南 2026 志愿数量按配置读取；产品验收默认 48，开发必须从河南省教育考试院核验官方口径。
- 普通本科批推荐单位是院校专业组，不是学校或单个专业；每个院校专业组志愿内最多 6 个专业并包含是否服从组内调剂。
- 学校最低分、院校专业组投档线、专业最低录取分必须分开展示；2025/2024 历史分数不得当作 2026 固定门槛。
- 所有招生、录取、计划、费用、就业数据必须保留来源、时间、置信度。
- 日语考生必须走语种限制和公共外语风险专门逻辑。
- “冲 / 稳 / 保”是筛选标签和推荐档位，不再使用“中”。
- 大学费用页合并到推荐和目标评估，不再保留独立导航。
- 就业数据不足时必须标注，不得编造岗位数或薪资。

---

## File Structure

- Create: `app/models/henan_data.py`
- Create: `app/models/henan_source_registry.py`
- Create: `app/loader/henan_data_loader.py`
- Create: `app/loader/henan_program_group_index.py`
- Create: `app/loader/henan_source_registry_loader.py`
- Create: `app/loader/henan_coverage_report.py`
- Create: `app/engine/admission_data_provider.py`
- Create: `app/engine/henan_policy.py`
- Create: `app/engine/henan_recommendation.py`
- Create: `app/engine/henan_employment.py`
- Create: `app/engine/target_evaluation.py`
- Modify: `app/api/routers/volunteer.py`
- Create: `app/api/routers/target.py`
- Modify: `app/api/main.py`
- Create: `data/seed/henan/policy/2026.yaml`
- Create: `data/seed/henan/universities.yaml`
- Create: `data/seed/henan/admission_history_2025.yaml`
- Create: `data/seed/henan/admission_history_2024.yaml`
- Create: `data/seed/henan/program_groups_2026.yaml`
- Create: `data/seed/henan/enrollment_plans_2026.yaml`
- Create: `data/seed/henan/employment_signals.yaml`
- Create: `data/seed/henan/source_registry.yaml`
- Create: `data/seed/henan/data_coverage_report.example.json`
- Modify: `web-ui/src/App.tsx`
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/client.ts`
- Modify: `web-ui/src/components/ScoreForm.tsx`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Delete or route-hide: `web-ui/src/pages/UniversityCostPage.tsx`
- Create: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Create: tests under `tests/models/`, `tests/loader/`, `tests/engine/`, `tests/api/`, `web-ui/e2e/`

---

### Task 0: 全量真实数据源登记和覆盖报告

**Files:**
- Create: `app/models/henan_source_registry.py`
- Create: `app/loader/henan_source_registry_loader.py`
- Create: `app/loader/henan_coverage_report.py`
- Create: `data/seed/henan/source_registry.yaml`
- Create: `data/seed/henan/data_coverage_report.example.json`
- Test: `tests/loader/test_henan_source_registry.py`
- Test: `tests/loader/test_henan_coverage_report.py`

**Interfaces:**
- Produces:
  - `HenanDataSource`
  - `HenanDatasetRequirement`
  - `load_henan_source_registry(path: Path) -> list[HenanDataSource]`
  - `build_henan_coverage_report(registry: list[HenanDataSource], records: dict[str, int]) -> dict`
  - `assert_henan_launch_gate(report: dict) -> None`
- Consumes: none.

- [ ] **Step 1: Write failing tests for source registry**

Create `tests/loader/test_henan_source_registry.py`:

```python
from pathlib import Path

import pytest

from app.loader.henan_source_registry_loader import load_henan_source_registry


FIXTURE = Path("data/seed/henan/source_registry.yaml")


def test_registry_distinguishes_historical_and_2026_datasets():
    sources = load_henan_source_registry(FIXTURE)
    by_dataset = {source.dataset_key: source for source in sources}

    assert by_dataset["score_segment_2025"].year_type == "historical"
    assert by_dataset["score_segment_2024"].year_type == "historical"
    assert by_dataset["admission_history_2025"].year_type == "historical"
    assert by_dataset["admission_history_2024"].year_type == "historical"
    assert by_dataset["program_groups_2026"].year_type == "latest_2026"
    assert by_dataset["enrollment_plans_henan_2026"].year_type == "latest_2026"
    assert by_dataset["tuition_accommodation_2026"].year_type == "latest_2026"
    assert by_dataset["major_employment_signal_2026"].year_type == "current_signal"


def test_registry_requires_authoritative_primary_source():
    sources = load_henan_source_registry(FIXTURE)
    for source in sources:
        assert source.primary_source_name
        assert source.primary_source_url.startswith("https://") or source.primary_source_url.startswith("http://")
        assert source.required_fields
        assert source.verification_rules


def test_registry_rejects_unclassified_dataset(tmp_path):
    bad = tmp_path / "bad_registry.yaml"
    bad.write_text(
        """
- dataset_key: unclassified
  display_name: 未分类数据
  year_type: unknown
  primary_source_name: 河南省教育考试院
  primary_source_url: https://www.haeea.cn/
  required_fields: [school_code]
  verification_rules: [保留来源]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="year_type"):
        load_henan_source_registry(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/loader/test_henan_source_registry.py -v
```

Expected: FAIL because `app.loader.henan_source_registry_loader` does not exist.

- [ ] **Step 3: Implement source registry models and loader**

Create `app/models/henan_source_registry.py`:

```python
from pydantic import BaseModel, Field, HttpUrl


class HenanDataSource(BaseModel):
    dataset_key: str
    display_name: str
    year_type: str
    years: list[int]
    primary_source_name: str
    primary_source_url: HttpUrl
    auxiliary_source_names: list[str] = Field(default_factory=list)
    required_fields: list[str]
    verification_rules: list[str]
    missing_data_behavior: str
    blocks_recommendation_when_missing: bool

    def validate_year_type(self) -> None:
        allowed = {"historical", "latest_2026", "historical_and_latest", "current_signal"}
        if self.year_type not in allowed:
            raise ValueError(f"year_type must be one of {sorted(allowed)}")
```

Create `app/loader/henan_source_registry_loader.py`:

```python
from pathlib import Path

import yaml

from app.models.henan_source_registry import HenanDataSource


def load_henan_source_registry(path: str | Path) -> list[HenanDataSource]:
    source_path = Path(path)
    raw = yaml.safe_load(source_path.read_text(encoding="utf-8")) or []
    sources = [HenanDataSource(**item) for item in raw]
    for source in sources:
        source.validate_year_type()
    return sources
```

- [ ] **Step 4: Add source registry seed**

Create `data/seed/henan/source_registry.yaml`:

```yaml
- dataset_key: score_segment_2025
  display_name: 河南2025一分一段
  year_type: historical
  years: [2025]
  primary_source_name: 河南省教育考试院
  primary_source_url: https://www.haeea.cn/
  auxiliary_source_names: []
  required_fields: [year, track, score, cumulative_count, rank_low, rank_high, source_url]
  verification_rules:
    - 累计人数必须随分数下降单调增加
    - 分数段总人数必须与官方公布人数一致
    - 历史数据只用于参考，不替代2026考生真实位次
  missing_data_behavior: 禁止进行2025位次换算和两年趋势判断
  blocks_recommendation_when_missing: true

- dataset_key: score_segment_2024
  display_name: 河南2024一分一段
  year_type: historical
  years: [2024]
  primary_source_name: 河南省教育考试院
  primary_source_url: https://www.haeea.cn/
  auxiliary_source_names: []
  required_fields: [year, track, score, cumulative_count, rank_low, rank_high, source_url]
  verification_rules:
    - 累计人数必须随分数下降单调增加
    - 只能作为趋势辅助，不能单独支撑保底判断
  missing_data_behavior: 缺少2024时允许运行，但趋势置信度降低
  blocks_recommendation_when_missing: false

- dataset_key: admission_history_2025
  display_name: 河南2025历史录取分数和位次
  year_type: historical
  years: [2025]
  primary_source_name: 河南省教育考试院和院校本科招生网
  primary_source_url: https://www.haeea.cn/
  auxiliary_source_names: [阳光高考, 各院校本科招生网]
  required_fields: [year, track, batch, school_code, school_name, min_score, min_rank, data_granularity, source_url]
  verification_rules:
    - 2025优先于2024
    - 专业级数据不可由校级数据伪造
    - 同一记录多源冲突时设为needs_review
  missing_data_behavior: 不允许输出高置信度稳保推荐
  blocks_recommendation_when_missing: true

- dataset_key: admission_history_2024
  display_name: 河南2024历史录取分数和位次
  year_type: historical
  years: [2024]
  primary_source_name: 河南省教育考试院和院校本科招生网
  primary_source_url: https://www.haeea.cn/
  auxiliary_source_names: [阳光高考, 各院校本科招生网]
  required_fields: [year, track, batch, school_code, school_name, min_score, min_rank, data_granularity, source_url]
  verification_rules:
    - 2024仅作为波动趋势辅助
    - 缺少2025时不得单独判定保
  missing_data_behavior: 趋势置信度降低
  blocks_recommendation_when_missing: false

- dataset_key: universities_2026
  display_name: 2026在河南招生院校属性
  year_type: latest_2026
  years: [2026]
  primary_source_name: 阳光高考院校库和2026河南招生专业目录
  primary_source_url: https://gaokao.chsi.com.cn/
  auxiliary_source_names: [教育部高校名单, 院校官网]
  required_fields: [school_code, school_name, province, city, ownership, school_level, source_url]
  verification_rules:
    - 学校代码和学校名必须一致
    - 公办民办属性不得由旧年数据覆盖2026官方信息
  missing_data_behavior: 不参与公办民办中外合作筛选
  blocks_recommendation_when_missing: true

- dataset_key: program_groups_2026
  display_name: 河南2026院校专业组和专业限制
  year_type: latest_2026
  years: [2026]
  primary_source_name: 河南2026招生专业目录和院校招生章程
  primary_source_url: https://www.haeea.cn/
  auxiliary_source_names: [各院校本科招生网, 阳光高考]
  required_fields: [year, track, school_code, major_group_code, included_majors, primary_subject_requirement, elective_subject_requirement, accepted_exam_languages, adjustment_scope, source_url]
  verification_rules:
    - 专业组代码必须来自2026河南招生材料
    - 日语、英语限报、公共外语信息必须来自招生章程或院校明确说明
  missing_data_behavior: 不得推荐该专业组
  blocks_recommendation_when_missing: true

- dataset_key: enrollment_plans_henan_2026
  display_name: 2026面向河南招生计划
  year_type: latest_2026
  years: [2026]
  primary_source_name: 河南2026招生专业目录和院校分省计划
  primary_source_url: https://www.haeea.cn/
  auxiliary_source_names: [院校本科招生网, 阳光高考招生计划]
  required_fields: [year, source_province, track, batch, school_code, major_group_code, major_name, plan_count, source_url]
  verification_rules:
    - source_province必须为河南
    - 学校河南总计划必须能由专业计划汇总或被官方总数解释
  missing_data_behavior: 不得进入稳或保
  blocks_recommendation_when_missing: true

- dataset_key: tuition_accommodation_2026
  display_name: 2026学费住宿费
  year_type: latest_2026
  years: [2026]
  primary_source_name: 院校2026招生章程和收费公示
  primary_source_url: https://gaokao.chsi.com.cn/
  auxiliary_source_names: [院校财务处或招生网, 河南招生专业目录]
  required_fields: [school_code, school_name, major_name, tuition_per_year, accommodation_per_year, source_url]
  verification_rules:
    - 中外合作和高收费专业必须按专业记录
    - 住宿费允许区间，学费必须明确到专业或项目
  missing_data_behavior: 推荐结果显示费用待核验，不计算4年总费用
  blocks_recommendation_when_missing: false

- dataset_key: major_employment_signal_2026
  display_name: 2026专业就业和政策信号
  year_type: current_signal
  years: [2026]
  primary_source_name: 阳光高考专业库
  primary_source_url: https://gaokao.chsi.com.cn/
  auxiliary_source_names: [BOSS直聘, 国家政策公开信息, 院校专业介绍]
  required_fields: [major_name, direction, policy_signal, domestic_demand_summary, evidence_level, source_url]
  verification_rules:
    - 招聘数据只作为补充信号
    - 样本不足时必须输出就业数据不足
  missing_data_behavior: 不阻断推荐，但不得编造薪资
  blocks_recommendation_when_missing: false
```

- [ ] **Step 5: Run registry tests**

Run:

```bash
python -m pytest tests/loader/test_henan_source_registry.py -v
```

Expected: PASS.

- [ ] **Step 6: Write failing tests for coverage report and launch gate**

Create `tests/loader/test_henan_coverage_report.py`:

```python
import pytest

from app.loader.henan_coverage_report import (
    assert_henan_launch_gate,
    build_henan_coverage_report,
)
from app.loader.henan_source_registry_loader import load_henan_source_registry


def test_coverage_report_keeps_historical_and_2026_counts_separate():
    registry = load_henan_source_registry("data/seed/henan/source_registry.yaml")
    report = build_henan_coverage_report(
        registry,
        records={
            "score_segment_2025": 500,
            "score_segment_2024": 500,
            "admission_history_2025": 3000,
            "admission_history_2024": 2800,
            "universities_2026": 1500,
            "program_groups_2026": 3200,
            "enrollment_plans_henan_2026": 12000,
            "tuition_accommodation_2026": 9000,
            "major_employment_signal_2026": 180,
        },
    )

    assert report["historical"]["score_segment_2025"] == 500
    assert report["historical"]["admission_history_2024"] == 2800
    assert report["latest_2026"]["program_groups_2026"] == 3200
    assert report["latest_2026"]["enrollment_plans_henan_2026"] == 12000
    assert report["current_signal"]["major_employment_signal_2026"] == 180


def test_launch_gate_blocks_when_2026_plan_or_group_missing():
    registry = load_henan_source_registry("data/seed/henan/source_registry.yaml")
    report = build_henan_coverage_report(
        registry,
        records={
            "score_segment_2025": 500,
            "score_segment_2024": 500,
            "admission_history_2025": 3000,
            "admission_history_2024": 2800,
            "universities_2026": 1500,
            "program_groups_2026": 0,
            "enrollment_plans_henan_2026": 0,
            "tuition_accommodation_2026": 9000,
            "major_employment_signal_2026": 180,
        },
    )

    with pytest.raises(ValueError, match="program_groups_2026"):
        assert_henan_launch_gate(report)


def test_launch_gate_allows_missing_employment_salary_data():
    registry = load_henan_source_registry("data/seed/henan/source_registry.yaml")
    report = build_henan_coverage_report(
        registry,
        records={
            "score_segment_2025": 500,
            "score_segment_2024": 500,
            "admission_history_2025": 3000,
            "admission_history_2024": 2800,
            "universities_2026": 1500,
            "program_groups_2026": 3200,
            "enrollment_plans_henan_2026": 12000,
            "tuition_accommodation_2026": 0,
            "major_employment_signal_2026": 0,
        },
    )

    assert_henan_launch_gate(report)
```

- [ ] **Step 7: Implement coverage report**

Create `app/loader/henan_coverage_report.py`:

```python
from app.models.henan_source_registry import HenanDataSource


def build_henan_coverage_report(
    registry: list[HenanDataSource],
    records: dict[str, int],
) -> dict:
    report = {
        "historical": {},
        "latest_2026": {},
        "historical_and_latest": {},
        "current_signal": {},
        "blocking_missing": [],
        "warnings": [],
    }
    for source in registry:
        count = records.get(source.dataset_key, 0)
        report[source.year_type][source.dataset_key] = count
        if count <= 0 and source.blocks_recommendation_when_missing:
            report["blocking_missing"].append(source.dataset_key)
        elif count <= 0:
            report["warnings"].append(source.dataset_key)
    return report


def assert_henan_launch_gate(report: dict) -> None:
    blocking = report.get("blocking_missing", [])
    if blocking:
        raise ValueError(f"河南志愿推关键数据缺失: {', '.join(blocking)}")
```

- [ ] **Step 8: Add example coverage report**

Create `data/seed/henan/data_coverage_report.example.json`:

```json
{
  "historical": {
    "score_segment_2025": 500,
    "score_segment_2024": 500,
    "admission_history_2025": 3000,
    "admission_history_2024": 2800
  },
  "latest_2026": {
    "universities_2026": 1500,
    "program_groups_2026": 3200,
    "enrollment_plans_henan_2026": 12000,
    "tuition_accommodation_2026": 9000
  },
  "current_signal": {
    "major_employment_signal_2026": 180
  },
  "blocking_missing": [],
  "warnings": []
}
```

- [ ] **Step 9: Run coverage tests**

Run:

```bash
python -m pytest tests/loader/test_henan_source_registry.py tests/loader/test_henan_coverage_report.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add app/models/henan_source_registry.py app/loader/henan_source_registry_loader.py app/loader/henan_coverage_report.py data/seed/henan/source_registry.yaml data/seed/henan/data_coverage_report.example.json tests/loader/test_henan_source_registry.py tests/loader/test_henan_coverage_report.py
git commit -m "feat: add henan data source registry"
```

### Task 1: 河南数据模型

**Files:**
- Create: `app/models/henan_data.py`
- Test: `tests/models/test_henan_data_models.py`

**Interfaces:**
- Produces:
  - `HenanAdmissionPolicy`
  - `HenanUniversity`
  - `HenanAdmissionHistory`
  - `HenanProgramGroup`
  - `HenanEnrollmentPlan`
  - `HenanCostProfile`
  - `MajorEmploymentSignal`

- [ ] **Step 1: Write failing tests**

Create `tests/models/test_henan_data_models.py`:

```python
from app.models.henan_data import (
    HenanAdmissionPolicy,
    HenanUniversity,
    HenanProgramGroup,
    HenanEnrollmentPlan,
    MajorEmploymentSignal,
)


def test_policy_has_parallel_volunteer_count_and_adjustment_rule():
    policy = HenanAdmissionPolicy(
        year=2026,
        province="河南",
        batch="本科批",
        track="历史类",
        parallel_volunteer_count=48,
        volunteer_unit="院校专业组",
        major_count_per_group=6,
        has_major_adjustment=True,
        filing_rule_summary="平行志愿，按位次投档",
        source_name="河南省教育考试院",
        source_url="https://www.haeea.cn/",
        as_of="2026-06-26",
        confidence=0.9,
    )
    assert policy.parallel_volunteer_count == 48
    assert policy.volunteer_unit == "院校专业组"


def test_program_group_supports_japanese_language_risk_fields():
    group = HenanProgramGroup(
        year=2026,
        track="历史类",
        school_code="10475",
        school_name="河南大学",
        major_group_code="101",
        major_group_name="历史类不限组",
        included_majors=["汉语言文学"],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        accepted_exam_languages=["英语", "日语"],
        public_foreign_languages=["英语"],
        single_subject_requirements=[],
        adjustment_scope="组内专业",
        source_name="河南大学本科招生网",
        source_url="https://zs.henu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.8,
        review_status="verified",
    )
    assert group.public_foreign_languages == ["英语"]


def test_enrollment_plan_is_henan_specific():
    plan = HenanEnrollmentPlan(
        year=2026,
        source_province="河南",
        school_code="10459",
        school_name="郑州大学",
        major_group_code="501",
        major_name="计算机科学与技术",
        plan_count=120,
        school_system_years=4,
        tuition=5700,
        accommodation=1100,
        batch="本科批",
        track="物理类",
        source_name="郑州大学本科招生网",
        source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.9,
    )
    assert plan.source_province == "河南"


def test_employment_signal_can_mark_insufficient_data():
    signal = MajorEmploymentSignal(
        major_name="历史学",
        direction="师范教育",
        policy_signal="稳定",
        domestic_demand_summary="以教师编制、教培、文博方向为主",
        job_market_city_scope="河南",
        evidence_level="C",
        source_name="阳光高考专业库",
        source_url="https://gaokao.chsi.com.cn/",
        as_of="2026-06-26",
        confidence=0.6,
    )
    assert signal.boss_job_count is None
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/models/test_henan_data_models.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 3: Implement models**

Create `app/models/henan_data.py`:

```python
from pydantic import BaseModel, Field


class SourceStamped(BaseModel):
    source_name: str
    source_url: str
    as_of: str
    confidence: float = Field(ge=0, le=1)
    review_status: str = "verified"


class HenanAdmissionPolicy(SourceStamped):
    year: int
    province: str = "河南"
    batch: str
    track: str
    parallel_volunteer_count: int
    volunteer_unit: str
    major_count_per_group: int
    has_major_adjustment: bool
    filing_rule_summary: str


class HenanUniversity(SourceStamped):
    school_code: str
    school_name: str
    province: str
    city: str
    ownership: str
    school_level: str = ""
    strong_majors: list[str] = []
    tags: list[str] = []


class HenanAdmissionHistory(SourceStamped):
    year: int
    track: str
    school_code: str
    school_name: str
    major_group_code: str | None = None
    major_group_name: str = ""
    major_name: str | None = None
    min_score: int | None = None
    min_rank: int | None = None
    avg_score: int | None = None
    avg_rank: int | None = None
    plan_count: int | None = None
    batch: str
    data_granularity: str


class HenanProgramGroup(SourceStamped):
    year: int
    track: str
    batch: str = "本科批"
    school_code: str
    school_name: str
    major_group_code: str
    major_group_name: str
    included_majors: list[str] = []
    major_codes: list[str] = []
    primary_subject_requirement: str | None = None
    elective_subject_requirement: dict = {}
    required_exam_language: str | None = None
    accepted_exam_languages: list[str] = []
    public_foreign_languages: list[str] = []
    single_subject_requirements: list[dict] = []
    oral_test_required: bool = False
    adjustment_scope: str = ""


class HenanEnrollmentPlan(SourceStamped):
    year: int
    source_province: str = "河南"
    school_origin_province: str = ""
    is_henan_local_school: bool = False
    school_code: str
    school_name: str
    major_group_code: str
    major_name: str
    plan_count: int = Field(ge=0)
    school_system_years: int | None = None
    tuition: int | None = None
    accommodation: int | None = None
    batch: str
    track: str


class HenanCostProfile(SourceStamped):
    school_code: str
    school_name: str
    major_name: str | None = None
    tuition_per_year: int | None = None
    accommodation_per_year: int | None = None
    city_living_cost_low: int | None = None
    city_living_cost_mid: int | None = None
    city_living_cost_high: int | None = None
    four_year_total_mid: int | None = None


class MajorEmploymentSignal(SourceStamped):
    major_name: str
    direction: str
    policy_signal: str = ""
    domestic_demand_summary: str = ""
    job_market_city_scope: str = "河南"
    boss_job_count: int | None = None
    salary_p25: int | None = None
    salary_p50: int | None = None
    salary_p75: int | None = None
    evidence_level: str
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/models/test_henan_data_models.py --basetemp .pytest-tmp -q`

Expected: 4 passed.

---

### Task 2: 河南 seed loader

**Files:**
- Create: `app/loader/henan_data_loader.py`
- Create seed files under `data/seed/henan/`
- Test: `tests/loader/test_henan_data_loader.py`

**Interfaces:**
- Produces:
  - `load_henan_policy(seed_dir) -> list[HenanAdmissionPolicy]`
  - `load_henan_universities(seed_dir) -> list[HenanUniversity]`
  - `load_henan_program_groups(seed_dir) -> list[HenanProgramGroup]`
  - `load_henan_enrollment_plans(seed_dir) -> list[HenanEnrollmentPlan]`
  - `load_henan_employment_signals(seed_dir) -> list[MajorEmploymentSignal]`

- [ ] **Step 1: Create minimal seed files**

Create `data/seed/henan/policy/2026.yaml`:

```yaml
- year: 2026
  province: 河南
  batch: 本科批
  track: 历史类
  parallel_volunteer_count: 48
  volunteer_unit: 院校专业组
  major_count_per_group: 6
  has_major_adjustment: true
  filing_rule_summary: 平行志愿，按位次投档；志愿数量需以河南省教育考试院2026正式文件核验
  source_name: 河南省教育考试院
  source_url: https://www.haeea.cn/
  as_of: "2026-06-26"
  confidence: 0.7
  review_status: needs_review
```

Create `data/seed/henan/universities.yaml`:

```yaml
- school_code: "10459"
  school_name: 郑州大学
  province: 河南
  city: 郑州
  ownership: 公办
  school_level: 双一流
  strong_majors: [临床医学, 计算机科学与技术, 材料科学与工程]
  tags: [省内头部, 综合类]
  source_name: 阳光高考
  source_url: https://gaokao.chsi.com.cn/
  as_of: "2026-06-26"
  confidence: 0.8
  review_status: needs_review
```

Create `data/seed/henan/program_groups_2026.yaml`:

```yaml
- year: 2026
  track: 物理类
  school_code: "10459"
  school_name: 郑州大学
  major_group_code: "501"
  major_group_name: 物理类计算机组
  included_majors: [计算机科学与技术, 软件工程]
  primary_subject_requirement: 物理
  elective_subject_requirement: {require: [化学], any_of: []}
  accepted_exam_languages: [英语, 日语]
  public_foreign_languages: [英语]
  single_subject_requirements: []
  adjustment_scope: 组内专业
  source_name: 郑州大学本科招生网
  source_url: https://ao.zzu.edu.cn/
  as_of: "2026-06-26"
  confidence: 0.7
  review_status: needs_review
```

Create `data/seed/henan/enrollment_plans_2026.yaml`:

```yaml
- year: 2026
  source_province: 河南
  school_code: "10459"
  school_name: 郑州大学
  major_group_code: "501"
  major_name: 计算机科学与技术
  plan_count: 0
  school_system_years: 4
  tuition: 5700
  accommodation: 1100
  batch: 本科批
  track: 物理类
  source_name: 郑州大学本科招生网
  source_url: https://ao.zzu.edu.cn/
  as_of: "2026-06-26"
  confidence: 0.4
  review_status: needs_review
```

Create `data/seed/henan/employment_signals.yaml`:

```yaml
- major_name: 计算机科学与技术
  direction: 计算机
  policy_signal: 数字经济、人工智能相关岗位需求较高
  domestic_demand_summary: 北上广深和郑州均有软件开发、测试、运维岗位需求；需持续更新招聘数据
  job_market_city_scope: 北上广深
  boss_job_count:
  salary_p25:
  salary_p50:
  salary_p75:
  evidence_level: C
  source_name: 阳光高考专业库
  source_url: https://gaokao.chsi.com.cn/
  as_of: "2026-06-26"
  confidence: 0.5
  review_status: needs_review
```

- [ ] **Step 2: Write failing tests**

Create `tests/loader/test_henan_data_loader.py`:

```python
from pathlib import Path

from app.loader.henan_data_loader import (
    load_henan_policy,
    load_henan_universities,
    load_henan_program_groups,
    load_henan_enrollment_plans,
    load_henan_employment_signals,
)


SEED = Path("data/seed")


def test_load_policy():
    policies = load_henan_policy(SEED)
    assert policies[0].province == "河南"
    assert policies[0].parallel_volunteer_count == 48


def test_load_universities():
    universities = load_henan_universities(SEED)
    assert any(u.school_name == "郑州大学" for u in universities)


def test_load_program_groups():
    groups = load_henan_program_groups(SEED)
    zzu = next(g for g in groups if g.school_name == "郑州大学")
    assert zzu.elective_subject_requirement["require"] == ["化学"]


def test_load_enrollment_plans():
    plans = load_henan_enrollment_plans(SEED)
    assert plans[0].source_province == "河南"


def test_load_employment_signals():
    signals = load_henan_employment_signals(SEED)
    assert signals[0].major_name == "计算机科学与技术"
```

- [ ] **Step 3: Verify tests fail**

Run: `python -m pytest tests/loader/test_henan_data_loader.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 4: Implement loader**

Create `app/loader/henan_data_loader.py`:

```python
from pathlib import Path

import yaml

from app.models.henan_data import (
    HenanAdmissionPolicy,
    HenanEnrollmentPlan,
    HenanProgramGroup,
    HenanUniversity,
    MajorEmploymentSignal,
)


def _read_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def load_henan_policy(seed_dir: Path) -> list[HenanAdmissionPolicy]:
    rows = []
    for path in (seed_dir / "henan/policy").glob("*.yaml"):
        rows.extend(_read_yaml(path))
    return [HenanAdmissionPolicy.model_validate(x) for x in rows]


def load_henan_universities(seed_dir: Path) -> list[HenanUniversity]:
    return [HenanUniversity.model_validate(x) for x in _read_yaml(seed_dir / "henan/universities.yaml")]


def load_henan_program_groups(seed_dir: Path) -> list[HenanProgramGroup]:
    return [HenanProgramGroup.model_validate(x) for x in _read_yaml(seed_dir / "henan/program_groups_2026.yaml")]


def load_henan_enrollment_plans(seed_dir: Path) -> list[HenanEnrollmentPlan]:
    return [HenanEnrollmentPlan.model_validate(x) for x in _read_yaml(seed_dir / "henan/enrollment_plans_2026.yaml")]


def load_henan_employment_signals(seed_dir: Path) -> list[MajorEmploymentSignal]:
    return [MajorEmploymentSignal.model_validate(x) for x in _read_yaml(seed_dir / "henan/employment_signals.yaml")]
```

- [ ] **Step 5: Verify tests pass**

Run: `python -m pytest tests/loader/test_henan_data_loader.py --basetemp .pytest-tmp -q`

Expected: 5 passed.

---

### Task 2A: 专业反推专业组和省内外数据接口

**Files:**
- Create: `app/loader/henan_program_group_index.py`
- Create: `app/engine/admission_data_provider.py`
- Test: `tests/loader/test_henan_program_group_index.py`
- Test: `tests/engine/test_admission_data_provider.py`

**Interfaces:**
- Produces:
  - `find_groups_by_major(groups, school_code: str, major_name: str, track: str, batch: str) -> list`
  - `AdmissionDataProvider`
  - `HenanAdmissionDataProvider`

- [ ] **Step 1: Write failing tests for major-to-group lookup**

Create `tests/loader/test_henan_program_group_index.py`:

```python
from app.loader.henan_program_group_index import find_groups_by_major
from app.models.henan_data import HenanProgramGroup


def _group(code, majors, track="历史类", batch="本科批"):
    return HenanProgramGroup(
        year=2026,
        track=track,
        batch=batch,
        school_code="10469",
        school_name="河南牧业经济学院",
        major_group_code=code,
        major_group_name=f"{code}组",
        included_majors=majors,
        major_codes=[],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        accepted_exam_languages=["英语", "日语"],
        public_foreign_languages=["英语"],
        adjustment_scope="组内专业",
        source_name="河南2026招生专业目录",
        source_url="https://www.haeea.cn/",
        as_of="2026-06-26",
        confidence=0.9,
    )


def test_find_groups_by_major_returns_all_matching_groups():
    groups = [
        _group("101", ["会计学", "财务管理"]),
        _group("105", ["会计学"], batch="本科批"),
        _group("201", ["动物医学"], track="物理类"),
    ]

    result = find_groups_by_major(groups, "10469", "会计学", "历史类", "本科批")

    assert [group.major_group_code for group in result] == ["101", "105"]


def test_find_groups_by_major_does_not_cross_track_or_school():
    groups = [
        _group("101", ["会计学"], track="历史类"),
        _group("201", ["会计学"], track="物理类"),
    ]

    result = find_groups_by_major(groups, "10469", "会计学", "历史类", "本科批")

    assert [group.major_group_code for group in result] == ["101"]
```

- [ ] **Step 2: Implement major-to-group lookup**

Create `app/loader/henan_program_group_index.py`:

```python
def _normalize_major(name: str) -> str:
    return name.replace("（", "(").replace("）", ")").strip()


def find_groups_by_major(
    groups: list,
    school_code: str,
    major_name: str,
    track: str,
    batch: str,
) -> list:
    normalized = _normalize_major(major_name)
    matches = []
    for group in groups:
        if group.school_code != school_code:
            continue
        if group.track != track:
            continue
        if getattr(group, "batch", batch) != batch:
            continue
        majors = [_normalize_major(item) for item in group.included_majors]
        if normalized in majors:
            matches.append(group)
    return matches
```

- [ ] **Step 3: Write failing tests for provider boundary**

Create `tests/engine/test_admission_data_provider.py`:

```python
import pytest

from app.engine.admission_data_provider import HenanAdmissionDataProvider


def test_henan_provider_only_serves_henan_candidates():
    provider = HenanAdmissionDataProvider()
    assert provider.source_province == "河南"

    with pytest.raises(ValueError, match="仅支持河南"):
        provider.ensure_supported("山东")


def test_provider_keeps_henan_plans_for_in_and_out_of_province_schools():
    provider = HenanAdmissionDataProvider()
    plans = [
        {"source_province": "河南", "school_origin_province": "河南", "school_name": "郑州大学"},
        {"source_province": "河南", "school_origin_province": "湖北", "school_name": "武汉大学"},
        {"source_province": "山东", "school_origin_province": "河南", "school_name": "郑州大学"},
    ]

    result = provider.filter_plans_for_source_province(plans, "河南")

    assert [item["school_name"] for item in result] == ["郑州大学", "武汉大学"]
```

- [ ] **Step 4: Implement provider boundary**

Create `app/engine/admission_data_provider.py`:

```python
from typing import Protocol


class AdmissionDataProvider(Protocol):
    source_province: str

    def ensure_supported(self, source_province: str) -> None:
        ...

    def filter_plans_for_source_province(self, plans: list[dict], source_province: str) -> list[dict]:
        ...


class HenanAdmissionDataProvider:
    source_province = "河南"

    def ensure_supported(self, source_province: str) -> None:
        if source_province != self.source_province:
            raise ValueError("河南志愿推当前仅支持河南考生")

    def filter_plans_for_source_province(self, plans: list[dict], source_province: str) -> list[dict]:
        self.ensure_supported(source_province)
        return [plan for plan in plans if plan.get("source_province") == self.source_province]
```

- [ ] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/loader/test_henan_program_group_index.py tests/engine/test_admission_data_provider.py --basetemp .pytest-tmp
```

Expected: PASS.

---

### Task 3: 河南政策和冲稳保引擎

**Files:**
- Create: `app/engine/henan_policy.py`
- Create: `app/engine/henan_recommendation.py`
- Test: `tests/engine/test_henan_recommendation.py`

**Interfaces:**
- Produces:
  - `check_henan_eligibility(profile, group) -> tuple[bool, list[str], list[str]]`
  - `classify_henan_bucket(student_rank, historical_rank, policy_mode) -> str`
  - `classify_group_bucket(student_rank: int, adjusted_rank: int | None, has_2025_history: bool, has_2026_plan: bool, has_verified_group: bool, confidence: float) -> str`
  - `get_bucket_quota(policy_count: int, strategy: str, profile: dict) -> dict[str, tuple[int, int]]`
  - `build_48_volunteer_draft(candidates, policy) -> dict`
  - `build_henan_candidates(profile: dict) -> list[dict]`

- [ ] **Step 1: Write failing tests**

Create `tests/engine/test_henan_recommendation.py`:

```python
from app.engine.henan_recommendation import (
    build_48_volunteer_draft,
    check_henan_eligibility,
    classify_henan_bucket,
    classify_group_bucket,
    get_bucket_quota,
)
from app.models.henan_data import HenanAdmissionPolicy, HenanProgramGroup


def _policy():
    return HenanAdmissionPolicy(
        year=2026,
        province="河南",
        batch="本科批",
        track="历史类",
        parallel_volunteer_count=48,
        volunteer_unit="院校专业组",
        major_count_per_group=6,
        has_major_adjustment=True,
        filing_rule_summary="平行志愿",
        source_name="河南省教育考试院",
        source_url="https://www.haeea.cn/",
        as_of="2026-06-26",
        confidence=0.7,
    )


def test_japanese_student_blocked_by_english_required_group():
    group = HenanProgramGroup(
        year=2026,
        track="历史类",
        school_code="x",
        school_name="测试大学",
        major_group_code="101",
        major_group_name="英语专业组",
        included_majors=["英语"],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        required_exam_language="英语",
        accepted_exam_languages=["英语"],
        public_foreign_languages=["英语"],
        single_subject_requirements=[],
        adjustment_scope="组内专业",
        source_name="招生章程",
        source_url="https://example.com",
        as_of="2026-06-26",
        confidence=0.9,
    )
    ok, blocked, warnings = check_henan_eligibility(
        profile={
            "primary_subject": "历史",
            "elective_subjects": ["政治", "地理"],
            "exam_foreign_language": "日语",
            "foreign_language_score": 120,
            "math_score": 90,
        },
        group=group,
    )
    assert ok is False
    assert any("英语语种" in x for x in blocked)


def test_bucket_classification():
    assert classify_henan_bucket(student_rank=52000, historical_rank=50000, policy_mode="冲") == "冲"
    assert classify_henan_bucket(student_rank=49000, historical_rank=50000, policy_mode="稳") == "稳"
    assert classify_henan_bucket(student_rank=40000, historical_rank=50000, policy_mode="保") == "保"


def test_group_bucket_requires_2026_plan_and_verified_group():
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=True,
        has_2026_plan=False,
        has_verified_group=True,
        confidence=0.9,
    ) == "不推荐"
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=True,
        has_2026_plan=True,
        has_verified_group=False,
        confidence=0.9,
    ) == "不推荐"


def test_group_bucket_does_not_mark_safe_without_2025_history_or_confidence():
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=False,
        has_2026_plan=True,
        has_verified_group=True,
        confidence=0.9,
    ) == "稳"
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=True,
        has_2026_plan=True,
        has_verified_group=True,
        confidence=0.5,
    ) == "稳"


def test_group_bucket_uses_rank_gap_thresholds():
    assert classify_group_bucket(58000, 50000, True, True, True, 0.9) == "不推荐"
    assert classify_group_bucket(54000, 50000, True, True, True, 0.9) == "冲"
    assert classify_group_bucket(49500, 50000, True, True, True, 0.9) == "稳"
    assert classify_group_bucket(43000, 50000, True, True, True, 0.9) == "保"


def test_bucket_quota_for_balanced_48_volunteers():
    quota = get_bucket_quota(48, "均衡", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"冲": (8, 12), "稳": (20, 24), "保": (12, 16)}


def test_bucket_quota_defaults_to_conservative_for_history_japanese():
    quota = get_bucket_quota(48, "自动", {"track": "历史类", "exam_foreign_language": "日语"})
    assert quota == {"冲": (6, 8), "稳": (22, 26), "保": (14, 18)}


def test_bucket_quota_for_aggressive_48_volunteers():
    quota = get_bucket_quota(48, "积极", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"冲": (12, 16), "稳": (18, 22), "保": (8, 12)}


def test_48_draft_respects_policy_count():
    candidates = [{"bucket": "保", "school_name": f"学校{i}", "major_group_code": str(i)} for i in range(60)]
    draft = build_48_volunteer_draft(candidates, _policy())
    assert len(draft["items"]) == 48


def test_48_draft_uses_major_group_as_volunteer_unit():
    candidates = [
        {
            "bucket": "稳",
            "school_name": "河南牧业经济学院",
            "major_group_code": "101",
            "major_group_name": "历史不限组",
            "selected_majors": ["会计学", "财务管理", "物流管理"],
        },
        {
            "bucket": "稳",
            "school_name": "河南牧业经济学院",
            "major_group_code": "102",
            "major_group_name": "历史政治组",
            "selected_majors": ["思想政治教育"],
        },
    ]
    draft = build_48_volunteer_draft(candidates, _policy())
    assert draft["items"][0]["volunteer_unit"] == "院校专业组"
    assert draft["items"][0]["major_group_code"] == "101"
    assert draft["items"][1]["major_group_code"] == "102"
    assert len(draft["items"]) == 2
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/engine/test_henan_recommendation.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 3: Implement recommendation engine**

Create `app/engine/henan_recommendation.py`:

```python
def check_henan_eligibility(profile: dict, group) -> tuple[bool, list[str], list[str]]:
    blocked: list[str] = []
    warnings: list[str] = []

    if group.primary_subject_requirement and profile.get("primary_subject") != group.primary_subject_requirement:
        blocked.append(f"首选科目要求{group.primary_subject_requirement}")

    require = (group.elective_subject_requirement or {}).get("require", [])
    for subject in require:
        if subject not in profile.get("elective_subjects", []):
            blocked.append(f"再选科目要求包含{subject}")

    if group.required_exam_language == "英语" and profile.get("exam_foreign_language") != "英语":
        blocked.append("要求英语语种，日语考生不可报")

    accepted = group.accepted_exam_languages or []
    if accepted and profile.get("exam_foreign_language") not in accepted:
        blocked.append(f"外语语种需为{'/'.join(accepted)}")

    if profile.get("exam_foreign_language") == "日语" and "日语" not in (group.public_foreign_languages or []):
        warnings.append("入学后公共外语可能仅开英语，日语考生有适应风险")

    return len(blocked) == 0, blocked, warnings


def classify_henan_bucket(student_rank: int, historical_rank: int | None, policy_mode: str) -> str:
    if historical_rank is None or student_rank <= 0:
        return "不推荐"
    ratio = (student_rank - historical_rank) / historical_rank
    if ratio > 0.12:
        return "不推荐"
    if ratio > 0.03:
        return "冲"
    if ratio >= -0.12:
        return "稳"
    return "保"


def classify_group_bucket(
    student_rank: int,
    adjusted_rank: int | None,
    has_2025_history: bool,
    has_2026_plan: bool,
    has_verified_group: bool,
    confidence: float,
) -> str:
    if not has_2026_plan or not has_verified_group:
        return "不推荐"
    if adjusted_rank is None or adjusted_rank <= 0 or student_rank <= 0:
        return "不推荐"

    rank_gap_ratio = (student_rank - adjusted_rank) / adjusted_rank
    if rank_gap_ratio > 0.15:
        return "不推荐"
    if rank_gap_ratio > 0.03:
        return "冲"
    if rank_gap_ratio >= -0.10:
        return "稳"
    if not has_2025_history or confidence < 0.7:
        return "稳"
    return "保"


def get_bucket_quota(policy_count: int, strategy: str, profile: dict) -> dict[str, tuple[int, int]]:
    if policy_count != 48:
        ratio = policy_count / 48

        def scaled(low: int, high: int) -> tuple[int, int]:
            return (max(0, round(low * ratio)), max(0, round(high * ratio)))
    else:
        def scaled(low: int, high: int) -> tuple[int, int]:
            return (low, high)

    if strategy == "自动" and profile.get("track") == "历史类" and profile.get("exam_foreign_language") == "日语":
        strategy = "保守"
    elif strategy == "自动":
        strategy = "均衡"

    if strategy == "保守":
        return {"冲": scaled(6, 8), "稳": scaled(22, 26), "保": scaled(14, 18)}
    if strategy == "积极":
        return {"冲": scaled(12, 16), "稳": scaled(18, 22), "保": scaled(8, 12)}
    return {"冲": scaled(8, 12), "稳": scaled(20, 24), "保": scaled(12, 16)}


def build_48_volunteer_draft(candidates: list[dict], policy) -> dict:
    ordered = sorted(
        candidates,
        key=lambda x: {"冲": 0, "稳": 1, "保": 2, "不推荐": 3}.get(x.get("bucket"), 9),
    )
    items = []
    for item in ordered[: policy.parallel_volunteer_count]:
        majors = item.get("selected_majors", [])
        if len(majors) > policy.major_count_per_group:
            majors = majors[: policy.major_count_per_group]
        items.append(
            {
                **item,
                "volunteer_unit": "院校专业组",
                "selected_majors": majors,
            }
        )
    return {
        "policy_count": policy.parallel_volunteer_count,
        "items": items,
    }


def build_henan_candidates(profile: dict) -> list[dict]:
    """Build homepage recommendation candidates.

    The production implementation loads 2026 Henan program groups, 2026 Henan
    plans, 2025/2024 admission history, costs, and employment signals before
    calling check_henan_eligibility() and classify_henan_bucket().
    """
    if profile.get("source_province") not in (None, "河南"):
        raise ValueError("河南志愿推仅支持河南考生")
    return []
```

Create `app/engine/henan_policy.py`:

```python
def assert_henan_only(province: str) -> None:
    if province != "河南":
        raise ValueError("河南志愿推仅支持河南考生")
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/engine/test_henan_recommendation.py --basetemp .pytest-tmp -q`

Expected: 3 passed.

---

### Task 4: 合并费用页到推荐和目标评估

**Files:**
- Modify: `web-ui/src/App.tsx`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Modify: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Test: `web-ui/e2e/navigation.spec.ts`

**Interfaces:**
- Removes visible `/cost` navigation.
- Keeps cost fields in result cards.

- [ ] **Step 1: Write e2e test**

Create `web-ui/e2e/navigation.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("大学费用不再作为独立导航出现", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "大学费用" })).toHaveCount(0);
});

test("推荐结果仍展示费用", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /生成志愿表|生成中/ }).click();
  await expect(page.getByText(/4年费用|代表院校4年费用|¥/)).toBeVisible({ timeout: 15000 });
});
```

- [ ] **Step 2: Modify navigation**

In `web-ui/src/App.tsx`, remove the visible nav link to `/cost`. Keep route only if backward compatibility is required:

```tsx
// Remove: <NavLink to="/cost">大学费用</NavLink>
```

- [ ] **Step 3: Verify build**

Run: `npm.cmd run build`

Expected: build succeeds.

---

### Task 5: 首页表单和筛选改为冲稳保

**Files:**
- Modify: `web-ui/src/components/ScoreForm.tsx`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Modify: `web-ui/src/api/types.ts`
- Test: `web-ui/e2e/advisory.spec.ts`

**Interfaces:**
- Replaces strategy buttons with `冲 / 稳 / 保 / 全部`.
- Adds focused schools and interest majors.

- [ ] **Step 1: Add TypeScript fields**

Modify advisory request type in `web-ui/src/api/types.ts`:

```ts
focused_schools?: string[];
interest_majors?: string[];
display_bucket?: "全部" | "冲" | "稳" | "保";
```

- [ ] **Step 2: Modify ScoreForm**

Change strategy options:

```ts
const RISK_OPTIONS = [
  { value: "冲", label: "冲", desc: "只看冲刺志愿" },
  { value: "稳", label: "稳", desc: "只看稳妥志愿" },
  { value: "保", label: "保", desc: "只看保底志愿" },
];
```

Add two inputs:

```tsx
<input
  value={focusedSchoolsText}
  onChange={(e) => setFocusedSchoolsText(e.target.value)}
  placeholder="关注院校，用空格或逗号分隔"
/>
<input
  value={interestMajorsText}
  onChange={(e) => setInterestMajorsText(e.target.value)}
  placeholder="兴趣专业，用空格或逗号分隔"
/>
```

Submit:

```ts
focused_schools: splitWords(focusedSchoolsText),
interest_majors: splitWords(interestMajorsText),
display_bucket: risk,
```

- [ ] **Step 3: Filter visible buckets**

In `HomePage.tsx`, store selected bucket and only render matching bucket:

```tsx
const visibleBuckets = selectedBucket === "全部"
  ? BUCKETS
  : BUCKETS.filter((b) => b.label === selectedBucket);
```

- [ ] **Step 4: Build**

Run: `npm.cmd run build`

Expected: build succeeds.

---

### Task 6: 目标评估页面联动院校/专业/专业组

**Files:**
- Create or replace: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Modify: `web-ui/src/api/client.ts`
- Modify: `web-ui/src/api/types.ts`
- Create: `app/engine/target_evaluation.py`
- Test: `tests/engine/test_target_evaluation.py`
- Test: `tests/api/test_target_evaluation_api.py`
- Create API endpoint: `GET /api/v1/henan/options`
- Create API endpoint: `POST /api/v1/henan/target-evaluation`

**Interfaces:**
- Produces frontend options:
  - schools
  - majors by school
  - groups by school
- Produces target evaluation:
  - `evaluate_target_school(profile: dict, target_school: str, target_majors: list[str], target_group: str | None, candidates: list[dict]) -> dict`
  - Reuses `check_henan_eligibility(...)` and `classify_henan_bucket(...)` from Task 3.
  - Returns school-level `不推荐` when no target major/group qualifies for `冲` / `稳` / `保`.

- [ ] **Step 1: API options test**

Create `tests/api/test_henan_options_api.py`:

```python
from fastapi.testclient import TestClient

from app.api.main import app


def test_henan_options_returns_schools():
    client = TestClient(app)
    r = client.get("/api/v1/henan/options")
    assert r.status_code == 200
    body = r.json()
    assert "schools" in body
```

- [ ] **Step 2: Implement options router**

Create `app/api/routers/henan.py`:

```python
from pathlib import Path

from fastapi import APIRouter

from app.loader.henan_data_loader import (
    load_henan_enrollment_plans,
    load_henan_program_groups,
    load_henan_universities,
)

router = APIRouter(prefix="/henan", tags=["henan"])


@router.get("/options")
def options():
    seed = Path("data/seed")
    universities = load_henan_universities(seed)
    plans = load_henan_enrollment_plans(seed)
    groups = load_henan_program_groups(seed)
    return {
        "schools": [{"code": u.school_code, "name": u.school_name} for u in universities],
        "majors": [
            {"school": p.school_name, "major": p.major_name, "group": p.major_group_code}
            for p in plans
        ],
        "groups": [
            {"school": g.school_name, "code": g.major_group_code, "name": g.major_group_name}
            for g in groups
        ],
    }
```

Register in `app/api/main.py`:

```python
from app.api.routers import henan
app.include_router(henan.router, prefix="/api/v1")
```

- [ ] **Step 3: Write target evaluation engine tests**

Create `tests/engine/test_target_evaluation.py`:

```python
from app.engine.target_evaluation import evaluate_target_school


def _candidate(school, major, group, bucket, rank_gap=0, qualified=True):
    return {
        "school_name": school,
        "major_name": major,
        "major_group_code": group,
        "major_group_name": f"{group}组",
        "bucket": bucket,
        "rank_gap": rank_gap,
        "qualified": qualified,
        "blocked_reasons": [] if qualified else ["选科或语种不符合"],
        "bucket_reason": "复用首页专业推荐冲稳保逻辑",
    }


def test_target_school_returns_reachable_majors_by_bucket():
    result = evaluate_target_school(
        profile={"score": 610, "rank": 12000, "track": "历史类", "source_province": "河南"},
        target_school="郑州大学",
        target_majors=[],
        target_group=None,
        candidates=[
            _candidate("郑州大学", "法学", "101", "冲", rank_gap=800),
            _candidate("郑州大学", "历史学", "102", "稳", rank_gap=-500),
            _candidate("河南大学", "汉语言文学", "201", "稳", rank_gap=-1000),
        ],
    )

    assert result["school_name"] == "郑州大学"
    assert result["overall_bucket"] == "可评估"
    assert [item["bucket"] for item in result["items"]] == ["冲", "稳"]
    assert {item["major_group_code"] for item in result["items"]} == {"101", "102"}


def test_target_school_filters_to_selected_majors():
    result = evaluate_target_school(
        profile={"score": 610, "rank": 12000, "track": "历史类", "source_province": "河南"},
        target_school="郑州大学",
        target_majors=["历史学"],
        target_group=None,
        candidates=[
            _candidate("郑州大学", "法学", "101", "冲", rank_gap=800),
            _candidate("郑州大学", "历史学", "102", "稳", rank_gap=-500),
        ],
    )

    assert len(result["items"]) == 1
    assert result["items"][0]["major_name"] == "历史学"
    assert result["items"][0]["bucket"] == "稳"


def test_target_school_rejects_when_no_major_or_group_is_reachable():
    result = evaluate_target_school(
        profile={"score": 480, "rank": 85000, "track": "历史类", "source_province": "河南"},
        target_school="郑州大学",
        target_majors=[],
        target_group=None,
        candidates=[
            _candidate("郑州大学", "法学", "101", "不推荐", rank_gap=35000, qualified=True),
            _candidate("郑州大学", "历史学", "102", "不推荐", rank_gap=32000, qualified=True),
        ],
    )

    assert result["school_name"] == "郑州大学"
    assert result["overall_bucket"] == "不推荐"
    assert result["items"] == []
    assert "没有达到冲稳保条件的专业或专业组" in result["reasons"]


def test_target_evaluation_keeps_group_and_major_risk_separate():
    result = evaluate_target_school(
        profile={"score": 500, "rank": 52000, "track": "历史类", "source_province": "河南"},
        target_school="河南牧业经济学院",
        target_majors=["会计学"],
        target_group=None,
        candidates=[
            {
                "school_name": "河南牧业经济学院",
                "major_name": "会计学",
                "major_group_code": "101",
                "major_group_name": "历史不限组",
                "bucket": "冲",
                "qualified": True,
                "group_bucket": "冲",
                "major_bucket": "不推荐",
                "selected_majors": ["会计学", "财务管理"],
                "bucket_reason": "专业组可冲，但会计学历史专业位次不足",
                "blocked_reasons": [],
            }
        ],
    )

    assert result["items"][0]["group_bucket"] == "冲"
    assert result["items"][0]["major_bucket"] == "不推荐"
    assert "专业组可冲" in result["items"][0]["bucket_reason"]
```

- [ ] **Step 4: Implement target evaluation engine**

Create `app/engine/target_evaluation.py`:

```python
REACHABLE_BUCKETS = {"冲", "稳", "保"}


def evaluate_target_school(
    profile: dict,
    target_school: str,
    target_majors: list[str],
    target_group: str | None,
    candidates: list[dict],
) -> dict:
    if profile.get("source_province") not in (None, "河南"):
        return {
            "school_name": target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": ["河南志愿推仅支持河南考生"],
        }

    scoped = [item for item in candidates if item.get("school_name") == target_school]
    if target_majors:
        scoped = [item for item in scoped if item.get("major_name") in target_majors]
    if target_group:
        scoped = [item for item in scoped if item.get("major_group_code") == target_group]

    reachable = [
        item
        for item in scoped
        if item.get("qualified", True) and item.get("bucket") in REACHABLE_BUCKETS
    ]

    if not reachable:
        reasons = ["没有达到冲稳保条件的专业或专业组"]
        blocked = [reason for item in scoped for reason in item.get("blocked_reasons", [])]
        reasons.extend(sorted(set(blocked)))
        return {
            "school_name": target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": reasons,
        }

    return {
        "school_name": target_school,
        "overall_bucket": "可评估",
        "items": reachable,
        "reasons": [],
    }
```

- [ ] **Step 5: Write target evaluation API tests**

Create `tests/api/test_target_evaluation_api.py`:

```python
from fastapi.testclient import TestClient

from app.api.main import app


def test_target_evaluation_returns_not_recommended_for_unreachable_school():
    client = TestClient(app)
    response = client.post(
        "/api/v1/henan/target-evaluation",
        json={
            "score": 480,
            "rank": 85000,
            "track": "历史类",
            "source_province": "河南",
            "target_school": "郑州大学",
            "target_majors": [],
            "target_group": None,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_bucket"] == "不推荐"
    assert body["items"] == []
```

- [ ] **Step 6: Implement target evaluation API endpoint**

Add to `app/api/routers/henan.py`:

```python
from pydantic import BaseModel

from app.engine.henan_recommendation import build_henan_candidates
from app.engine.target_evaluation import evaluate_target_school


class HenanTargetEvaluationRequest(BaseModel):
    score: int
    rank: int | None = None
    track: str
    source_province: str = "河南"
    target_school: str
    target_majors: list[str] = []
    target_group: str | None = None
    exam_foreign_language: str = "英语"
    subjects: list[str] = []
    obey_adjustment: bool = True


@router.post("/henan/target-evaluation")
def henan_target_evaluation(req: HenanTargetEvaluationRequest):
    profile = req.model_dump()
    candidates = build_henan_candidates(profile)
    return evaluate_target_school(
        profile=profile,
        target_school=req.target_school,
        target_majors=req.target_majors,
        target_group=req.target_group,
        candidates=candidates,
    )
```

`build_henan_candidates(profile)` must be the same candidate generator used by the homepage professional recommendation flow. It must already apply `check_henan_eligibility(...)`, 2026 Henan plan validation, subject/language restrictions, and `classify_henan_bucket(...)`. The target endpoint may filter that candidate list by school, major, or group, but it must not recalculate a looser result.

- [ ] **Step 7: Build target page**

Implement `TargetEvaluationPage.tsx` with:

- school select
- multi-select target majors
- optional group select
- score/subjects/language fields
- result cards grouped by `冲 / 稳 / 保`
- school-level `不推荐` state when the API returns no reachable major or major group
- explicit reasons such as rank gap, missing Henan plan, subject mismatch, language restriction, or no reachable major group

- [ ] **Step 8: Verify**

Run:

```powershell
python -m pytest tests/api/test_henan_options_api.py tests/api/test_target_evaluation_api.py tests/engine/test_target_evaluation.py --basetemp .pytest-tmp
npm.cmd run build
```

Expected: pass.

---

### Task 7: 就业信号接入

**Files:**
- Create: `app/engine/henan_employment.py`
- Test: `tests/engine/test_henan_employment.py`

**Interfaces:**
- Produces:
  - `score_employment_signal(major_name, signals) -> dict`

- [ ] **Step 1: Write failing tests**

Create `tests/engine/test_henan_employment.py`:

```python
from app.engine.henan_employment import score_employment_signal
from app.models.henan_data import MajorEmploymentSignal


def test_missing_employment_data_is_explicit():
    result = score_employment_signal("历史学", [])
    assert result["status"] == "就业数据不足"


def test_signal_returns_summary():
    signal = MajorEmploymentSignal(
        major_name="计算机科学与技术",
        direction="计算机",
        policy_signal="数字经济相关",
        domestic_demand_summary="软件开发岗位较多",
        job_market_city_scope="北上广深",
        evidence_level="C",
        source_name="阳光高考专业库",
        source_url="https://gaokao.chsi.com.cn/",
        as_of="2026-06-26",
        confidence=0.5,
    )
    result = score_employment_signal("计算机科学与技术", [signal])
    assert result["status"] == "有就业信号"
    assert "软件开发" in result["summary"]
```

- [ ] **Step 2: Implement**

Create `app/engine/henan_employment.py`:

```python
def score_employment_signal(major_name: str, signals: list) -> dict:
    signal = next((s for s in signals if s.major_name == major_name), None)
    if signal is None:
        return {
            "status": "就业数据不足",
            "summary": "暂无足够就业数据，不能用就业前景作为主要推荐依据",
            "confidence": 0.0,
        }
    return {
        "status": "有就业信号",
        "summary": signal.domestic_demand_summary,
        "policy_signal": signal.policy_signal,
        "evidence_level": signal.evidence_level,
        "confidence": signal.confidence,
    }
```

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/engine/test_henan_employment.py --basetemp .pytest-tmp -q`

Expected: 2 passed.

---

### Task 8: 全量验收

- [ ] **Step 1: Run Python tests**

Run:

```powershell
python -m pytest tests/models tests/loader tests/engine tests/api --basetemp .pytest-tmp
```

Expected: all pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
npm.cmd run build
```

Working directory: `web-ui`

Expected: build succeeds.

- [ ] **Step 3: Browser smoke**

Open `http://localhost:5173/`:

- Product title is “河南志愿推”.
- Navigation has no standalone “大学费用”.
- Strategy buttons are “冲 / 稳 / 保”.
- Choosing “冲” only shows 冲 bucket.
- Historical + Japanese default scenario blocks English-only majors.
- Focused school appears in analysis result.
- Interest major affects candidate list.
- Target evaluation page has school dropdown and major multi-select.
