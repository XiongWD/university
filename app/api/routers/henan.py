"""河南志愿推 API 端点（design §6、§9）。

GET  /henan/options              院校/专业/专业组下拉选项
POST /henan/recommendation       志愿推荐（数据就绪门禁 + 冲稳保 buckets）
POST /henan/target-evaluation    目标院校评估（复用首页冲稳保逻辑）

数据从 data/seed/henan/ 加载。普通批推荐单位是院校专业组。
"""
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.volunteer import convert_score_to_rank
from app.engine.henan_recommendation import (
    build_henan_candidates,
    build_henan_volunteer_table,
    sort_henan_bucket_candidates,
)
from app.engine.henan_target_evaluation import evaluate_target_school
from app.loader.henan_coverage_report import (
    assert_henan_recommendation_ready,
    build_actual_henan_coverage,
    build_henan_data_evidence,
    build_henan_readiness_status,
)
from app.loader.henan_data_loader import (
    load_henan_enrollment_plans,
    load_henan_policy,
    load_henan_program_groups,
    load_henan_universities,
)
from app.loader.henan_scope import (
    filter_henan_history_regular_scope,
    filter_henan_history_regular_universities,
)
from app.models.tables import ScoreRankEntryRow, ScoreRankTableRow
from app.repositories.mappers import score_rank_entry_to_domain

router = APIRouter(prefix="/henan", tags=["henan"])

_SEED_DIR = Path("data/seed")
_SUPPORTED_SOURCE_PROVINCE = "河南"

# /options 接口的进程级缓存（首次加载 ~7s，后续秒回）
# 数据源是静态 seed YAML，进程生命周期内不会变化，可安全缓存
_OPTIONS_CACHE: dict | None = None


@router.get("/options")
def options():
    """返回目标评估页联动所需的院校/专业/专业组下拉选项。

    首次调用从磁盘解析 ~12MB YAML（约 7 秒），结果缓存在进程内存中，
    后续调用直接返回缓存，避免页面刷新时重复加载。
    """
    global _OPTIONS_CACHE
    if _OPTIONS_CACHE is not None:
        return _OPTIONS_CACHE

    universities = load_henan_universities(_SEED_DIR)
    plans = load_henan_enrollment_plans(_SEED_DIR)
    groups = load_henan_program_groups(_SEED_DIR)
    groups, plans = filter_henan_history_regular_scope(groups, plans)
    universities = filter_henan_history_regular_universities(universities, groups)
    coverage, readiness = _build_status_payload()

    school_items = sorted(
        { (u.school_code, u.school_name) for u in universities },
        key=lambda x: (x[1], x[0]),
    )
    major_items = sorted(
        { (p.school_name, p.major_name, p.major_group_code) for p in plans },
        key=lambda x: (x[0], x[1], x[2]),
    )
    group_items = sorted(
        { (g.school_name, g.major_group_code, g.major_group_name, g.track) for g in groups },
        key=lambda x: (x[0], x[1]),
    )
    payload = {
        "schools": [{"code": code, "name": name} for code, name in school_items],
        "majors": [{"school": school, "major": major, "group": group} for school, major, group in major_items],
        "groups": [{"school": school, "code": code, "name": name, "track": track} for school, code, name, track in group_items],
        "scope": {
            "source_province": _SUPPORTED_SOURCE_PROVINCE,
            "year": 2026,
            "track": _SUPPORTED_TRACK,
            "batch": "本科批",
        },
        "coverage": coverage,
        "data_evidence": build_henan_data_evidence(coverage),
        **readiness,
    }

    _OPTIONS_CACHE = payload
    return payload
_SUPPORTED_TRACK = "历史类"


def _build_scope_not_ready(reason: str, coverage: dict) -> dict:
    return {
        "data_ready": False,
        "pilot_ready": False,
        "production_ready": False,
        "coverage_status": "not_ready",
        "coverage_notes": ["非全量覆盖：当前请求超出河南 2026 历史类普通本科批可用范围。"],
        "readiness_errors": [reason],
        "coverage": coverage,
        "data_evidence": build_henan_data_evidence(coverage),
        "buckets": {"搏": [], "冲": [], "稳": [], "保": [], "垫": [], "不推荐": [], "需人工复核": []},
        "volunteer_table": None,
        "language_restriction_summary": None,
    }


