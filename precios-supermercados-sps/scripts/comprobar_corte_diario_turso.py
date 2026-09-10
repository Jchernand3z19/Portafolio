#!/usr/bin/env python3
"""Comprueba si Turso ya contiene un corte aceptado hoy para todo el scope productivo.

La operación es estrictamente read-only. Se usa para decidir si una ventana de
recuperación debe reintentar una ejecución programada fallida o no generar más
tráfico live.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from actualizar_mvp_sqlite_la_colonia import SnapshotError  # noqa: E402
from actualizar_mvp_turso_la_colonia import _execute_rows, _pipeline, _stmt  # noqa: E402

HN_ZONE = ZoneInfo("America/Tegucigalpa")
EXPECTED_SCOPE = (
    ("la_colonia", "la_colonia_sps"),
    ("la_colonia", "la_colonia_tgu"),
    ("comisariato_los_andes", "comisariato_los_andes_sps"),
    ("paiz", "paiz_tgu_multiplaza"),
    ("paiz", "paiz_tgu_proceres"),
    ("colonial", "colonial_sps"),
    ("walmart", "walmart_sps"),
    ("walmart", "walmart_tgu_ffaa"),
    ("walmart", "walmart_tgu_el_sauce"),
    ("pricesmart", "pricesmart_sps"),
    ("pricesmart", "pricesmart_tgu"),
)


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotError("daily_cut_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def honduras_day_window(now_utc: datetime) -> tuple[datetime, datetime, str]:
    local = now_utc.astimezone(HN_ZONE)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), start_local.date().isoformat()


def evaluate_rows(rows: list[list[object]], *, now_utc: datetime) -> dict[str, object]:
    start, end, local_date = honduras_day_window(now_utc)
    latest: dict[tuple[str, str], datetime] = {}
    for row in rows:
        if len(row) != 3 or not isinstance(row[0], str) or not isinstance(row[1], str) or not isinstance(row[2], str):
            raise SnapshotError("daily_cut_row_invalid")
        key = (row[0], row[1])
        if key not in EXPECTED_SCOPE:
            continue
        observed = parse_utc(row[2])
        if not (start <= observed < end):
            continue
        current = latest.get(key)
        if current is None or observed > current:
            latest[key] = observed
    missing = [
        {"supermarket_id": supermarket_id, "location_id": location_id}
        for supermarket_id, location_id in EXPECTED_SCOPE
        if (supermarket_id, location_id) not in latest
    ]
    return {
        "schema": "precios-sps-daily-cut-status/v1",
        "local_date": local_date,
        "time_zone": "America/Tegucigalpa",
        "expected_scope_count": len(EXPECTED_SCOPE),
        "accepted_scope_count": len(latest),
        "complete_today": not missing,
        "missing_scope": missing,
        "latest_observed_at_utc": {
            f"{supermarket_id}:{location_id}": observed.isoformat().replace("+00:00", "Z")
            for (supermarket_id, location_id), observed in sorted(latest.items())
        },
    }


def fetch_rows(url: str, token: str, *, start: datetime, end: datetime) -> list[list[object]]:
    sql = """
        SELECT supermarket_id,location_id,observed_at_utc
        FROM scrape_runs
        WHERE run_status='success'
          AND julianday(observed_at_utc)>=julianday(?)
          AND julianday(observed_at_utc)<julianday(?)
        ORDER BY observed_at_utc
    """
    data = _pipeline(
        url,
        token,
        [
            {"type": "execute", "stmt": _stmt(sql, (start.isoformat(), end.isoformat()))},
            {"type": "close"},
        ],
    )
    results = data.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise SnapshotError("daily_cut_turso_response_invalid")
    return _execute_rows(results[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now-utc", help="UTC ISO-8601 determinista para pruebas/operación controlada")
    args = parser.parse_args()
    now_utc = parse_utc(args.now_utc) if args.now_utc else datetime.now(timezone.utc)
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if not url or not token:
        raise SystemExit("turso_credentials_missing")
    start, end, _ = honduras_day_window(now_utc)
    rows = fetch_rows(url, token, start=start, end=end)
    result = evaluate_rows(rows, now_utc=now_utc)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["complete_today"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
