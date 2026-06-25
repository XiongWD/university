from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session_dep
from app.models.tables import UniversityRow
from app.repositories.mappers import university_to_domain

router = APIRouter(prefix="/universities", tags=["universities"])


@router.get("")
def list_universities(tier: str | None = None, session: Session = Depends(get_session_dep)):
    stmt = select(UniversityRow)
    if tier:
        stmt = stmt.where(UniversityRow.tier == tier)
    result = []
    for r in session.exec(stmt):
        d = university_to_domain(r).model_dump(mode="json")
        d["id"] = r.id
        result.append(d)
    return result
