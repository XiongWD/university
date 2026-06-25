"""Table ↔ Domain 映射层。

集中六类实体的拍平/重组逻辑，可独立测试。
JSON 字段用 json.dumps/loads，ensure_ascii=False 保留中文。
"""

import json

from app.models.admission import AdmissionRecord, Batch
from app.models.base import CostBand
from app.models.career import (
    Career, EstablishmentType, PromotionSpeed, SalaryBand,
)
from app.models.city import CityCost, RentTiers
from app.models.insurance import InsuranceRates, RatePair, SocialInsurance
from app.models.major import (
    Barriers, EmploymentDensity, Major, SalaryQuantile, Upside,
)
from app.models.student import (
    FamilyResources, MinorLanguage, RiskPreference, StudentProfile,
)
from app.models.university import (
    Discipline, EmploymentAbility, University, UniversityTier,
)
from app.models.tables import (
    AdmissionRow, CareerRow, CityCostRow, MajorRow,
    SocialInsuranceRow, StudentRow, UniversityRow,
)


# ---------- Career ----------
def career_to_row(c: Career) -> CareerRow:
    return CareerRow(
        name=c.name, category=c.category,
        entry_salary_low=c.entry_salary.low, entry_salary_mid=c.entry_salary.mid,
        entry_salary_high=c.entry_salary.high,
        mid5_low=c.mid_salary_5y.low, mid5_mid=c.mid_salary_5y.mid, mid5_high=c.mid_salary_5y.high,
        ceil15_low=c.ceil_salary_15y.low, ceil15_mid=c.ceil_salary_15y.mid,
        ceil15_high=c.ceil_salary_15y.high,
        stability=c.stability, promotion_speed=c.promotion_speed.value,
        establishment_type=c.establishment_type.value,
        related_majors=json.dumps(c.related_majors, ensure_ascii=False),
        source=c.source, as_of=c.as_of, confidence=c.confidence, note=c.note,
    )


def career_to_domain(r: CareerRow) -> Career:
    return Career(
        name=r.name, category=r.category,
        entry_salary=SalaryBand(low=r.entry_salary_low, mid=r.entry_salary_mid, high=r.entry_salary_high),
        mid_salary_5y=SalaryBand(low=r.mid5_low, mid=r.mid5_mid, high=r.mid5_high),
        ceil_salary_15y=SalaryBand(low=r.ceil15_low, mid=r.ceil15_mid, high=r.ceil15_high),
        stability=r.stability, promotion_speed=PromotionSpeed(r.promotion_speed),
        establishment_type=EstablishmentType(r.establishment_type),
        related_majors=json.loads(r.related_majors),
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )


# ---------- CityCost ----------
def city_to_row(c: CityCost) -> CityCostRow:
    return CityCostRow(
        city=c.city,
        rent_single_low=c.rent.single.low, rent_single_high=c.rent.single.high,
        rent_onebed_low=c.rent.one_bed.low, rent_onebed_high=c.rent.one_bed.high,
        rent_shared_low=c.rent.shared.low, rent_shared_high=c.rent.shared.high,
        food_low=c.food.low, food_high=c.food.high,
        commute_low=c.commute.low, commute_high=c.commute.high,
        other_low=c.other.low, other_high=c.other.high,
        monthly_total_low=c.monthly_total.low, monthly_total_high=c.monthly_total.high,
        house_price_avg=c.house_price_avg,
        source=c.source, as_of=c.as_of, confidence=c.confidence, note=c.note,
    )


def city_to_domain(r: CityCostRow) -> CityCost:
    return CityCost(
        city=r.city,
        rent=RentTiers(
            single=CostBand(low=r.rent_single_low, high=r.rent_single_high),
            one_bed=CostBand(low=r.rent_onebed_low, high=r.rent_onebed_high),
            shared=CostBand(low=r.rent_shared_low, high=r.rent_shared_high),
        ),
        food=CostBand(low=r.food_low, high=r.food_high),
        commute=CostBand(low=r.commute_low, high=r.commute_high),
        other=CostBand(low=r.other_low, high=r.other_high),
        monthly_total=CostBand(low=r.monthly_total_low, high=r.monthly_total_high),
        house_price_avg=r.house_price_avg,
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )


# ---------- University ----------
def university_to_row(u: University) -> UniversityRow:
    return UniversityRow(
        name=u.name, province=u.province, tier=u.tier.value,
        campus_tier=u.employment_ability.campus_tier,
        avg_entry_salary=u.employment_ability.avg_entry_salary,
        employment_rate=u.employment_ability.employment_rate,
        disciplines=json.dumps([d.model_dump() for d in u.disciplines], ensure_ascii=False),
        source=u.source, as_of=u.as_of, confidence=u.confidence, note=u.note,
    )


def university_to_domain(r: UniversityRow) -> University:
    return University(
        name=r.name, province=r.province, tier=UniversityTier(r.tier),
        employment_ability=EmploymentAbility(
            campus_tier=r.campus_tier, avg_entry_salary=r.avg_entry_salary,
            employment_rate=r.employment_rate,
        ),
        disciplines=[Discipline(**d) for d in json.loads(r.disciplines)],
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )


