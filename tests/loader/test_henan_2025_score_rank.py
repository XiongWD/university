"""河南2025一分一段表（OCR自官方PDF）导入与位次查询测试。

硬锚点（4个，均经官方公布值精确校验）：
- 物理类 本科线427 → 累计 348,358（官方公布本科上线物理类348358）
- 历史类 本科线471 → 累计 90,174（官方公布本科上线历史类90174）
- 物理类 600分 → 累计 45,887
- 历史类 600分 → 累计 6,178（注：非官方估算的4922，官方真实值为6178）
"""
from pathlib import Path

from sqlmodel import Session, select

from app.db import init_db
from app.engine.rank_query import score_to_rank
from app.loader.dataset_importer import import_score_rank_csv
from app.models.provincial import ScoreRankEntry
from app.models.tables import ScoreRankEntryRow, ScoreRankTableRow

CSV = Path("data/datasets/henan_2025_score_rank.csv")


def _load_2025(session):
    return import_score_rank_csv(CSV, session, ["河南"], [2025])


def test_henan_2025_imports_both_tracks(isolated_db):
    init_db()
    with Session(init_db()) as s:
        report = _load_2025(s)
        assert set(report.keys()) == {"河南/2025/物理类", "河南/2025/历史类"}
        assert report["河南/2025/物理类"] >= 500
        assert report["河南/2025/历史类"] >= 480


def test_henan_2025_sourced_as_official_ocr(isolated_db):
    init_db()
    with Session(init_db()) as s:
        _load_2025(s)
        tbls = s.exec(select(ScoreRankTableRow)
                      .where(ScoreRankTableRow.province == "河南")
                      .where(ScoreRankTableRow.year == 2025)).all()
        assert len(tbls) == 2
        for t in tbls:
            assert "河南省教育考试院" in t.source
            assert t.confidence >= 0.9
            assert t.as_of.year == 2025


def _entries_for(session, track):
    tbl = session.exec(select(ScoreRankTableRow)
                       .where(ScoreRankTableRow.province == "河南")
                       .where(ScoreRankTableRow.year == 2025)
                       .where(ScoreRankTableRow.track == track)).first()
    rows = session.exec(select(ScoreRankEntryRow)
                        .where(ScoreRankEntryRow.table_id == tbl.id)).all()
    return [ScoreRankEntry(score=r.score, count_at=r.count_at,
                           cumulative_rank=r.cumulative_rank) for r in rows]


# ===== 硬锚点精确校验 =====
def test_anchor_physics_undergrad_427(isolated_db):
    """物理类本科线427 → 累计 348,358（官方公布）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2025(s)
        assert score_to_rank(_entries_for(s, "物理类"), 427) == 348358


def test_anchor_history_undergrad_471(isolated_db):
    """历史类本科线471 → 累计 90,174（官方公布）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2025(s)
        assert score_to_rank(_entries_for(s, "历史类"), 471) == 90174


def test_anchor_physics_600(isolated_db):
    """物理类600分 → 累计 45,887。"""
    init_db()
    with Session(init_db()) as s:
        _load_2025(s)
        assert score_to_rank(_entries_for(s, "物理类"), 600) == 45887


def test_anchor_history_600(isolated_db):
    """历史类600分 → 累计 6,178（官方真实值，非非官方估算的4922）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2025(s)
        assert score_to_rank(_entries_for(s, "历史类"), 600) == 6178


def test_idempotent_reimport_2025(isolated_db):
    init_db()
    with Session(init_db()) as s:
        r1 = _load_2025(s)
        r2 = _load_2025(s)
        assert r1 == r2
