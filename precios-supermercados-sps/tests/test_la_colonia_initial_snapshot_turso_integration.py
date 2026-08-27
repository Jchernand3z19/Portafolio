from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from precios_supermercados.commercial_persistence_guard import (
    LA_COLONIA_INITIAL_SNAPSHOT_OFFERS,
    LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID,
)
from precios_supermercados.la_colonia_initial_snapshot import (
    LA_COLONIA_INITIAL_SNAPSHOT_JSON_SHA256,
    apply_la_colonia_initial_snapshot_turso,
)


SNAPSHOT_ENV = "PRECIOS_SPS_APPROVED_SNAPSHOT_JSON"


def _approved_snapshot() -> Path:
    raw = os.environ.get(SNAPSHOT_ENV, "").strip()
    if not raw:
        pytest.skip(f"{SNAPSHOT_ENV} no configurado; se ejecuta en el preflight de primera carga")
    path = Path(raw)
    assert path.is_file(), path
    return path


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def test_exact_approved_snapshot_round_trip_on_real_sqlite() -> None:
    path = _approved_snapshot()
    import hashlib

    assert hashlib.sha256(path.read_bytes()).hexdigest() == LA_COLONIA_INITIAL_SNAPSHOT_JSON_SHA256

    connection = sqlite3.connect(":memory:")
    result = apply_la_colonia_initial_snapshot_turso(path, connection=connection)

    assert result.exact_run_replay is False
    assert _count(connection, "offers_current") == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert _count(connection, "offer_history") == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert _count(connection, "source_products") == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert _count(connection, "scrape_runs") == 1

    assert connection.execute(
        "SELECT COUNT(*) FROM offers_current WHERE location_id = 'la_colonia_sps'"
    ).fetchone()[0] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert connection.execute(
        "SELECT COUNT(*) FROM offers_current WHERE current_price_minor IS NOT NULL"
    ).fetchone()[0] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert connection.execute(
        "SELECT COUNT(*) FROM offers_current WHERE availability = 'in_stock'"
    ).fetchone()[0] == 7081
    assert connection.execute(
        "SELECT COUNT(*) FROM offers_current WHERE availability = 'unknown'"
    ).fetchone()[0] == 2358
    assert connection.execute(
        "SELECT COUNT(*) FROM source_products WHERE mapping_status = 'mapped'"
    ).fetchone()[0] == 8965
    assert connection.execute(
        "SELECT COUNT(*) FROM source_products WHERE mapping_status = 'pending'"
    ).fetchone()[0] == 474
    assert connection.execute(
        "SELECT COUNT(*) FROM source_products WHERE review_status = 'needs_review'"
    ).fetchone()[0] == 1003
    assert connection.execute(
        "SELECT scrape_run_id FROM scrape_runs"
    ).fetchone()[0] == LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID

    before = {
        table: _count(connection, table)
        for table in ("offers_current", "offer_history", "source_products", "scrape_runs")
    }
    replay = apply_la_colonia_initial_snapshot_turso(path, connection=connection)
    assert replay.exact_run_replay is True
    after = {table: _count(connection, table) for table in before}
    assert after == before

    connection.close()
