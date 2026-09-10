from __future__ import annotations

from datetime import datetime, timezone

from scripts.comprobar_corte_diario_turso import EXPECTED_SCOPE, evaluate_rows, honduras_day_window


def _rows(timestamp: str) -> list[list[object]]:
    return [[supermarket_id, location_id, timestamp] for supermarket_id, location_id in EXPECTED_SCOPE]


def test_complete_daily_cut_requires_every_productive_scope() -> None:
    now = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    result = evaluate_rows(_rows("2026-09-10T13:00:00Z"), now_utc=now)
    assert result["local_date"] == "2026-09-10"
    assert result["expected_scope_count"] == 11
    assert result["accepted_scope_count"] == 11
    assert result["complete_today"] is True
    assert result["missing_scope"] == []


def test_missing_one_scope_keeps_daily_cut_incomplete() -> None:
    now = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    rows = _rows("2026-09-10T13:00:00Z")[:-1]
    result = evaluate_rows(rows, now_utc=now)
    assert result["complete_today"] is False
    assert result["accepted_scope_count"] == 10
    assert result["missing_scope"] == [
        {"supermarket_id": EXPECTED_SCOPE[-1][0], "location_id": EXPECTED_SCOPE[-1][1]}
    ]


def test_honduras_day_boundary_uses_local_date_not_utc_date() -> None:
    now = datetime(2026, 9, 11, 4, 30, tzinfo=timezone.utc)  # Sep 10, 22:30 Honduras
    start, end, local_date = honduras_day_window(now)
    assert local_date == "2026-09-10"
    assert start == datetime(2026, 9, 10, 6, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 11, 6, 0, tzinfo=timezone.utc)
    result = evaluate_rows(_rows("2026-09-11T04:00:00Z"), now_utc=now)
    assert result["complete_today"] is True


def test_previous_local_day_is_not_accepted_and_duplicate_rows_do_not_inflate_count() -> None:
    now = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    rows = _rows("2026-09-09T13:00:00Z")
    rows.extend([
        [EXPECTED_SCOPE[0][0], EXPECTED_SCOPE[0][1], "2026-09-10T12:00:00Z"],
        [EXPECTED_SCOPE[0][0], EXPECTED_SCOPE[0][1], "2026-09-10T13:00:00Z"],
    ])
    result = evaluate_rows(rows, now_utc=now)
    assert result["accepted_scope_count"] == 1
    assert result["complete_today"] is False
    key = f"{EXPECTED_SCOPE[0][0]}:{EXPECTED_SCOPE[0][1]}"
    assert result["latest_observed_at_utc"][key] == "2026-09-10T13:00:00Z"
