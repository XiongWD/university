"""志愿推荐 advisory 主链路编排：专业方向优先（父设计 §3）。

纯函数，数据由 router 注入。资格前置门 → 位次 → market×fit 专业方向评分
→ 录取预测 → 费用压力 → 冲稳保分桶 → 可解释输出。
"""
from __future__ import annotations

from app.models.admission import AdmissionRecord
from app.models.advisory import (
    BudgetSummary,
    IneligibleReason,
    MajorDirectionAdvice,
    VolunteerAdvisoryResult,
)
from app.models.city import CityCost
from app.models.eligibility import AdmissionOfferingRule, StudentAcademicProfile
from app.models.job_market import JobMarketSnapshot, MajorDirection
from app.models.life_path import AdmissionBuckets, FamilyBudget, SchoolOption
from app.models.major import Major
from app.models.program_plan import BatchLineDecision
from app.models.provincial import ScoreRankEntry
from app.models.university import University

# affordability 4 级阈值（§3.6，经验值，可调）
AFFORD_PRESSURE_THRESHOLD = 1.5  # cost_4y / annual_income <= 1.5 → 有压力
AFFORD_BURDEN_THRESHOLD = 3.0  # <= 3.0 → 明显负担；> 3.0 → 超预算


def classify_affordability(cost_4y: int, budget: FamilyBudget) -> str:
    """费用压力 4 级（§3.6）：可承受/有压力/明显负担/超预算。

    可承受 = 4 年总开销 <= 家庭可承担总预算；否则按 cost_4y/annual_income 分级。
    超预算 = 费用远超家庭年收入承受力（ratio > BURDEN 阈值）。
    """
    if cost_4y <= budget.affordable_total:
        return "可承受"
    pressure = cost_4y / max(budget.annual_income, 1)
    if pressure <= AFFORD_PRESSURE_THRESHOLD:
        return "有压力"
    if pressure <= AFFORD_BURDEN_THRESHOLD:
        return "明显负担"
    return "超预算"


def _match_direction(offering: AdmissionOfferingRule, directions: list[MajorDirection]) -> MajorDirection:
    """匹配 offering 到 MajorDirection：direction_hint 优先，否则子串匹配。"""
    hint = getattr(offering, "direction_hint", None) or ""
    if hint:
        for d in directions:
            if d.name == hint:
                return d
    best = directions[0] if directions else None
    best_score = -1
    for d in directions:
        score = sum(1 for m in d.majors if m in offering.major_group_name or m in offering.school)
        if score > best_score:
            best, best_score = d, score
    return best


def _compute_4y_cost(uni: University | None, city_map: dict[str, CityCost], school: str) -> tuple[int, int, int, int]:
    """4 年费用分项 (tuition_4y, accommodation_4y, living_4y, total_4y)。"""
    if uni:
        city = city_map.get(uni.city) if uni.city else None
        if city and city.monthly_total is not None:
            mt = city.monthly_total
            monthly_mid = (mt.low + mt.high) / 2
        else:
            monthly_mid = 2000  # 默认郑州级
        t4 = uni.tuition * 4
        a4 = uni.accommodation * 4
        l4 = int(monthly_mid * 12 * 4)
        return t4, a4, l4, t4 + a4 + l4
    # 无 university 数据：按校名估
    is_private = any(k in school for k in ["升达", "黄河科技", "工商", "商丘", "西亚斯"])
    t4 = 40000 if is_private else 20000
    a4 = 4000
    l4 = 96000
    return t4, a4, l4, t4 + a4 + l4


_LEVEL_BUCKETS = {
    "冲": "reach", "偏冲": "reach",
    "稳": "match",
    "偏保": "safe", "保": "safe",
    # "不推荐" 不进任何桶（不可推荐的院校不作为推荐输出）
}

_PRIVATE_KEYWORDS = ["升达", "黄河科技", "工商", "商丘", "西亚斯"]


