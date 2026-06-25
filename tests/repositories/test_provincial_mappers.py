from datetime import date

from app.models.provincial import (
    BatchLines, ProvincialControlLine, ScoreRankEntry, ScoreRankTable,
)
from app.models.tables import (
    ProvincialControlLineRow, ScoreRankEntryRow, ScoreRankTableRow,
)
from app.repositories.mappers import (
    provincial_control_line_to_domain, provincial_control_line_to_row,
    score_rank_entry_to_domain, score_rank_entry_to_row,
    score_rank_table_to_domain, score_rank_table_to_row,
)


def test_control_line_roundtrip_preserves_fields_and_source():
    dom = ProvincialControlLine(
        province="广东", year=2024, track="物理类",
        batches=BatchLines(special_line=539, undergrad_batch=442),
        source="广东省教育考试院2024", as_of=date(2024, 6, 25),
        confidence=0.85, note="新高考",
    )
    row = provincial_control_line_to_row(dom)
    assert isinstance(row, ProvincialControlLineRow)
    assert row.special_line == 539 and row.undergrad_batch == 442
    assert row.first_batch is None
    back = provincial_control_line_to_domain(row)
    assert back.batches.special_line == 539
    assert back.source == dom.source and back.confidence == 0.85


def test_score_rank_table_roundtrip():
    dom = ScoreRankTable(
        province="河南", year=2024, track="理科",
        entries=[ScoreRankEntry(score=690, count_at=22, cumulative_rank=215)],
        source="Gaokao-score-distribution数据集", as_of=date(2024, 7, 1),
        confidence=0.8, note=None,
    )
    row = score_rank_table_to_row(dom)
    assert isinstance(row, ScoreRankTableRow)
    back = score_rank_table_to_domain(row, [])
    assert back.province == "河南" and back.source == dom.source


def test_score_rank_entry_roundtrip():
    e = ScoreRankEntry(score=690, count_at=22, cumulative_rank=215)
    row = score_rank_entry_to_row(e, table_id=1)
    assert isinstance(row, ScoreRankEntryRow)
    assert row.table_id == 1
    back = score_rank_entry_to_domain(row)
    assert back.cumulative_rank == 215
