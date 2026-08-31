#!/usr/bin/env python3
"""Aplica snapshots completos de La Colonia al SQLite MVP de cinco tablas."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generar_mvp_sqlite_la_colonia import create_schema  # noqa: E402

SUPERMARKET_ID = "la_colonia"
LOCATIONS = {"la_colonia_sps": "San Pedro Sula", "la_colonia_tgu": "Tegucigalpa"}
COLONIAL_LOCATIONS = {"colonial_sps": "San Pedro Sula"}
WALMART_LOCATIONS = {"walmart_sps": "San Pedro Sula", "walmart_tgu_ffaa": "Tegucigalpa", "walmart_tgu_el_sauce": "Tegucigalpa"}
WALMART_SELLERS = {"walmart_sps": "walmarthnwm947", "walmart_tgu_ffaa": "walmarthnwm4041", "walmart_tgu_el_sauce": "walmarthnwm4410"}
STATE_COLUMNS = ("current_price_minor", "reported_regular_price_minor", "is_promotion", "availability")
PRODUCT_KEYS = {
    "availability", "brand", "category", "current_price", "ean", "is_promotion",
    "item_id", "presentation", "product_id", "reference", "reported_regular_price",
    "source_key", "source_key_type", "source_name",
}


class SnapshotError(ValueError):
    pass


def _minor(value: object, required: bool = False) -> int | None:
    if value is None:
        if required:
            raise SnapshotError("snapshot_price_missing")
        return None
    if not isinstance(value, str) or value != value.strip() or not value:
        raise SnapshotError("snapshot_price_invalid")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise SnapshotError("snapshot_price_invalid") from exc
    cents = amount * 100
    if not amount.is_finite() or amount < 0 or cents != cents.to_integral_value():
        raise SnapshotError("snapshot_price_invalid")
    return int(cents)


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SnapshotError("snapshot_observed_at_invalid")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SnapshotError("snapshot_observed_at_invalid") from exc


def validate_snapshot_bytes(raw: bytes, *, supermarket_id: str = SUPERMARKET_ID) -> dict[str, Any]:
    if supermarket_id not in (SUPERMARKET_ID, "colonial", "walmart"):
        raise SnapshotError("snapshot_supermarket_invalid")
    locations = {SUPERMARKET_ID: LOCATIONS, "colonial": COLONIAL_LOCATIONS, "walmart": WALMART_LOCATIONS}[supermarket_id]
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot_json_invalid") from exc
    expected = {
        "result": "success", "supermarket_id": supermarket_id,
        "catalog_complete": True, "validation_passed": True,
        "location_verified_same_run": True,
    }
    if not isinstance(data, dict):
        raise SnapshotError("snapshot_json_invalid")
    for key, value in expected.items():
        if data.get(key) != value:
            raise SnapshotError(f"snapshot_metadata_invalid:{key}")
    location_id = data.get("location_id")
    if location_id not in locations or data.get("city") != locations[location_id]:
        raise SnapshotError("snapshot_location_invalid")
    _utc(data.get("observed_at_utc"))

    rows = data.get("products")
    if not isinstance(rows, list) or not rows:
        raise SnapshotError("snapshot_products_invalid")
    priced_count = sum(isinstance(row, dict) and row.get("current_price") is not None for row in rows)
    if (data.get("skus_extracted") != len(rows) or data.get("skus_with_price") != priced_count
            or (supermarket_id != "walmart" and priced_count != len(rows))):
        raise SnapshotError("snapshot_sku_count_mismatch")

    identities, source_products = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != PRODUCT_KEYS:
            raise SnapshotError("snapshot_product_schema_invalid")
        identity = (row["source_key_type"], row["source_key"])
        if not all(isinstance(v, str) and v for v in (*identity, row["source_name"])):
            raise SnapshotError("snapshot_product_identity_invalid")
        if identity in identities:
            raise SnapshotError("snapshot_product_identity_duplicate")
        identities.add(identity)
        if row["product_id"] is None or row["item_id"] is None:
            raise SnapshotError("snapshot_source_id_missing")
        source_products.add(str(row["product_id"]))
        _minor(row["current_price"], supermarket_id != "walmart")
        _minor(row["reported_regular_price"])
        if type(row["is_promotion"]) is not bool and not (supermarket_id == "walmart" and row["is_promotion"] is None):
            raise SnapshotError("snapshot_promotion_invalid")
        if row["availability"] not in {"in_stock", "out_of_stock", "unknown"}:
            raise SnapshotError("snapshot_availability_invalid")

    reported = data.get("catalog_products_reported")
    if (
        not isinstance(reported, int) or isinstance(reported, bool) or reported <= 0
        or data.get("unique_products_extracted") != reported
        or len(source_products) != reported
    ):
        raise SnapshotError("snapshot_product_count_mismatch")
    if supermarket_id == "colonial":
        if (any(data.get(k) is not True for k in ("catalog_complete", "validation_passed", "location_verified_same_run"))
                or data.get("currency") != "HNL"
                or data.get("scope") != "public_ecommerce_sps_not_physical_branch_inventory"
                or any(type(data.get(k)) is not int or data[k] != reported for k in ("membership_count", "html_cards_count"))):
            raise SnapshotError("colonial_evidence_invalid")
        for row in rows:
            if (row["source_key_type"] != "item_id" or row["source_key"] != row["item_id"]
                    or any(not isinstance(row[k], str) or not row[k].isdigit() or int(row[k]) <= 0 for k in ("product_id", "item_id"))):
                raise SnapshotError("colonial_identity_invalid")
        counts = {state: sum(row["availability"] == state for row in rows)
                  for state in {row["availability"] for row in rows}}
        if data.get("availability_counts") != counts:
            raise SnapshotError("colonial_availability_counts_invalid")
    if supermarket_id == "walmart":
        import base64
        import math
        seller = WALMART_SELLERS[location_id]
        if (any(data.get(k) is not True for k in ("catalog_complete", "validation_passed", "location_verified_same_run"))
                or any(type(data.get(k)) is not int for k in ("skus_extracted", "skus_with_price", "catalog_products_reported", "unique_products_extracted", "membership_count"))
                or data.get("currency") != "HNL" or data.get("seller_id") != seller
                or data.get("region_id") != base64.b64encode(("SW#" + seller).encode()).decode()
                or data.get("sales_channel") != "1"
                or data.get("scope") != "public_ecommerce_selected_store_not_universal_city_price"
                or type(data.get("membership_count")) is not int or data["membership_count"] != reported
                or data.get("membership_sha256") != hashlib.sha256("\n".join(sorted(source_products)).encode()).hexdigest()):
            raise SnapshotError("walmart_evidence_invalid")
        details = data.get("source_details")
        if not isinstance(details, dict) or set(details) != {r["source_key"] for r in rows}:
            raise SnapshotError("walmart_source_details_invalid")
        for row in rows:
            if (row["source_key_type"] != "item_id" or row["source_key"] != row["item_id"]
                    or any(not isinstance(row[k], str) or not row[k].isdigit() or int(row[k]) <= 0 for k in ("product_id", "item_id"))
                    or any(row[k] is not None and not isinstance(row[k], str) for k in ("reference", "ean", "brand", "presentation", "category"))):
                raise SnapshotError("walmart_identity_invalid")
            detail = details[row["source_key"]]
            if not isinstance(detail, dict):
                raise SnapshotError("walmart_source_details_invalid")
            quantity = detail.get("available_quantity_signal")
            if quantity is not None and (type(quantity) not in {int, float} or not math.isfinite(quantity) or quantity < 0):
                raise SnapshotError("walmart_availability_evidence_invalid")
            availability = "unknown" if quantity is None else "in_stock" if quantity > 0 else "out_of_stock"
            if row["availability"] != availability:
                raise SnapshotError("walmart_availability_evidence_invalid")
            if row["current_price"] is None:
                if (row["availability"] != "out_of_stock" or row["reported_regular_price"] is not None
                        or row["is_promotion"] is not None or detail.get("price_status") != "unavailable_zero_offer"
                        or type(detail.get("available_quantity_signal")) not in {int, float} or detail.get("available_quantity_signal") != 0
                        or detail.get("source_price") != "0.00" or detail.get("source_list_price") != "0.00"):
                    raise SnapshotError("walmart_unpriced_offer_invalid")
            elif (_minor(row["current_price"], True) <= 0 or row["reported_regular_price"] is None
                    or _minor(row["reported_regular_price"], True) < _minor(row["current_price"], True)
                    or row["is_promotion"] is not (_minor(row["reported_regular_price"], True) > _minor(row["current_price"], True))
                    or detail.get("source_price") != row["current_price"]
                    or detail.get("source_list_price") != row["reported_regular_price"]
                    or detail.get("price_status") != "observed"):
                raise SnapshotError("walmart_price_evidence_invalid")
        counts = {v: sum(r["availability"] == v for r in rows) for v in {r["availability"] for r in rows}}
        if data.get("availability_counts") != counts:
            raise SnapshotError("walmart_availability_counts_invalid")
    return data


def initialize_database(path: Path) -> None:
    if path.exists():
        raise SnapshotError(f"database_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        create_schema(con)
        con.execute("INSERT INTO supermarkets VALUES (?, ?, ?)", (SUPERMARKET_ID, "La Colonia", "HN"))
        con.executemany(
            "INSERT INTO locations VALUES (?, ?, ?, ?)",
            [(key, SUPERMARKET_ID, city, "HN") for key, city in LOCATIONS.items()],
        )
        con.commit()
    except Exception:
        con.close()
        path.unlink(missing_ok=True)
        raise
    con.close()


def _upsert_product(con: sqlite3.Connection, row: dict[str, Any]) -> tuple[int, bool]:
    identity = (SUPERMARKET_ID, str(row["source_key_type"]), str(row["source_key"]))
    current = con.execute(
        "SELECT product_id FROM products WHERE supermarket_id=? AND source_key_type=? AND source_key=?",
        identity,
    ).fetchone()
    values = (
        str(row["product_id"]), str(row["item_id"]), row["reference"], row["ean"],
        row["source_name"], row["brand"], row["presentation"], row["category"],
    )
    if current is None:
        cursor = con.execute(
            """INSERT INTO products (
                supermarket_id, source_key_type, source_key, source_catalog_product_id,
                source_item_id, reference, ean, name, brand, presentation, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*identity, *values),
        )
        return int(cursor.lastrowid), True
    product_id = int(current["product_id"])
    con.execute(
        """UPDATE products SET source_catalog_product_id=?, source_item_id=?, reference=?,
        ean=?, name=?, brand=?, presentation=?, category=? WHERE product_id=?""",
        (*values, product_id),
    )
    return product_id, False


