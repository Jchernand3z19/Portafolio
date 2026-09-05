#!/usr/bin/env python3
"""Parche temporal idempotente: todos los persistidores aceptan la tabla derivada."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / "scripts" / "actualizar_mvp_turso_comisariato_los_andes.py",
    ROOT / "scripts" / "actualizar_mvp_turso_paiz.py",
)
TEST = ROOT / "tests" / "test_turso_homologation_schema_transition.py"


def patch_script(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("    EXPECTED_TABLES,\n", "")
    if "    _validate_table_names,\n" not in text:
        text = text.replace("    _stmt,\n)", "    _stmt,\n    _validate_table_names,\n)", 1)
    old = "    if {str(row[0]) for row in _execute_rows(results[0])} != EXPECTED_TABLES:\n        raise SnapshotError(\"turso_schema_mismatch\")\n"
    new = "    _validate_table_names(str(row[0]) for row in _execute_rows(results[0]))\n"
    if new not in text:
        if text.count(old) != 1:
            raise SystemExit(f"table_guard_patch_failed:{path.name}:{text.count(old)}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def patch_test() -> None:
    text = TEST.read_text(encoding="utf-8")
    marker = "test_all_turso_persistors_share_optional_derived_table_guard"
    if marker not in text:
        text += '''\n\ndef test_all_turso_persistors_share_optional_derived_table_guard() -> None:\n    for filename in (\n        \"actualizar_mvp_turso_comisariato_los_andes.py\",\n        \"actualizar_mvp_turso_paiz.py\",\n    ):\n        source = (ROOT / \"scripts\" / filename).read_text(encoding=\"utf-8\")\n        assert \"_validate_table_names(str(row[0]) for row in _execute_rows(results[0]))\" in source\n        assert \"!= EXPECTED_TABLES\" not in source\n'''
    TEST.write_text(text, encoding="utf-8")


def main() -> None:
    for path in TARGETS:
        patch_script(path)
    patch_test()
    print("HOMOLOGATION_TABLE_COMPAT_PATCH_OK=1")


if __name__ == "__main__":
    main()
