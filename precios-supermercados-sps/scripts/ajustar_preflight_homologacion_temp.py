#!/usr/bin/env python3
"""Parche temporal idempotente para compatibilidad del preflight diario."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "actualizar_mvp_turso_la_colonia.py"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"preflight_patch_contract_failed:{text.count(old)}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'EXPECTED_TABLES = {"supermarkets", "locations", "products", "price_history", "scrape_runs"}\n',
        'EXPECTED_TABLES = {"supermarkets", "locations", "products", "price_history", "scrape_runs"}\n'
        'OPTIONAL_DERIVED_TABLES = {"product_homologation_profiles"}\n\n\n'
        'def _validate_table_names(names: object) -> None:\n'
        '    try:\n'
        '        observed = {str(name) for name in names}\n'
        '    except TypeError as exc:\n'
        '        raise SnapshotError("turso_schema_mismatch") from exc\n'
        '    if not EXPECTED_TABLES <= observed:\n'
        '        raise SnapshotError("turso_schema_mismatch")\n'
        '    if not observed <= EXPECTED_TABLES | OPTIONAL_DERIVED_TABLES:\n'
        '        raise SnapshotError("turso_schema_mismatch")\n',
    )
    text = replace_once(
        text,
        '    if {str(row[0]) for row in _execute_rows(results[0])} != EXPECTED_TABLES:\n        raise SnapshotError("turso_schema_mismatch")\n',
        '    _validate_table_names(str(row[0]) for row in _execute_rows(results[0]))\n',
    )
    TARGET.write_text(text, encoding="utf-8")
    print("PRECHECK_PATCH_OK=1")


if __name__ == "__main__":
    main()
