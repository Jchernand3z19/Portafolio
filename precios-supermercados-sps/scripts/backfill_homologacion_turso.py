#!/usr/bin/env python3
"""Backfill controlado de homologación en Turso desde `products` ya persistidos.

No consulta supermercados. La carga usa una tabla staging permanente y sólo
modifica la tabla derivada `product_homologation_profiles` después de validar
cobertura completa.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from actualizar_mvp_sqlite_la_colonia import SnapshotError  # noqa: E402
from actualizar_mvp_turso_la_colonia import (  # noqa: E402
    _execute_rows,
    _pipeline,
    _run_batch,
    _stmt,
    _validate_table_names,
)
from precios_supermercados.product_homologation_persistence import (  # noqa: E402
    NORMALIZATION_VERSION,
    TABLE_NAME,
    ProductHomologationPersistenceError,
    ProductHomologationRow,
    build_homologation_rows,
    records_from_product_rows,
)

STAGE_TABLE = "product_homologation_profiles_stage"
EXPECTED_COLUMNS = (
    "product_id",
    "supermarket_id",
    "normalized_name",
    "normalized_brand",
    "canonical_gtin",
    "canonical_product_id",
    "category",
    "subcategory",
    "product_type",
    "taxonomy_rule_id",
    "presentation_dimension",
    "presentation_total_base",
    "presentation_pack_count",
    "presentation_unit_amount_base",
    "presentation_status",
    "comparison_status",
    "conflict_reasons_json",
    "normalization_version",
    "profile_hash",
    "updated_at_utc",
)

TARGET_TABLE_SQL = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    product_id INTEGER PRIMARY KEY,
    supermarket_id TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    normalized_brand TEXT,
    canonical_gtin TEXT,
    canonical_product_id TEXT,
    category TEXT,
    subcategory TEXT,
    product_type TEXT,
    taxonomy_rule_id TEXT,
    presentation_dimension TEXT CHECK (
        presentation_dimension IS NULL OR presentation_dimension IN ('mass_g','volume_ml','count','ounce')
    ),
    presentation_total_base TEXT,
    presentation_pack_count INTEGER CHECK (presentation_pack_count IS NULL OR presentation_pack_count > 0),
    presentation_unit_amount_base TEXT,
    presentation_status TEXT NOT NULL CHECK (
        presentation_status IN ('confirmed','name_only','source_only','name_preferred_source_conflict','ambiguous_multipack','conflict','missing')
    ),
    comparison_status TEXT NOT NULL CHECK (
        comparison_status IN ('ready','review_required','single_source','unmapped')
    ),
    conflict_reasons_json TEXT NOT NULL,
    normalization_version TEXT NOT NULL,
    profile_hash TEXT NOT NULL CHECK (length(profile_hash) = 64),
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (product_id, supermarket_id) REFERENCES products(product_id, supermarket_id),
    CHECK ((canonical_gtin IS NULL) = (canonical_product_id IS NULL)),
    CHECK (
        (comparison_status = 'unmapped' AND canonical_gtin IS NULL)
        OR (comparison_status != 'unmapped' AND canonical_gtin IS NOT NULL)
    )
) STRICT"""

STAGE_TABLE_SQL = f"""CREATE TABLE {STAGE_TABLE} (
    product_id INTEGER PRIMARY KEY,
    supermarket_id TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    normalized_brand TEXT,
    canonical_gtin TEXT,
    canonical_product_id TEXT,
    category TEXT,
    subcategory TEXT,
    product_type TEXT,
    taxonomy_rule_id TEXT,
    presentation_dimension TEXT,
    presentation_total_base TEXT,
    presentation_pack_count INTEGER,
    presentation_unit_amount_base TEXT,
    presentation_status TEXT NOT NULL,
    comparison_status TEXT NOT NULL,
    conflict_reasons_json TEXT NOT NULL,
    normalization_version TEXT NOT NULL,
    profile_hash TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
) STRICT"""

