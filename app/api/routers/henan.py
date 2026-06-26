"""河南志愿推 API 端点（design §6、§9）。

GET  /henan/options              院校/专业/专业组下拉选项
POST /henan/recommendation       志愿推荐（数据就绪门禁 + 冲稳保 buckets）
POST /henan/target-evaluation    目标院校评估（复用首页冲稳保逻辑）

数据从 data/seed/henan/ 加载。普通批推荐单位是院校专业组。
"""
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.engine.henan_recommendation import build_henan_candidates
from app.engine.henan_target_evaluation import evaluate_target_school
from app.loader.henan_coverage_report import (
    assert_henan_recommendation_ready,
    build_actual_henan_coverage,
)
from app.loader.henan_data_loader import (
    load_henan_enrollment_plans,
    load_henan_program_groups,
    load_henan_universities,
)

router = APIRouter(prefix="/henan", tags=["henan"])

_SEED_DIR = Path("data/seed")


@router.get("/options")
def options():
    """返回目标评估页联动所需的院校/专业/专业组下拉选项。"""
    universities = load_henan_universities(_SEED_DIR)
    plans = load_henan_enrollment_plans(_SEED_DIR)
    groups = load_henan_program_groups(_SEED_DIR)
    return {
        "schools": [{"code": u.school_code, "name": u.school_name} for u in universities],
        "majors": [
            {"school": p.school_name, "major": p.major_name, "group": p.major_group_code}
            for p in plans
        ],
        "groups": [
            {"school": g.school_name, "code": g.major_group_code, "name": g.major_group_name, "track": g.track}
            for g in groups
        ],
    }


class HenanRecommendationRequest(BaseModel):
    score: int
    rank: int | None = None
    track: str
    source_province: str = "河南"
    primary_subject: str
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    strategy: str = "自动"


@router.post("/recommendation")
def recommendation(req: HenanRecommendationRequest):
    """志愿推荐主端点（design D1）。

    先跑数据就绪门禁，再生成候选并分桶。data_ready=false 时仍返回候选
    （带需人工复核/不推荐），前端显示未就绪 banner 而非假推荐。
    """
    profile = req.model_dump()
    coverage = build_actual_henan_coverage(_SEED_DIR)

    data_ready = True
    readiness_errors: list[str] = []
    try:
        assert_henan_recommendation_ready(coverage)
    except ValueError as exc:
        data_ready = False
        readiness_errors.append(str(exc))

    # 非河南生源：build_henan_candidates 会抛错，捕获后 data_ready=false
    try:
        candidates = build_henan_candidates(profile)
    except ValueError as exc:
        return {
            "data_ready": False,
            "readiness_errors": [str(exc)],
            "coverage": coverage,
            "buckets": {"冲": [], "稳": [], "保": [], "不推荐": [], "需人工复核": []},
        }

    buckets: dict[str, list] = {"冲": [], "稳": [], "保": [], "不推荐": [], "需人工复核": []}
    for item in candidates:
        buckets.setdefault(item["bucket"], []).append(item)

    return {
        "data_ready": data_ready,
        "readiness_errors": readiness_errors,
        "coverage": coverage,
        "buckets": buckets,
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
    obey_adjustment: bool = True


@router.post("/target-evaluation")
def target_evaluation(req: HenanTargetEvaluationRequest):
    """目标院校评估（design §9.3）：复用首页专业推荐冲稳保逻辑，不放宽规则。

    build_henan_candidates 已应用 check_henan_eligibility + 2026 计划校验 + 分桶；
    本端点只按目标校/专业/专业组筛选并判定可达性。
    """
    profile = {
        "score": req.score,
        "rank": req.rank,
        "track": req.track,
        "source_province": req.source_province,
        "exam_foreign_language": req.exam_foreign_language,
        "primary_subject": req.primary_subject or ("历史" if req.track == "历史类" else "物理"),
        "elective_subjects": req.elective_subjects,
        "obey_adjustment": req.obey_adjustment,
    }
    # 仅支持河南：非河南生源直接返回院校级不推荐，而非 500（design §1 范围）
    if req.source_province != "河南":
        return {
            "school_name": req.target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": ["河南志愿推仅支持河南考生"],
        }
    candidates = build_henan_candidates(profile)
    return evaluate_target_school(
        profile=profile,
        target_school=req.target_school,
        target_majors=req.target_majors,
        target_group=req.target_group,
        candidates=candidates,
    )