def build_advisory(
    profile: StudentAcademicProfile,
    budget: FamilyBudget,
    offerings: list[AdmissionOfferingRule],
    directions: list[MajorDirection],
    snap_map: dict[str, list[JobMarketSnapshot]],
    admissions: list[AdmissionRecord],
    unis: list[University],
    cities: list[CityCost],
    majors: list[Major],
    careers: list,
    rank_entries: list[ScoreRankEntry],
    data_year: int = 2025,
    risk_preference: str = "中",
    undergrad_line: int | None = None,
    junior_college_line: int | None = None,
    data_sources: list[dict] | None = None,
) -> VolunteerAdvisoryResult:
    """专业方向优先主链路（§3）。纯函数，数据由 router 注入。"""
    from app.engine.admission_prediction import predict_group_admission
    from app.engine.batch_line import decide_batch_position
    from app.engine.eligibility import filter_eligible
    from app.engine.job_market import score_direction
    from app.engine.major_fit import compute_major_value_academic
    from app.engine.risk_buckets import classify_rank_gap
    from app.engine.volunteer import convert_score_to_rank

    # [§3.2] 资格前置门
    eligible, ineligible = filter_eligible(profile, offerings)

    # [§3.3] 位次
    track = "历史类" if profile.primary_subject == "历史" else "物理类"
    student_rank = convert_score_to_rank(rank_entries, profile.total_score) or 0

    # [§5.2] 批次线判断（使用真实省控线）
    batch_line_decision = decide_batch_position(
        score=profile.total_score,
        rank=student_rank,
        undergrad_line=undergrad_line,
        junior_college_line=junior_college_line,
    )
    review_warnings: list[str] = []
    # 缺省控线时标注数据不足，降低结果可信度
    if undergrad_line is None:
        review_warnings.append("缺少目标年份本科线数据，仅按位次推荐并降低置信度")

    adm_by_school = {a.school: a for a in admissions}
    uni_map = {u.name: u for u in unis}
    city_map = {c.city: c for c in cities}
    major_map = {m.name: m for m in majors}

    buckets = AdmissionBuckets()
    ineligible_options: list[IneligibleReason] = []
    dir_agg: dict[str, list[dict]] = {}  # direction_name -> 聚合项

    for off, elig_result in eligible:
        direction = _match_direction(off, directions)
        if direction is None:
            continue
        market = score_direction(direction, snap_map)
        # [§3.4] market × fit（修正 life_paths 把 major_value 错设为 current_market_score）
        matched_major_name = next((m for m in direction.majors if m in major_map), None)
        major_obj = major_map.get(matched_major_name) if matched_major_name else (majors[0] if majors else None)
        if major_obj is None:
            # 无任何 major 数据可评分：跳过该 offering（不强行评分导致 AttributeError）
            continue
        english_dep = getattr(off, "english_dependency_level", "low")
        major_value, breakdown = compute_major_value_academic(
            market, profile, major_obj, english_dependency=english_dep,
        )

        # [§3.3] 录取预测
        adm = adm_by_school.get(off.school)
        baseline = adm.min_rank if adm else None
        group_pred = predict_group_admission(
            off.school, off.major_group_code, student_rank, baseline_rank_2025=baseline,
        )
        # [§5.5] 风险偏好分桶：按位次差 + 报考策略重新判定档位（更可解释）
        # 有历史投档位次时用 classify_rank_gap 精确分桶；
        # 缺位次基准时降级到录取预测引擎的默认档位，并标注数据缺口。
        if baseline is None:
            level = group_pred.admission_level.value
            review_warnings.append(
                f"{off.school}缺少历史投档位次，档位为估算值，需补齐数据后复核"
            )
        else:
            level = classify_rank_gap(student_rank, baseline, risk_preference)

        # [§3.6] 费用 4 年分项
        uni = uni_map.get(off.school)
        t4, a4, l4, total4 = _compute_4y_cost(uni, city_map, off.school)
        ownership = uni.nature if uni else (
            "民办" if any(k in off.school for k in _PRIVATE_KEYWORDS) else "公办"
        )
        afford = classify_affordability(total4, budget)

        warnings: list[str] = []
        if group_pred.data_granularity in ("group", "school"):
            warnings.append("组内目标专业数据不足，仅按专业组投档参考")
        if not budget.accept_private_school and ownership != "公办":
            warnings.append("家庭不接受民办/中外合作")

        opt = SchoolOption(
            school=off.school,
            major_group_code=off.major_group_code,
            matched_major=matched_major_name,
            ownership=ownership,
            city=uni.city if uni else None,
            admission_level=level,
            admission_probability_note=group_pred.note,
            total_cost_4y=total4,
            affordability_status=afford,
            data_granularity=group_pred.data_granularity,
            confidence=group_pred.confidence,
            warnings=warnings,
        )
        # 不推荐（含未识别 level）的院校不作为推荐输出，不进任何桶
        bk = _LEVEL_BUCKETS.get(level)
        if bk is None:
            continue
        getattr(buckets, bk).append(opt)

        # 方向聚合（加权均值用）
        dir_agg.setdefault(direction.name, []).append({
            "market_value": breakdown["market_value"],
            "student_fit": breakdown["student_fit"],
            "major_value": breakdown["major_value"],
            "direction": direction,
            "math_risk": breakdown.get("math_learning_risk", 0),
            "english_adapt": breakdown.get("english_adaptation", 1),
            "major_name": matched_major_name,
        })

    # 不可报原因（§3.2 保留并输出）
    for off, res in ineligible:
        ineligible_options.append(IneligibleReason(
            school=off.school,
            major_group_name=off.major_group_name,
            reasons=res.reasons,
            blocked_summary=res.blocked_summary,
        ))

    # 专业方向聚合（加权均值，等权）
    major_directions: list[MajorDirectionAdvice] = []
    for dname, items in dir_agg.items():
        n = len(items) or 1
        mv = sum(it["market_value"] for it in items) / n
        sf = sum(it["student_fit"] for it in items) / n
        mav = sum(it["major_value"] for it in items) / n
        d = items[0]["direction"]
        risk: list[str] = []
        fit_exp: list[str] = []
        if any(it["math_risk"] > 0.5 for it in items):
            risk.append(f"{dname} 方向数学学习风险较高，数学较弱考生需谨慎")
        if any(it["english_adapt"] < 0.4 for it in items):
            risk.append(f"{dname} 方向英语适配偏低，需评估实际英语能力")
        if sf >= 0.6:
            fit_exp.append(f"{dname} 与考生选科/单科能力匹配较好")
        major_directions.append(MajorDirectionAdvice(
            direction=dname,
            recommended_majors=list(d.majors[:5]),
            market_value=round(mv, 3),
            student_fit=round(sf, 3),
            major_value=round(mav, 3),
            fit_explanation=fit_exp,
            risk_warnings=risk,
        ))
    major_directions.sort(key=lambda x: x.major_value, reverse=True)

    # 报考策略只调整输出焦点，不改变资格过滤和录取档位判断本身。
    # 冲：保留更多冲刺项；中：三档均衡；稳：压缩冲刺项，突出兜底项。
    if risk_preference == "冲":
        buckets.reach = buckets.reach[:12]
        buckets.match = buckets.match[:8]
        buckets.safe = buckets.safe[:4]
    elif risk_preference == "稳":
        buckets.reach = buckets.reach[:2]
        buckets.match = buckets.match[:6]
        buckets.safe = buckets.safe[:12]
    else:
        buckets.reach = buckets.reach[:6]
        buckets.match = buckets.match[:8]
        buckets.safe = buckets.safe[:6]

    # BudgetSummary（取代表院校中位费用）
    all_opts = buckets.reach + buckets.match + buckets.safe
    if all_opts:
        rep = sorted(all_opts, key=lambda o: o.total_cost_4y)[len(all_opts) // 2]
        budget_summary = BudgetSummary(
            total_4y=rep.total_cost_4y,
            affordable_total=budget.affordable_total,
            affordability_status=rep.affordability_status,
            data_note="费用按代表院校（中位）展示；各校分项见 school_options",
        )
    else:
        budget_summary = BudgetSummary(
            affordable_total=budget.affordable_total, data_note="无可推荐院校",
        )

    notes = [
        f"录取数据基于 {data_year} 年同制度位次参考",
        "专业方向评分 = 市场参考 × 考生适配（乘法门控）",
    ]

    return VolunteerAdvisoryResult(
        student_rank=student_rank,
        province=profile.province,
        track=track,
        data_year=data_year,
        major_directions=major_directions,
        school_options=buckets,
        ineligible_options=ineligible_options,
        budget_summary=budget_summary,
        notes=notes,
        batch_line_decision=batch_line_decision,
        data_sources=data_sources or [],
        review_warnings=review_warnings,
        recommendation_policy=f"按{risk_preference}策略使用位次差分桶",
    )
