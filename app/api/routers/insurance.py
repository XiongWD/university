from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.insurance import compute_take_home_pay, compute_total_labor_cost
from app.models.insurance import SocialInsurance
from app.models.tables import SocialInsuranceRow
from app.repositories.mappers import insurance_to_domain

router = APIRouter(prefix="/insurance", tags=["insurance"])


class ComputeRequest(BaseModel):
    salary: int
    city: str
    special_deduction: int = 0


@router.post("/compute")
def compute(req: ComputeRequest, session: Session = Depends(get_session_dep)):
    row = session.exec(
        select(SocialInsuranceRow).where(SocialInsuranceRow.city == req.city)
    ).first()
    if not row:
        raise HTTPException(404, f"城市 {req.city} 社保配置不存在")
    si: SocialInsurance = insurance_to_domain(row)
    return {
        "salary": req.salary,
        "city": req.city,
        "total_labor_cost": compute_total_labor_cost(req.salary, si),
        "take_home_pay": compute_take_home_pay(req.salary, si, req.special_deduction),
    }