def _summarize_language_restriction(exam_foreign_language: str, candidates: list[dict]) -> dict | None:
    """语种限制顶部汇总（日语考生场景）：区分硬阻、英语适应风险、语种数据缺失。"""
    if exam_foreign_language == "英语":
        return None
    from collections import Counter
    counts = Counter((c.get("language_restriction") or {}).get("level") for c in candidates)
    hard = counts.get("hard_blocked", 0)
    soft = counts.get("soft_warning", 0)
    missing = counts.get("missing_data", 0)
    partial = counts.get("partial", 0)
    same_language_major_group_count = sum(
        1
        for c in candidates
        if any(exam_foreign_language in str(x) for x in (c.get("selected_majors") or []))
    )
    reachable_same_language_major_group_count = sum(
        1
        for c in candidates
        if c.get("bucket") in {"冲", "稳", "保"}
        and any(exam_foreign_language in str(x) for x in (c.get("selected_majors") or []))
    )
    if hard == 0 and soft == 0 and missing == 0 and partial == 0 and reachable_same_language_major_group_count > 0:
        return None
    parts: list[str] = []
    if hard:
        parts.append(f"{hard} 个专业组整组要求英语语种，已置为“不推荐”")
    if partial:
        parts.append(f"{partial} 个专业组部分专业限英语语种（如英语专业），其余专业仍可填报")
    if soft:
        parts.append(f"{soft} 个专业组明确仅开英语公共外语，存在入学后英语适应风险")
    if missing:
        parts.append(f"{missing} 个专业组缺少公共外语语种数据，暂无法确认日语适配")
    if reachable_same_language_major_group_count == 0:
        parts.append(f"当前分数条件下未检出可达的{exam_foreign_language}专业组")
    return {
        "exam_foreign_language": exam_foreign_language,
        "hard_blocked_count": hard,
        "partial_count": partial,
        "soft_warning_count": soft,
        "missing_data_count": missing,
        "same_language_major_group_count": same_language_major_group_count,
        "reachable_same_language_major_group_count": reachable_same_language_major_group_count,
        "note": "；".join(parts),
    }


def _build_status_payload() -> tuple[dict, dict]:
    coverage = build_actual_henan_coverage(_SEED_DIR)
    return coverage, build_henan_readiness_status(coverage)


def _resolve_rank_from_score(
    session: Session,
    score: int,
    year: int = 2026,
    province: str = "河南",
    track: str = "历史类",
) -> int | None:
    table = session.exec(
        select(ScoreRankTableRow)
        .where(ScoreRankTableRow.province == province)
        .where(ScoreRankTableRow.year == year)
        .where(ScoreRankTableRow.track == track)
    ).first()
    if not table:
        return None
    entry_rows = session.exec(
        select(ScoreRankEntryRow)
        .where(ScoreRankEntryRow.table_id == table.id)
        .order_by(ScoreRankEntryRow.score.desc())
    ).all()
    entries = [score_rank_entry_to_domain(row) for row in entry_rows]
    return convert_score_to_rank(entries, score)


class HenanRecommendationRequest(BaseModel):
    score: int
    rank: int | None = None
    track: str
    source_province: str = "河南"
    primary_subject: str
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    subject_scores_detail: dict[str, int] = {}
    strategy: str = "自动"
    # 排序与偏好（problem2/3/4）：sort_mode 位次|成功率；prefer_local/prefer_public 勾选
    sort_mode: str = "rank"
    prefer_local: bool = False
    prefer_public: bool = False
    prefer_same_language_major: bool = False
    interest_majors: list[str] = []


