from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import actualizar_mvp_sqlite_la_colonia as updater  # noqa: E402


def product(
    key: str = "sku-1", pid: str = "product-1", item: str = "item-1",
    price: str = "100.00", availability: str = "in_stock",
) -> dict[str, object]:
    return {
        "availability": availability, "brand": "Marca", "category": "Categoria",
        "current_price": price, "ean": f"ean-{key}", "is_promotion": price != "100.00",
        "item_id": item, "presentation": None, "product_id": pid, "reference": f"ref-{key}",
        "reported_regular_price": "100.00" if price != "100.00" else None,
        "source_key": key, "source_key_type": "item_id", "source_name": f"Producto {key}",
    }


def snapshot(
    when: str, rows: list[dict[str, object]] | None = None,
    location: str = "la_colonia_sps",
) -> bytes:
    rows = rows or [product()]
    total = len({str(row["product_id"]) for row in rows})
    return json.dumps({
        "result": "success", "supermarket_id": "la_colonia", "location_id": location,
        "city": updater.LOCATIONS[location], "catalog_complete": True,
        "validation_passed": True, "location_verified_same_run": True,
        "observed_at_utc": when, "skus_extracted": len(rows), "skus_with_price": len(rows),
        "catalog_products_reported": total, "unique_products_extracted": total, "products": rows,
    }, separators=(",", ":")).encode()


def db(tmp_path: Path) -> Path:
    path = tmp_path / "mvp.db"
    updater.initialize_database(path)
    return path


def counts(path: Path) -> tuple[int, int, int]:
    con = sqlite3.connect(path)
    try:
        return tuple(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("scrape_runs", "products", "price_history"))
    finally:
        con.close()


def test_historical_updater_required_cases(tmp_path: Path) -> None:
    path = db(tmp_path)

    # Caso 1: mismo estado registra run, no duplica historia.
    updater.apply_snapshot(path, snapshot("2026-08-28T01:00:00Z"), run_id="run-1")
    same = updater.apply_snapshot(path, snapshot("2026-08-28T02:00:00Z"), run_id="run-2")
    assert same["history_unchanged"] == 1
    assert counts(path) == (2, 1, 1)

    # Caso 2: cambio de precio cierra el periodo anterior y abre otro.
    changed = updater.apply_snapshot(
        path, snapshot("2026-08-28T03:00:00Z", [product(price="90.00")]), run_id="run-3"
    )
    assert (changed["history_closed"], changed["history_opened"]) == (1, 1)

    # Caso 3: disponibilidad también forma parte del estado comercial.
    availability = updater.apply_snapshot(
        path,
        snapshot("2026-08-28T04:00:00Z", [product(price="90.00", availability="out_of_stock")]),
        run_id="run-4",
    )
    assert (availability["history_closed"], availability["history_opened"]) == (1, 1)

    # Caso 4: producto nuevo abre su primer periodo.
    rows = [
        product(price="90.00", availability="out_of_stock"),
        product("sku-2", "product-2", "item-2"),
    ]
    new_product = updater.apply_snapshot(
        path, snapshot("2026-08-28T05:00:00Z", rows), run_id="run-5"
    )
    assert new_product["products_inserted"] == 1
    assert counts(path) == (5, 2, 4)

    # Caso 5: replay exacto no duplica.
    raw = snapshot("2026-08-28T06:00:00Z", rows)
    updater.apply_snapshot(path, raw, run_id="run-6")
    before_replay = counts(path)
    assert updater.apply_snapshot(path, raw, run_id="run-6")["replayed"] is True
    assert counts(path) == before_replay

    # Caso 6: un run incompleto se rechaza antes de tocar el estado aceptado.
    before_invalid = updater.validate_database(path)
    invalid = json.loads(snapshot("2026-08-28T07:00:00Z", rows))
    invalid["catalog_complete"] = False
    with pytest.raises(updater.SnapshotError, match="catalog_complete"):
        updater.apply_snapshot(path, json.dumps(invalid).encode(), run_id="run-invalid")
    assert updater.validate_database(path) == before_invalid

    con = sqlite3.connect(path)
    try:
        periods = con.execute(
            """SELECT current_price_minor, availability, valid_to_utc
               FROM price_history WHERE product_id=1 ORDER BY valid_from_utc"""
        ).fetchall()
    finally:
        con.close()
    assert periods[:3] == [
        (10000, "in_stock", "2026-08-28T03:00:00Z"),
        (9000, "in_stock", "2026-08-28T04:00:00Z"),
        (9000, "out_of_stock", None),
    ]


def test_same_source_product_has_independent_sps_tgu_history(tmp_path: Path) -> None:
    path = db(tmp_path)
    updater.apply_snapshot(path, snapshot("2026-08-28T01:00:00Z"), run_id="sps")
    updater.apply_snapshot(
        path, snapshot("2026-08-28T02:00:00Z", location="la_colonia_tgu"), run_id="tgu"
    )
    con = sqlite3.connect(path)
    try:
        assert con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
        assert con.execute(
            """SELECT location_id, COUNT(*) FROM price_history WHERE valid_to_utc IS NULL
               GROUP BY location_id ORDER BY location_id"""
        ).fetchall() == [("la_colonia_sps", 1), ("la_colonia_tgu", 1)]
    finally:
        con.close()
