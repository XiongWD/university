"""目标院校 + 专业评估引擎（design target-admission-evaluation §5）。

评估链路（design §5）：
  输入校验 → 数据检索（分省计划 + 专业组规则 + 历史投档 + 一分一段）
  → 资格判断 → 投档风险 → 专业风险 → 数据缺口 → 来源汇总

严格区分「能投进专业组」与「能录取目标专业」。不输出精确百分比，
风险档位固定为 高 / 中高 / 中 / 低 / 不可报 / 数据不足。
"""
from __future__ import annotations

from app.engine.volunteer import convert_score_to_rank
from app.models.admission import AdmissionRecord
from app.models.program_plan import EnrollmentPlan, ProgramGroupRule
from app.models.provincial import ScoreRankEntry
from app.models.target_evaluation import (
    AdmissionSource,
    EligibilityAssessment,
    MajorAdmissionAssessment,
    RiskAssessment,
    TargetEvaluationRequest,
    TargetEvaluationResult,
)


def _filter_plans(req: TargetEvaluationRequest, plans: list[EnrollmentPlan]) -> list[EnrollmentPlan]:
    """只取目标院校在生源地、目标年份的计划；不把全国/外省计划当本地计划。"""
    return [
        p for p in plans
        if p.school == req.target_school
        and p.source_province == req.source_province
        and p.year == req.data_year
        and (req.target_major is None or p.major_name == req.target_major)
    ]


def _find_rule(plan: EnrollmentPlan, rules: list[ProgramGroupRule]) -> ProgramGroupRule | None:
    """按校 + 省份 + 年份 + 专业组代码匹配选科规则。"""
    return next(
        (
            r for r in rules
            if r.school == plan.school
            and r.province == plan.source_province
            and r.year == plan.year
            and r.major_group_code == plan.major_group_code
        ),
        None,
    )


def _check_rule(req: TargetEvaluationRequest, rule: ProgramGroupRule | None) -> tuple[list[str], list[str]]:
    """资格硬过滤：首选科目 + 再选科目。返回 (blocked_reasons, review_warnings)。"""
    reasons: list[str] = []
    warnings: list[str] = []
    if rule is None:
        warnings.append("缺少目标专业组选科规则，资格按宽松口径判断，需补齐章程核验")
        return reasons, warnings
    if rule.primary_subject_requirement and req.primary_subject != rule.primary_subject_requirement:
        reasons.append(f"首选科目要求{rule.primary_subject_requirement}，考生为{req.primary_subject}")
    require = (rule.elective_subject_rule or {}).get("require", [])
    for subject in require:
        if subject not in req.elective_subjects:
            reasons.append(f"再选科目要求包含{subject}，考生再选为{'+'.join(req.elective_subjects) or '无'}")
    return reasons, warnings


def _build_sources(
    plans: list[EnrollmentPlan],
    rules: list[ProgramGroupRule],
    admissions: list[AdmissionRecord],
) -> list[AdmissionSource]:
    """汇总评估用到的数据来源（design §8：所有来源必须进入 sources 数组）。"""
    sources: list[AdmissionSource] = []
    for p in plans:
        sources.append(AdmissionSource(
            source_name=p.source_name, source_url=p.source_url,
            source_type="enrollment_plan", as_of=p.as_of, confidence=p.confidence,
        ))
    for r in rules:
        sources.append(AdmissionSource(
            source_name=r.source_name, source_url=r.source_url,
            source_type="admission_brochure", as_of=r.as_of, confidence=r.confidence,
        ))
    for a in admissions:
        sources.append(AdmissionSource(
            source_name=getattr(a, "source", "historical_admission"),
            source_url=getattr(a, "source_url", "") or "",
            source_type="historical_admission",
            as_of=str(getattr(a, "year", "")),
            confidence=getattr(a, "confidence", 0.7),
        ))
    return sources


def _band_from_rank_gap(student_rank: int, baseline_rank: int) -> tuple[str, str]:
    """有历史投档位次时按位次差给出风险档位（不输出精确概率）。

    gap_ratio = (student_rank - baseline_rank) / baseline_rank
    < 0 表示考生位次优于投档线（更稳）；> 0 表示弱于投档线（更险）。
    """
    if student_rank <= 0 or baseline_rank <= 0:
        return "数据不足", "位次或投档线数据异常"
    gap_ratio = (student_rank - baseline_rank) / baseline_rank
    if gap_ratio <= -0.15:
        return "低", f"考生位次{student_rank}明显优于投档位次{baseline_rank}（差比{gap_ratio:.0%}）"
    if gap_ratio <= 0.06:
        return "中", f"考生位次{student_rank}接近投档位次{baseline_rank}（差比{gap_ratio:.0%}）"
    if gap_ratio <= 0.18:
        return "中高", f"考生位次{student_rank}略弱于投档位次{baseline_rank}（差比{gap_ratio:.0%}）"
    return "高", f"考生位次{student_rank}明显弱于投档位次{baseline_rank}（差比{gap_ratio:.0%}）"


