#!/usr/bin/env python3
"""Crea o recalcula perfiles derivados de homologación desde `products`.

El modo SQLite es deliberadamente offline: no consulta supermercados ni modifica
`products`, `price_history` o `scrape_runs`.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from precios_supermercados.product_homologation_persistence import (
    TABLE_NAME,
    ProductHomologationPersistenceError,
    build_homologation_rows,
    persist_sqlite_rows,
    records_from_product_rows,
)


def _count(con: sqlite3.Connection, table: str) -> int:
    row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    if row is None or len(row) != 1:
        raise ProductHomologationPersistenceError(f"count_failed:{table}")
    return int(row[0])


def backfill_sqlite(path: Path, *, updated_at_utc: str | None = None) -> dict[str, object]:
    if not path.is_file():
        raise ProductHomologationPersistenceError("database_missing")

    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        before = {
            "products": _count(con, "products"),
            "price_history": _count(con, "price_history"),
            "scrape_runs": _count(con, "scrape_runs") if _table_exists(con, "scrape_runs") else 0,
        }
        product_rows = con.execute(
            "SELECT product_id,supermarket_id,name,brand,presentation,category,ean "
            "FROM products ORDER BY product_id"
        ).fetchall()
        records = records_from_product_rows(product_rows)
        if len(records) != before["products"]:
            raise ProductHomologationPersistenceError("source_product_count_mismatch")
        derived = build_homologation_rows(records, updated_at_utc=updated_at_utc)

        try:
            result = persist_sqlite_rows(con, derived)
            after = {
                "products": _count(con, "products"),
                "price_history": _count(con, "price_history"),
                "scrape_runs": _count(con, "scrape_runs") if _table_exists(con, "scrape_runs") else 0,
                "profiles": _count(con, TABLE_NAME),
            }
            if after["products"] != before["products"]:
                raise ProductHomologationPersistenceError("products_mutated")
            if after["price_history"] != before["price_history"]:
                raise ProductHomologationPersistenceError("price_history_mutated")
            if after["scrape_runs"] != before["scrape_runs"]:
                raise ProductHomologationPersistenceError("scrape_runs_mutated")
            if after["profiles"] != before["products"]:
                raise ProductHomologationPersistenceError("profile_coverage_incomplete")
            if con.execute("PRAGMA foreign_key_check").fetchall():
                raise ProductHomologationPersistenceError("foreign_key_check_failed")
            integrity = con.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                raise ProductHomologationPersistenceError("integrity_check_failed")
            con.commit()
        except Exception:
            con.rollback()
            raise

        statuses = {
            str(status): int(count)
            for status, count in con.execute(
                f"SELECT comparison_status,COUNT(*) FROM {TABLE_NAME} GROUP BY comparison_status"
            ).fetchall()
        }
        classified = int(
            con.execute(
                f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE product_type IS NOT NULL"
            ).fetchone()[0]
        )
        return {
            **result,
            "comparison_status": dict(sorted(statuses.items())),
            "classified_product_type": classified,
            "product_count_before": before["products"],
            "price_history_count_before": before["price_history"],
            "price_history_count_after": after["price_history"],
            "scrape_runs_count_before": before["scrape_runs"],
            "scrape_runs_count_after": after["scrape_runs"],
            "foreign_key_violations": 0,
            "integrity_check": "ok",
        }
    finally:
        con.close()


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--updated-at-utc")
    args = parser.parse_args()
    result = backfill_sqlite(args.sqlite, updated_at_utc=args.updated_at_utc)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