def _state(row: dict[str, Any]) -> tuple[int, int | None, int, str]:
    return (_minor(row["current_price"], True), _minor(row["reported_regular_price"]),
            int(row["is_promotion"]), str(row["availability"]))


def _apply_state(
    con: sqlite3.Connection, product_id: int, location_id: str,
    observed_at: str, run_id: str, row: dict[str, Any],
) -> tuple[int, int, int]:
    state = _state(row)
    current = con.execute(
        """SELECT current_price_minor, reported_regular_price_minor, is_promotion,
        availability, valid_from_utc FROM price_history
        WHERE product_id=? AND location_id=? AND valid_to_utc IS NULL""",
        (product_id, location_id),
    ).fetchone()
    if current is not None and tuple(current[key] for key in STATE_COLUMNS) == state:
        return 0, 0, 1
    if current is not None:
        if _utc(observed_at) <= _utc(current["valid_from_utc"]):
            raise SnapshotError("snapshot_out_of_order")
        con.execute(
            "UPDATE price_history SET valid_to_utc=? WHERE product_id=? AND location_id=? AND valid_to_utc IS NULL",
            (observed_at, product_id, location_id),
        )
    con.execute(
        """INSERT INTO price_history (
            product_id, supermarket_id, location_id, current_price_minor,
            reported_regular_price_minor, is_promotion, availability, currency,
            valid_from_utc, valid_to_utc, scrape_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'HNL', ?, NULL, ?)""",
        (product_id, SUPERMARKET_ID, location_id, *state, observed_at, run_id),
    )
    return 1, int(current is not None), 0


