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
