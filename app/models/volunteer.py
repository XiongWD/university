"""志愿填报引擎的输入输出 domain 模型（纯 Pydantic，不入库）。"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Strategy(str, Enum):
    """冲稳保三档：位次越靠前(数字越小)越难录。"""

    SPRINT = "冲"  # 学校录取位次显著优于考生 → 有希望但冒险
    STABLE = "稳"  # 位次接近 → 匹配度最高
    SAFE = "保"  # 学校录取位次显著低于考生 → 兜底


class AdmissionProbability(BaseModel):
    """单个志愿的录取概率估算。"""

    probability: float  # 0-1，估算录取概率
    basis: str  # 估算依据说明，如"近1年位次匹配"


class VolunteerSuggestion(BaseModel):
    """单条志愿建议。"""

    strategy: Strategy
    school: str
    major: Optional[str] = None
    major_group: Optional[str] = None
    subject_requirement: Optional[str] = None
    last_year_rank: int  # 学校最近一年录取最低位次
    last_year_score: int  # 学校最近一年录取最低分
    student_rank: int  # 考生等效位次
    probability: AdmissionProbability
    note: Optional[str] = None


class VolunteerTable(BaseModel):
    """完整志愿表（冲稳保分档 + 溯源）。"""

    student_score: int
    student_rank: int  # 今年位次
    equivalent_rank: Optional[int]  # 折算到数据年份的等效位次（若有折算）
    track: str
    data_year: int  # 录取数据所属年份
    sprint: list[VolunteerSuggestion]
    stable: list[VolunteerSuggestion]
    safe: list[VolunteerSuggestion]
    source_note: str  # 数据来源与时效说明，如"基于2024历年数据预测"


# ── 我的志愿组（用户手动编排，持久化，design：志愿编排工作台）──────────────


class UserVolunteerItem(BaseModel):
    """志愿项（院校专业组）。展示字段由 GET 时用当前推荐引擎重算，非依赖添加时快照。"""

    id: int
    group_id: int
    school_code: str
    school_name: str
    major_group_code: str
    major_group_name: str
    algorithm_tier_at_add: str  # 添加时算法档位（审计快照，不变）
    latest_algorithm_tier: str  # GET 时用 profile_snapshot 重算的当前档位
    algorithm_changed: bool  # 当前档位 != 添加时（数据/规则变化时提示，不覆盖规划档）
    planned_tier: Optional[str] = None  # 用户规划档位（搏/冲/稳/保/垫）；null=用算法档
    effective_tier: str  # planned_tier or latest_algorithm_tier（展示/统计用）
    sort_order: int
    eligibility_status: str  # 当前资格状态（GET 重算：eligible/partially_eligible/uncertain/ineligible）
    # 拍平展示字段（GET 重算）——支持对比决策（学费/位次/计算公式）
    is_henan_local: Optional[bool] = None
    school_ownership: Optional[str] = None
    school_city: Optional[str] = None
    four_year_total: Optional[int] = None
    tuition_per_year: Optional[int] = None  # 学费/年
    accommodation: Optional[int] = None  # 住宿费/年
    plan_count: Optional[int] = None  # 2026河南计划人数
    selected_majors: Optional[list[str]] = None  # 组内专业（对比用）
    # 位次对比 + 计算公式（GET 重算，供展开详情对比）
    student_rank: Optional[int] = None
    reference_rank: Optional[int] = None  # 归一化后参考录取位次
    advantage: Optional[int] = None  # 参考位次 − 考生位次
    advantage_ratio: Optional[float] = None  # advantage / 考生位次
    baseline_year: Optional[int] = None  # 参考数据年份
    risk_level: Optional[str] = None  # 风险等级文字
    # 真实志愿填报代码（来自 heao）：yxdh=河南院校代码，zyzh=专业组号
    yxdh: Optional[str] = None
    zyzh: Optional[str] = None


class StructureHint(BaseModel):
    """志愿组结构平衡提示（温和，非官方要求，标注可配置）。"""

    code: str
    message: str
    severity: str = "info"  # info / warning


class VolunteerStats(BaseModel):
    """志愿组统计（档位/地域/性质 + 温和结构提示）。"""

    total: int
    by_effective_tier: dict[str, int]  # effective_tier 统计（规划优先）
    by_algorithm_tier: dict[str, int]
    local_count: int
    out_of_province_count: int
    public_count: int
    private_count: int
    structure_hints: list[StructureHint] = []


class UserVolunteerGroup(BaseModel):
    """志愿方案（含 items + stats）。"""

    id: int
    owner_key: str
    name: str
    version: int
    manually_reordered: bool
    profile_snapshot: dict
    items: list[UserVolunteerItem]
    stats: VolunteerStats


class VolunteerConflictError(Exception):
    """乐观锁冲突（version 不符），HTTP 层映射为 409。"""

    def __init__(self, message: str, latest_group: "UserVolunteerGroup | None" = None):
        super().__init__(message)
        self.latest_group = latest_group
