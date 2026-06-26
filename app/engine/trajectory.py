"""志愿推荐集成引擎：志愿推荐 + 费用 + 就业参考，一站式串联。

复用已有引擎：
- volunteer.generate_volunteer_table（冲稳保志愿表）
- cost.compute_annual_cost（大学年成本）
聚合 University（费用）+ Major/Career（就业）数据。

纯函数，无 DB 依赖；数据由 router 注入。
"""
from __future__ import annotations

from app.engine.cost import compute_annual_cost
from app.engine.volunteer import generate_volunteer_table
from app.models.admission import AdmissionRecord
from app.models.career import Career
from app.models.city import CityCost
from app.models.life_trajectory import (
    CareerProspect,
    CostSummary,
    PaybackAnalysis,
    TrajectoryItem,
)
from app.models.major import Major
from app.models.provincial import ScoreRankEntry
from app.models.student import StudentProfile
from app.models.university import University
from app.models.volunteer import VolunteerSuggestion


def _build_cost(
    school: str,
    unis: dict[str, University],
    cities: dict[str, CityCost],
    years: int,
) -> CostSummary | None:
    """构建单校费用汇总。无该校数据返回 None。"""
    u = unis.get(school)
    if not u:
        return None
    city_cost = cities.get(u.city) if u.city else None
    if city_cost:
        annual = compute_annual_cost(city_cost, u.tuition, u.accommodation)
        living_per_year = annual.low - u.tuition - u.accommodation
        city_src = f"{u.city}城市成本"
    else:
        living_per_year = 12 * 2000  # 全国基准降级
        city_src = "全国基准估算"
    annual_total = living_per_year + u.tuition + u.accommodation
    return CostSummary(
        tuition_total=u.tuition * years,
        accommodation_total=u.accommodation * years,
        living_total=living_per_year * years,
        grand_total=annual_total * years,
        annual_total=annual_total,
        years=years,
        nature=u.nature.value,
        city=u.city,
        city_cost_source=city_src,
    )


def _build_career(
    major_name: str | None,
    majors: dict[str, Major],
    careers: dict[str, Career],
) -> CareerProspect | None:
    """构建就业前景。无匹配数据返回 None。"""
    # 优先按专业名匹配 Major
    m = majors.get(major_name) if major_name else None
    entry_low = entry_mid = entry_high = None
    mid5 = ceil15 = None
    stability = None
    est_type = None
    sources = []

    if m:
        entry_low, entry_mid, entry_high = m.salary.p25, m.salary.p50, m.salary.p75
        sources.append(f"专业({m.name})薪资三分位")

    # 尝试用专业名匹配相关职业的5年/15年薪资
    if major_name:
        for c in careers.values():
            if major_name in c.related_majors:
                mid5 = c.mid_salary_5y.mid
                ceil15 = c.ceil_salary_15y.high
                stability = c.stability
                est_type = c.establishment_type.value
                sources.append(f"职业({c.name})薪资曲线")
                break

    if entry_low is None and mid5 is None:
        return None

    return CareerProspect(
        major_name=major_name,
        entry_salary_low=entry_low or 0,
        entry_salary_mid=entry_mid or 0,
        entry_salary_high=entry_high or 0,
        mid_salary_5y=mid5,
        ceil_salary_15y=ceil15,
        stability=stability,
        establishment_type=est_type,
        source="；".join(sources) if sources else "无匹配数据",
    )


# DEPRECATED: 教育投入产出/收益叙事已废弃，见 volunteer-recommendation-refocus；主链路不再调用，仅保留签名以维持兼容
def _build_payback(cost: CostSummary | None, career: CareerProspect | None) -> PaybackAnalysis | None:
    """Deprecated stub：回本叙事已移除，恒返回 None。签名保留以维持导入兼容。"""
    return None


def _item_from_suggestion(
    sug: VolunteerSuggestion,
    unis: dict[str, University],
    cities: dict[str, CityCost],
    majors: dict[str, Major],
    careers: dict[str, Career],
    years: int,
    batch: str = "本科批",
) -> TrajectoryItem:
    cost = _build_cost(sug.school, unis, cities, years)
    career = _build_career(sug.major, majors, careers)
    # DEPRECATED: 回本(payback)叙事已废弃，见 volunteer-recommendation-refocus；主链路不再生成
    payback = None
    # 学历层次：专科批次→专科，其余→本科
    degree = "专科" if "专科" in batch else "本科"
    return TrajectoryItem(
        strategy=sug.strategy.value,
        school=sug.school,
        major=sug.major,
        major_group=sug.major_group,
        subject_requirement=sug.subject_requirement,
        batch=batch,
        degree_level=degree,
        last_year_rank=sug.last_year_rank,
        last_year_score=sug.last_year_score,
        student_rank=sug.student_rank,
        probability=sug.probability.probability,
        cost=cost,
        career=career,
        payback=payback,
    )


def build_life_trajectory(
    student: StudentProfile,
    admissions: list[AdmissionRecord],
    rank_entries: list[ScoreRankEntry],
    unis: list[University],
    cities: list[CityCost],
    majors: list[Major],
    careers: list[Career],
    track: str,
    data_year: int,
    years: int = 4,
):
    """构建志愿推荐结果：冲稳保志愿 + 每校费用 + 就业参考。

    1. 先生成冲稳保志愿表（复用 volunteer 引擎）
    2. 每条志愿附加费用与就业参考
    """
    from app.models.life_trajectory import LifeTrajectory

    table = generate_volunteer_table(
        student, admissions, rank_entries, track, data_year,
    )
    uni_map = {u.name: u for u in unis}
    city_map = {c.city: c for c in cities}
    major_map = {m.name: m for m in majors}
    career_map = {c.name: c for c in careers}

    def transform(items):
        # 从admission记录取batch（本科批/专科等），无则默认本科批
        adm_map = {a.school: a for a in admissions}
        results = []
        for s in items:
            adm = adm_map.get(s.school)
            batch = adm.batch.value if adm else "本科批"
            results.append(_item_from_suggestion(s, uni_map, city_map, major_map, career_map, years, batch))
        return results

    return LifeTrajectory(
        student_score=table.student_score,
        student_rank=table.student_rank,
        track=track,
        data_year=data_year,
        sprint=transform(table.sprint),
        stable=transform(table.stable),
        safe=transform(table.safe),
        source_note=table.source_note + "；费用基于院校招生网2024标准，就业基于专业/职业历史数据",
    )