# ---------- Major ----------
def major_to_row(m: Major) -> MajorRow:
    return MajorRow(
        name=m.name, category=m.category,
        jobs=m.employment_density.jobs, frequency=m.employment_density.frequency,
        city_coverage=m.employment_density.city_coverage,
        p25=m.salary.p25, p50=m.salary.p50, p75=m.salary.p75,
        barrier_english=m.barriers.english, barrier_math=m.barriers.math,
        barrier_certificate=m.barriers.certificate, barrier_postgrad=m.barriers.postgrad,
        upside_management=m.upside.management, upside_freelance=m.upside.freelance,
        upside_cross_industry=m.upside.cross_industry,
        source=m.source, as_of=m.as_of, confidence=m.confidence, note=m.note,
    )


def major_to_domain(r: MajorRow) -> Major:
    return Major(
        name=r.name, category=r.category,
        employment_density=EmploymentDensity(
            jobs=r.jobs, frequency=r.frequency, city_coverage=r.city_coverage,
        ),
        salary=SalaryQuantile(p25=r.p25, p50=r.p50, p75=r.p75),
        barriers=Barriers(
            english=r.barrier_english, math=r.barrier_math,
            certificate=r.barrier_certificate, postgrad=r.barrier_postgrad,
        ),
        upside=Upside(
            management=r.upside_management, freelance=r.upside_freelance,
            cross_industry=r.upside_cross_industry,
        ),
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )


# ---------- SocialInsurance ----------
def insurance_to_row(si: SocialInsurance) -> SocialInsuranceRow:
    r = si.rates
    return SocialInsuranceRow(
        city=si.city,
        pension_employee=r.pension.employee, pension_employer=r.pension.employer,
        medical_employee=r.medical.employee, medical_employer=r.medical.employer,
        unemployment_employee=r.unemployment.employee, unemployment_employer=r.unemployment.employer,
        workinjury_employee=r.work_injury.employee, workinjury_employer=r.work_injury.employer,
        maternity_employee=r.maternity.employee, maternity_employer=r.maternity.employer,
        housing_employee=r.housing_fund.employee, housing_employer=r.housing_fund.employer,
        source=si.source, as_of=si.as_of, confidence=si.confidence, note=si.note,
    )


def insurance_to_domain(r: SocialInsuranceRow) -> SocialInsurance:
    return SocialInsurance(
        city=r.city,
        rates=InsuranceRates(
            pension=RatePair(employee=r.pension_employee, employer=r.pension_employer),
            medical=RatePair(employee=r.medical_employee, employer=r.medical_employer),
            unemployment=RatePair(employee=r.unemployment_employee, employer=r.unemployment_employer),
            work_injury=RatePair(employee=r.workinjury_employee, employer=r.workinjury_employer),
            maternity=RatePair(employee=r.maternity_employee, employer=r.maternity_employer),
            housing_fund=RatePair(employee=r.housing_employee, employer=r.housing_employer),
        ),
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )


# ---------- Admission ----------
def admission_to_row(a: AdmissionRecord) -> AdmissionRow:
    return AdmissionRow(
        school=a.school, major=a.major, province=a.province,
        year=a.year, track=a.track, min_score=a.min_score,
        min_rank=a.min_rank, avg_score=a.avg_score, batch=a.batch.value,
        source=a.source, as_of=a.as_of, confidence=a.confidence, note=a.note,
    )


def admission_to_domain(r: AdmissionRow) -> AdmissionRecord:
    return AdmissionRecord(
        school=r.school, major=r.major, province=r.province,
        year=r.year, track=r.track, min_score=r.min_score,
        min_rank=r.min_rank, avg_score=r.avg_score, batch=Batch(r.batch),
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )


# ---------- Student ----------
def student_to_row(s: StudentProfile) -> StudentRow:
    return StudentRow(
        province=s.province, total_score=s.total_score,
        subject_scores=json.dumps(s.subject_scores, ensure_ascii=False),
        minor_language=json.dumps(s.minor_language.model_dump(), ensure_ascii=False) if s.minor_language else None,
        family_resources=json.dumps(s.family_resources.model_dump(), ensure_ascii=False),
        gender=s.gender,
        interests=json.dumps(s.interests, ensure_ascii=False),
        strengths=json.dumps(s.strengths, ensure_ascii=False),
        risk_preference=s.risk_preference.value,
        source=s.source, as_of=s.as_of, confidence=s.confidence, note=s.note,
    )


def student_to_domain(r: StudentRow) -> StudentProfile:
    minor = None
    if r.minor_language:
        minor = MinorLanguage(**json.loads(r.minor_language))
    return StudentProfile(
        province=r.province, total_score=r.total_score,
        subject_scores=json.loads(r.subject_scores),
        minor_language=minor,
        family_resources=FamilyResources(**json.loads(r.family_resources)),
        gender=r.gender,
        interests=json.loads(r.interests),
        strengths=json.loads(r.strengths),
        risk_preference=RiskPreference(r.risk_preference),
        source=r.source, as_of=r.as_of, confidence=r.confidence, note=r.note,
    )
