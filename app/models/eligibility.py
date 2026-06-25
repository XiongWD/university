"""资格链模型（V2.2 第0层——定义可行解空间）。

核心纠正（评审）：
- 高考应试语种（硬约束）≠ 外语单科成绩（门槛）≠ 实际英语能力（软适配）
- 数学仅章程明确门槛才硬过滤，否则只能标学习风险
- 选科用于资格过滤，不单独生成另一套位次
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EnglishLevel(str, Enum):
    """实际英语能力（与高考应试语种独立）。"""

    NONE = "none"          # 几乎无英语能力（如日语考生未系统学英语）
    BASIC = "basic"        # 基础（能简单交流，四六级难通过）
    INTERMEDIATE = "intermediate"  # 中等（四级水平）
    ADVANCED = "advanced"  # 高级（六级+/流利）


class BlockedField(str, Enum):
    """资格被阻挡的字段类型（用于EligibilityResult诊断）。"""

    EXAM_LANGUAGE = "exam_language"      # 高考应试语种不符
    FOREIGN_SCORE = "foreign_score"      # 外语单科不达标
    ENGLISH_SCORE = "english_score"      # 英语单科不达标（限英语语种专业）
    MATH_SCORE = "math_score"            # 数学单科不达标
    PRIMARY_SUBJECT = "primary_subject"  # 首选科目（历史/物理）不符
    ELECTIVE_SUBJECT = "elective_subject"  # 再选科目不符
    ORAL_TEST = "oral_test"              # 口试要求不符
    OTHER = "other"


class StudentAcademicProfile(BaseModel):
    """考生学业画像（资格链输入）。

    关键区分（不可混用）：
    - exam_foreign_language + foreign_language_score：高考录取资格用
    - english_actual_level：入学后课程适配+就业用（日语考生可能英语薄弱）
    """

    province: str
    admission_year: int = 2026
    total_score: int
    primary_subject: str  # 历史 / 物理（3+1+2首选）

    # 单科高考实考分
    chinese_score: int = 0
    math_score: int = 0
    exam_foreign_language: str = "英语"  # 高考应试语种：日语/英语/俄语/德语/法语/西班牙语
    foreign_language_score: int = 0  # 该语种的高考成绩

    # 实际英语能力（与高考语种独立，软适配用）
    english_actual_level: EnglishLevel = EnglishLevel.INTERMEDIATE

    # 3+1+2 再选
    elective_subjects: list[str] = []  # 如["政治","地理"]

    # 口试
    oral_test_taken: bool | None = None
    oral_test_result: str | None = None


class SubjectScoreRule(BaseModel):
    """单科门槛规则（区分外语/英语/数学，区分语种适用）。"""

    subject: str  # math / foreign_language / english
    operator: str = ">="  # >= / >
    threshold: float
    score_full_mark: int = 150
    applies_to_exam_language: str | None = None  # None=不限语种适用；"英语"=仅英语考生
    source_text: str = ""  # 章程原文（可追溯）


class AdmissionOfferingRule(BaseModel):
    """招生专业组的资格规则（ABCD四类规则的载体）。

    从招生章程结构化提取，每个学校×专业组一条。
    """

    school: str
    major_group_code: str | None = None
    major_group_name: str = ""
    province: str
    batch: str = "本科批"

    # A类：高考应试语种（硬约束）
    accepted_exam_languages: list[str] = []  # 空=不限；["英语"]=仅英语；["英语","日语"]=两者可
    required_exam_language: str | None = None  # None=不限；"英语"=必须英语语种

    # B类：单科门槛（硬约束，需区分外语/英语）
    subject_score_rules: list[SubjectScoreRule] = []

    # C类：3+1+2 选科要求（硬约束）
    primary_subject_requirement: str | None = None  # 历史/物理，None=不限
    elective_subject_rule: dict = {}  # 如{"require": ["政治"], "any_of": []}，空=不限

    # D类：入学后语言风险（软约束，不挡资格但标风险）
    public_foreign_languages: list[str] = []  # 入学后公共外语开设，如["英语"]
    major_instruction_languages: list[str] = []  # 专业课授课语言
    english_dependency_level: str = "low"  # low/medium/high
    language_transition_risk: str = "low"  # low/medium/high

    # 口试
    oral_test_required: bool = False

    # 溯源
    source: str = ""
    as_of: str = ""
    confidence: float = 0.7


class EligibilityResult(BaseModel):
    """资格判定结果（Phase 1 核心输出）。"""

    eligible: bool
    reasons: list[str] = []  # 通过/不通过的具体原因（可解释）
    blocked_fields: list[BlockedField] = []  # 被哪个规则阻挡
    language_risk: str = "low"  # 软风险：入学后语言适应（low/medium/high）

    @property
    def blocked_summary(self) -> str:
        """人类可读的阻挡原因汇总。"""
        if self.eligible:
            return "符合资格"
        names = {
            BlockedField.EXAM_LANGUAGE: "高考应试语种不符",
            BlockedField.FOREIGN_SCORE: "外语单科分不达标",
            BlockedField.ENGLISH_SCORE: "英语单科分不达标",
            BlockedField.MATH_SCORE: "数学单科分不达标",
            BlockedField.PRIMARY_SUBJECT: "首选科目(历史/物理)不符",
            BlockedField.ELECTIVE_SUBJECT: "再选科目不符",
            BlockedField.ORAL_TEST: "口试要求不符",
        }
        return "；".join(names.get(f, f.value) for f in self.blocked_fields)
