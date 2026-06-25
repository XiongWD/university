"""省级分数数据查询端点：省控线 + 一分一段表双向查询。

复用 admissions router 模式：字段匹配查询，mapper *_to_domain 还原，
响应附 id + 来源字段。空结果返回空列表不报错。
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session_dep
from app.engine.rank_query import rank_to_score, score_to_rank
from app.models.tables import (
    ProvincialControlLineRow, ScoreRankEntryRow, ScoreRankTableRow,
)
from app.repositories.mappers import (
    provincial_control_line_to_domain, score_rank_entry_to_domain,
)

router = APIRouter(prefix="/provincial", tags=["provincial"])


@router.get("/control-line")
def control_line(
    province: str | None = None,
    year: int | None = None,
    track: str | None = None,
    session: Session = Depends(get_session_dep),
):
    stmt = select(ProvincialControlLineRow)
    if province:
        stmt = stmt.where(ProvincialControlLineRow.province == province)
    if year:
        stmt = stmt.where(ProvincialControlLineRow.year == year)
    if track:
        stmt = stmt.where(ProvincialControlLineRow.track == track)
    result = []
    for r in session.exec(stmt):
        d = provincial_control_line_to_domain(r).model_dump(mode="json")
        d["id"] = r.id
        result.append(d)
    return result


def _load_table_entries(session, province, year, track):
    """加载某省年科类的 entries，返回 (table_row|None, list[ScoreRankEntry])。"""
    tbl = session.exec(
        select(ScoreRankTableRow)
        .where(ScoreRankTableRow.province == province)
        .where(ScoreRankTableRow.year == year)
        .where(ScoreRankTableRow.track == track)
    ).first()
    if not tbl:
        return None, []
    entry_rows = session.exec(
        select(ScoreRankEntryRow)
        .where(ScoreRankEntryRow.table_id == tbl.id)
        .order_by(ScoreRankEntryRow.score.desc())
    ).all()
    entries = [score_rank_entry_to_domain(er) for er in entry_rows]
    return tbl, entries


@router.get("/score-rank")
def score_rank(
    province: str,
    year: int,
    track: str,
    session: Session = Depends(get_session_dep),
):
    tbl, entries = _load_table_entries(session, province, year, track)
    if tbl is None:
        return []
    return [e.model_dump(mode="json") for e in entries]


@router.get("/score-rank/rank")
def score_to_rank_ep(
    province: str,
    year: int,
    track: str,
    score: int,
    session: Session = Depends(get_session_dep),
):
    tbl, entries = _load_table_entries(session, province, year, track)
    rank = score_to_rank(entries, score) if entries else None
    return {
        "province": province, "year": year, "track": track, "score": score,
        "rank": rank,
        "source": tbl.source if tbl else None,
        "confidence": tbl.confidence if tbl else None,
    }


@router.get("/score-rank/score")
def rank_to_score_ep(
    province: str,
    year: int,
    track: str,
    rank: int,
    session: Session = Depends(get_session_dep),
):
    tbl, entries = _load_table_entries(session, province, year, track)
    s = rank_to_score(entries, rank) if entries else None
    return {
        "province": province, "year": year, "track": track, "rank": rank,
        "score": s,
        "source": tbl.source if tbl else None,
        "confidence": tbl.confidence if tbl else None,
    }