def apply_snapshot(
    database: Path, raw: bytes, *, run_id: str, source_artifact_id: str | None = None,
) -> dict[str, Any]:
    snapshot = validate_snapshot_bytes(raw)
    if not run_id.strip():
        raise SnapshotError("run_id_missing")
    if not database.exists():
        raise SnapshotError(f"database_missing:{database}")
    digest = hashlib.sha256(raw).hexdigest()
    location_id, observed_at = snapshot["location_id"], snapshot["observed_at_utc"]
    summary = {
        "run_id": run_id, "location_id": location_id, "source_json_sha256": digest,
        "replayed": False, "products_inserted": 0, "products_updated": 0,
        "history_opened": 0, "history_closed": 0, "history_unchanged": 0,
    }

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        previous_run = con.execute(
            "SELECT location_id, run_status, source_json_sha256 FROM scrape_runs WHERE scrape_run_id=?",
            (run_id,),
        ).fetchone()
        if previous_run is not None:
            if (
                previous_run["location_id"] == location_id
                and previous_run["run_status"] == "success"
                and previous_run["source_json_sha256"] == digest
            ):
                con.rollback()
                summary["replayed"] = True
                return summary
            raise SnapshotError("run_id_conflict")

        rows = snapshot["products"]
        con.execute(
            """INSERT INTO scrape_runs (
                scrape_run_id, supermarket_id, location_id, observed_at_utc, run_status,
                sku_count, catalog_product_count, source_artifact_id, source_json_sha256, error_reason
            ) VALUES (?, ?, ?, ?, 'success', ?, ?, ?, ?, NULL)""",
            (run_id, SUPERMARKET_ID, location_id, observed_at, len(rows),
             snapshot["catalog_products_reported"], source_artifact_id, digest),
        )
        for row in rows:
            product_id, inserted = _upsert_product(con, row)
            summary["products_inserted" if inserted else "products_updated"] += 1
            opened, closed, unchanged = _apply_state(
                con, product_id, location_id, observed_at, run_id, row
            )
            summary["history_opened"] += opened
            summary["history_closed"] += closed
            summary["history_unchanged"] += unchanged
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise SnapshotError("database_foreign_key_check_failed")
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
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
        duplicate_open = con.execute(
            """SELECT COUNT(*) FROM (
                SELECT product_id, location_id FROM price_history WHERE valid_to_utc IS NULL
                GROUP BY product_id, location_id HAVING COUNT(*)>1
            )"""
        ).fetchone()[0]
        if integrity != "ok" or foreign_keys or duplicate_open:
            raise SnapshotError("database_integrity_failed")
        result = {
            table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("supermarkets", "locations", "products", "price_history", "scrape_runs")
        }
        result["open_price_history"] = con.execute(
            "SELECT COUNT(*) FROM price_history WHERE valid_to_utc IS NULL"
        ).fetchone()[0]
        result["current_availability"] = {
            location: dict(con.execute(
                """SELECT availability, COUNT(*) FROM price_history
                WHERE location_id=? AND valid_to_utc IS NULL GROUP BY availability""",
                (location,),
            ).fetchall())
            for location in LOCATIONS
        }
        result["sqlite_integrity"] = integrity
        return result
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
        result = {
            "apply": apply_snapshot(
                args.database, raw, run_id=args.run_id,
                source_artifact_id=args.source_artifact_id,
            ),
            "database": validate_database(args.database),
            "database_path": str(args.database),
        }
    except Exception:
        if created:
            args.database.unlink(missing_ok=True)
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
