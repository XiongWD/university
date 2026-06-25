"""志愿填报引擎 API 端点。

POST /volunteer/recommend：输入考生画像 → 返回冲稳保志愿表。
GET /volunteer/admissions：录取数据查询（支持 track/year/score 范围筛选）。
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.trajectory import build_life_trajectory
from app.engine.volunteer import generate_volunteer_table
from app.models.admission import Batch
from app.models.provincial import ScoreRankEntry
from app.models.student import FamilyResources, MinorLanguage, RiskPreference, StudentProfile
from app.models.tables import (
    AdmissionRow, CareerRow, CityCostRow, MajorRow, ScoreRankEntryRow,
    ScoreRankTableRow, UniversityRow,
)
from app.repositories.mappers import (
    admission_to_domain, career_to_domain, city_to_domain, major_to_domain,
    university_to_domain,
)

router = APIRouter(prefix="/volunteer", tags=["volunteer"])


# ---------- 请求模型 ----------
class RecommendRequest(BaseModel):
    """推荐请求（松散校验，便于前端拼装）。"""

    province: str
    total_score: int
    track: str  # 文/理/物理类/历史类
    data_year: int = 2026  # 默认当年最新
    risk_preference: RiskPreference = RiskPreference.BALANCED
    gender: str = ""
    interests: list[str] = []
    strengths: list[str] = []
    subject_scores: dict[str, int] = {}
    total_this_year: int | None = None  # 等效位次用，可选
    total_history: int | None = None
    # 选科/外语/单科（填报硬门槛）
    foreign_language: str = "英语"  # 英语/日语/俄语/德语/法语/西班牙语
    elective_subjects: list[str] = []  # 再选科目(3+1+2的"2")
    subject_scores_detail: dict[str, int] = {}  # 单科分数


# ---------- 取数辅助 ----------
def _load_rank_entries(session: Session, province: str, year: int, track: str):
    """取一分一段表 entries（用于位次换算）。返回 list[ScoreRankEntry]。"""
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


def _load_admissions(session: Session, province: str, track: str, year: int):
    """取某省/track/年份的录取数据 → list[AdmissionRecord]。"""
    rows = session.exec(
        select(AdmissionRow)
        .where(AdmissionRow.province == province)
        .where(AdmissionRow.track == track)
        .where(AdmissionRow.year == year)
    ).all()
    return [admission_to_domain(r) for r in rows]


def _build_student(req: RecommendRequest) -> StudentProfile:
    """从请求构建学生画像（含选科/外语/单科）。"""
    return StudentProfile(
        province=req.province, total_score=req.total_score,
        subject_scores=req.subject_scores or {"总分": req.total_score},
        minor_language=None, family_resources=FamilyResources(),
        gender=req.gender, interests=req.interests, strengths=req.strengths,
        risk_preference=req.risk_preference,
        source="api请求", as_of=date.today(), confidence=1.0,
        foreign_language=req.foreign_language,
        elective_subjects=req.elective_subjects,
        subject_scores_detail=req.subject_scores_detail,
    )


# ---------- 端点 ----------
@router.post("/recommend")
def recommend(req: RecommendRequest, session: Session = Depends(get_session_dep)):
    """生成冲稳保志愿表。

    位次表用 data_year（与录取数据同年），保证分↔位次换算口径一致。
    若该年无位次表（如2024有录取数据但位次表不全），降级返回空位次（引擎容错）。
    """
    entries = _load_rank_entries(session, req.province, req.data_year, req.track)
    admissions = _load_admissions(session, req.province, req.track, req.data_year)

    student = _build_student(req)

    table = generate_volunteer_table(
        student=student, admissions=admissions, rank_entries=entries,
        track=req.track, data_year=req.data_year,
        total_this_year=req.total_this_year, total_history=req.total_history,
    )
    return table.model_dump(mode="json")


# ---------- 取数辅助（人生轨迹用）----------
def _load_universities(session: Session):
    rows = session.exec(select(UniversityRow)).all()
    return [university_to_domain(r) for r in rows]


def _load_cities(session: Session):
    rows = session.exec(select(CityCostRow)).all()
    return [city_to_domain(r) for r in rows]


def _load_majors(session: Session):
    rows = session.exec(select(MajorRow)).all()
    return [major_to_domain(r) for r in rows]


def _load_careers(session: Session):
    rows = session.exec(select(CareerRow)).all()
    return [career_to_domain(r) for r in rows]


@router.post("/life-trajectory")
def life_trajectory(req: RecommendRequest, session: Session = Depends(get_session_dep)):
    """人生轨迹：志愿推荐 + 每校费用 + 就业前景 + 回本分析。

    家长和孩子筛选志愿时一站式看到「读这所大学要花多少、毕业后赚多少、多久回本」。
    复用 volunteer 引擎生成冲稳保，再附加 University(费用)+Major/Career(就业)数据。
    """
    entries = _load_rank_entries(session, req.province, req.data_year, req.track)
    admissions = _load_admissions(session, req.province, req.track, req.data_year)

    student = _build_student(req)

    trajectory = build_life_trajectory(
        student=student,
        admissions=admissions,
        rank_entries=entries,
        unis=_load_universities(session),
        cities=_load_cities(session),
        majors=_load_majors(session),
        careers=_load_careers(session),
        track=req.track,
        data_year=req.data_year,
        years=4,
    )
    return trajectory.model_dump(mode="json")


@router.get("/admissions")
def list_admissions(
    province: str | None = None,
    track: str | None = None,
    year: int | None = None,
    school: str | None = None,
    min_score: int | None = None,  # 录取最低分 ≥ 此值
    max_score: int | None = None,  # 录取最低分 ≤ 此值（用于按分数范围筛选可报学校）
    session: Session = Depends(get_session_dep),
):
    """录取数据查询（支持按 track/year/分数范围筛选）。"""
    stmt = select(AdmissionRow)
    if province:
        stmt = stmt.where(AdmissionRow.province == province)
    if track:
        stmt = stmt.where(AdmissionRow.track == track)
    if year:
        stmt = stmt.where(AdmissionRow.year == year)
    if school:
        stmt = stmt.where(AdmissionRow.school == school)
    if min_score is not None:
        stmt = stmt.where(AdmissionRow.min_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(AdmissionRow.min_score <= max_score)
    result = []
    for r in session.exec(stmt):
        d = admission_to_domain(r).model_dump(mode="json")
        d["id"] = r.id
        result.append(d)
    return result
