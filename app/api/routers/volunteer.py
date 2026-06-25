"""志愿填报引擎 API 端点。

POST /volunteer/recommend：输入考生画像 → 返回冲稳保志愿表（传统）。
POST /volunteer/life-paths：人生路径（V2.2 三路径+资格链+预算）。
GET /volunteer/admissions：录取数据查询。
"""

import yaml
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.eligibility import filter_eligible
from app.engine.job_market import score_direction
from app.engine.life_path import build_life_paths
from app.engine.admission_prediction import predict_group_admission
from app.engine.trajectory import build_life_trajectory
from app.engine.volunteer import generate_volunteer_table
from app.models.admission import Batch
from app.models.eligibility import (
    EnglishLevel, StudentAcademicProfile,
)
from app.models.life_path import FamilyBudget
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


class LifePathsRequest(BaseModel):
    """人生路径请求（V2.2 完整学业画像+家庭预算）。"""

    province: str = "河南"
    total_score: int
    primary_subject: str  # 历史/物理
    chinese_score: int = 0
    math_score: int = 0
    exam_foreign_language: str = "英语"
    foreign_language_score: int = 0
    english_actual_level: str = "intermediate"  # none/basic/intermediate/advanced
    elective_subjects: list[str] = []
    # 家庭预算
    family_annual_income: int = 80000
    family_savings: int = 0
    max_annual_education_budget: int = 0
    accepted_loan_amount: int = 0
    accept_private_school: bool = True


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


# ---------- V2.2 人生路径端点 ----------
_SEED_DIR = Path("data/seed")


def _load_offerings():
    """加载招生专业组规则（从YAML，非DB——规则数据量小且需频繁迭代）。"""
    path = _SEED_DIR / "admission_offerings/admission_offerings.yaml"
    if not path.exists():
        return []
    from app.models.eligibility import AdmissionOfferingRule
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [AdmissionOfferingRule.model_validate(d) for d in data]


def _load_directions_and_snapshots():
    """加载专业方向+职业快照。"""
    from app.models.job_market import JobMarketSnapshot, MajorDirection
    dirs_data = yaml.safe_load((_SEED_DIR / "major_directions/major_directions.yaml").read_text(encoding="utf-8")) or []
    snaps_data = yaml.safe_load((_SEED_DIR / "job_markets/job_snapshots.yaml").read_text(encoding="utf-8")) or []
    directions = [MajorDirection.model_validate(d) for d in dirs_data]
    snaps = [JobMarketSnapshot.model_validate(d) for d in snaps_data]
    snap_map = {}
    for s in snaps:
        snap_map.setdefault(s.career_id, []).append(s)
    return directions, snap_map


def _build_academic_profile(req: LifePathsRequest) -> StudentAcademicProfile:
    """从请求构建学业画像。"""
    level_map = {
        "none": EnglishLevel.NONE, "basic": EnglishLevel.BASIC,
        "intermediate": EnglishLevel.INTERMEDIATE, "advanced": EnglishLevel.ADVANCED,
    }
    return StudentAcademicProfile(
        province=req.province, admission_year=2026,
        total_score=req.total_score, primary_subject=req.primary_subject,
        chinese_score=req.chinese_score, math_score=req.math_score,
        exam_foreign_language=req.exam_foreign_language,
        foreign_language_score=req.foreign_language_score,
        english_actual_level=level_map.get(req.english_actual_level, EnglishLevel.INTERMEDIATE),
        elective_subjects=req.elective_subjects,
    )


def _build_budget(req: LifePathsRequest) -> FamilyBudget:
    return FamilyBudget(
        annual_income=req.family_annual_income,
        available_savings=req.family_savings,
        max_annual_education_budget=req.max_annual_education_budget,
        accepted_loan_amount=req.accepted_loan_amount,
        accept_private_school=req.accept_private_school,
    )