def evaluate_target(
    req: TargetEvaluationRequest,
    plans: list[EnrollmentPlan],
    rules: list[ProgramGroupRule],
    admissions: list[AdmissionRecord],
    rank_entries: list[ScoreRankEntry],
) -> TargetEvaluationResult:
    """目标院校/专业评估主链路（design §5）。"""
    matched_plans = _filter_plans(req, plans)
    sources = _build_sources(matched_plans, rules, admissions)
    student_rank = convert_score_to_rank(rank_entries, req.total_score) if rank_entries else None

    # [§5.2 数据检索] 无该省该年计划 → 数据不足，绝不用全国/外省计划顶替
    if not matched_plans:
        return TargetEvaluationResult(
            target_school=req.target_school,
            target_major=req.target_major,
            source_province=req.source_province,
            eligibility=EligibilityAssessment(
                eligible=False,
                review_warnings=[
                    f"缺少{req.target_school}在{req.source_province}的{req.data_year}分专业计划"
                ],
            ),
            group_admission=RiskAssessment(risk_band="数据不足", confidence=0.2),
            major_admission=MajorAdmissionAssessment(risk_band="数据不足"),
            sources=sources,
            missing_data=["2026_enrollment_plan"],
            recommendation_summary="缺少目标院校分省分专业计划，无法给出可靠评估",
        )

    plan = matched_plans[0]
    rule = _find_rule(plan, rules)
    blocked, rule_warnings = _check_rule(req, rule)

    # [§5.3 资格判断] 不符 → 不可报
    if blocked:
        return TargetEvaluationResult(
            target_school=req.target_school,
            target_major=req.target_major,
            source_province=req.source_province,
            eligibility=EligibilityAssessment(eligible=False, blocked_reasons=blocked, review_warnings=rule_warnings),
            group_admission=RiskAssessment(
                risk_band="不可报", student_rank=student_rank, confidence=0.9,
                basis="选科或资格条件不满足目标专业组要求",
            ),
            major_admission=MajorAdmissionAssessment(
                risk_band="不可报",
                target_major_available=True,
                plan_count=plan.plan_count,
                adjustment_risk="不可报",
            ),
            sources=sources,
            missing_data=[],
            recommendation_summary="当前选科或资格条件不满足目标专业组要求",
        )

    # [§5.4 投档风险] 找目标院校同省历史投档位次作 baseline
    hist = next(
        (a for a in admissions
         if a.school == req.target_school and getattr(a, "province", "") == req.source_province),
        None,
    )
    baseline_rank = hist.min_rank if hist else None

    if baseline_rank is not None and student_rank is not None:
        band, basis = _band_from_rank_gap(student_rank, baseline_rank)
        data_year_used = getattr(hist, "year", None)
        confidence = getattr(hist, "confidence", 0.6)
        missing: list[str] = []
        # 资格可报但投档高风险时，总结要明确点出录取难度，避免"可报=能录"误解
        if band == "高":
            group_summary = (
                f"资格可报，但录取难度大：目标院校在{req.source_province}投档风险为{band}（{basis}）；"
                + ("服从调剂仅在过投档线后才有意义" if req.accept_adjustment
                   else "不服从调剂且投档困难，几乎无录取可能")
            )
        else:
            group_summary = (
                f"目标院校在{req.source_province}投档风险为{band}；"
                + ("服从调剂可降低退档风险" if req.accept_adjustment else "不服从调剂存在退档风险")
            )
    else:
        band = "数据不足"
        basis = "缺少同专业组/同省历史投档位次，暂不输出风险档位"
        data_year_used = None
        confidence = 0.4
        missing = ["historical_group_rank"]
        group_summary = "资格满足，但缺少历史投档位次，需补齐数据后评估风险"

    # [§5.5 专业风险] 目标专业在计划内可报；分专业历史位次通常缺失 → 数据不足
    major_band = band if baseline_rank is not None else "数据不足"
    # 调剂风险必须结合投档风险：投档高风险时即便服从调剂也难有录取机会，
    # 不能因为勾了"服从调剂"就无脑给"低"。
    if band == "数据不足":
        adjustment = "数据不足"
    elif band == "高":
        # 投档困难：服从调剂"理论上"能兜，但根本进不了档就谈不上调剂
        adjustment = "高" if not req.accept_adjustment else "中高"
    elif band == "中高":
        adjustment = "中高" if not req.accept_adjustment else "低"
    else:  # 低/中：投档希望较大，服从调剂能显著降退档风险
        adjustment = "低" if req.accept_adjustment else "中高"

    return TargetEvaluationResult(
        target_school=req.target_school,
        target_major=req.target_major,
        source_province=req.source_province,
        eligibility=EligibilityAssessment(eligible=True, review_warnings=rule_warnings),
        group_admission=RiskAssessment(
            risk_band=band,
            basis=basis,
            student_rank=student_rank,
            baseline_rank=baseline_rank,
            data_year_used=data_year_used,
            confidence=confidence,
        ),
        major_admission=MajorAdmissionAssessment(
            risk_band=major_band,
            target_major_available=True,
            plan_count=plan.plan_count,
            basis=f"{req.target_major}在{req.source_province}{req.data_year}计划{plan.plan_count}人",
            adjustment_risk=adjustment,
        ),
        sources=sources,
        missing_data=missing,
        recommendation_summary=group_summary,
    )