@router.post("/recommendation")
def recommendation(req: HenanRecommendationRequest, session: Session = Depends(get_session_dep)):
    """志愿推荐主端点（design D1）。

    先跑数据就绪门禁，再生成候选并分桶。data_ready=false 时仍返回候选
    （带需人工复核/不推荐），前端显示未就绪 banner 而非假推荐。
    """
    profile = req.model_dump()
    coverage, readiness = _build_status_payload()

    if req.source_province != _SUPPORTED_SOURCE_PROVINCE:
        return _build_scope_not_ready("河南志愿推仅支持河南考生", coverage)
    if req.track != _SUPPORTED_TRACK:
        return _build_scope_not_ready("河南志愿推当前仅支持2026历史类普通本科批", coverage)
    if profile.get("rank") in (None, 0):
        profile["rank"] = _resolve_rank_from_score(session, req.score)
        if profile["rank"] is None:
            return _build_scope_not_ready("无法根据河南 2026 历史类一分一段表换算当前分数位次", coverage)

    readiness_errors: list[str] = []
    try:
        assert_henan_recommendation_ready(coverage)
    except ValueError as exc:
        readiness_errors.append(str(exc))

    # 非河南生源：build_henan_candidates 会抛错，捕获后 data_ready=false
    try:
        candidates = build_henan_candidates(profile)
    except ValueError as exc:
        return _build_scope_not_ready(str(exc), coverage)

    # 本科线资格门：低于本科线不生成常规本科五档，输出线下提示
    if profile.get("_batch_ineligible"):
        gap = profile.get("_batch_gap", 0)
        undergrad_line = 459  # 2026历史类本科批控制线
        return {
            "data_ready": True,
            "pilot_ready": coverage.get("pilot_ready", False),
            "production_ready": coverage.get("production_ready", False),
            "coverage_status": coverage.get("coverage_status", "pilot_ready"),
            "coverage": coverage.get("coverage", {}),
            "data_evidence": coverage.get("data_evidence", {}),
            "score": req.score,
            "batch_eligibility": "ineligible",
            "batch_message": (
                f"当前成绩 {req.score} 分低于普通本科批控制线 {undergrad_line} 分（差 {gap} 分），"
                f"不具备常规本科批填报资格。建议重点规划高职专科批，"
                f"同时关注后续本科征集志愿及官方是否允许降分填报。"
            ),
            "buckets": {"搏": [], "冲": [], "稳": [], "保": [], "垫": [], "不推荐": [], "需人工复核": []},
            "volunteer_table": None,
        }

    # 分类池：保留全部候选的档位统计（含超冲，不截断），用于验证五档分类合理性
    _ALL_TIERS = ["超冲", "搏", "冲", "稳", "保", "垫", "需人工复核", "不推荐"]
    classification_pool: dict[str, list] = {t: [] for t in _ALL_TIERS}
    for item in candidates:
        classification_pool.setdefault(item["bucket"], []).append(item)
    classification_pool_counts = {t: len(classification_pool[t]) for t in _ALL_TIERS}

    # 需复核原因细分统计（design：需人工复核≠不符合，需告知用户具体缺什么数据）
    review_reason_labels = {
        "missing_verified_2025_rank": "缺2025同口径录取位次",
        "only_2024_old_regime": "仅有2024旧文科数据",
        "missing_verified_2026_plan": "2026招生计划未核验",
        "unverified_2026_group": "2026专业组结构未核验",
        "other_review_needed": "其他数据待核验",
    }
    review_counts: dict[str, int] = {code: 0 for code in review_reason_labels}
    for item in classification_pool["需人工复核"]:
        code = item.get("review_reason_code") or "other_review_needed"
        review_counts[code] = review_counts.get(code, 0) + 1
    review_summary = {
        "total": len(classification_pool["需人工复核"]),
        "by_reason": review_counts,
        "labels": review_reason_labels,
        "note": (
            f"需复核共 {len(classification_pool['需人工复核'])} 个专业组，主要是数据证据不足"
            f"（非资格不符）。最大原因：{review_reason_labels[max(review_counts, key=review_counts.get)]}"
            if classification_pool["需人工复核"] else "无需复核专业组"
        ),
    }

    # 展示池：超冲默认不展示（资格可报但门槛明显过高）；其余档位排序+限量
    _DISPLAY_TIERS = ("搏", "冲", "稳", "保", "垫")
    buckets: dict[str, list] = {"搏": [], "冲": [], "稳": [], "保": [], "垫": [], "不推荐": [], "需人工复核": []}
    for bucket in _DISPLAY_TIERS:
        buckets[bucket] = sort_henan_bucket_candidates(classification_pool[bucket], profile)
    # 不推荐/需人工复核 直接转（不排序，让用户看到资格/数据问题）
    buckets["不推荐"] = classification_pool["不推荐"]
    buckets["需人工复核"] = classification_pool["需人工复核"]

    # 展示池限量：分类池全保留，展示池按档位截断（搏10/冲20/稳30/保25/垫15）
    _DISPLAY_CAP = {"搏": 10, "冲": 20, "稳": 30, "保": 25, "垫": 15}
    for bucket, cap in _DISPLAY_CAP.items():
        if len(buckets[bucket]) > cap:
            buckets[bucket] = buckets[bucket][:cap]

    # 48 志愿草案（design §8.4，问题1）：策略感知的配额与排序
    policies = load_henan_policy(_SEED_DIR)
    policy = next(
        (p for p in policies if p.track == "历史类" and p.batch == "本科批"),
        None,
    )
    volunteer_table = None
    if policy is not None:
        volunteer_table = build_henan_volunteer_table(profile, candidates, policy)

    # 语种限制汇总（日语考生场景）：顶部明确标注英语限制概况
    language_restriction_summary = _summarize_language_restriction(req.exam_foreign_language, candidates)

    return {
        **readiness,
        "readiness_errors": readiness_errors,
        "coverage": coverage,
        "data_evidence": build_henan_data_evidence(coverage),
        "buckets": buckets,
        "classification_pool_counts": classification_pool_counts,
        "boundary_rounding_method": "round_half_up",
        "display_sort_basis": "省内优先→公办优先→专业匹配→语种适配→位次安全度→费用",
        "display_pool_caps": {"搏": 10, "冲": 20, "稳": 30, "保": 25, "垫": 15},
        "volunteer_table": volunteer_table,
        "language_restriction_summary": language_restriction_summary,
        "review_summary": review_summary,
    }