@router.post("/life-paths")
def life_paths(req: LifePathsRequest, session: Session = Depends(get_session_dep)):
    """V2.2 人生路径：资格链→录取→市场→适配→三路径。

    这是专业优先推荐的核心端点。
    先过Eligibility定义可行解空间，再在合法集合上优化三路径。
    返回LifePathResult（三路径+家庭预算+说明）。
    """
    profile = _build_academic_profile(req)
    budget = _build_budget(req)
    offerings = _load_offerings()
    directions, snap_map = _load_directions_and_snapshots()

    # [0] Eligibility：定义可行解空间
    eligible, ineligible = filter_eligible(profile, offerings)

    # 取一分一段表算位次
    track = "历史类" if profile.primary_subject == "历史" else "物理类"
    entries = _load_rank_entries(session, profile.province, 2026, track)
    from app.engine.volunteer import convert_score_to_rank
    student_rank = convert_score_to_rank(entries, profile.total_score) or 0

    # 取录取数据（历史位次）
    admissions = _load_admissions(session, profile.province, track, 2025)
    adm_by_school = {a.school: a for a in admissions}

    # 构建 candidates（合法集合上的候选）
    # 从University查真实费用 + Major查真实薪资
    from app.models.tables import UniversityRow
    uni_map = {}
    for u in session.exec(select(UniversityRow)).all():
        uni_map[u.name] = u
    # Major薪资映射（按专业名，MajorRow已拍平为p25/p50/p75列）
    from app.models.tables import MajorRow
    major_salary = {}
    for m in session.exec(select(MajorRow)).all():
        major_salary[m.name] = {"p25": m.p25, "p50": m.p50, "p75": m.p75}

    candidates = []
    for off, elig_result in eligible:
        # 匹配专业方向：优先用direction_hint，否则按专业组名匹配
        direction = directions[0]
        hint = getattr(off, "direction_hint", None) or ""
        if hint:
            for d in directions:
                if d.name == hint:
                    direction = d
                    break
        else:
            best_match = 0
            for d in directions:
                score = sum(1 for m in d.majors if m in off.major_group_name or m in off.school)
                if score > best_match:
                    best_match = score
                    direction = d
        market = score_direction(direction, snap_map)
        # 录取预测
        adm = adm_by_school.get(off.school)
        baseline_2025 = adm.min_rank if adm else None
        group_pred = predict_group_admission(
            school=off.school, major_group_code=off.major_group_code,
            student_rank=student_rank, baseline_rank_2025=baseline_2025,
        )
        # 费用：从University查，无则按性质估
        uni = uni_map.get(off.school)
        if uni:
            # 生活费按城市估：郑州等约2000/月，沿海约3500/月
            living_monthly = 2000
            if uni.city in ("深圳", "北京", "上海", "广州", "杭州"):
                living_monthly = 3500
            elif uni.city in ("苏州", "宁波", "南京"):
                living_monthly = 2800
            cost = (uni.tuition + uni.accommodation + 12 * living_monthly) * 4
            ownership = uni.nature
        else:
            is_private = any(k in off.school for k in ["升达", "黄河科技", "工商", "商丘", "西亚斯"])
            cost = 160000 if is_private else 100000
            ownership = "民办" if is_private else "公办"
        # 薪资：从Major查（按方向的第一个匹配专业），无则默认
        sal = {"p25": 4500, "p50": 5500, "p75": 7500}
        for mname in direction.majors:
            if mname in major_salary:
                sal = major_salary[mname]
                break
        candidates.append({
            "school": off.school, "direction": direction.name,
            "major": off.major_group_name, "ownership": ownership,
            "admission_level": group_pred.admission_level.value,
            "cost_4y": cost, "market": market,
            "major_value": market.current_market_score,
            "target_careers": list(direction.career_weights.keys())[:3],
            "salary_p50": sal["p50"], "salary_p25": sal["p25"], "salary_p75": sal["p75"],
            "overall_score": market.current_market_score,
            "data_granularity": "group", "confidence": group_pred.confidence,
            "city": uni.city if uni else None,
            "school_province": off.province if off.province != "河南" else
                (adm.province if adm and adm.province != "河南" else "河南"),
            "planned_enrollment": adm.planned_enrollment if adm else None,
        })

    # [5] Path Optimizer：三路径
    result = build_life_paths(profile, candidates, budget)
    # 附加不可报原因（可解释）
    result.notes.extend([
        f"{off.school}({off.major_group_name})不可报：{res.blocked_summary}"
        for off, res in ineligible
    ])
    return result.model_dump(mode="json")
