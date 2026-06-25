"""录取数据原始查询端点（仅字段匹配，不做分数筛选——筛选归 decision-engine）。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session_dep
from app.models.tables import AdmissionRow
from app.repositories.mappers import admission_to_domain

router = APIRouter(prefix="/admissions", tags=["admissions"])


@router.get("")
def list_admissions(
    province: str | None = None,
    track: str | None = None,
    school: str | None = None,
    session: Session = Depends(get_session_dep),
):
    stmt = select(AdmissionRow)
    if province:
        stmt = stmt.where(AdmissionRow.province == province)
    if track:
        stmt = stmt.where(AdmissionRow.track == track)
    if school:
        stmt = stmt.where(AdmissionRow.school == school)
    result = []
    for r in session.exec(stmt):
        d = admission_to_domain(r).model_dump(mode="json")
        d["id"] = r.id
        result.append(d)
    return result