INDEX_STEPS = (
    ("index_canonical", f"CREATE INDEX IF NOT EXISTS idx_product_homologation_canonical ON {TABLE_NAME}(canonical_product_id) WHERE canonical_product_id IS NOT NULL", ()),
    ("index_type", f"CREATE INDEX IF NOT EXISTS idx_product_homologation_type ON {TABLE_NAME}(product_type) WHERE product_type IS NOT NULL", ()),
    ("index_brand", f"CREATE INDEX IF NOT EXISTS idx_product_homologation_brand ON {TABLE_NAME}(normalized_brand) WHERE normalized_brand IS NOT NULL", ()),
    ("index_comparison", f"CREATE INDEX IF NOT EXISTS idx_product_homologation_comparison ON {TABLE_NAME}(comparison_status, canonical_product_id)", ()),
)


def _query(url: str, token: str, sql: str, args: tuple[object, ...] = ()) -> list[list[object]]:
    data = _pipeline(
        url,
        token,
        [{"type": "execute", "stmt": _stmt(sql, args)}, {"type": "close"}],
    )
    results = data.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise SnapshotError("homologation_turso_query_response_invalid")
    return _execute_rows(results[0])


def _scalar(url: str, token: str, sql: str, args: tuple[object, ...] = ()) -> int:
    rows = _query(url, token, sql, args)
    if len(rows) != 1 or len(rows[0]) != 1 or type(rows[0][0]) is not int:
        raise SnapshotError("homologation_turso_scalar_invalid")
    return int(rows[0][0])


def _ensure_schema(url: str, token: str) -> None:
    exists = _query(
        url,
        token,
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (TABLE_NAME,),
    )
    steps: list[tuple[str, str, tuple[object, ...]]] = [("begin", "BEGIN IMMEDIATE", ())]
    if not exists:
        steps.append(("create_target", TARGET_TABLE_SQL, ()))
    steps.extend(INDEX_STEPS)
    steps.append(("commit", "COMMIT", ()))
    _run_batch(url, token, steps)

    columns = _query(
        url,
        token,
        "SELECT name FROM pragma_table_info(?) ORDER BY cid",
        (TABLE_NAME,),
    )
    if tuple(str(row[0]) for row in columns) != EXPECTED_COLUMNS:
        raise SnapshotError("homologation_turso_schema_mismatch")


def _fetch_products(url: str, token: str) -> tuple[tuple[int, object], ...]:
    expected = _scalar(url, token, "SELECT COUNT(*) FROM products")
    records = []
    cursor = 0
    while True:
        rows = _query(
            url,
            token,
            "SELECT product_id,supermarket_id,name,brand,presentation,category,ean "
            "FROM products WHERE product_id>? ORDER BY product_id LIMIT 2000",
            (cursor,),
        )
        if not rows:
            break
        adapted = records_from_product_rows(tuple(tuple(row) for row in rows))
        records.extend(adapted)
        cursor = adapted[-1][0]
        if len(rows) < 2000:
            break
    if len(records) != expected:
        raise SnapshotError(f"homologation_turso_product_count_mismatch:{expected}:{len(records)}")
    return tuple(records)



def _fetch_profile_state(url: str, token: str) -> dict[int, tuple[str, str]]:
    expected = _scalar(url, token, f"SELECT COUNT(*) FROM {TABLE_NAME}")
    result: dict[int, tuple[str, str]] = {}
    cursor = 0
    while True:
        rows = _query(
            url,
            token,
            f"SELECT product_id,profile_hash,normalization_version FROM {TABLE_NAME} WHERE product_id>? ORDER BY product_id LIMIT 2000",
            (cursor,),
        )
        if not rows:
            break
        for product_id, profile_hash, version in rows:
            if type(product_id) is not int or not isinstance(profile_hash, str) or not isinstance(version, str):
                raise SnapshotError("homologation_profile_state_invalid")
            result[int(product_id)] = (profile_hash, version)
        cursor = int(rows[-1][0])
        if len(rows) < 2000:
            break
    if len(result) != expected:
        raise SnapshotError(f"homologation_profile_state_count_mismatch:{expected}:{len(result)}")
    return result


