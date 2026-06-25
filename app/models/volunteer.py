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
