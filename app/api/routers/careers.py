from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session_dep
from app.models.tables import CareerRow
from app.repositories.mappers import career_to_domain

router = APIRouter(prefix="/careers", tags=["careers"])


@router.get("")
def list_careers(category: str | None = None, session: Session = Depends(get_session_dep)):
    stmt = select(CareerRow)
    if category:
        stmt = stmt.where(CareerRow.category == category)
    result = []
    for r in session.exec(stmt):
        d = career_to_domain(r).model_dump(mode="json")
        d["id"] = r.id  # 补充 id 供详情查询
        result.append(d)
    return result


@router.get("/{career_id}")
def get_career(career_id: int, session: Session = Depends(get_session_dep)):
    row = session.get(CareerRow, career_id)
    if not row:
        raise HTTPException(404, "career not found")
    return career_to_domain(row).model_dump(mode="json")
