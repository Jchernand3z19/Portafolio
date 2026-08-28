from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actualizar_mvp_sqlite_la_colonia as updater  # noqa: E402


def _product(
    *,
    source_key: str = "sku-1",
    product_id: str = "product-1",
    item_id: str = "item-1",
    price: str = "100.00",
    availability: str = "in_stock",
) -> dict[str, object]:
    return {
        "availability": availability,
        "brand": "Marca",
        "category": "Categoria",
        "current_price": price,
        "ean": f"ean-{source_key}",
        "is_promotion": price != "100.00",
        "item_id": item_id,
        "presentation": None,
        "product_id": product_id,
        "reference": f"ref-{source_key}",
        "reported_regular_price": "100.00" if price != "100.00" else None,
        "source_key": source_key,
        "source_key_type": "item_id",
        "source_name": f"Producto {source_key}",
    }


def _snapshot(
    *,
    observed_at: str,
    products: list[dict[str, object]] | None = None,
    location_id: str = "la_colonia_sps",
) -> bytes:
    rows = products or [_product()]
    source_products = {str(row["product_id"]) for row in rows}
    return json.dumps(
        {
            "result": "success",
            "supermarket_id": "la_colonia",
            "location_id": location_id,
            "city": updater.LOCATIONS[location_id],
            "catalog_complete": True,
            "validation_passed": True,
            "location_verified_same_run": True,
            "observed_at_utc": observed_at,
            "skus_extracted": len(rows),
            "skus_with_price": len(rows),
            "catalog_products_reported": len(source_products),
            "unique_products_extracted": len(source_products),
            "products": rows,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _new_db(tmp_path: Path) -> Path:
    database = tmp_path / "mvp.db"
    updater.initialize_database(database)
    return database


def _counts(database: Path) -> tuple[int, int, int]:
    con = sqlite3.connect(database)
    try:
        return (
            con.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0],
            con.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0],
        )
    finally:
        con.close()


def test_same_state_registers_run_without_redundant_history(tmp_path: Path) -> None:
    database = _new_db(tmp_path)
    updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T01:00:00Z"),
        run_id="run-1",
    )
    result = updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T02:00:00Z"),
        run_id="run-2",
    )

    assert result["history_unchanged"] == 1
    assert result["history_opened"] == 0
    assert _counts(database) == (2, 1, 1)


def test_price_change_closes_previous_period_and_opens_new_one(tmp_path: Path) -> None:
    database = _new_db(tmp_path)
    updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T01:00:00Z"),
        run_id="run-1",
    )
    updater.apply_snapshot(
        database,
        _snapshot(
            observed_at="2026-08-28T02:00:00Z",
            products=[_product(price="90.00")],
        ),
        run_id="run-2",
    )

    con = sqlite3.connect(database)
    try:
        rows = con.execute(
            """
            SELECT current_price_minor, valid_from_utc, valid_to_utc
            FROM price_history
            ORDER BY valid_from_utc
            """
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        (10000, "2026-08-28T01:00:00Z", "2026-08-28T02:00:00Z"),
        (9000, "2026-08-28T02:00:00Z", None),
    ]


def test_availability_change_creates_new_commercial_period(tmp_path: Path) -> None:
    database = _new_db(tmp_path)
    updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T01:00:00Z"),
        run_id="run-1",
    )
    result = updater.apply_snapshot(
        database,
        _snapshot(
            observed_at="2026-08-28T02:00:00Z",
            products=[_product(availability="out_of_stock")],
        ),
        run_id="run-2",
    )

    assert result["history_closed"] == 1
    assert result["history_opened"] == 1
    con = sqlite3.connect(database)
    try:
        current = con.execute(
            """
            SELECT availability
            FROM price_history
            WHERE valid_to_utc IS NULL
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert current == "out_of_stock"


def test_new_product_is_inserted_with_initial_period(tmp_path: Path) -> None:
    database = _new_db(tmp_path)
    updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T01:00:00Z"),
        run_id="run-1",
    )
    result = updater.apply_snapshot(
        database,
        _snapshot(
            observed_at="2026-08-28T02:00:00Z",
            products=[
                _product(),
                _product(
                    source_key="sku-2",
                    product_id="product-2",
                    item_id="item-2",
                ),
            ],
        ),
        run_id="run-2",
    )

    assert result["products_inserted"] == 1
    assert result["history_opened"] == 1
    assert _counts(database) == (2, 2, 2)


def test_exact_replay_is_idempotent(tmp_path: Path) -> None:
    database = _new_db(tmp_path)
    raw = _snapshot(observed_at="2026-08-28T01:00:00Z")
    updater.apply_snapshot(database, raw, run_id="run-1")
    result = updater.apply_snapshot(database, raw, run_id="run-1")

    assert result["replayed"] is True
    assert _counts(database) == (1, 1, 1)


def test_invalid_or_incomplete_run_does_not_modify_accepted_state(
    tmp_path: Path,
) -> None:
    database = _new_db(tmp_path)
    updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T01:00:00Z"),
        run_id="run-1",
    )
    before = updater.validate_database(database)

    invalid = json.loads(
        _snapshot(observed_at="2026-08-28T02:00:00Z").decode("utf-8")
    )
    invalid["catalog_complete"] = False
    with pytest.raises(updater.SnapshotError, match="catalog_complete"):
        updater.apply_snapshot(
            database,
            json.dumps(invalid).encode("utf-8"),
            run_id="run-invalid",
        )

    assert updater.validate_database(database) == before


def test_same_source_product_keeps_location_history_isolated(tmp_path: Path) -> None:
    database = _new_db(tmp_path)
    updater.apply_snapshot(
        database,
        _snapshot(observed_at="2026-08-28T01:00:00Z"),
        run_id="run-sps",
    )
    updater.apply_snapshot(
        database,
        _snapshot(
            observed_at="2026-08-28T02:00:00Z",
            location_id="la_colonia_tgu",
        ),
        run_id="run-tgu",
    )

    con = sqlite3.connect(database)
    try:
        products = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        locations = con.execute(
            """
            SELECT location_id, COUNT(*)
            FROM price_history
            WHERE valid_to_utc IS NULL
            GROUP BY location_id
            ORDER BY location_id
            """
        ).fetchall()
    finally:
        con.close()
    assert products == 1
    assert locations == [("la_colonia_sps", 1), ("la_colonia_tgu", 1)]
