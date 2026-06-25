"""一分一段表 CSV 导入器。

运行时由 FastAPI lifespan 调用：CSV 缺失降级为空集不阻断启动。
CSV 列名映射（真实表头带 BOM，用 utf-8-sig 解码）：
  最高分/最低分 → score（实测恒等，取最高分）
  人数 → count_at
  累计 → cumulative_rank
  省级行政区 → province
  综合 → track
  年份 → year
  模式 → 仅校验不入库
来源标注：source="Gaokao-score-distribution数据集", confidence=0.8。
幂等：复用按业务主键 upsert（省/年/科类），删旧 entries 再写新。
"""

import csv
from datetime import date
from pathlib import Path

from sqlmodel import Session, select

from app.models.provincial import ScoreRankEntry, ScoreRankTable
from app.models.tables import ScoreRankEntryRow, ScoreRankTableRow
from app.repositories.mappers import (
    _check_sourced, score_rank_entry_to_row, score_rank_table_to_row,
)

SOURCE_NAME = "Gaokao-score-distribution数据集"
DEFAULT_CONFIDENCE = 0.8
DEFAULT_AS_OF = date(2024, 7, 1)

# 按 CSV 文件名覆盖来源元数据（更准确的溯源）
_FILE_META: dict[str, dict] = {
    "henan_2025_score_rank.csv": {
        "source": "河南省教育考试院2025(OCR自官方PDF,4硬锚点校验)",
        "confidence": 0.95,
        "as_of": date(2025, 6, 25),
    },
    "henan_2026_score_rank.csv": {
        "source": "河南省教育考试院2026(OCR自官方PDF,5硬锚点校验)",
        "confidence": 0.95,
        "as_of": date(2026, 6, 25),
    },
}

# CSV 真实列名 → 内部字段
_COL_SCORE = "最高分"
_COL_COUNT = "人数"
_COL_CUMU = "累计"
_COL_PROV = "省级行政区"
_COL_TRACK = "综合"
_COL_YEAR = "年份"


def _find_table(session: Session, province: str, year: int, track: str):
    stmt = (select(ScoreRankTableRow)
            .where(ScoreRankTableRow.province == province)
            .where(ScoreRankTableRow.year == year)
            .where(ScoreRankTableRow.track == track))
    return session.exec(stmt).first()


def import_score_rank_csv(
    csv_path: Path, session: Session,
    provinces: list[str], years: list[int],
) -> dict[str, int]:
    """从 CSV 导入一分一段表。返回 {省/年/科类: 导入条数}。

    CSV 缺失 → 返回 {} 不抛异常（降级）。
    位次单调性违反 → 抛 ValueError（拒绝并报告）。
    """
    csv_path = Path(csv_path)
    report: dict[str, int] = {}
    if not csv_path.exists():
        return report  # 降级：不阻断启动

    prov_set = set(provinces)
    year_set = set(years)
    buckets: dict[tuple[str, int, str], list[ScoreRankEntry]] = {}

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            try:
                prov = raw[_COL_PROV]
                year = int(raw[_COL_YEAR])
                track = raw[_COL_TRACK]
                score = int(raw[_COL_SCORE])
                count = int(raw[_COL_COUNT])
                cumu = int(raw[_COL_CUMU])
            except (KeyError, ValueError, TypeError):
                continue  # 缺关键字段/类型错误 → 剔除（清洗）
            if prov not in prov_set or year not in year_set:
                continue  # 白名单过滤
            buckets.setdefault((prov, year, track), []).append(
                ScoreRankEntry(score=score, count_at=count, cumulative_rank=cumu)
            )

    for (prov, year, track), entries in buckets.items():
        # 来源元数据：文件特定则覆盖默认
        meta = _FILE_META.get(csv_path.name, {})
        dom = ScoreRankTable(
            province=prov, year=year, track=track, entries=entries,
            source=meta.get("source", SOURCE_NAME),
            as_of=meta.get("as_of", DEFAULT_AS_OF),
            confidence=meta.get("confidence", DEFAULT_CONFIDENCE),
            note=meta.get("note"),
        )
        table_row = score_rank_table_to_row(dom)
        _check_sourced(table_row)
        existing = _find_table(session, prov, year, track)
        if existing:
            # 幂等 upsert：删旧 entries，更新表头
            for old in session.exec(
                select(ScoreRankEntryRow)
                .where(ScoreRankEntryRow.table_id == existing.id)
            ).all():
                session.delete(old)
            existing.source = dom.source
            existing.as_of = dom.as_of
            existing.confidence = dom.confidence
            existing.note = dom.note
            session.flush()
            table_id = existing.id
        else:
            session.add(table_row)
            session.flush()
            table_id = table_row.id
        for e in entries:
            session.add(score_rank_entry_to_row(e, table_id=table_id))
        session.commit()
        report[f"{prov}/{year}/{track}"] = len(entries)
    return report
