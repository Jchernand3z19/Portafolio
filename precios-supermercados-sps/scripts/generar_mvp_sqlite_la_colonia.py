#!/usr/bin/env python3
"""Genera el SQLite mínimo del MVP de La Colonia SPS desde el snapshot aprobado.

No consulta La Colonia, no usa credenciales y no conecta con Turso. El archivo
resultante se puede importar con la opción nativa "Upload SQLite File" de Turso.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED_JSON_SHA256 = "2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50"
EXPECTED_SUPERMARKET_ID = "la_colonia"
EXPECTED_LOCATION_ID = "la_colonia_sps"
EXPECTED_SKUS = 9439
EXPECTED_PRODUCTS = 9437
EXPECTED_RUN_ID = "32922877781"
EXPECTED_ARTIFACT_ID = "9590684834"

PRODUCT_KEYS = {
    "availability",
    "brand",
    "category",
    "current_price",
    "ean",
    "is_promotion",
    "item_id",
    "presentation",
    "product_id",
    "reference",
    "reported_regular_price",
    "source_key",
    "source_key_type",
    "source_name",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def price_minor(value: object, *, required: bool) -> int | None:
    if value is None:
        if required:
            fail("precio requerido ausente")
        return None
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        fail("precio inválido")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        fail("precio inválido")
    if not amount.is_finite() or amount < 0:
        fail("precio inválido")
    minor = amount * 100
    if minor != minor.to_integral_value():
        fail("precio con más de dos decimales")
    return int(minor)


def load_snapshot(path: Path) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_JSON_SHA256:
        fail("snapshot_json_digest_mismatch")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fail("snapshot_json_invalid")

    expected = {
        "result": "success",
        "supermarket_id": EXPECTED_SUPERMARKET_ID,
        "location_id": EXPECTED_LOCATION_ID,
        "catalog_complete": True,
        "validation_passed": True,
        "location_verified_same_run": True,
        "catalog_products_reported": EXPECTED_PRODUCTS,
        "unique_products_extracted": EXPECTED_PRODUCTS,
        "skus_extracted": EXPECTED_SKUS,
        "skus_with_price": EXPECTED_SKUS,
        "catalog_product_coverage": 1.0,
        "extraction_enabled": False,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            fail(f"snapshot_metadata_mismatch:{key}")

    observed_at = data.get("observed_at_utc")
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        fail("snapshot_observed_at_invalid")

    products = data.get("products")
    if not isinstance(products, list) or len(products) != EXPECTED_SKUS:
        fail("snapshot_offer_count_mismatch")

    identities: set[tuple[str, str]] = set()
    product_ids: set[str] = set()
    for row in products:
        if not isinstance(row, dict) or set(row) != PRODUCT_KEYS:
            fail("snapshot_product_schema_mismatch")
        key_type = row["source_key_type"]
        source_key = row["source_key"]
        if (
            not isinstance(key_type, str)
            or not key_type
            or not isinstance(source_key, str)
            or not source_key
        ):
            fail("snapshot_source_identity_invalid")
        identity = (key_type, source_key)
        if identity in identities:
            fail("snapshot_source_identity_duplicate")
        identities.add(identity)
        product_ids.add(str(row["product_id"]))
        price_minor(row["current_price"], required=True)
        price_minor(row["reported_regular_price"], required=False)
        if type(row["is_promotion"]) is not bool:
            fail("snapshot_promotion_invalid")
        if row["availability"] not in {"in_stock", "unknown"}:
            fail("snapshot_availability_invalid")

    if len(product_ids) != EXPECTED_PRODUCTS:
        fail("snapshot_product_identity_count_mismatch")
    return data


def create_database(snapshot: dict, output: Path) -> dict[str, int | str]:
    if output.exists():
        fail(f"output_exists:{output}")

    con = sqlite3.connect(output)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(
            """
            CREATE TABLE scrape_runs (
                scrape_run_id TEXT PRIMARY KEY,
                supermarket_id TEXT NOT NULL,
                location_id TEXT NOT NULL,
                observed_at_utc TEXT NOT NULL,
                run_status TEXT NOT NULL CHECK (run_status = 'success'),
                sku_count INTEGER NOT NULL CHECK (sku_count > 0),
                catalog_product_count INTEGER NOT NULL CHECK (catalog_product_count > 0),
                source_artifact_id TEXT NOT NULL,
                source_json_sha256 TEXT NOT NULL
            );

            CREATE TABLE offer_history (
                supermarket_id TEXT NOT NULL,
                location_id TEXT NOT NULL,
                source_key_type TEXT NOT NULL,
                source_key TEXT NOT NULL,
                source_catalog_product_id TEXT NOT NULL,
                source_item_id TEXT NOT NULL,
                reference TEXT,
                ean TEXT,
                source_name TEXT NOT NULL,
                brand TEXT,
                presentation TEXT,
                category TEXT,
                current_price_minor INTEGER NOT NULL CHECK (current_price_minor >= 0),
                reported_regular_price_minor INTEGER CHECK (reported_regular_price_minor >= 0),
                is_promotion INTEGER NOT NULL CHECK (is_promotion IN (0, 1)),
                availability TEXT NOT NULL CHECK (availability IN ('in_stock', 'unknown')),
                currency TEXT NOT NULL CHECK (currency = 'HNL'),
                valid_from_utc TEXT NOT NULL,
                valid_to_utc TEXT,
                scrape_run_id TEXT NOT NULL,
                PRIMARY KEY (
                    supermarket_id,
                    location_id,
                    source_key_type,
                    source_key,
                    valid_from_utc
                ),
                FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(scrape_run_id)
            );
            """
        )

        observed_at = snapshot["observed_at_utc"]
        con.execute(
            """
            INSERT INTO scrape_runs (
                scrape_run_id, supermarket_id, location_id, observed_at_utc,
                run_status, sku_count, catalog_product_count,
                source_artifact_id, source_json_sha256
            ) VALUES (?, ?, ?, ?, 'success', ?, ?, ?, ?)
            """,
            (
                EXPECTED_RUN_ID,
                EXPECTED_SUPERMARKET_ID,
                EXPECTED_LOCATION_ID,
                observed_at,
                EXPECTED_SKUS,
                EXPECTED_PRODUCTS,
                EXPECTED_ARTIFACT_ID,
                EXPECTED_JSON_SHA256,
            ),
        )

        rows = []
        for item in snapshot["products"]:
            rows.append(
                (
                    EXPECTED_SUPERMARKET_ID,
                    EXPECTED_LOCATION_ID,
                    item["source_key_type"],
                    item["source_key"],
                    str(item["product_id"]),
                    str(item["item_id"]),
                    item["reference"],
                    item["ean"],
                    item["source_name"],
                    item["brand"],
                    item["presentation"],
                    item["category"],
                    price_minor(item["current_price"], required=True),
                    price_minor(item["reported_regular_price"], required=False),
                    int(item["is_promotion"]),
                    item["availability"],
                    "HNL",
                    observed_at,
                    None,
                    EXPECTED_RUN_ID,
                )
            )

        con.executemany(
            """
            INSERT INTO offer_history (
                supermarket_id, location_id, source_key_type, source_key,
                source_catalog_product_id, source_item_id, reference, ean,
                source_name, brand, presentation, category,
                current_price_minor, reported_regular_price_minor,
                is_promotion, availability, currency,
                valid_from_utc, valid_to_utc, scrape_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.commit()

        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            fail(f"sqlite_integrity_failed:{integrity}")
        offer_count = con.execute("SELECT COUNT(*) FROM offer_history").fetchone()[0]
        run_count = con.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
        open_count = con.execute(
            "SELECT COUNT(*) FROM offer_history WHERE valid_to_utc IS NULL"
        ).fetchone()[0]
        priced_count = con.execute(
            "SELECT COUNT(*) FROM offer_history WHERE current_price_minor IS NOT NULL"
        ).fetchone()[0]
        unknown_count = con.execute(
            "SELECT COUNT(*) FROM offer_history WHERE availability = 'unknown'"
        ).fetchone()[0]
        promo_count = con.execute(
            "SELECT COUNT(*) FROM offer_history WHERE is_promotion = 1"
        ).fetchone()[0]

        if (offer_count, run_count, open_count, priced_count, unknown_count) != (
            9439,
            1,
            9439,
            9439,
            2358,
        ):
            fail("sqlite_reconciliation_failed")

        return {
            "offers": offer_count,
            "runs": run_count,
            "open_offers": open_count,
            "priced_offers": priced_count,
            "availability_unknown": unknown_count,
            "promotions": promo_count,
            "sqlite_integrity": integrity,
        }
    except Exception:
        con.rollback()
        con.close()
        if output.exists():
            output.unlink()
        raise
    finally:
        try:
            con.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot_json", type=Path)
    parser.add_argument("output_db", type=Path)
    args = parser.parse_args()

    snapshot = load_snapshot(args.snapshot_json)
    summary = create_database(snapshot, args.output_db)
    summary["output"] = str(args.output_db)
    summary["sha256"] = hashlib.sha256(args.output_db.read_bytes()).hexdigest()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
