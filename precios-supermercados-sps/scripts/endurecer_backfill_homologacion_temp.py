#!/usr/bin/env python3
"""Parche temporal idempotente para endurecer la transición de homologación."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TURSO = ROOT / "scripts" / "backfill_homologacion_turso.py"
PERSIST = ROOT / "src" / "precios_supermercados" / "product_homologation_persistence.py"
TESTS = ROOT / "tests" / "test_product_homologation_persistence.py"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"patch_contract_failed:{old[:60]}:{text.count(old)}")
    return text.replace(old, new, 1)


def patch_persistence() -> None:
    text = PERSIST.read_text(encoding="utf-8")
    text = text.replace("source_profile_coverage_mismatch", "profile_product_count_mismatch")
    PERSIST.write_text(text, encoding="utf-8")


def patch_turso() -> None:
    text = TURSO.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    _run_batch,\n    _stmt,\n)",
        "    _run_batch,\n    _stmt,\n    _validate_table_names,\n)",
    )
    source_preflight = '''\n\ndef _source_preflight(url: str, token: str) -> dict[str, int]:\n    table_rows = _query(\n        url,\n        token,\n        \"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name\",\n    )\n    _validate_table_names(str(row[0]) for row in table_rows)\n    target_exists = any(str(row[0]) == TABLE_NAME for row in table_rows)\n    state = {\n        \"products\": _scalar(url, token, \"SELECT COUNT(*) FROM products\"),\n        \"price_history\": _scalar(url, token, \"SELECT COUNT(*) FROM price_history\"),\n        \"scrape_runs\": _scalar(url, token, \"SELECT COUNT(*) FROM scrape_runs\"),\n        \"profiles\": (\n            _scalar(url, token, f\"SELECT COUNT(*) FROM {TABLE_NAME}\")\n            if target_exists\n            else 0\n        ),\n    }\n    foreign_keys = _scalar(url, token, \"SELECT COUNT(*) FROM pragma_foreign_key_check\")\n    duplicate_current = _scalar(\n        url,\n        token,\n        \"SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)\",\n    )\n    integrity = _query(url, token, \"PRAGMA integrity_check\")\n    if foreign_keys != 0 or duplicate_current != 0 or integrity != [[\"ok\"]]:\n        raise SnapshotError(\"homologation_source_preflight_integrity_failed\")\n    return state\n'''
    text = replace_once(
        text,
        "\ndef _preflight(url: str, token: str) -> dict[str, int]:\n",
        source_preflight + "\n\ndef _preflight(url: str, token: str) -> dict[str, int]:\n",
    )
    drop_stage = '''\n\ndef _drop_stage(url: str, token: str) -> None:\n    _run_batch(\n        url,\n        token,\n        [\n            (\"begin\", \"BEGIN IMMEDIATE\", ()),\n            (\"drop_stage\", f\"DROP TABLE IF EXISTS {STAGE_TABLE}\", ()),\n            (\"commit\", \"COMMIT\", ()),\n        ],\n    )\n'''
    text = replace_once(
        text,
        "\ndef _delta_counts(url: str, token: str) -> dict[str, int]:\n",
        drop_stage + "\n\ndef _delta_counts(url: str, token: str) -> dict[str, int]:\n",
    )
    old = '''    _ensure_schema(database_url, auth_token)\n    before = _preflight(database_url, auth_token)\n    products = _fetch_products(database_url, auth_token)\n    if len(products) != before[\"products\"]:\n        raise SnapshotError(\"homologation_source_changed_during_read\")\n    derived = build_homologation_rows(\n        products,\n        updated_at_utc=updated_at_utc,\n        normalization_version=NORMALIZATION_VERSION,\n    )\n    _stage_rows(database_url, auth_token, derived)\n    delta = _delta_counts(database_url, auth_token)\n    _apply_stage(database_url, auth_token, before, len(derived))\n    post = _postflight(database_url, auth_token, before, len(derived))\n    _run_batch(\n        database_url,\n        auth_token,\n        [\n            (\"begin\", \"BEGIN IMMEDIATE\", ()),\n            (\"drop_stage\", f\"DROP TABLE IF EXISTS {STAGE_TABLE}\", ()),\n            (\"commit\", \"COMMIT\", ()),\n        ],\n    )\n    return {\n        \"normalization_version\": NORMALIZATION_VERSION,\n        \"processed\": len(derived),\n        **delta,\n        **post,\n    }\n'''
    new = '''    before = _source_preflight(database_url, auth_token)\n    _ensure_schema(database_url, auth_token)\n    after_schema = _preflight(database_url, auth_token)\n    if after_schema != before:\n        raise SnapshotError(\"homologation_source_changed_during_schema_transition\")\n\n    products = _fetch_products(database_url, auth_token)\n    if len(products) != before[\"products\"]:\n        raise SnapshotError(\"homologation_source_changed_during_read\")\n    derived = build_homologation_rows(\n        products,\n        updated_at_utc=updated_at_utc,\n        normalization_version=NORMALIZATION_VERSION,\n    )\n    delta: dict[str, int] = {}\n    post: dict[str, object] = {}\n    try:\n        _stage_rows(database_url, auth_token, derived)\n        delta = _delta_counts(database_url, auth_token)\n        _apply_stage(database_url, auth_token, before, len(derived))\n        post = _postflight(database_url, auth_token, before, len(derived))\n    finally:\n        _drop_stage(database_url, auth_token)\n    return {\n        \"normalization_version\": NORMALIZATION_VERSION,\n        \"processed\": len(derived),\n        **delta,\n        **post,\n    }\n'''
    text = replace_once(text, old, new)
    TURSO.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = "def test_partial_recalculation_fails_even_with_preexisting_full_profiles"
    if marker not in text:
        text += '''\n\ndef test_partial_recalculation_fails_even_with_preexisting_full_profiles(tmp_path: Path) -> None:\n    con = create_base_db(tmp_path / \"mvp.sqlite\")\n    try:\n        insert_product(con, 1, \"la_colonia\", \"Arroz Uno 1 lb\")\n        insert_product(con, 2, \"walmart\", \"Arroz Dos 1 lb\")\n        full = build_homologation_rows(\n            fetch_source_rows(con), updated_at_utc=\"2026-09-04T20:00:00Z\"\n        )\n        persist_sqlite_rows(con, full)\n        con.commit()\n\n        partial = build_homologation_rows(\n            (source(1, \"la_colonia\", \"Arroz Uno 1 lb\"),),\n            updated_at_utc=\"2026-09-04T21:00:00Z\",\n        )\n        with pytest.raises(\n            ProductHomologationPersistenceError,\n            match=\"profile_product_count_mismatch\",\n        ):\n            persist_sqlite_rows(con, partial)\n        assert con.execute(f\"SELECT COUNT(*) FROM {TABLE_NAME}\").fetchone() == (2,)\n    finally:\n        con.close()\n'''
    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_persistence()
    patch_turso()
    patch_tests()
    print("HOMOLOGATION_HARDENING_PATCH_OK=1")


if __name__ == "__main__":
    main()
