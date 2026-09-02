from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actualizar_mvp_sqlite_la_colonia as sqlite_updater  # noqa: E402
import actualizar_mvp_turso_la_colonia as turso_updater  # noqa: E402


def _product(index: int, *, brand: str = "Marca") -> dict[str, object]:
    key = f"sku-{index}"
    return {
        "availability": "in_stock",
        "brand": brand,
        "category": "Categoria",
        "current_price": "100.00",
        "ean": f"ean-{key}",
        "is_promotion": False,
        "item_id": f"item-{index}",
        "presentation": None,
        "product_id": f"product-{index}",
        "reference": f"ref-{key}",
        "reported_regular_price": None,
        "source_key": key,
        "source_key_type": "item_id",
        "source_name": f"Producto {index}",
    }


def _snapshot(when: str, rows: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {
            "result": "success",
            "supermarket_id": "la_colonia",
            "location_id": "la_colonia_sps",
            "city": "San Pedro Sula",
            "catalog_complete": True,
            "validation_passed": True,
            "location_verified_same_run": True,
            "observed_at_utc": when,
            "skus_extracted": len(rows),
            "skus_with_price": len(rows),
            "catalog_products_reported": len(rows),
            "unique_products_extracted": len(rows),
            "products": rows,
        },
        separators=(",", ":"),
    ).encode()


def _steps(raw: bytes, *, run_id: str) -> list[tuple[str, str, tuple[object, ...]]]:
    snap = sqlite_updater.validate_snapshot_bytes(raw)
    return turso_updater._mutation_steps(
        turso_updater._normalised_json(snap),
        location_id="la_colonia_sps",
        observed_at=str(snap["observed_at_utc"]),
        run_id=run_id,
        sku_count=len(snap["products"]),
        catalog_count=int(snap["catalog_products_reported"]),
        artifact_id=None,
        digest=hashlib.sha256(raw).hexdigest(),
    )


def _apply(path: Path, raw: bytes, *, run_id: str) -> dict[str, int]:
    changes: dict[str, int] = {}
    con = sqlite3.connect(path, isolation_level=None)
    try:
        for name, sql, args in _steps(raw, run_id=run_id):
            con.execute(sql, args)
            if name in {"insert_run", "upsert_products", "close_history", "open_history"}:
                changes[name] = int(con.execute("SELECT changes()").fetchone()[0])
    finally:
        con.close()
    return changes


def _measure_unchanged_work(tmp_path: Path, count: int) -> int:
    path = tmp_path / f"mvp-{count}.db"
    sqlite_updater.initialize_database(path)
    rows = [_product(index) for index in range(count)]
    _apply(path, _snapshot("2026-08-30T01:00:00Z", rows), run_id="run-1")
    unchanged = _snapshot("2026-08-30T02:00:00Z", rows)
    instructions = 0

    def progress() -> int:
        nonlocal instructions
        instructions += 100
        return 0

    con = sqlite3.connect(path, isolation_level=None)
    con.set_progress_handler(progress, 100)
    try:
        for _, sql, args in _steps(unchanged, run_id="run-2"):
            con.execute(sql, args)
    finally:
        con.set_progress_handler(None, 0)
        con.close()
    return instructions


def test_unchanged_run_writes_only_scrape_run(tmp_path: Path) -> None:
    path = tmp_path / "mvp.db"
    sqlite_updater.initialize_database(path)
    rows = [_product(index) for index in range(64)]
    _apply(path, _snapshot("2026-08-30T01:00:00Z", rows), run_id="run-1")

    changes = _apply(
        path,
        _snapshot("2026-08-30T02:00:00Z", rows),
        run_id="run-2",
    )

    assert changes == {
        "insert_run": 1,
        "upsert_products": 0,
        "close_history": 0,
        "open_history": 0,
    }
    con = sqlite3.connect(path)
    try:
        assert con.execute("SELECT COUNT(*) FROM products").fetchone() == (64,)
        assert con.execute("SELECT COUNT(*) FROM price_history").fetchone() == (64,)
        assert con.execute("SELECT COUNT(*) FROM scrape_runs").fetchone() == (2,)
    finally:
        con.close()


def test_metadata_only_change_updates_one_product_without_history_write(tmp_path: Path) -> None:
    path = tmp_path / "mvp.db"
    sqlite_updater.initialize_database(path)
    rows = [_product(index) for index in range(32)]
    _apply(path, _snapshot("2026-08-30T01:00:00Z", rows), run_id="run-1")

    changed = [_product(index, brand="Marca nueva" if index == 7 else "Marca") for index in range(32)]
    changes = _apply(
        path,
        _snapshot("2026-08-30T02:00:00Z", changed),
        run_id="run-2",
    )

    assert changes["upsert_products"] == 1
    assert changes["close_history"] == 0
    assert changes["open_history"] == 0
    con = sqlite3.connect(path)
    try:
        assert con.execute(
            "SELECT brand FROM products WHERE source_key='sku-7'"
        ).fetchone() == ("Marca nueva",)
        assert con.execute("SELECT COUNT(*) FROM price_history").fetchone() == (32,)
    finally:
        con.close()


def test_full_unchanged_pipeline_work_grows_below_quadratic(tmp_path: Path) -> None:
    work = [_measure_unchanged_work(tmp_path, count) for count in (128, 256, 512)]

    assert all(value > 0 for value in work)
    # Una duplicación de N no debe acercarse al ~4x característico de O(N²).
    assert work[1] < work[0] * 3
    assert work[2] < work[1] * 3


def test_daily_workflow_avoids_global_database_counts() -> None:
    workflow = (
        ROOT.parent / ".github" / "workflows" / "precios-supermercados-sps-la-colonia-mvp-update.yml"
    ).read_text()

    assert "SELECT (SELECT COUNT(*) FROM products)" not in workflow
    assert "FROM price_history WHERE valid_to_utc IS NULL GROUP BY" not in workflow
    assert "supermarket_id=? AND location_id IN (?,?)" in workflow
    assert "actual[1] < expected[1]" in workflow
    assert "open_by_location != expected_open_by_location" not in workflow
