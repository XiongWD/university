from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session_dep
from app.models.tables import MajorRow
from app.repositories.mappers import major_to_domain

router = APIRouter(prefix="/majors", tags=["majors"])


@router.get("")
def list_majors(session: Session = Depends(get_session_dep)):
    return [
        major_to_domain(r).model_dump(mode="json")
        for r in session.exec(select(MajorRow))
    ]
