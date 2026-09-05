#!/usr/bin/env python3
"""Parche temporal idempotente para refresh diferencial de homologación."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKFILL = ROOT / "scripts" / "backfill_homologacion_turso.py"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "precios-supermercados-sps-la-colonia-mvp-update.yml"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"patch_contract_failed:{count}:{old[:80]}")
    return text.replace(old, new, 1)


def patch_backfill() -> None:
    text = BACKFILL.read_text(encoding="utf-8")
    fetch_state = '''\n\ndef _fetch_profile_state(url: str, token: str) -> dict[int, tuple[str, str]]:\n    expected = _scalar(url, token, f\"SELECT COUNT(*) FROM {TABLE_NAME}\")\n    result: dict[int, tuple[str, str]] = {}\n    cursor = 0\n    while True:\n        rows = _query(\n            url,\n            token,\n            f\"SELECT product_id,profile_hash,normalization_version FROM {TABLE_NAME} WHERE product_id>? ORDER BY product_id LIMIT 2000\",\n            (cursor,),\n        )\n        if not rows:\n            break\n        for product_id, profile_hash, version in rows:\n            if type(product_id) is not int or not isinstance(profile_hash, str) or not isinstance(version, str):\n                raise SnapshotError(\"homologation_profile_state_invalid\")\n            result[int(product_id)] = (profile_hash, version)\n        cursor = int(rows[-1][0])\n        if len(rows) < 2000:\n            break\n    if len(result) != expected:\n        raise SnapshotError(f\"homologation_profile_state_count_mismatch:{expected}:{len(result)}\")\n    return result\n'''
    text = replace_once(
        text,
        "\ndef _chunks(rows: tuple[ProductHomologationRow, ...], size: int) -> Iterable[tuple[ProductHomologationRow, ...]]:\n",
        fetch_state + "\n\ndef _chunks(rows: tuple[ProductHomologationRow, ...], size: int) -> Iterable[tuple[ProductHomologationRow, ...]]:\n",
    )
    old_apply = '''def _apply_stage(url: str, token: str, before: dict[str, int], expected: int) -> None:\n    steps = [\n        (\"drop_guard\", \"DROP TABLE IF EXISTS temp.homologation_guard\", ()),\n        (\"guard_table\", \"CREATE TEMP TABLE homologation_guard(value INTEGER NOT NULL CHECK(value=0)) STRICT\", ()),\n        (\"begin\", \"BEGIN IMMEDIATE\", ()),\n        (\"guard_stage\", f\"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM {STAGE_TABLE}\", (expected,)),\n        (\"guard_products_before\", \"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM products\", (before[\"products\"],)),\n        (\"guard_history_before\", \"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM price_history\", (before[\"price_history\"],)),\n        (\"guard_runs_before\", \"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM scrape_runs\", (before[\"scrape_runs\"],)),\n        (\"upsert_profiles\", _TARGET_UPSERT, ()),\n        (\"guard_profile_count\", f\"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM {TABLE_NAME}\", (expected,)),\n        (\"guard_fk\", \"INSERT INTO homologation_guard SELECT COUNT(*) FROM pragma_foreign_key_check\", ()),\n        (\"commit\", \"COMMIT\", ()),\n    ]\n    _run_batch(url, token, steps)\n'''
    new_apply = '''def _apply_stage(\n    url: str,\n    token: str,\n    before: dict[str, int],\n    *,\n    staged_expected: int,\n    profile_expected: int,\n) -> None:\n    steps = [\n        (\"drop_guard\", \"DROP TABLE IF EXISTS temp.homologation_guard\", ()),\n        (\"guard_table\", \"CREATE TEMP TABLE homologation_guard(value INTEGER NOT NULL CHECK(value=0)) STRICT\", ()),\n        (\"begin\", \"BEGIN IMMEDIATE\", ()),\n        (\"guard_stage\", f\"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM {STAGE_TABLE}\", (staged_expected,)),\n        (\"guard_products_before\", \"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM products\", (before[\"products\"],)),\n        (\"guard_history_before\", \"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM price_history\", (before[\"price_history\"],)),\n        (\"guard_runs_before\", \"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM scrape_runs\", (before[\"scrape_runs\"],)),\n        (\"upsert_profiles\", _TARGET_UPSERT, ()),\n        (\"guard_profile_count\", f\"INSERT INTO homologation_guard SELECT CASE WHEN COUNT(*)=? THEN 0 ELSE 1 END FROM {TABLE_NAME}\", (profile_expected,)),\n        (\"guard_fk\", \"INSERT INTO homologation_guard SELECT COUNT(*) FROM pragma_foreign_key_check\", ()),\n        (\"commit\", \"COMMIT\", ()),\n    ]\n    _run_batch(url, token, steps)\n'''
    text = replace_once(text, old_apply, new_apply)
    old_body = '''    before = _source_preflight(database_url, auth_token)\n    _ensure_schema(database_url, auth_token)\n    after_schema = _preflight(database_url, auth_token)\n    if after_schema != before:\n        raise SnapshotError(\"homologation_source_changed_during_schema_transition\")\n\n    products = _fetch_products(database_url, auth_token)\n    if len(products) != before[\"products\"]:\n        raise SnapshotError(\"homologation_source_changed_during_read\")\n    derived = build_homologation_rows(\n        products,\n        updated_at_utc=updated_at_utc,\n        normalization_version=NORMALIZATION_VERSION,\n    )\n    delta: dict[str, int] = {}\n    post: dict[str, object] = {}\n    try:\n        _stage_rows(database_url, auth_token, derived)\n        delta = _delta_counts(database_url, auth_token)\n        _apply_stage(database_url, auth_token, before, len(derived))\n        post = _postflight(database_url, auth_token, before, len(derived))\n    finally:\n        _drop_stage(database_url, auth_token)\n    return {\n        \"normalization_version\": NORMALIZATION_VERSION,\n        \"processed\": len(derived),\n        **delta,\n        **post,\n    }\n'''
    new_body = '''    before = _source_preflight(database_url, auth_token)\n    if before[\"profiles\"] == 0:\n        _ensure_schema(database_url, auth_token)\n        after_schema = _preflight(database_url, auth_token)\n        if after_schema != before:\n            raise SnapshotError(\"homologation_source_changed_during_schema_transition\")\n\n    products = _fetch_products(database_url, auth_token)\n    if len(products) != before[\"products\"]:\n        raise SnapshotError(\"homologation_source_changed_during_read\")\n    derived = build_homologation_rows(\n        products,\n        updated_at_utc=updated_at_utc,\n        normalization_version=NORMALIZATION_VERSION,\n    )\n    derived_state = {\n        row.product_id: (row.profile_hash, row.normalization_version)\n        for row in derived\n    }\n    existing_state = _fetch_profile_state(database_url, auth_token)\n    extra_profiles = set(existing_state) - set(derived_state)\n    if extra_profiles:\n        raise SnapshotError(\"homologation_profile_ids_not_in_products\")\n\n    changed = tuple(\n        row for row in derived\n        if existing_state.get(row.product_id) != (row.profile_hash, row.normalization_version)\n    )\n    if not changed:\n        post = _postflight(database_url, auth_token, before, len(derived))\n        return {\n            \"normalization_version\": NORMALIZATION_VERSION,\n            \"processed\": len(derived),\n            \"inserted\": 0,\n            \"updated\": 0,\n            \"unchanged\": len(derived),\n            \"no_op\": True,\n            \"staging_written\": False,\n            **post,\n        }\n\n    delta: dict[str, int] = {}\n    post: dict[str, object] = {}\n    try:\n        _stage_rows(database_url, auth_token, changed)\n        staged_delta = _delta_counts(database_url, auth_token)\n        _apply_stage(\n            database_url,\n            auth_token,\n            before,\n            staged_expected=len(changed),\n            profile_expected=len(derived),\n        )\n        post = _postflight(database_url, auth_token, before, len(derived))\n        delta = {\n            \"inserted\": staged_delta[\"inserted\"],\n            \"updated\": staged_delta[\"updated\"],\n            \"unchanged\": len(derived) - staged_delta[\"inserted\"] - staged_delta[\"updated\"],\n        }\n    finally:\n        _drop_stage(database_url, auth_token)\n    return {\n        \"normalization_version\": NORMALIZATION_VERSION,\n        \"processed\": len(derived),\n        \"no_op\": False,\n        \"staging_written\": True,\n        **delta,\n        **post,\n    }\n'''
    text = replace_once(text, old_body, new_body)
    BACKFILL.write_text(text, encoding="utf-8")


def patch_workflow() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "      - name: Refrescar homologación derivada\n"
    if marker in text:
        return
    anchor = "      - name: Publicar evidencia\n        if: always()\n"
    block = '''      - name: Refrescar homologación derivada\n        working-directory: precios-supermercados-sps\n        env:\n          TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}\n          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}\n        run: |\n          mkdir -p run-artifacts/homologation\n          python scripts/backfill_homologacion_turso.py \\\n            --updated-at-utc \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" \\\n            | tee run-artifacts/homologation/daily-refresh.json\n\n'''
    if text.count(anchor) != 1:
        raise SystemExit(f"workflow_anchor_failed:{text.count(anchor)}")
    text = text.replace(anchor, block + anchor, 1)
    WORKFLOW.write_text(text, encoding="utf-8")


def main() -> None:
    patch_backfill()
    patch_workflow()
    print("HOMOLOGATION_DAILY_REFRESH_PATCH_OK=1")


if __name__ == "__main__":
    main()
