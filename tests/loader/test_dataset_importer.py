import csv

import pytest
from sqlmodel import Session, select

from app.db import init_db
from app.loader.dataset_importer import import_score_rank_csv
from app.models.tables import ScoreRankEntryRow, ScoreRankTableRow


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["最高分", "最低分", "人数", "累计", "省级行政区",
                    "综合", "年份", "总分(裸分)", "模式"])
        w.writerows(rows)
    return path


def test_import_parses_and_stores(isolated_db, tmp_path):
    csv_path = _write_csv(tmp_path / "gaokao.csv", [
        [691, 691, 19, 193, "河南", "理科", 2024, 750, "3+X"],
        [690, 690, 22, 215, "河南", "理科", 2024, 750, "3+X"],
        [689, 689, 24, 239, "河南", "理科", 2024, 750, "3+X"],
    ])
    init_db()
    with Session(init_db()) as s:
        rep = import_score_rank_csv(csv_path, s, ["河南"], [2024])
        assert rep["河南/2024/理科"] == 3
        tbl = s.exec(select(ScoreRankTableRow)).one()
        assert tbl.source == "Gaokao-score-distribution数据集"
        assert tbl.confidence == 0.8
        entries = s.exec(select(ScoreRankEntryRow)).all()
        assert len(entries) == 3


def test_import_idempotent(isolated_db, tmp_path):
    csv_path = _write_csv(tmp_path / "gaokao.csv", [
        [690, 690, 22, 215, "河南", "理科", 2024, 750, "3+X"],
        [689, 689, 24, 239, "河南", "理科", 2024, 750, "3+X"],
    ])
    init_db()
    with Session(init_db()) as s:
        import_score_rank_csv(csv_path, s, ["河南"], [2024])
        rep2 = import_score_rank_csv(csv_path, s, ["河南"], [2024])
        assert rep2["河南/2024/理科"] == 2
        assert len(s.exec(select(ScoreRankTableRow)).all()) == 1
        assert len(s.exec(select(ScoreRankEntryRow)).all()) == 2


def test_import_filters_by_province_year(isolated_db, tmp_path):
    csv_path = _write_csv(tmp_path / "gaokao.csv", [
        [690, 690, 22, 215, "河南", "理科", 2024, 750, "3+X"],
        [690, 690, 700, 22216, "广东", "物理类", 2024, 750, "3+1+2"],
        [690, 690, 10, 50, "河南", "理科", 2023, 750, "3+X"],
    ])
    init_db()
    with Session(init_db()) as s:
        rep = import_score_rank_csv(csv_path, s, ["河南"], [2024])
        assert rep == {"河南/2024/理科": 1}


def test_import_rejects_monotonic_violation(isolated_db, tmp_path):
    csv_path = _write_csv(tmp_path / "gaokao.csv", [
        [691, 691, 5, 500, "河南", "理科", 2024, 750, "3+X"],
        [690, 690, 22, 215, "河南", "理科", 2024, 750, "3+X"],
    ])
    init_db()
    with Session(init_db()) as s:
        with pytest.raises(ValueError):
            import_score_rank_csv(csv_path, s, ["河南"], [2024])


def test_import_missing_csv_degrades_gracefully(isolated_db, tmp_path):
    init_db()
    with Session(init_db()) as s:
        rep = import_score_rank_csv(tmp_path / "nope.csv", s, ["河南"], [2024])
        assert rep == {}
