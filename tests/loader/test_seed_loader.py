import pytest
from sqlmodel import Session, select

from app.db import init_db
from app.loader.seed_loader import load_all_seeds, is_db_empty, SeedLoadError
from app.models.tables import CareerRow


CAREER_YAML = """\
- name: 公务员-科员
  category: 公务员
  entry_salary: {low: 4000, mid: 5000, high: 6000}
  mid_salary_5y: {low: 7000, mid: 8000, high: 9000}
  ceil_salary_15y: {low: 10000, mid: 12000, high: 15000}
  stability: 0.9
  promotion_speed: 慢
  establishment_type: 行政编
  related_majors: [法学]
  source: 公开报告2024
  as_of: 2024-05-01
  confidence: 0.5
  note: 待爬虫校准
"""

BAD_YAML = """\
- name: 坏记录
  category: 公务员
  entry_salary: {low: 4000, mid: 5000, high: 6000}
  mid_salary_5y: {low: 7000, mid: 8000, high: 9000}
  ceil_salary_15y: {low: 10000, mid: 12000, high: 15000}
  stability: 0.9
  promotion_speed: 慢
  establishment_type: 行政编
  related_majors: []
  as_of: 2024-05-01
  confidence: 0.5
"""


def _write(tmp_path, rel, text):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_load_seeds_idempotent(tmp_path, isolated_db):
    _write(tmp_path, "careers/careers.yaml", CAREER_YAML)
    init_db()
    with Session(init_db()) as s:
        assert is_db_empty(s) is True
        report = load_all_seeds(tmp_path, s)
        assert report["careers"][0] == 1
        # 再次加载：幂等，数量不变
        report2 = load_all_seeds(tmp_path, s)
        assert report2["careers"][0] == 1
        rows = s.exec(select(CareerRow)).all()
        assert len(rows) == 1


def test_load_rejects_missing_source(tmp_path, isolated_db):
    _write(tmp_path, "careers/careers.yaml", BAD_YAML)
    init_db()
    with Session(init_db()) as s:
        with pytest.raises(SeedLoadError) as ei:
            load_all_seeds(tmp_path, s)
        msg = str(ei.value)
        assert "source" in msg.lower() or "careers" in msg.lower()
