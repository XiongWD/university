from pathlib import Path

from app.loader.henan_data_loader import find_best_historical_baseline, load_henan_admission_history
from app.models.henan_data import HenanAdmissionHistory


SEED = Path("data/seed")


def _hist(**kw):
    base = dict(
        year=2025, track="历史类", school_code="10459", school_name="郑州大学",
        major_group_code="101", major_group_name="历史类人文组", major_name="法学",
        min_score=600, min_rank=15000, avg_score=610, batch="本科批",
        data_granularity="major", source_name="河南省教育考试院2025",
        source_url="https://www.haeea.cn/", as_of="2025-08-01",
        confidence=0.85, review_status="verified",
    )
    base.update(kw)
    return HenanAdmissionHistory(**base)


def test_load_history_returns_real_records():
    history = load_henan_admission_history(SEED)
    assert len(history) > 0
    assert any(h.year == 2025 for h in history)
    assert any(h.year == 2024 for h in history)


def test_2025_major_level_rank_wins_over_group_fallback():
    history = [
        _hist(min_rank=15000, data_granularity="major", major_name="法学"),
        _hist(min_rank=18000, data_granularity="major_group", major_name=None),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="101", major_names=["法学"],
        track="历史类", batch="本科批",
    )
    assert baseline["adjusted_min_rank"] == 15000
    assert baseline["data_granularity"] == "major"


def test_2025_group_level_rank_returned_when_major_level_missing():
    """2025 专业级缺失时，2025 专业组级优先于加权趋势。"""
    history = [
        _hist(year=2025, min_rank=20000, data_granularity="major_group", major_name=None),
        _hist(year=2024, min_rank=22000, data_granularity="major_group", major_name=None),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="101", major_names=["法学"],
        track="历史类", batch="本科批",
    )
    # 2025+2024 组级都在 → 用加权趋势（20000*0.7 + 22000*0.3 = 20600），比单年更稳定
    assert baseline["adjusted_min_rank"] == 20600
    assert baseline["data_granularity"] == "major_group_trend"


def test_2025_2024_weighted_trend_only_when_2025_group_missing():
    """仅有 2024 专业组级时，应直接用 2024 专业组级（比校级精确）。"""
    history = [
        _hist(year=2024, min_rank=22000, data_granularity="major_group", major_name=None),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="101", major_names=["法学"],
        track="历史类", batch="本科批",
    )
    assert baseline is not None
    assert baseline["adjusted_min_rank"] == 22000
    assert baseline["year"] == 2024
    assert baseline["data_granularity"] == "major_group"


def test_missing_verified_history_returns_none():
    history = [
        _hist(min_rank=None, review_status="needs_review", data_granularity="major"),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="101", major_names=["法学"],
        track="历史类", batch="本科批",
    )
    assert baseline is None


def test_school_level_fallback_is_low_confidence():
    history = [
        _hist(min_rank=30000, data_granularity="school", major_name=None, major_group_code=None),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="101", major_names=["法学"],
        track="历史类", batch="本科批",
    )
    assert baseline is not None
    assert baseline["data_granularity"] == "school"


def test_inferred_school_fallback_uses_same_school_verified_2025_history():
    history = [
        _hist(
            year=2025,
            major_group_code="201",
            major_group_name="history-group-201",
            major_name=None,
            min_rank=22000,
            data_granularity="major_group",
        ),
        _hist(
            year=2025,
            major_group_code="202",
            major_group_name="history-group-202",
            major_name=None,
            min_rank=18000,
            data_granularity="major_group",
        ),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="999", major_names=["journalism"],
        track="历史类", batch="本科批",
    )
    assert baseline is not None
    assert baseline["adjusted_min_rank"] == 18000
    assert baseline["year"] == 2025
    assert baseline["data_granularity"] == "school_inferred"


def test_inferred_school_fallback_uses_verified_2024_history_when_2025_missing():
    history = [
        _hist(
            year=2024,
            major_group_code="301",
            major_group_name="history-group-301",
            major_name=None,
            min_rank=26000,
            data_granularity="major_group",
        ),
    ]
    baseline = find_best_historical_baseline(
        history, school_code="10459", group_code="999", major_names=["journalism"],
        track="历史类", batch="本科批",
    )
    assert baseline is not None
    assert baseline["adjusted_min_rank"] == 26000
    assert baseline["year"] == 2024
    assert baseline["data_granularity"] == "school_inferred"


def test_importer_rejects_verified_row_without_min_rank(tmp_path):
    import csv
    import subprocess
    import sys

    bad_csv = tmp_path / "bad.csv"
    with bad_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "year", "track", "school_code", "school_name", "major_group_code",
            "major_group_name", "major_name", "min_score", "min_rank", "avg_score",
            "plan_count", "batch", "data_granularity", "source_name", "source_url",
            "source_published_at", "confidence", "review_status",
        ])
        w.writeheader()
        w.writerow({
            "year": "2025", "track": "历史类", "school_code": "10459", "school_name": "郑州大学",
            "major_group_code": "101", "major_group_name": "人文组", "major_name": "法学",
            "min_score": "600", "min_rank": "0", "avg_score": "610", "plan_count": "12",
            "batch": "本科批", "data_granularity": "major",
            "source_name": "考试院", "source_url": "https://www.haeea.cn/",
            "source_published_at": "2025-08-01", "confidence": "0.85", "review_status": "verified",
        })

    result = subprocess.run(
        [sys.executable, "scripts/import_henan_admission_history.py", str(bad_csv), "--year", "2025"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "min_rank" in result.stderr or "min_rank" in result.stdout
