"""大学数据查询 + 大学期间费用估算端点。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.cost import compute_annual_cost
from app.models.tables import CityCostRow, UniversityRow
from app.repositories.mappers import city_to_domain, university_to_domain

router = APIRouter(prefix="/universities", tags=["universities"])


@router.get("")
def list_universities(
    tier: str | None = None,
    nature: str | None = None,  # 公立/民办/中外合作
    province: str | None = None,
    session: Session = Depends(get_session_dep),
):
    stmt = select(UniversityRow)
    if tier:
        stmt = stmt.where(UniversityRow.tier == tier)
    if nature:
        stmt = stmt.where(UniversityRow.nature == nature)
    if province:
        stmt = stmt.where(UniversityRow.province == province)
    result = []
    for r in session.exec(stmt):
        d = university_to_domain(r).model_dump(mode="json")
        d["id"] = r.id
        result.append(d)
    return result


class CostEstimate(BaseModel):
    """大学期间费用估算结果。"""

    school: str
    nature: str
    city: str | None
    years: int
    tuition_per_year: int
    accommodation_per_year: int
    living_cost_per_year: int  # 12×月生活费中位（来自城市成本，无城市则降级省级估算）
    annual_total: int
    grand_total: int  # years × annual_total
    city_cost_source: str | None  # 生活费来源（城市成本表 or 省级估算）
    note: str | None = None


@router.get("/{school}/cost")
def estimate_cost(
    school: str,
    years: int = 4,
    session: Session = Depends(get_session_dep),
):
    """估算大学期间总开销：学费 + 住宿费 + 生活费（按所在城市月成本×12）。

    复用 engine.cost.compute_annual_cost：年成本 = 12×月生活费中位 + 学费 + 住宿费。
    总开销 = 年成本 × years。无城市成本数据时用全国基准降级估算。
    """
    row = session.exec(
        select(UniversityRow).where(UniversityRow.name == school)
    ).first()
    if not row:
        return None

    # 查城市成本（生活费来源）
    city_row = None
    city_source = None
    if row.city:
        city_row = session.exec(
            select(CityCostRow).where(CityCostRow.city == row.city)
        ).first()
        if city_row:
            city_source = f"{row.city}城市成本"

    if city_row:
        annual = compute_annual_cost(city_to_domain(city_row), row.tuition, row.accommodation)
        living = annual.low - row.tuition - row.accommodation
        annual_total = annual.low
        if not city_source:
            city_source = f"{row.city}城市成本"
    else:
        # 降级：全国基准月生活费中位约2000
        living = 12 * 2000
        annual_total = living + row.tuition + row.accommodation
        city_source = "全国基准估算（无该城市数据）"

    return CostEstimate(
        school=row.name,
        nature=row.nature,
        city=row.city,
        years=years,
        tuition_per_year=row.tuition,
        accommodation_per_year=row.accommodation,
        living_cost_per_year=living,
        annual_total=annual_total,
        grand_total=annual_total * years,
        city_cost_source=city_source,
        note=row.note,
    )
