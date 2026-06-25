"""填报规则引擎（8大专家规则，纯函数）。

把用户提供的河南填报指南内置成系统逻辑。
部分规则已在其他引擎实现（选科/调剂/学费），此处补充缺失的：
1. 在豫招生计划数→名额波动风险（计划少=大小年概率高）
2. 同位分换算→跨年位次可比性修正
4. 地域热度差异→省内外院校投档热度标注
7. 就业考公地域壁垒→省内认可度优势标注
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class QuotaRisk(str, Enum):
    """招生计划数→波动风险（规则1）。"""

    STABLE = "稳定"    # 计划≥10人，波动小
    MODERATE = "中等"  # 计划3-9人，有一定波动
    HIGH = "高波动"    # 计划1-2人，大小年概率高，仅乐观场景可录也算冲


class RegionHeat(str, Enum):
    """地域热度（规则4，影响同档次院校分差）。"""

    INLAND_LOW = "中西部低热"   # 河南/中西部地市，投档线友好
    IN_PROVINCE = "省内"        # 河南省内，认可度高+计划多
    COASTAL_HIGH = "沿海高热"   # 江浙沪/广东/山东，投档线高15-40分


class EmploymentBarrier(BaseModel):
    """就业地域壁垒（规则7）。"""

    province_recognition: str  # 省内认可度: high/medium/low
    civil_service_advantage: str  # 考公考编优势: high/medium/low
    note: str = ""


def assess_quota_risk(planned_enrollment: int | None) -> tuple[QuotaRisk, str]:
    """规则1：招生计划数→波动风险。

    名额越少波动越大：1-2人极易大小年，3-9人有波动，≥10人稳定。
    """
    if planned_enrollment is None:
        return QuotaRisk.MODERATE, "计划数未知，假设中等波动"
    if planned_enrollment >= 10:
        return QuotaRisk.STABLE, f"计划{planned_enrollment}人，名额充足波动小"
    if planned_enrollment >= 3:
        return QuotaRisk.MODERATE, f"计划仅{planned_enrollment}人，有一定波动风险"
    return QuotaRisk.HIGH, f"计划仅{planned_enrollment}人！极易大小年，去年分低今年可能暴涨"


def convert_same_rank_score(
    student_rank: int,
    target_year_entries: list,  # ScoreRankEntry of target year
    student_year_entries: list,  # ScoreRankEntry of student's year
) -> int | None:
    """规则2：同位分换算——今年位次→目标年份等效分数。

    核心用法：今年480分位次73822 → 查2024年位次73822对应几分（同位分）。
    用同位分对比院校往年投档线，而非裸分480硬比。
    """
    from app.engine.rank_query import rank_to_score
    # 先确保student_rank在student_year的合理范围
    if not target_year_entries or student_rank <= 0:
        return None
    return rank_to_score(target_year_entries, student_rank)


def assess_region_heat(school_province: str, student_province: str = "河南") -> tuple[RegionHeat, str]:
    """规则4：地域热度差异。

    沿海(江浙沪粤鲁)投档线比同档次内陆高15-40分；
    省内认可度高+计划多；中西部地市最友好。
    """
    coastal = {"江苏", "浙江", "上海", "广东", "山东", "福建"}
    if school_province == student_province:
        return RegionHeat.IN_PROVINCE, "省内院校：计划多、认可度高、就业校招优势"
    if school_province in coastal:
        return RegionHeat.COASTAL_HIGH, f"{school_province}沿海院校：同档次投档线比内陆高15-40分，480分段基本只能冲民办"
    return RegionHeat.INLAND_LOW, f"{school_province}中西部/东北院校：投档线友好，480分段公办机会多"


def assess_employment_barrier(
    school_province: str, student_province: str = "河南"
) -> EmploymentBarrier:
    """规则7：就业考公地域壁垒。

    河南体制内(教师/公务员/事业单位)招聘，省内院校认可度高于外地普通二本。
    打算回河南就业→同等分数优先省内公办。
    """
    if school_province == student_province:
        return EmploymentBarrier(
            province_recognition="high",
            civil_service_advantage="high",
            note="省内院校：河南企业/中小学/国企校招优先本地，实习校招资源多",
        )
    # 省外
    return EmploymentBarrier(
        province_recognition="medium" if school_province in ("江西", "安徽", "湖北", "山西", "陕西") else "low",
        civil_service_advantage="low",
        note=f"省外({school_province})院校：回河南就业认可度低于省内同档次，考公考编无地域优势",
    )


def generate_filling_advice(
    school: str,
    school_province: str,
    planned_enrollment: int | None,
    student_province: str = "河南",
    admission_level: str = "稳",
) -> list[str]:
    """生成填报建议（综合规则1/4/5/7，可解释的专家提示）。

    返回建议列表，供前端展示给家长和考生。
    """
    advice: list[str] = []

    # 规则1：名额波动
    quota_risk, quota_note = assess_quota_risk(planned_enrollment)
    if quota_risk == QuotaRisk.HIGH:
        advice.append(f"⚠ {quota_note}。建议仅作冲刺，不要当稳保")
    elif quota_risk == QuotaRisk.MODERATE:
        advice.append(f"● {quota_note}，参考位次而非裸分")

    # 规则4：地域热度
    heat, heat_note = assess_region_heat(school_province, student_province)
    if heat == RegionHeat.COASTAL_HIGH:
        advice.append(f"⚠ {heat_note}")
    elif heat == RegionHeat.INLAND_LOW:
        advice.append(f"✓ {heat_note}")

    # 规则5：调剂风险（简化提示）
    if admission_level in ("冲", "偏冲"):
        advice.append("⚠ 冲的志愿务必勾选服从专业调剂，否则投档进校但6个专业录满会退档")

    # 规则7：就业壁垒
    barrier = assess_employment_barrier(school_province, student_province)
    if barrier.province_recognition == "low":
        advice.append(f"● {barrier.note}")
    elif barrier.province_recognition == "high":
        advice.append(f"✓ {barrier.note}")

    return advice


def check_same_rank_warning(
    student_score: int,
    same_rank_score_2024: int | None,
    school_min_score_2024: int | None,
) -> str | None:
    """规则2核心：同位分对比警告。

    用同位分（今年位次对应往年分数）对比院校往年投档线，
    而非裸分硬比。若裸分>校线但同位分<校线→实际更难。
    """
    if same_rank_score_2024 is None or school_min_score_2024 is None:
        return None
    # 裸分对比 vs 同位分对比
    raw_passes = student_score >= school_min_score_2024
    same_rank_passes = same_rank_score_2024 >= school_min_score_2024
    if raw_passes and not same_rank_passes:
        return (
            f"注意：裸分{student_score}>校线{school_min_score_2024}，"
            f"但同位分{same_rank_score_2024}<校线。试卷难度不同，"
            f"应以同位分判断——实际录取难度比裸分对比更高"
        )
    return None
