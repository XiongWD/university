"""目标院校 + 专业评估 API 端点。

POST /target/evaluate：输入生源地/分数/选科/目标院校与专业 →
返回资格、投档风险、专业风险、调剂风险、数据缺口与来源。

数据层复用河南 2026 专业组规则（program_groups）与分省分专业计划
（enrollment_plans），并从 DB 取历史投档数据与一分一段表。
"""
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.target_evaluation import evaluate_target
from app.models.admission import AdmissionRecord
from app.models.provincial import ScoreRankEntry
from app.models.program_plan import EnrollmentPlan, ProgramGroupRule
from app.models.target_evaluation import TargetEvaluationRequest
from app.repositories.mappers import admission_to_domain
from app.models.tables import AdmissionRow, ScoreRankEntryRow, ScoreRankTableRow

router = APIRouter(prefix="/target", tags=["target"])

_SEED_DIR = Path("data/seed")


def _load_target_plans() -> list[EnrollmentPlan]:
    """加载河南 2026 分省分专业计划（design §8 数据来源）。"""
    path = _SEED_DIR / "enrollment_plans/henan_2026.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [EnrollmentPlan.model_validate(x) for x in data]


def _load_target_rules() -> list[ProgramGroupRule]:
    """加载河南 2026 院校专业组选科规则。"""
    path = _SEED_DIR / "program_groups/henan_2026.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [ProgramGroupRule.model_validate(x) for x in data]


def _load_historical_admissions(session: Session, school: str, province: str) -> list[AdmissionRecord]:
    """取目标院校在生源地的历史投档数据，回退到最近年份。"""
    rows = session.exec(
        select(AdmissionRow)
        .where(AdmissionRow.school == school)
        .where(AdmissionRow.province == province)
        .order_by(AdmissionRow.year.desc())
    ).all()
    return [admission_to_domain(r) for r in rows]


def _load_rank_entries(session: Session, province: str, year: int, track: str) -> list[ScoreRankEntry]:
    """取一分一段表 entries（分数转位次用）。"""
    tbl = session.exec(
        select(ScoreRankTableRow)
        .where(ScoreRankTableRow.province == province)
        .where(ScoreRankTableRow.year == year)
        .where(ScoreRankTableRow.track == track)
    ).first()
    if not tbl:
        return []
    rows = session.exec(
        select(ScoreRankEntryRow).where(ScoreRankEntryRow.table_id == tbl.id)
    ).all()
    return [ScoreRankEntry(score=r.score, count_at=r.count_at,
                           cumulative_rank=r.cumulative_rank) for r in rows]


@router.post("/evaluate")
def evaluate(
    req: TargetEvaluationRequest,
    session: Session = Depends(get_session_dep),
):
    """目标院校/专业评估主接口。

    严格按生源地筛选分省计划，不把全国/外省计划当本地计划。
    缺 2026 招生计划时在 missing_data 标注并降低置信度。
    """
    track = "历史类" if req.primary_subject == "历史" else "物理类"
    result = evaluate_target(
        req=req,
        plans=_load_target_plans(),
        rules=_load_target_rules(),
        admissions=_load_historical_admissions(session, req.target_school, req.source_province),
        rank_entries=_load_rank_entries(session, req.source_province, req.data_year, track),
    )
    return result.model_dump(mode="json")
