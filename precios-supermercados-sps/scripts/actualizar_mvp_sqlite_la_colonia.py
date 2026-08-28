#!/usr/bin/env python3
"""Crea y actualiza el SQLite MVP de La Colonia a partir de snapshots aceptados.

No consulta La Colonia ni Turso. Mantiene cinco tablas y abre un nuevo periodo
de ``price_history`` sólo cuando cambia precio, precio regular reportado,
promoción o disponibilidad para un producto + ubicación.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generar_mvp_sqlite_la_colonia import create_schema  # noqa: E402

SUPERMARKET_ID = "la_colonia"
LOCATIONS = {
    "la_colonia_sps": "San Pedro Sula",
    "la_colonia_tgu": "Tegucigalpa",
}
COMMERCIAL_FIELDS = (
    "current_price_minor",
    "reported_regular_price_minor",
    "is_promotion",
    "availability",
)
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


class SnapshotError(ValueError):
    pass


def _price_minor(value: object, *, required: bool) -> int | None:
    if value is None:
        if required:
            raise SnapshotError("snapshot_price_missing")
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise SnapshotError("snapshot_price_invalid")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise SnapshotError("snapshot_price_invalid") from exc
    if not amount.is_finite() or amount < 0:
        raise SnapshotError("snapshot_price_invalid")
    minor = amount * 100
    if minor != minor.to_integral_value():
        raise SnapshotError("snapshot_price_precision_invalid")
    return int(minor)


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SnapshotError("snapshot_observed_at_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SnapshotError("snapshot_observed_at_invalid") from exc
    if parsed.utcoffset() is None:
        raise SnapshotError("snapshot_observed_at_invalid")
    return parsed


def validate_snapshot_bytes(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot_json_invalid") from exc
    if not isinstance(data, dict):
        raise SnapshotError("snapshot_json_invalid")

    required_metadata = {
        "result": "success",
        "supermarket_id": SUPERMARKET_ID,
        "catalog_complete": True,
        "validation_passed": True,
        "location_verified_same_run": True,
    }
    for key, expected in required_metadata.items():
        if data.get(key) != expected:
            raise SnapshotError(f"snapshot_metadata_invalid:{key}")

    location_id = data.get("location_id")
    if location_id not in LOCATIONS:
        raise SnapshotError("snapshot_location_invalid")
    if data.get("city") != LOCATIONS[location_id]:
        raise SnapshotError("snapshot_city_invalid")

    observed_at = data.get("observed_at_utc")
    _parse_utc(observed_at)

    products = data.get("products")
    if not isinstance(products, list) or not products:
        raise SnapshotError("snapshot_products_invalid")
    if data.get("skus_extracted") != len(products):
        raise SnapshotError("snapshot_sku_count_mismatch")
    if data.get("skus_with_price") != len(products):
        raise SnapshotError("snapshot_priced_sku_count_mismatch")

    identities: set[tuple[str, str]] = set()
    source_products: set[str] = set()
    for item in products:
        if not isinstance(item, dict) or set(item) != PRODUCT_KEYS:
            raise SnapshotError("snapshot_product_schema_invalid")
        key_type = item["source_key_type"]
        source_key = item["source_key"]
        source_name = item["source_name"]
        if (
            not isinstance(key_type, str)
            or not key_type
            or not isinstance(source_key, str)
            or not source_key
            or not isinstance(source_name, str)
            or not source_name
        ):
            raise SnapshotError("snapshot_product_identity_invalid")
        identity = (key_type, source_key)
        if identity in identities:
            raise SnapshotError("snapshot_product_identity_duplicate")
        identities.add(identity)

        source_product_id = item["product_id"]
        source_item_id = item["item_id"]
        if source_product_id is None or source_item_id is None:
            raise SnapshotError("snapshot_source_id_missing")
        source_products.add(str(source_product_id))

        _price_minor(item["current_price"], required=True)
        _price_minor(item["reported_regular_price"], required=False)
        if type(item["is_promotion"]) is not bool:
            raise SnapshotError("snapshot_promotion_invalid")
        if item["availability"] not in {"in_stock", "out_of_stock", "unknown"}:
            raise SnapshotError("snapshot_availability_invalid")

    reported_products = data.get("catalog_products_reported")
    unique_products = data.get("unique_products_extracted")
    if (
        isinstance(reported_products, bool)
        or not isinstance(reported_products, int)
        or reported_products <= 0
        or unique_products != reported_products
        or len(source_products) != reported_products
    ):
        raise SnapshotError("snapshot_product_count_mismatch")
    return data


def initialize_database(path: Path) -> None:
    if path.exists():
        raise SnapshotError(f"database_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        create_schema(con)
        con.execute(
            "INSERT INTO supermarkets (supermarket_id, name, country_code) VALUES (?, ?, ?)",
            (SUPERMARKET_ID, "La Colonia", "HN"),
        )
        con.executemany(
            """
            INSERT INTO locations (location_id, supermarket_id, city_name, country_code)
            VALUES (?, ?, ?, ?)
            """,
            (
                ("la_colonia_sps", SUPERMARKET_ID, LOCATIONS["la_colonia_sps"], "HN"),
                ("la_colonia_tgu", SUPERMARKET_ID, LOCATIONS["la_colonia_tgu"], "HN"),
            ),
        )
        con.commit()
    except Exception:
        con.rollback()
        con.close()
        if path.exists():
            path.unlink()
        raise
    finally:
        try:
            con.close()
        except Exception:
            pass


def _product_values(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        SUPERMARKET_ID,
        str(item["source_key_type"]),
        str(item["source_key"]),
        str(item["product_id"]),
        str(item["item_id"]),
        item["reference"],
        item["ean"],
        item["source_name"],
        item["brand"],
        item["presentation"],
        item["category"],
    )


def _commercial_state(item: Mapping[str, Any]) -> tuple[int, int | None, int, str]:
    return (
        _price_minor(item["current_price"], required=True),
        _price_minor(item["reported_regular_price"], required=False),
        int(item["is_promotion"]),
        str(item["availability"]),
    )


def apply_snapshot(
    database: Path,
    raw: bytes,
    *,
    run_id: str,
    source_artifact_id: str | None = None,
) -> dict[str, Any]:
    snapshot = validate_snapshot_bytes(raw)
    if not run_id.strip():
        raise SnapshotError("run_id_missing")
    if not database.exists():
        raise SnapshotError(f"database_missing:{database}")

    digest = hashlib.sha256(raw).hexdigest()
    location_id = str(snapshot["location_id"])
    observed_at = str(snapshot["observed_at_utc"])
    observed_dt = _parse_utc(observed_at)
    products = list(snapshot["products"])

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    summary: dict[str, Any] = {
        "run_id": run_id,
        "location_id": location_id,
        "source_json_sha256": digest,
        "replayed": False,
        "products_inserted": 0,
        "products_updated": 0,
        "history_opened": 0,
        "history_closed": 0,
        "history_unchanged": 0,
    }
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("BEGIN IMMEDIATE")

        existing_run = con.execute(
            """
            SELECT location_id, run_status, source_json_sha256
            FROM scrape_runs
            WHERE scrape_run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if existing_run is not None:
            if (
                existing_run["location_id"] == location_id
                and existing_run["run_status"] == "success"
                and existing_run["source_json_sha256"] == digest
            ):
                con.rollback()
                summary["replayed"] = True
                return summary
            raise SnapshotError("run_id_conflict")

        con.execute(
            """
            INSERT INTO scrape_runs (
                scrape_run_id, supermarket_id, location_id, observed_at_utc,
                run_status, sku_count, catalog_product_count,
                source_artifact_id, source_json_sha256, error_reason
            ) VALUES (?, ?, ?, ?, 'success', ?, ?, ?, ?, NULL)
            """,
            (
                run_id,
                SUPERMARKET_ID,
                location_id,
                observed_at,
                len(products),
                int(snapshot["catalog_products_reported"]),
                source_artifact_id,
                digest,
            ),
        )

        for item in products:
            values = _product_values(item)
            product = con.execute(
                """
                SELECT product_id
                FROM products
                WHERE supermarket_id = ?
                  AND source_key_type = ?
                  AND source_key = ?
                """,
                values[:3],
            ).fetchone()
            if product is None:
                cursor = con.execute(
                    """
                    INSERT INTO products (
                        supermarket_id, source_key_type, source_key,
                        source_catalog_product_id, source_item_id,
                        reference, ean, name, brand, presentation, category
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                product_id = int(cursor.lastrowid)
                summary["products_inserted"] += 1
            else:
                product_id = int(product["product_id"])
                con.execute(
                    """
                    UPDATE products
                    SET source_catalog_product_id = ?,
                        source_item_id = ?,
                        reference = ?,
                        ean = ?,
                        name = ?,
                        brand = ?,
                        presentation = ?,
                        category = ?
                    WHERE product_id = ?
                    """,
                    (*values[3:], product_id),
                )
                summary["products_updated"] += 1

            state = _commercial_state(item)
            current = con.execute(
                """
                SELECT current_price_minor, reported_regular_price_minor,
                       is_promotion, availability, valid_from_utc
                FROM price_history
                WHERE product_id = ?
                  AND location_id = ?
                  AND valid_to_utc IS NULL
                """,
                (product_id, location_id),
            ).fetchone()
            if current is None:
                con.execute(
                    """
                    INSERT INTO price_history (
                        product_id, supermarket_id, location_id,
                        current_price_minor, reported_regular_price_minor,
                        is_promotion, availability, currency,
                        valid_from_utc, valid_to_utc, scrape_run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'HNL', ?, NULL, ?)
                    """,
                    (
                        product_id,
                        SUPERMARKET_ID,
                        location_id,
                        *state,
                        observed_at,
                        run_id,
                    ),
                )
                summary["history_opened"] += 1
                continue

            previous_state = tuple(current[field] for field in COMMERCIAL_FIELDS)
            if previous_state == state:
                summary["history_unchanged"] += 1
                continue

            if observed_dt <= _parse_utc(current["valid_from_utc"]):
                raise SnapshotError("snapshot_out_of_order")
            con.execute(
                """
                UPDATE price_history
                SET valid_to_utc = ?
                WHERE product_id = ?
                  AND location_id = ?
                  AND valid_to_utc IS NULL
                """,
                (observed_at, product_id, location_id),
            )
            con.execute(
                """
                INSERT INTO price_history (
                    product_id, supermarket_id, location_id,
                    current_price_minor, reported_regular_price_minor,
                    is_promotion, availability, currency,
                    valid_from_utc, valid_to_utc, scrape_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'HNL', ?, NULL, ?)
                """,
                (
                    product_id,
                    SUPERMARKET_ID,
                    location_id,
                    *state,
                    observed_at,
                    run_id,
                ),
            )
            summary["history_closed"] += 1
            summary["history_opened"] += 1

        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise SnapshotError("database_foreign_key_check_failed")
        duplicate_open = con.execute(
            """
            SELECT 1
            FROM price_history
            WHERE valid_to_utc IS NULL
            GROUP BY product_id, location_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        ).fetchone()
        if duplicate_open is not None:
            raise SnapshotError("database_multiple_open_periods")
        con.commit()
        return summary
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def validate_database(database: Path) -> dict[str, Any]:
    con = sqlite3.connect(database)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SnapshotError(f"database_integrity_failed:{integrity}")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise SnapshotError("database_foreign_key_check_failed")
        duplicate_open = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT product_id, location_id
                FROM price_history
                WHERE valid_to_utc IS NULL
                GROUP BY product_id, location_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if duplicate_open:
            raise SnapshotError("database_multiple_open_periods")
        counts = {
            table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "supermarkets",
                "locations",
                "products",
                "price_history",
                "scrape_runs",
            )
        }
        open_history = con.execute(
            "SELECT COUNT(*) FROM price_history WHERE valid_to_utc IS NULL"
        ).fetchone()[0]
        by_location = {}
        for location_id in LOCATIONS:
            rows = con.execute(
                """
                SELECT availability, COUNT(*)
                FROM price_history
                WHERE location_id = ? AND valid_to_utc IS NULL
                GROUP BY availability
                """,
                (location_id,),
            ).fetchall()
            by_location[location_id] = {
                availability: count for availability, count in rows
            }
        return {
            **counts,
            "open_price_history": open_history,
            "current_availability": by_location,
            "sqlite_integrity": integrity,
        }
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("snapshot_json", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-artifact-id")
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()

    raw = args.snapshot_json.read_bytes()
    validate_snapshot_bytes(raw)
    created = False
    if args.create:
        initialize_database(args.database)
        created = True
    try:
        apply_summary = apply_snapshot(
            args.database,
            raw,
            run_id=args.run_id,
            source_artifact_id=args.source_artifact_id,
        )
        result = {
            "apply": apply_summary,
            "database": validate_database(args.database),
            "database_path": str(args.database),
        }
    except Exception:
        if created and args.database.exists():
            args.database.unlink()
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
