from enum import Enum

from pydantic import BaseModel

from app.models.base import SourcedRecord


class RiskPreference(str, Enum):
    SAFE = "稳"
    BALANCED = "中"
    AGGRESSIVE = "冲"


class MinorLanguage(BaseModel):
    lang: str
    level: str


class FamilyResources(BaseModel):
    has_govt_resource: bool = False
    has_medical_resource: bool = False
    has_education_resource: bool = False
    has_finance_resource: bool = False
    has_law_resource: bool = False
    has_business_resource: bool = False


class StudentProfile(SourcedRecord):
    """考生画像——模拟填报志愿的核心输入结构。"""

    province: str
    total_score: int
    subject_scores: dict[str, int]
    minor_language: MinorLanguage | None = None
    family_resources: FamilyResources
    gender: str
    interests: list[str]
    strengths: list[str]
    risk_preference: RiskPreference
    # 新高考选科与单科要求相关（3+1+2模式）
    foreign_language: str = "英语"  # 外语语种：英语/日语/俄语/德语/法语/西班牙语
    elective_subjects: list[str] = []  # 再选科目(3+1+2的"2")，如["政治","地理"]
    subject_scores_detail: dict[str, int] = {}  # 单科分数，如{"数学":95,"外语":110,"物理":80}
