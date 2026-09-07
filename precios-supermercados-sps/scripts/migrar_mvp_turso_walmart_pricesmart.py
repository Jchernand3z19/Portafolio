#!/usr/bin/env python3
"""Migra de forma controlada el esquema Turso previo a Walmart/PriceSmart.

Este runner reutiliza las migraciones offline ya congeladas para Walmart y
PriceSmart, pero las ejecuta contra Turso mediante el batch transaccional del
persistidor. Es idempotente, conserva conteos de las cinco tablas base y falla
cerrado ante cualquier esquema no reconocido.
"""
from __future__ import annotations

import json
import os
from typing import Any

import migrar_mvp_paiz as paiz
import migrar_mvp_pricesmart as pricesmart
import migrar_mvp_walmart as walmart
from actualizar_mvp_sqlite_la_colonia import SnapshotError
from actualizar_mvp_turso_la_colonia import _execute_rows, _pipeline, _run_batch, _stmt

BASE_TABLES = ("supermarkets", "locations", "products", "price_history", "scrape_runs")
MIGRATION_OBJECT_NAMES = {"locations", "price_history", "idx_locations_city_legacy"}


def _read_state(url: str, token: str) -> dict[str, Any]:
    requests = [
        {"type": "execute", "stmt": _stmt(walmart.SCHEMA_QUERY)},
        *[
            {"type": "execute", "stmt": _stmt(f"SELECT COUNT(*) FROM {table}")}
            for table in BASE_TABLES
        ],
        {"type": "execute", "stmt": _stmt("SELECT COUNT(*) FROM pragma_foreign_key_check")},
        {"type": "execute", "stmt": _stmt("PRAGMA integrity_check")},
        {"type": "close"},
    ]
    data = _pipeline(url, token, requests)
    results = data.get("results")
    expected = 1 + len(BASE_TABLES) + 2
    if not isinstance(results, list) or len(results) < expected:
        raise SnapshotError("mvp_turso_migration_state_invalid")

    schema_rows = _execute_rows(results[0])
    if any(len(row) != 2 or not isinstance(row[0], str) or not isinstance(row[1], str) for row in schema_rows):
        raise SnapshotError("mvp_turso_migration_schema_invalid")

    counts: dict[str, int] = {}
    for offset, table in enumerate(BASE_TABLES, start=1):
        rows = _execute_rows(results[offset])
        if len(rows) != 1 or len(rows[0]) != 1 or not isinstance(rows[0][0], int):
            raise SnapshotError(f"mvp_turso_migration_count_invalid:{table}")
        counts[table] = int(rows[0][0])

    fk_rows = _execute_rows(results[1 + len(BASE_TABLES)])
    integrity_rows = _execute_rows(results[2 + len(BASE_TABLES)])
    if fk_rows != [[0]] or integrity_rows != [["ok"]]:
        raise SnapshotError(f"mvp_turso_migration_preflight_failed:{fk_rows}:{integrity_rows}")
    return {"schema": schema_rows, "counts": counts}


def _migration_rows(schema_rows: list[list[object]]) -> list[tuple[str, str]]:
    rows = [(str(name), str(sql)) for name, sql in schema_rows if name in MIGRATION_OBJECT_NAMES]
    if {name for name, _ in rows} != MIGRATION_OBJECT_NAMES:
        raise SnapshotError("mvp_turso_migration_schema_objects_missing")
    return rows


def _base_rows(schema_rows: list[list[object]]) -> list[tuple[str, str]]:
    target_names = {name for name, _ in pricesmart.target_schema()}
    rows = [(str(name), str(sql)) for name, sql in schema_rows if name in target_names]
    if {name for name, _ in rows} != target_names:
        raise SnapshotError("mvp_turso_migration_base_schema_incomplete")
    return rows


def _next_stage(schema_rows: list[list[object]]) -> str | None:
    migration_rows = _migration_rows(schema_rows)
    objects = dict(migration_rows)

    # Una base que ya pasó por Paiz necesariamente pasó antes por Walmart y
    # PriceSmart; reconocerla evita que este runner deje de ser idempotente.
    if paiz.schema_ready_sql(objects.get("price_history")) and paiz.locations_index_ready_sql(
        objects.get("idx_locations_city_legacy")
    ):
        return None

    if pricesmart.schema_ready(migration_rows):
        return None

    base_rows = _base_rows(schema_rows)
    base_fingerprint = walmart.fingerprint(base_rows)

    if walmart.schema_ready(migration_rows):
        if base_fingerprint != pricesmart.PRE_PRICESMART_FINGERPRINT:
            raise SnapshotError("pricesmart_unrecognized_pre_migration_schema")
        return "pricesmart"

    if base_fingerprint != walmart.LEGACY_FINGERPRINT:
        raise SnapshotError("walmart_unrecognized_pre_migration_schema")
    return "walmart"


def _assert_unchanged_counts(before: dict[str, int], after: dict[str, int], stage: str) -> None:
    if after != before:
        raise SnapshotError(f"mvp_turso_migration_row_count_mismatch:{stage}:before={before}:after={after}")


def migrate_turso(url: str, token: str) -> dict[str, object]:
    if not url.strip() or not token.strip():
        raise SnapshotError("turso_credentials_missing")

    state = _read_state(url, token)
    baseline = dict(state["counts"])
    migrated: list[str] = []

    for _ in range(2):
        stage = _next_stage(state["schema"])
        if stage is None:
            return {
                "migrated": bool(migrated),
                "stages": migrated,
                "counts": baseline,
                "schema_ready": True,
            }

        steps = walmart.migration_steps() if stage == "walmart" else pricesmart.migration_steps()
        _run_batch(url, token, steps)
        migrated.append(stage)

        next_state = _read_state(url, token)
        _assert_unchanged_counts(baseline, dict(next_state["counts"]), stage)
        state = next_state

    pending = _next_stage(state["schema"])
    if pending is not None:
        raise SnapshotError(f"mvp_turso_migration_incomplete:{pending}")
    return {
        "migrated": bool(migrated),
        "stages": migrated,
        "counts": baseline,
        "schema_ready": True,
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
