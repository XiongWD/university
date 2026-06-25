from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session_dep
from app.models.tables import CityCostRow
from app.repositories.mappers import city_to_domain

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("")
def list_cities(session: Session = Depends(get_session_dep)):
    rows = session.exec(select(CityCostRow)).all()
    return [
        {
            "city": r.city,
            "house_price_avg": r.house_price_avg,
            "monthly_total": {"low": r.monthly_total_low, "high": r.monthly_total_high},
            "source": r.source,
            "as_of": str(r.as_of),
            "confidence": r.confidence,
            "note": r.note,
        }
        for r in rows
    ]


@router.get("/{city}/cost")
def get_city_cost(city: str, session: Session = Depends(get_session_dep)):
    row = session.exec(select(CityCostRow).where(CityCostRow.city == city)).first()
    if not row:
        raise HTTPException(404, "city not found")
    return city_to_domain(row).model_dump(mode="json")
