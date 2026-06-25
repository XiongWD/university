from sqlmodel import Session, select

from app.config import settings
from app.db import init_db
from app.loader.seed_loader import load_all_seeds
from app.models.tables import ProvincialControlLineRow


def test_provincial_control_line_seeds_load_and_meet_minimums(isolated_db):
    init_db()
    with Session(init_db()) as s:
        report = load_all_seeds(settings.seed_dir, s)
        # 河南物理/历史(2025-2026) + 文理(2022-2024历史保留) + 广东物理/历史(5年)
        assert report["provincial"][0] >= 16
        rows = s.exec(select(ProvincialControlLineRow)).all()
        for r in rows:
            assert r.source and r.as_of and r.confidence >= 0.8


def test_henan_2026_new_gaokao_mode(isolated_db):
    """河南2025起改3+1+2，2026应为物理类/历史类 + 本科批合并（无一本/二本）。"""
    init_db()
    with Session(init_db()) as s:
        load_all_seeds(settings.seed_dir, s)
        rows = s.exec(select(ProvincialControlLineRow)).all()
        h26 = [r for r in rows if r.province == "河南" and r.year == 2026]
        assert {r.track for r in h26} == {"物理类", "历史类"}
        phys = next(r for r in h26 if r.track == "物理类")
        assert phys.undergrad_batch == 419  # 2026官方
        assert phys.special_line == 513  # 2026官方(经教育在线/新蓝网核实)
        assert phys.first_batch is None  # 新高考无一本二本


def test_guangdong_2026_official(isolated_db):
    init_db()
    with Session(init_db()) as s:
        load_all_seeds(settings.seed_dir, s)
        rows = s.exec(select(ProvincialControlLineRow)).all()
        gd26 = next((r for r in rows
                     if r.province == "广东" and r.year == 2026 and r.track == "物理类"), None)
        assert gd26 is not None
        assert gd26.undergrad_batch == 425  # 2026官方
        assert gd26.special_line == 539