def _chunks(rows: tuple[ProductHomologationRow, ...], size: int) -> Iterable[tuple[ProductHomologationRow, ...]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _stage_payload(rows: tuple[ProductHomologationRow, ...]) -> str:
    return json.dumps([asdict(row) for row in rows], ensure_ascii=False, separators=(",", ":"))


_STAGE_INSERT = f"""INSERT INTO {STAGE_TABLE} ({','.join(EXPECTED_COLUMNS)})
SELECT
    CAST(json_extract(value,'$.product_id') AS INTEGER),
    json_extract(value,'$.supermarket_id'),
    json_extract(value,'$.normalized_name'),
    json_extract(value,'$.normalized_brand'),
    json_extract(value,'$.canonical_gtin'),
    json_extract(value,'$.canonical_product_id'),
    json_extract(value,'$.category'),
    json_extract(value,'$.subcategory'),
    json_extract(value,'$.product_type'),
    json_extract(value,'$.taxonomy_rule_id'),
    json_extract(value,'$.presentation_dimension'),
    json_extract(value,'$.presentation_total_base'),
    CAST(json_extract(value,'$.presentation_pack_count') AS INTEGER),
    json_extract(value,'$.presentation_unit_amount_base'),
    json_extract(value,'$.presentation_status'),
    json_extract(value,'$.comparison_status'),
    json_extract(value,'$.conflict_reasons_json'),
    json_extract(value,'$.normalization_version'),
    json_extract(value,'$.profile_hash'),
    json_extract(value,'$.updated_at_utc')
FROM json_each(?)"""

_TARGET_UPSERT = f"""INSERT INTO {TABLE_NAME} ({','.join(EXPECTED_COLUMNS)})
SELECT {','.join(EXPECTED_COLUMNS)} FROM {STAGE_TABLE} WHERE 1
ON CONFLICT(product_id) DO UPDATE SET
    supermarket_id=excluded.supermarket_id,
    normalized_name=excluded.normalized_name,
    normalized_brand=excluded.normalized_brand,
    canonical_gtin=excluded.canonical_gtin,
    canonical_product_id=excluded.canonical_product_id,
    category=excluded.category,
    subcategory=excluded.subcategory,
    product_type=excluded.product_type,
    taxonomy_rule_id=excluded.taxonomy_rule_id,
    presentation_dimension=excluded.presentation_dimension,
    presentation_total_base=excluded.presentation_total_base,
    presentation_pack_count=excluded.presentation_pack_count,
    presentation_unit_amount_base=excluded.presentation_unit_amount_base,
    presentation_status=excluded.presentation_status,
    comparison_status=excluded.comparison_status,
    conflict_reasons_json=excluded.conflict_reasons_json,
    normalization_version=excluded.normalization_version,
    profile_hash=excluded.profile_hash,
    updated_at_utc=excluded.updated_at_utc
WHERE {TABLE_NAME}.profile_hash <> excluded.profile_hash
   OR {TABLE_NAME}.normalization_version <> excluded.normalization_version"""



def _source_preflight(url: str, token: str) -> dict[str, int]:
    table_rows = _query(
        url,
        token,
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )
    _validate_table_names(str(row[0]) for row in table_rows)
    target_exists = any(str(row[0]) == TABLE_NAME for row in table_rows)
    state = {
        "products": _scalar(url, token, "SELECT COUNT(*) FROM products"),
        "price_history": _scalar(url, token, "SELECT COUNT(*) FROM price_history"),
        "scrape_runs": _scalar(url, token, "SELECT COUNT(*) FROM scrape_runs"),
        "profiles": (
            _scalar(url, token, f"SELECT COUNT(*) FROM {TABLE_NAME}")
            if target_exists
            else 0
        ),
    }
    foreign_keys = _scalar(url, token, "SELECT COUNT(*) FROM pragma_foreign_key_check")
    duplicate_current = _scalar(
        url,
        token,
        "SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)",
    )
    integrity = _query(url, token, "PRAGMA integrity_check")
    if foreign_keys != 0 or duplicate_current != 0 or integrity != [["ok"]]:
        raise SnapshotError("homologation_source_preflight_integrity_failed")
    return state


def _preflight(url: str, token: str) -> dict[str, int]:
    return {
        "products": _scalar(url, token, "SELECT COUNT(*) FROM products"),
        "price_history": _scalar(url, token, "SELECT COUNT(*) FROM price_history"),
        "scrape_runs": _scalar(url, token, "SELECT COUNT(*) FROM scrape_runs"),
        "profiles": _scalar(url, token, f"SELECT COUNT(*) FROM {TABLE_NAME}"),
    }


def _stage_rows(url: str, token: str, rows: tuple[ProductHomologationRow, ...]) -> None:
    _run_batch(
        url,
        token,
        [
            ("begin", "BEGIN IMMEDIATE", ()),
            ("drop_stage", f"DROP TABLE IF EXISTS {STAGE_TABLE}", ()),
            ("create_stage", STAGE_TABLE_SQL, ()),
            ("commit", "COMMIT", ()),
        ],
    )
    for index, chunk in enumerate(_chunks(rows, 1500)):
        _run_batch(
            url,
            token,
            [
                ("begin", "BEGIN IMMEDIATE", ()),
                (f"stage_chunk_{index}", _STAGE_INSERT, (_stage_payload(chunk),)),
                ("commit", "COMMIT", ()),
            ],
        )
    staged = _scalar(url, token, f"SELECT COUNT(*) FROM {STAGE_TABLE}")
    if staged != len(rows):
        raise SnapshotError(f"homologation_stage_count_mismatch:{staged}:{len(rows)}")



def _drop_stage(url: str, token: str) -> None:
    _run_batch(
        url,
        token,
        [
            ("begin", "BEGIN IMMEDIATE", ()),
            ("drop_stage", f"DROP TABLE IF EXISTS {STAGE_TABLE}", ()),
            ("commit", "COMMIT", ()),
        ],
    )


def _delta_counts(url: str, token: str) -> dict[str, int]:
    rows = _query(
        url,
        token,
        f"""SELECT
            SUM(CASE WHEN t.product_id IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN t.product_id IS NOT NULL AND (t.profile_hash<>s.profile_hash OR t.normalization_version<>s.normalization_version) THEN 1 ELSE 0 END),
            SUM(CASE WHEN t.product_id IS NOT NULL AND t.profile_hash=s.profile_hash AND t.normalization_version=s.normalization_version THEN 1 ELSE 0 END)
        FROM {STAGE_TABLE} s LEFT JOIN {TABLE_NAME} t ON t.product_id=s.product_id""",
    )
    if len(rows) != 1 or len(rows[0]) != 3:
        raise SnapshotError("homologation_delta_count_invalid")
    return {
        "inserted": int(rows[0][0] or 0),
        "updated": int(rows[0][1] or 0),
        "unchanged": int(rows[0][2] or 0),
    }


def _apply_stage(
    url: str,
    token: str,
    before: dict[str, int],
    *,
    staged_expected: int,
    profile_expected: int,
) -> None:
    steps = [
        ("drop_guard", "DROP TABLE IF EXISTS temp.homologation_guard", ()),
        ("guard_table", "CREATE TEMP TABLE homologation_guard(value INTEGER NOT NULL CHECK(value=0)) STRICT", ()),
        ("begin", "BEGIN IMMEDIATE", ()),
        ("guard_stage", f"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM {STAGE_TABLE}", (staged_expected,)),
        ("guard_products_before", "INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM products", (before["products"],)),
        ("guard_history_before", "INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM price_history", (before["price_history"],)),
        ("guard_runs_before", "INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM scrape_runs", (before["scrape_runs"],)),
        ("upsert_profiles", _TARGET_UPSERT, ()),
        ("guard_profile_count", f"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM {TABLE_NAME}", (profile_expected,)),
        ("guard_fk", "INSERT INTO homologation_guard SELECT COUNT(*) FROM pragma_foreign_key_check", ()),
        ("commit", "COMMIT", ()),
    ]
    _run_batch(url, token, steps)


def _postflight(url: str, token: str, before: dict[str, int], expected: int) -> dict[str, Any]:
    after = _preflight(url, token)
    if after["products"] != before["products"]:
        raise SnapshotError("homologation_products_mutated")
    if after["price_history"] != before["price_history"]:
        raise SnapshotError("homologation_price_history_mutated")
    if after["scrape_runs"] != before["scrape_runs"]:
        raise SnapshotError("homologation_scrape_runs_mutated")
    if after["profiles"] != expected:
        raise SnapshotError("homologation_profile_coverage_incomplete")
    fk = _scalar(url, token, "SELECT COUNT(*) FROM pragma_foreign_key_check")
    duplicate_current = _scalar(
        url,
        token,
        "SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)",
    )
    integrity = _query(url, token, "PRAGMA integrity_check")
    if fk != 0 or duplicate_current != 0 or integrity != [["ok"]]:
        raise SnapshotError("homologation_postflight_integrity_failed")
    statuses = _query(
        url,
        token,
        f"SELECT comparison_status,COUNT(*) FROM {TABLE_NAME} GROUP BY comparison_status ORDER BY comparison_status",
    )
    classified = _scalar(url, token, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE product_type IS NOT NULL")
    return {
        "profiles": after["profiles"],
        "comparison_status": {str(status): int(count) for status, count in statuses},
        "classified_product_type": classified,
        "foreign_key_violations": fk,
        "duplicate_open_periods": duplicate_current,
        "integrity_check": "ok",
        "products_unchanged": True,
        "price_history_unchanged": True,
        "scrape_runs_unchanged": True,
    }


def backfill_turso(
    database_url: str,
    auth_token: str,
    *,
    updated_at_utc: str | None = None,
) -> dict[str, object]:
    if not database_url.strip() or not auth_token.strip():
        raise ProductHomologationPersistenceError("turso_credentials_missing")
    before = _source_preflight(database_url, auth_token)
    if before["profiles"] == 0:
        _ensure_schema(database_url, auth_token)
        after_schema = _preflight(database_url, auth_token)
        if after_schema != before:
            raise SnapshotError("homologation_source_changed_during_schema_transition")

    products = _fetch_products(database_url, auth_token)
    if len(products) != before["products"]:
        raise SnapshotError("homologation_source_changed_during_read")
    derived = build_homologation_rows(
        products,
        updated_at_utc=updated_at_utc,
        normalization_version=NORMALIZATION_VERSION,
    )
    derived_state = {
        row.product_id: (row.profile_hash, row.normalization_version)
        for row in derived
    }
    existing_state = _fetch_profile_state(database_url, auth_token)
    extra_profiles = set(existing_state) - set(derived_state)
    if extra_profiles:
        raise SnapshotError("homologation_profile_ids_not_in_products")

    changed = tuple(
        row for row in derived
        if existing_state.get(row.product_id) != (row.profile_hash, row.normalization_version)
    )
    if not changed:
        post = _postflight(database_url, auth_token, before, len(derived))
        return {
            "normalization_version": NORMALIZATION_VERSION,
            "processed": len(derived),
            "inserted": 0,
            "updated": 0,
            "unchanged": len(derived),
            "no_op": True,
            "staging_written": False,
            **post,
        }

    delta: dict[str, int] = {}
    post: dict[str, object] = {}
    try:
        _stage_rows(database_url, auth_token, changed)
        staged_delta = _delta_counts(database_url, auth_token)
        _apply_stage(
            database_url,
            auth_token,
            before,
            staged_expected=len(changed),
            profile_expected=len(derived),
        )
        post = _postflight(database_url, auth_token, before, len(derived))
        delta = {
            "inserted": staged_delta["inserted"],
            "updated": staged_delta["updated"],
            "unchanged": len(derived) - staged_delta["inserted"] - staged_delta["updated"],
        }
    finally:
        _drop_stage(database_url, auth_token)
    return {
        "normalization_version": NORMALIZATION_VERSION,
        "processed": len(derived),
        "no_op": False,
        "staging_written": True,
        **delta,
        **post,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--updated-at-utc")
    args = parser.parse_args()
    result = backfill_turso(
        os.environ.get("TURSO_DATABASE_URL", ""),
        os.environ.get("TURSO_AUTH_TOKEN", ""),
        updated_at_utc=args.updated_at_utc,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
