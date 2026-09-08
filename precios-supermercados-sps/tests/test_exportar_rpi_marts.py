from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "exportar_rpi_marts.py"
SPEC = importlib.util.spec_from_file_location("exportar_rpi_marts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AS_OF = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


def build_db(path: Path, *, stale_b: bool = False) -> None:
    with sqlite3.connect(path) as con:
        con.executescript(
            """
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY, supermarket_id TEXT NOT NULL,
                name TEXT NOT NULL, brand TEXT, presentation TEXT, category TEXT, ean TEXT
            );
            CREATE TABLE price_history (
                product_id INTEGER NOT NULL, supermarket_id TEXT NOT NULL,
                location_id TEXT NOT NULL, current_price_minor INTEGER,
                reported_regular_price_minor INTEGER, is_promotion INTEGER,
                availability TEXT NOT NULL, valid_from_utc TEXT NOT NULL,
                valid_to_utc TEXT
            );
            CREATE TABLE scrape_runs (
                scrape_run_id TEXT PRIMARY KEY, supermarket_id TEXT NOT NULL,
                location_id TEXT NOT NULL, observed_at_utc TEXT NOT NULL,
                run_status TEXT NOT NULL
            );
            """
        )
        con.executemany(
            "INSERT INTO products VALUES(?,?,?,?,?,?,?)",
            (
                (1, "a", "Leche Sula entera 1 L", "Sula", "1 L", "Lácteos", "7590002040003"),
                (2, "b", "Sula leche entera 1 L", "Sula", "1 L", "Lácteos", "07590002040003"),
            ),
        )
        con.executemany(
            "INSERT INTO price_history VALUES(?,?,?,?,?,?,?,?,NULL)",
            (
                (1, "a", "a_sps", 2000, 2500, 1, "in_stock", "2026-09-01T12:00:00Z"),
                (2, "b", "b_sps", 2200, None, 0, "in_stock", "2026-09-02T12:00:00Z"),
            ),
        )
        con.executemany(
            "INSERT INTO scrape_runs VALUES(?,?,?,?,?)",
            (
                ("a-good", "a", "a_sps", "2026-09-08T10:00:00Z", "success"),
                ("a-rejected", "a", "a_sps", "2026-09-08T11:00:00Z", "rejected"),
                (
                    "b-good", "b", "b_sps",
                    "2026-09-06T06:00:00Z" if stale_b else "2026-09-08T09:00:00Z",
                    "success",
                ),
            ),
        )


def test_exporter_builds_hashed_business_and_consumer_marts_read_only(tmp_path: Path) -> None:
    database = tmp_path / "input.sqlite"
    output = tmp_path / "out"
    build_db(database)
    before = database.read_bytes()
    backend = MODULE.SQLiteBackend(database)
    try:
        manifest = MODULE.export_rpi_marts(
            backend,
            MODULE.parse_scope(("a=a_sps", "b=b_sps")),
            output,
            as_of_utc=AS_OF,
            freshness_window=timedelta(hours=24),
            require_products=True,
        )
    finally:
        backend.close()

    assert database.read_bytes() == before
    assert manifest["comparison_status"] == "COMPARABLE"
    assert manifest["safe_products"] == 1
    assert manifest["safe_offers"] == 2
    assert set(manifest["files_sha256"]) == {
        "business-mart.json",
        "business/dim_brand.csv",
        "business/dim_category.csv",
        "business/dim_location.csv",
        "business/dim_product.csv",
        "business/dim_retailer.csv",
        "business/fact_basket_cost.csv",
        "business/fact_current_comparison.csv",
        "business/fact_metric_coverage.csv",
        "consumer-mart.json",
    }
    consumer = json.loads((output / "consumer-mart.json").read_text())
    assert consumer["products"][0]["offers"][0]["current_price"] == "20.00"
    assert consumer["products"][0]["offers"][0]["reported_regular_price"] == "25.00"
    assert consumer["source_freshness"][0]["last_successful_run"] == "a-good"
    assert "a-rejected" not in json.dumps(consumer)


def test_exporter_labels_stale_source_and_suppresses_competitive_metrics(tmp_path: Path) -> None:
    database = tmp_path / "input.sqlite"
    output = tmp_path / "out"
    build_db(database, stale_b=True)
    backend = MODULE.SQLiteBackend(database)
    try:
        manifest = MODULE.export_rpi_marts(
            backend,
            MODULE.parse_scope(("a=a_sps", "b=b_sps")),
            output,
            as_of_utc=AS_OF,
            freshness_window=timedelta(hours=24),
        )
    finally:
        backend.close()

    assert manifest["comparison_status"] == "INSUFFICIENT_FRESH_COMPARISON"
    business = json.loads((output / "business-mart.json").read_text())
    assert all(row["pci"] is None for row in business["facts"]["fact_current_comparison"])
    assert any(row["freshness_status"] == "STALE" for row in business["source_freshness"])


def test_empty_safe_universe_still_writes_stable_csv_headers(tmp_path: Path) -> None:
    database = tmp_path / "input.sqlite"
    output = tmp_path / "out"
    build_db(database)
    with sqlite3.connect(database) as con:
        con.execute("UPDATE products SET ean='7501031311309' WHERE product_id=2")
    backend = MODULE.SQLiteBackend(database)
    try:
        manifest = MODULE.export_rpi_marts(
            backend,
            MODULE.parse_scope(("a=a_sps", "b=b_sps")),
            output,
            as_of_utc=AS_OF,
            freshness_window=timedelta(hours=24),
        )
    finally:
        backend.close()

    assert manifest["safe_products"] == 0
    assert json.loads((output / "consumer-mart.json").read_text())["products"] == []
    header = (output / "business" / "fact_current_comparison.csv").read_text().splitlines()[0]
    assert header.startswith("canonical_product_id,canonical_gtin,source_product_id")