class HenanTargetEvaluationRequest(BaseModel):
    score: int
    rank: int | None = None
    track: str
    source_province: str = "河南"
    target_school: str
    target_majors: list[str] = []
    target_group: str | None = None
    exam_foreign_language: str = "英语"
    primary_subject: str | None = None
    elective_subjects: list[str] = []
    subject_scores_detail: dict[str, int] = {}
    obey_adjustment: bool = True


@router.post("/target-evaluation")
def target_evaluation(req: HenanTargetEvaluationRequest, session: Session = Depends(get_session_dep)):
    """目标院校评估（design §9.3）：复用首页专业推荐冲稳保逻辑，不放宽规则。

    build_henan_candidates 已应用 check_henan_eligibility + 2026 计划校验 + 分桶；
    本端点只按目标校/专业/专业组筛选并判定可达性。
    """
    coverage, readiness = _build_status_payload()
    profile = {
        "score": req.score,
        "rank": req.rank,
        "track": req.track,
        "source_province": req.source_province,
        "exam_foreign_language": req.exam_foreign_language,
        "primary_subject": req.primary_subject or ("历史" if req.track == "历史类" else "物理"),
        "elective_subjects": req.elective_subjects,
        "subject_scores_detail": req.subject_scores_detail,
        "obey_adjustment": req.obey_adjustment,
    }
    # 仅支持河南：非河南生源直接返回院校级不推荐，而非 500（design §1 范围）
    if req.source_province != _SUPPORTED_SOURCE_PROVINCE:
        return {
            "school_name": req.target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": ["河南志愿推仅支持河南考生"],
            "coverage": coverage,
            "data_evidence": build_henan_data_evidence(coverage),
            "data_ready": False,
            "pilot_ready": False,
            "production_ready": False,
            "coverage_status": "not_ready",
            "coverage_notes": ["非全量覆盖：当前请求超出河南 2026 历史类普通本科批可用范围。"],
        }
    if req.track != _SUPPORTED_TRACK:
        return {
            "school_name": req.target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": ["河南志愿推当前仅支持2026历史类普通本科批"],
            "coverage": coverage,
            "data_evidence": build_henan_data_evidence(coverage),
            "data_ready": False,
            "pilot_ready": False,
            "production_ready": False,
            "coverage_status": "not_ready",
            "coverage_notes": ["非全量覆盖：当前请求超出河南 2026 历史类普通本科批可用范围。"],
        }
    if profile.get("rank") in (None, 0):
        profile["rank"] = _resolve_rank_from_score(session, req.score)
        if profile["rank"] is None:
            return {
                "school_name": req.target_school,
                "overall_bucket": "不推荐",
                "items": [],
                "reasons": ["无法根据河南 2026 历史类一分一段表换算当前分数位次"],
                "coverage": coverage,
                "data_evidence": build_henan_data_evidence(coverage),
                "data_ready": False,
                "pilot_ready": False,
                "production_ready": False,
                "coverage_status": "not_ready",
                "coverage_notes": ["非全量覆盖：当前请求缺少可用位次，无法进入目标评估。"],
            }
    candidates = build_henan_candidates(profile)
    # 本科线资格门：低于本科线不生成常规本科目标评估，输出线下提示
    if profile.get("_batch_ineligible"):
        gap = profile.get("_batch_gap", 0)
        undergrad_line = 459
        return {
            "school_name": req.target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": [
                f"当前成绩 {req.score} 分低于普通本科批控制线 {undergrad_line} 分（差 {gap} 分），"
                f"不具备常规本科批填报资格。建议重点规划高职专科批，"
                f"同时关注后续本科征集志愿。"
            ],
            "batch_eligibility": "ineligible",
            **readiness,
        }
    result = evaluate_target_school(
        profile=profile,
        target_school=req.target_school,
        target_majors=req.target_majors,
        target_group=req.target_group,
        candidates=candidates,
    )
    return {
        **result,
        "coverage": coverage,
        "data_evidence": build_henan_data_evidence(coverage),
        **readiness,
    }
