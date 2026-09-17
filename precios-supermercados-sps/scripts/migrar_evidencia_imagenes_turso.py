#!/usr/bin/env python3
"""Crea de forma idempotente la evidencia temporal de imágenes en Turso."""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from actualizar_mvp_sqlite_la_colonia import SnapshotError
from actualizar_mvp_turso_la_colonia import (
    _execute_rows,
    _pipeline,
    _run_batch,
    _stmt,
    _validate_table_names,
)
from generar_mvp_sqlite_la_colonia import create_product_image_schema, create_schema

TABLE_NAME = "product_images"
INDEX_NAMES = (
    "idx_product_images_current",
    "idx_product_images_current_primary",
)
EXPECTED_COLUMNS = (
    "product_image_id",
    "product_id",
    "supermarket_id",
    "location_id",
    "image_url",
    "source_position",
    "is_primary",
    "source_image_id",
    "valid_from_utc",
    "valid_to_utc",
    "first_seen_run_id",
    "last_seen_run_id",
)
BASE_TABLES = (
    "supermarkets",
    "locations",
    "products",
    "price_history",
    "scrape_runs",
)


def target_objects() -> dict[str, str]:
    """Obtiene el DDL desde el esquema SQLite canónico para evitar divergencias."""

    con = sqlite3.connect(":memory:")
    try:
        create_schema(con)
        create_product_image_schema(con)
        names = (TABLE_NAME, *INDEX_NAMES)
        placeholders = ",".join("?" for _ in names)
        rows = con.execute(
            f"SELECT name,sql FROM sqlite_master WHERE name IN ({placeholders})",
            names,
        ).fetchall()
    finally:
        con.close()
    result = {str(name): str(sql) for name, sql in rows if sql is not None}
    if set(result) != set(names):
        raise SnapshotError("product_images_target_schema_incomplete")
    return result


def _read_state(url: str, token: str) -> dict[str, Any]:
    requests = [
        {
            "type": "execute",
            "stmt": _stmt(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ),
        },
        *[
            {"type": "execute", "stmt": _stmt(f"SELECT COUNT(*) FROM {table}")}
            for table in BASE_TABLES
        ],
        {
            "type": "execute",
            "stmt": _stmt("SELECT COUNT(*) FROM pragma_foreign_key_check"),
        },
        {"type": "execute", "stmt": _stmt("PRAGMA integrity_check")},
        {"type": "close"},
    ]
    data = _pipeline(url, token, requests)
    results = data.get("results")
    expected = 1 + len(BASE_TABLES) + 2
    if not isinstance(results, list) or len(results) < expected:
        raise SnapshotError("product_images_migration_state_invalid")

    table_names = {str(row[0]) for row in _execute_rows(results[0])}
    _validate_table_names(table_names)
    counts: dict[str, int] = {}
    for offset, table in enumerate(BASE_TABLES, start=1):
        rows = _execute_rows(results[offset])
        if len(rows) != 1 or len(rows[0]) != 1 or type(rows[0][0]) is not int:
            raise SnapshotError(f"product_images_migration_count_invalid:{table}")
        counts[table] = int(rows[0][0])
    if (
        _execute_rows(results[1 + len(BASE_TABLES)]) != [[0]]
        or _execute_rows(results[2 + len(BASE_TABLES)]) != [["ok"]]
    ):
        raise SnapshotError("product_images_migration_integrity_failed")

    columns: tuple[str, ...] = ()
    indexes: set[str] = set()
    image_count = 0
    if TABLE_NAME in table_names:
        detail = _pipeline(
            url,
            token,
            [
                {
                    "type": "execute",
                    "stmt": _stmt(
                        "SELECT name FROM pragma_table_info(?) ORDER BY cid",
                        (TABLE_NAME,),
                    ),
                },
                {
                    "type": "execute",
                    "stmt": _stmt(
                        "SELECT name FROM sqlite_master WHERE type='index' "
                        "AND tbl_name=? ORDER BY name",
                        (TABLE_NAME,),
                    ),
                },
                {
                    "type": "execute",
                    "stmt": _stmt(f"SELECT COUNT(*) FROM {TABLE_NAME}"),
                },
                {"type": "close"},
            ],
        )
        detail_results = detail.get("results")
        if not isinstance(detail_results, list) or len(detail_results) < 3:
            raise SnapshotError("product_images_migration_detail_invalid")
        columns = tuple(str(row[0]) for row in _execute_rows(detail_results[0]))
        indexes = {str(row[0]) for row in _execute_rows(detail_results[1])}
        count_rows = _execute_rows(detail_results[2])
        if (
            len(count_rows) != 1
            or len(count_rows[0]) != 1
            or type(count_rows[0][0]) is not int
        ):
            raise SnapshotError("product_images_migration_image_count_invalid")
        image_count = int(count_rows[0][0])
    return {
        "table_exists": TABLE_NAME in table_names,
        "columns": columns,
        "indexes": indexes,
        "base_counts": counts,
        "image_count": image_count,
    }


def schema_ready(state: dict[str, Any]) -> bool:
    return (
        state.get("table_exists") is True
        and tuple(state.get("columns", ())) == EXPECTED_COLUMNS
        and set(INDEX_NAMES) <= set(state.get("indexes", set()))
    )


def migration_steps(state: dict[str, Any]) -> list[tuple[str, str, tuple[object, ...]]]:
    ddl = target_objects()
    if state.get("table_exists") and tuple(state.get("columns", ())) != EXPECTED_COLUMNS:
        raise SnapshotError("product_images_unrecognized_schema")
    steps: list[tuple[str, str, tuple[object, ...]]] = [
        ("begin", "BEGIN IMMEDIATE", ())
    ]
    if not state.get("table_exists"):
        steps.append(("create_product_images", ddl[TABLE_NAME], ()))
    existing_indexes = set(state.get("indexes", set()))
    for name in INDEX_NAMES:
        if name not in existing_indexes:
            steps.append((f"create_{name}", ddl[name], ()))
    steps.append(("commit", "COMMIT", ()))
    return steps


def migrate_turso(url: str, token: str) -> dict[str, object]:
    if not url.strip() or not token.strip():
        raise SnapshotError("turso_credentials_missing")
    before = _read_state(url, token)
    if schema_ready(before):
        return {
            "migrated": False,
            "schema_ready": True,
            "base_counts": before["base_counts"],
            "image_count": before["image_count"],
        }
    steps = migration_steps(before)
    _run_batch(url, token, steps)
    after = _read_state(url, token)
    if not schema_ready(after):
        raise SnapshotError("product_images_migration_incomplete")
    if after["base_counts"] != before["base_counts"]:
        raise SnapshotError("product_images_migration_base_counts_changed")
    if before["table_exists"] and after["image_count"] != before["image_count"]:
        raise SnapshotError("product_images_migration_image_count_changed")
    return {
        "migrated": True,
        "schema_ready": True,
        "base_counts": after["base_counts"],
        "image_count": after["image_count"],
    }


def main() -> None:
    try:
        result = migrate_turso(
            os.environ.get("TURSO_DATABASE_URL", ""),
            os.environ.get("TURSO_AUTH_TOKEN", ""),
        )
    except SnapshotError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
