"""河南志愿推底层数据模型（design §4）。

覆盖：志愿规则政策、院校属性、历史录取、2026 专业组、招生计划、
费用画像、就业信号。所有模型继承 SourceStamped，强制来源/时间/置信度可追溯。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceStamped(BaseModel):
    """带来源追溯的记录基类（design §2：每条数据必须有来源与置信度）。"""

    source_name: str
    source_url: str
    source_api_endpoint: str = ""
    source_params: str = ""
    source_page: str = ""
    source_response_checksum: str = ""
    as_of: str
    confidence: float = Field(ge=0, le=1)
    review_status: str = "verified"


class HenanAdmissionPolicy(SourceStamped):
    """河南志愿规则配置（design §3.1）。志愿数量等必须从官方核验。"""

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
    """在河南招生院校属性（design §4.1）。含省内与省外院校。"""

    school_code: str
    school_name: str
    province: str
    city: str
    ownership: str  # 公办 / 民办 / 中外合作 / 独立学院 / 高职高专
    school_level: str = ""  # 985 / 211 / 双一流 / 省重点 / 普通本科 / 高职高专
    strong_majors: list[str] = []
    tags: list[str] = []
    # 真实志愿填报用（design §4.1 扩展）：
    # yxdh = 河南省考试院院校代码（考生在志愿系统实际输入的代码，≠国标码≠gaokao.cn school_id）
    henan_school_code: str = ""
    # 官网 / 招生网站（供人工复核查 2026 招生简章，来自 heao schoolBaseInfo）
    official_website: str = ""
    enrollment_website: str = ""


class HenanAdmissionHistory(SourceStamped):
    """2025/2024 历史录取分数和位次（design §4.2）。"""

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
    data_granularity: str  # major / major_group / school


class HenanProgramGroup(SourceStamped):
    """2026 院校专业组和专业限制（design §4.3）。"""

    year: int
    track: str
    batch: str = "本科批"
    school_code: str
    school_name: str
    major_group_code: str
    major_group_name: str
    # 真实志愿填报用（design §4.3 扩展）：
    # volunteer_group_code = 河南省考试院专业组代码（考生在志愿系统实际输入的专业组号，
    # 来自 heao zyzh；≠ gaokao.cn major_group_code）。缺失时用 major_group_code 兜底展示。
    volunteer_group_code: str = ""
    included_majors: list[str] = []
    major_codes: list[str] = []
    primary_subject_requirement: str | None = None  # 物理 / 历史 / 空
    elective_subject_requirement: dict = {}  # {"require": [...], "any_of": [...]}
    required_exam_language: str | None = None
    accepted_exam_languages: list[str] = []
    public_foreign_languages: list[str] = []
    single_subject_requirements: list[dict] = []
    oral_test_required: bool = False
    adjustment_scope: str = ""  # 调剂范围（仅组内）
    # 语种规则作用域标记（资格链专业级下沉，design §3.4/§8.2）：
    # True = 组内各专业语种规则不一致，组级 accepted/required 已置空，
    #         运行时必须按专业级 plan.accepted_exam_languages 逐专业判断；
    # False = 组内全专业规则一致，组级字段即为有效限制。
    has_mixed_language_rules: bool = False
    # 体检/专项限制（design §4.3 扩展）
    physical_restrictions: str = ""  # 辨色力异常 / 身高要求 / 视力要求 / 听说要求
    special_qualification_type: str = ""  # 高校专项 / 地方专项 / 国家专项 / 公费师范 / 定向医学生 / 中外合作 / 高收费
    remarks: str = ""


class HenanEnrollmentPlan(SourceStamped):
    """2026 面向河南招生计划（design §4.4）。source_province 固定河南。"""

    year: int
    source_province: str = "河南"  # 考生生源地，固定河南
    school_origin_province: str = ""  # 高校所在地，区分省内/省外
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
    # 资格链扩展字段（design §4.4 扩展）
    campus: str = ""  # 办学地点
    physical_restrictions: str = ""  # 体检限制文本
    special_qualification_type: str = ""  # 专项类型
    accepted_exam_languages: str = ""  # 接受外语语种
    remarks: str = ""


class HenanCostProfile(SourceStamped):
    """院校/专业费用画像（design §4.5）。"""

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
    """专业就业与政策信号（design §4.6）。招聘数据仅作补充，不足时不编造。"""

    major_name: str
    direction: str
    policy_signal: str = ""
    domestic_demand_summary: str = ""
    job_market_city_scope: str = "河南"  # 全国 / 北上广深 / 河南
    boss_job_count: int | None = None
    salary_p25: int | None = None
    salary_p50: int | None = None
    salary_p75: int | None = None
    evidence_level: str  # 证据等级
