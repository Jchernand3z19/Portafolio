#!/usr/bin/env python3
"""Migra de forma idempotente price_history para ofertas agotadas de Paiz.

La migración amplía únicamente la excepción ya aceptada para ofertas sin precio:
Walmart/PriceSmart -> Walmart/PriceSmart/Paiz. Conserva todas las filas, índices,
claves foráneas y registra los dos contextos TGU de Paiz.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from actualizar_mvp_sqlite_la_colonia import SnapshotError
from actualizar_mvp_turso_la_colonia import _execute_rows, _pipeline, _run_batch, _stmt

SUPERMARKET_ID = "paiz"
SUPERMARKET_NAME = "Paiz"
COUNTRY = "HN"
LOCATIONS = {
    "paiz_tgu_multiplaza": "Tegucigalpa",
    "paiz_tgu_proceres": "Tegucigalpa",
}
OLD_FRAGMENT = "supermarket_id IN ('walmart', 'pricesmart')"
NEW_FRAGMENT = "supermarket_id IN ('walmart', 'pricesmart', 'paiz')"


def schema_ready_sql(sql: object) -> bool:
    return isinstance(sql, str) and NEW_FRAGMENT in sql and OLD_FRAGMENT not in sql


def _target_ddl(current_sql: str, table_name: str = "paiz_new_price_history") -> str:
    if schema_ready_sql(current_sql):
        source = current_sql
    elif OLD_FRAGMENT in current_sql:
        source = current_sql.replace(OLD_FRAGMENT, NEW_FRAGMENT, 1)
    else:
        raise SnapshotError("paiz_unrecognized_price_history_check")
    marker = "CREATE TABLE price_history"
    if marker not in source:
        marker = "CREATE TABLE \"price_history\""
    if marker not in source:
        raise SnapshotError("paiz_price_history_ddl_invalid")
    return source.replace(marker, f"CREATE TABLE {table_name}", 1)


def _validate_scope_rows(supermarket: list[list[object]], locations: list[list[object]]) -> None:
    if supermarket and supermarket != [[SUPERMARKET_NAME, COUNTRY]]:
        raise SnapshotError(f"paiz_supermarket_conflict:{supermarket}")
    expected = [[location_id, SUPERMARKET_ID, city, COUNTRY] for location_id, city in sorted(LOCATIONS.items())]
    if locations and locations != expected:
        raise SnapshotError(f"paiz_location_conflict:{locations}")


def migrate_sqlite(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SnapshotError("database_missing")
    con = sqlite3.connect(path, isolation_level=None)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        current = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='price_history'").fetchone()
        index = con.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_price_history_current'").fetchone()
        if not current or not isinstance(current[0], str) or not index or not isinstance(index[0], str):
            raise SnapshotError("paiz_schema_objects_missing")
        existing_supermarket = con.execute(
            "SELECT name,country_code FROM supermarkets WHERE supermarket_id=?", (SUPERMARKET_ID,)
        ).fetchall()
        existing_locations = con.execute(
            "SELECT location_id,supermarket_id,city_name,country_code FROM locations WHERE supermarket_id=? ORDER BY location_id",
            (SUPERMARKET_ID,),
        ).fetchall()
        _validate_scope_rows([list(row) for row in existing_supermarket], [list(row) for row in existing_locations])
        already = schema_ready_sql(current[0])
        if not already:
            ddl = _target_ddl(current[0])
            before = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
            con.execute("PRAGMA foreign_keys=OFF")
            con.execute("BEGIN IMMEDIATE")
            con.execute(ddl)
            con.execute("INSERT INTO paiz_new_price_history SELECT * FROM price_history")
            copied = con.execute("SELECT COUNT(*) FROM paiz_new_price_history").fetchone()[0]
            if copied != before:
                raise SnapshotError("paiz_migration_row_count_mismatch")
            con.execute("DROP TABLE price_history")
            con.execute("ALTER TABLE paiz_new_price_history RENAME TO price_history")
            con.execute(index[0])
            con.execute("COMMIT")
            con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT OR IGNORE INTO supermarkets VALUES(?,?,?)", (SUPERMARKET_ID, SUPERMARKET_NAME, COUNTRY))
        for location_id, city in LOCATIONS.items():
            con.execute("INSERT OR IGNORE INTO locations VALUES(?,?,?,?)", (location_id, SUPERMARKET_ID, city, COUNTRY))
        con.execute("COMMIT")
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        integrity = con.execute("PRAGMA integrity_check").fetchall()
        duplicate = con.execute(
            "SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)"
        ).fetchone()[0]
        final_sql = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='price_history'").fetchone()[0]
        if not schema_ready_sql(final_sql) or fk or integrity != [("ok",)] or duplicate:
            raise SnapshotError("paiz_migration_postflight_failed")
        return {"migrated": not already, "foreign_key_violations": 0, "duplicate_open_periods": 0, "integrity_check": "ok"}
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        try:
            con.execute("PRAGMA foreign_keys=ON")
        finally:
            con.close()


def _turso_preflight(url: str, token: str) -> dict[str, Any]:
    data = _pipeline(
        url,
        token,
        [
            {"type": "execute", "stmt": _stmt("SELECT sql FROM sqlite_master WHERE type='table' AND name='price_history'")},
            {"type": "execute", "stmt": _stmt("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_price_history_current'")},
            {"type": "execute", "stmt": _stmt("SELECT COUNT(*) FROM price_history")},
            {"type": "execute", "stmt": _stmt("SELECT name,country_code FROM supermarkets WHERE supermarket_id=?", (SUPERMARKET_ID,))},
            {"type": "execute", "stmt": _stmt("SELECT location_id,supermarket_id,city_name,country_code FROM locations WHERE supermarket_id=? ORDER BY location_id", (SUPERMARKET_ID,))},
            {"type": "close"},
        ],
    )
    results = data.get("results")
    if not isinstance(results, list) or len(results) < 5:
        raise SnapshotError("paiz_turso_migration_preflight_invalid")
    ddl_rows = _execute_rows(results[0])
    index_rows = _execute_rows(results[1])
    counts = _execute_rows(results[2])
    supermarket = _execute_rows(results[3])
    locations = _execute_rows(results[4])
    if len(ddl_rows) != 1 or not isinstance(ddl_rows[0][0], str) or len(index_rows) != 1 or not isinstance(index_rows[0][0], str) or len(counts) != 1:
        raise SnapshotError("paiz_turso_schema_objects_missing")
    _validate_scope_rows(supermarket, locations)
    return {"ddl": ddl_rows[0][0], "index": index_rows[0][0], "count": counts[0][0], "ready": schema_ready_sql(ddl_rows[0][0])}


def migrate_turso(url: str, token: str) -> dict[str, object]:
    if not url.strip() or not token.strip():
        raise SnapshotError("turso_credentials_missing")
    pre = _turso_preflight(url, token)
    if pre["ready"]:
        steps = [
            ("begin", "BEGIN IMMEDIATE", ()),
            ("register_supermarket", "INSERT OR IGNORE INTO supermarkets VALUES(?,?,?)", (SUPERMARKET_ID, SUPERMARKET_NAME, COUNTRY)),
            *[(f"register_{location_id}", "INSERT OR IGNORE INTO locations VALUES(?,?,?,?)", (location_id, SUPERMARKET_ID, city, COUNTRY)) for location_id, city in LOCATIONS.items()],
            ("commit", "COMMIT", ()),
        ]
        _run_batch(url, token, steps)
        migrated = False
    else:
        ddl = _target_ddl(str(pre["ddl"]))
        steps = [
            ("foreign_keys_off", "PRAGMA foreign_keys=OFF", ()),
            ("drop_guard", "DROP TABLE IF EXISTS temp.paiz_migration_guard", ()),
            ("guard_table", "CREATE TEMP TABLE paiz_migration_guard(value INTEGER NOT NULL CHECK(value=0)) STRICT", ()),
            ("begin", "BEGIN IMMEDIATE", ()),
            ("create_price_history", ddl, ()),
            ("copy_price_history", "INSERT INTO paiz_new_price_history SELECT * FROM price_history", ()),
            ("guard_copy", "INSERT INTO paiz_migration_guard SELECT CASE WHEN (SELECT COUNT(*) FROM paiz_new_price_history)=(SELECT COUNT(*) FROM price_history) THEN 0 ELSE 1 END", ()),
            ("drop_price_history", "DROP TABLE price_history", ()),
            ("rename_price_history", "ALTER TABLE paiz_new_price_history RENAME TO price_history", ()),
            ("index_current", str(pre["index"]), ()),
            ("register_supermarket", "INSERT OR IGNORE INTO supermarkets VALUES(?,?,?)", (SUPERMARKET_ID, SUPERMARKET_NAME, COUNTRY)),
            *[(f"register_{location_id}", "INSERT OR IGNORE INTO locations VALUES(?,?,?,?)", (location_id, SUPERMARKET_ID, city, COUNTRY)) for location_id, city in LOCATIONS.items()],
            ("guard_fk", "INSERT INTO paiz_migration_guard SELECT COUNT(*) FROM pragma_foreign_key_check", ()),
            ("commit", "COMMIT", ()),
            ("foreign_keys_on", "PRAGMA foreign_keys=ON", ()),
        ]
        _run_batch(url, token, steps)
        migrated = True

    data = _pipeline(
        url,
        token,
        [
            {"type": "execute", "stmt": _stmt("SELECT sql FROM sqlite_master WHERE type='table' AND name='price_history'")},
            {"type": "execute", "stmt": _stmt("SELECT COUNT(*) FROM price_history")},
            {"type": "execute", "stmt": _stmt("SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)")},
            {"type": "execute", "stmt": _stmt("SELECT COUNT(*) FROM pragma_foreign_key_check")},
            {"type": "execute", "stmt": _stmt("PRAGMA integrity_check")},
            {"type": "execute", "stmt": _stmt("SELECT location_id,supermarket_id,city_name,country_code FROM locations WHERE supermarket_id=? ORDER BY location_id", (SUPERMARKET_ID,))},
            {"type": "close"},
        ],
    )
    results = data.get("results")
    if not isinstance(results, list) or len(results) < 6:
        raise SnapshotError("paiz_turso_migration_postflight_invalid")
    ddl = _execute_rows(results[0])
    count = _execute_rows(results[1])
    dupes = _execute_rows(results[2])
    fk = _execute_rows(results[3])
    integrity = _execute_rows(results[4])
    locations = _execute_rows(results[5])
    expected_locations = [[location_id, SUPERMARKET_ID, city, COUNTRY] for location_id, city in sorted(LOCATIONS.items())]
    if (
        len(ddl) != 1 or not schema_ready_sql(ddl[0][0])
        or count != [[pre["count"]]]
        or dupes != [[0]] or fk != [[0]] or integrity != [["ok"]]
        or locations != expected_locations
    ):
        raise SnapshotError(f"paiz_turso_migration_postflight_failed:{count}:{dupes}:{fk}:{integrity}:{locations}")
    return {
        "migrated": migrated,
        "price_history_rows": count[0][0],
        "duplicate_open_periods": 0,
        "foreign_key_violations": 0,
        "integrity_check": "ok",
        "locations": [row[0] for row in locations],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path)
    parser.add_argument("--turso", action="store_true")
    args = parser.parse_args()
    if bool(args.sqlite) == bool(args.turso):
        raise SystemExit("choose_exactly_one_migration_target")
    try:
        result = migrate_sqlite(args.sqlite) if args.sqlite else migrate_turso(
            os.environ.get("TURSO_DATABASE_URL", ""), os.environ.get("TURSO_AUTH_TOKEN", "")
        )
    except SnapshotError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
