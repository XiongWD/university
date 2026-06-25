from sqlmodel import Session, select

from app.config import settings
from app.db import init_db
from app.loader.seed_loader import load_all_seeds
from app.models.tables import ProvincialControlLineRow


def test_provincial_control_line_seeds_load_and_meet_minimums(isolated_db):
    init_db()
    with Session(init_db()) as s:
        report = load_all_seeds(settings.seed_dir, s)
        # 两省 × 3年 × 2科类 = 12 条
        assert report["provincial"][0] >= 12
        rows = s.exec(select(ProvincialControlLineRow)).all()
        for r in rows:
            assert r.source and r.as_of and r.confidence >= 0.8


def test_henan_has_first_second_batch_guangdong_has_undergrad(isolated_db):
    init_db()
    with Session(init_db()) as s:
        load_all_seeds(settings.seed_dir, s)
        rows = s.exec(select(ProvincialControlLineRow)).all()
        henan = [r for r in rows if r.province == "河南"]
        gd = [r for r in rows if r.province == "广东"]
        assert henan and any(r.first_batch for r in henan)
        assert gd and any(r.undergrad_batch for r in gd)
        # 结构差异：广东无一本/二本
        assert all(r.first_batch is None for r in gd)
