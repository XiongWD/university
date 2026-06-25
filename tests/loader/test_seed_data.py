from sqlmodel import Session, select

from app.config import settings
from app.db import init_db
from app.loader.seed_loader import load_all_seeds
from app.models.tables import (
    AdmissionRow, CareerRow, CityCostRow, MajorRow,
    SocialInsuranceRow, UniversityRow,
)


def test_all_seeds_load_and_meet_minimums(isolated_db):
    init_db()
    with Session(init_db()) as s:
        report = load_all_seeds(settings.seed_dir, s)
        assert report["cities"][0] >= 7
        assert report["careers"][0] >= 15
        assert report["universities"][0] >= 10
        assert report["majors"][0] >= 15
        # 每条均有来源字段，手编种子 confidence ≤ 0.6
        for row in s.exec(select(CareerRow)).all():
            assert row.source and row.as_of and 0.0 <= row.confidence <= 0.6
        for row in s.exec(select(CityCostRow)).all():
            assert row.note and "待爬虫校准" in row.note


def test_admissions_seed_present(isolated_db):
    init_db()
    with Session(init_db()) as s:
        load_all_seeds(settings.seed_dir, s)
        rows = s.exec(select(AdmissionRow)).all()
        assert len(rows) >= 3  # 3-5 校示例


def test_insurance_seed_includes_baseline(isolated_db):
    init_db()
    with Session(init_db()) as s:
        load_all_seeds(settings.seed_dir, s)
        cities = {r.city for r in s.exec(select(SocialInsuranceRow)).all()}
        assert "全国基准" in cities
