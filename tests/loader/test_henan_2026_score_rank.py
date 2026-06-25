"""河南2026一分一段表（OCR自官方PDF）导入与位次查询测试。

硬锚点（5个，均经官方公布值精确校验）：
- 物理类 本科线419 → 累计 359,972（官方公布本科上线物理类359972）
- 历史类 本科线459 → 累计 92,756（官方公布本科上线历史类92756）
- 本科上线总量 359972+92756 = 452,728（官方公布452728）
- 600分全省 32622+4922 = 37,544（官方公布37544）
- 700分 物理类累计 48（官方公布700分以上48人）
"""
from pathlib import Path

from sqlmodel import Session, select

from app.db import init_db
from app.engine.rank_query import rank_to_score, score_to_rank
from app.loader.dataset_importer import import_score_rank_csv
from app.models.provincial import ScoreRankEntry
from app.models.tables import ScoreRankEntryRow, ScoreRankTableRow

CSV = Path("data/datasets/henan_2026_score_rank.csv")


def _load_2026(session):
    return import_score_rank_csv(CSV, session, ["河南"], [2026])


def test_henan_2026_imports_both_tracks(isolated_db):
    init_db()
    with Session(init_db()) as s:
        report = _load_2026(s)
        assert set(report.keys()) == {"河南/2026/物理类", "河南/2026/历史类"}
        assert report["河南/2026/物理类"] >= 500
        assert report["河南/2026/历史类"] >= 480


def test_henan_2026_sourced_as_official_ocr(isolated_db):
    """2026 数据应标注为官方OCR源、置信≥0.9、as_of=2026-06-25。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        tbls = s.exec(select(ScoreRankTableRow)
                      .where(ScoreRankTableRow.province == "河南")
                      .where(ScoreRankTableRow.year == 2026)).all()
        assert len(tbls) == 2
        for t in tbls:
            assert "河南省教育考试院" in t.source
            assert t.confidence >= 0.9
            assert t.as_of.year == 2026


def _entries_for(session, track):
    tbl = session.exec(select(ScoreRankTableRow)
                       .where(ScoreRankTableRow.province == "河南")
                       .where(ScoreRankTableRow.year == 2026)
                       .where(ScoreRankTableRow.track == track)).first()
    rows = session.exec(select(ScoreRankEntryRow)
                        .where(ScoreRankEntryRow.table_id == tbl.id)).all()
    return [ScoreRankEntry(score=r.score, count_at=r.count_at,
                           cumulative_rank=r.cumulative_rank) for r in rows]


# ===== 硬锚点精确校验（与官方公布值逐一比对）=====
def test_anchor_physics_undergrad_line_419(isolated_db):
    """物理类本科线419分 → 累计位次应为359,972（官方公布本科上线物理类）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        entries = _entries_for(s, "物理类")
        assert score_to_rank(entries, 419) == 359972


def test_anchor_history_undergrad_line_459(isolated_db):
    """历史类本科线459分 → 累计位次应为92,756（官方公布本科上线历史类）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        entries = _entries_for(s, "历史类")
        assert score_to_rank(entries, 459) == 92756


def test_anchor_total_undergrad_452728(isolated_db):
    """本科上线总量 = 物理类419位次 + 历史类459位次 = 452,728（官方公布）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        phys = score_to_rank(_entries_for(s, "物理类"), 419)
        hist = score_to_rank(_entries_for(s, "历史类"), 459)
        assert phys + hist == 452728


def test_anchor_600_total_37544(isolated_db):
    """600分全省累计 = 物理32622 + 历史4922 = 37,544（官方公布600分及以上37544人）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        phys = score_to_rank(_entries_for(s, "物理类"), 600)
        hist = score_to_rank(_entries_for(s, "历史类"), 600)
        assert phys + hist == 37544


def test_anchor_700_physics_48(isolated_db):
    """物理类700分累计应为48（官方公布700分及以上48人）。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        entries = _entries_for(s, "物理类")
        assert score_to_rank(entries, 700) == 48


# ===== 位次法双向查询可用性 =====
def test_rank_to_score_works_on_2026(isolated_db):
    """位次→分数就近匹配：物理类位次165386（特控线513附近）应回指513分。"""
    init_db()
    with Session(init_db()) as s:
        _load_2026(s)
        entries = _entries_for(s, "物理类")
        assert rank_to_score(entries, 165386) == 513


def test_idempotent_reimport(isolated_db):
    """重复导入幂等：第二次不产生重复条目。"""
    init_db()
    with Session(init_db()) as s:
        r1 = _load_2026(s)
        r2 = _load_2026(s)
        assert r1 == r2
        # 物理类条目数应保持不变（无重复）
        entries = _entries_for(s, "物理类")
        scores = [e.score for e in entries]
        assert len(scores) == len(set(scores))
