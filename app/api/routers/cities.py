from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session_dep
from app.models.tables import CityCostRow
from app.repositories.mappers import city_to_domain

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("")
def list_cities(session: Session = Depends(get_session_dep)):
    rows = session.exec(select(CityCostRow)).all()
    result = []
    for r in rows:
        d = city_to_domain(r).model_dump(mode="json")
        d["id"] = r.id
        result.append(d)
    return result


@router.get("/{city}/cost")
def get_city_cost(city: str, session: Session = Depends(get_session_dep)):
    row = session.exec(select(CityCostRow).where(CityCostRow.city == city)).first()
    if not row:
        raise HTTPException(404, "city not found")
    return city_to_domain(row).model_dump(mode="json")
