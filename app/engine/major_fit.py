"""专业适配引擎（P0-专业评分，纯函数）。

核心：major_value = market_value × student_fit（乘法门控）。
- market_value 来自 job_market 引擎的 MarketScores
- student_fit = 选科资格 + 数学适配 + 外语适配 + 学习难度 + 兴趣意愿
- 乘法门控：student_fit 极低则整体坍缩，不靠其他维度加分补救。
  例：数学适配0.2的学生，即使计算机 market_value=0.9，major_value=0.18，不会排前列。

拆分两类分数（评审纠正）：
- 专业市场价值 market_value（外部客观，与考生无关）
- 学生专业适配 student_fit（与考生能力/选科/兴趣耦合）
最终乘法合成，确保"学得会"先于"市场好"。
"""
from __future__ import annotations

from app.engine.job_market import MarketScores
from app.models.major import Major
from app.models.student import StudentProfile


def _math_fit(student: StudentProfile, major: Major) -> float:
    """数学适配：专业要求数学(barriers.math)时，看考生数学分。

    不要求数学的专业返回1.0（不构成障碍）；要求时按分数归一。
    """
    if not major.barriers.math:
        return 1.0
    math_score = student.subject_scores_detail.get("数学")
    if math_score is None:
        return 0.5  # 无数据中性
    # 满分150，90=及格线。90以下显著降级，120+优秀
    if math_score >= 120:
        return 1.0
    if math_score >= 100:
        return 0.8
    if math_score >= 90:
        return 0.6
    if math_score >= 75:
        return 0.35  # 及格线下，明显不适合
    return 0.15  # 极低，乘法门控会拉垮整体


def _foreign_language_fit(student: StudentProfile, major: Major) -> float:
    """外语适配：专业要求英语(barriers.english)时，看考生外语语种+分数。

    - 日语考生+要求英语的专业返回降级值（非直接0，因部分专业可适应，但显著低）
    - 日语考生+不要求英语返回1.0
    """
    if not major.barriers.english:
        return 1.0
    # 专业要求英语能力
    if student.foreign_language != "英语":
        # 小语种考生面对英语要求专业，适配降低（但非完全不可，可补救）
        return 0.4
    fl_score = student.subject_scores_detail.get("外语")
    if fl_score is None:
        return 0.6
    if fl_score >= 120:
        return 1.0
    if fl_score >= 100:
        return 0.8
    if fl_score >= 90:
        return 0.6
    return 0.3


def _subject_eligibility(student: StudentProfile, major: Major) -> float:
    """选科资格适配（简化：精确资格在eligibility引擎硬过滤）。

    此处返回1.0（资格是硬过滤层职责，不在适配打分重复）。
    """
    return 1.0


def _interest_fit(student: StudentProfile, major: Major) -> float:
    """兴趣适配：考生interests/strengths含专业相关关键词则加分。"""
    text = " ".join(student.interests + student.strengths).lower()
    major_name = major.name.lower()
    major_cat = major.category.lower()
    # 双向子串匹配：兴趣词是专业名子串，或专业名token在兴趣文本中
    interest_tokens = [t for t in text.split() if len(t) >= 2]
    name_tokens = [t for t in major_name.replace("与", " ").split() if len(t) >= 2]
    if any(it in major_name for it in interest_tokens) or any(nt in text for nt in name_tokens):
        return 1.0
    if major_cat in text:
        return 0.8
    return 0.6  # 无明确兴趣匹配，中性偏好


def _certificate_postgrad_fit(student: StudentProfile, major: Major) -> float:
    """证书/考研依赖适配：需证书或考研的专业，对"求稳"考生略降（时间长投入）。"""
    if student.risk_preference.value == "稳":
        if major.barriers.postgrad:
            return 0.7  # 稳健考生对考研依赖专业略保守
        if major.barriers.certificate:
            return 0.85
    return 1.0


def compute_student_fit(student: StudentProfile, major: Major) -> float:
    """计算学生-专业适配分(0-1)。

    硬门槛维度（数学/外语）用乘法合成（任一极低即坍缩），软维度（兴趣/证书）加权。
    这是评审强调的乘法门控：加法会被高分稀释，数学0.35不该被兴趣0.6救回。

    硬门槛（乘法）：math_fit × language_fit（专业有要求时）
    软维度（加权）：interest 0.6 + cert 0.4
    合成：hard_gate × soft_avg，确保"学不会"优先于"感兴趣"。
    """
    # 硬门槛：专业有要求时该维度参与乘法门控；无要求时为1.0（不拖累）
    hard = _math_fit(student, major) * _foreign_language_fit(student, major)
    # 软维度：加权平均
    soft = 0.6 * _interest_fit(student, major) + 0.4 * _certificate_postgrad_fit(student, major)
    # 选科资格作为独立因子（硬过滤层已保证资格，此处1.0）
    # 合成：硬门槛门控软维度
    return hard * (0.5 + 0.5 * soft)  # soft影响缩放，但hard是主控


def compute_major_value(
    market_scores: MarketScores,
    student: StudentProfile,
    major: Major,
    market_weight: float = 0.6,
) -> tuple[float, dict]:
    """计算专业综合价值 = market_value x student_fit（乘法门控）。

    market_value = current_market_score 与 future_outlook_score 的加权。
    返回 (major_value 0-1, breakdown 各维度得分)。

    乘法门控含义：student_fit=0.2 + market_value=0.9 得到 0.18（坍缩），
    不会被高分市场补救——"学不会的专业市场再好也不推"。
    """
    # market_value: 当前与未来加权（默认当前为主，因应届首先看就业）
    market_value = market_weight * market_scores.current_market_score + (
        1 - market_weight
    ) * market_scores.future_outlook_score

    student_fit = compute_student_fit(student, major)

    # 乘法门控核心
    major_value = market_value * student_fit

    breakdown = {
        "market_value": round(market_value, 3),
        "current_market": market_scores.current_market_score,
        "future_outlook": market_scores.future_outlook_score,
        "student_fit": round(student_fit, 3),
        "major_value": round(major_value, 3),
        "career_stage": market_scores.career_stage.value,
        "evidence_level": market_scores.evidence_level,
    }
    return round(major_value, 3), breakdown
