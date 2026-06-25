from datetime import date

from sqlmodel import Session

from app.db import init_db, get_session
from app.models.tables import CareerRow


def test_init_db_creates_tables(isolated_db):
    engine = init_db()
    with Session(engine) as s:
        row = CareerRow(
            name="测试", category="x",
            entry_salary_low=1, entry_salary_mid=2, entry_salary_high=3,
            mid5_low=1, mid5_mid=2, mid5_high=3,
            ceil15_low=1, ceil15_mid=2, ceil15_high=3,
            stability=0.5, promotion_speed="慢",
            establishment_type="行政编", related_majors="[]",
            source="t", as_of=date(2024, 1, 1), confidence=0.5, note=None,
        )
        s.add(row)
        s.commit()
        assert row.id is not None
