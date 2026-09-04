from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actualizar_mvp_turso_la_colonia as updater  # noqa: E402
from actualizar_mvp_sqlite_la_colonia import SnapshotError  # noqa: E402


def test_preflight_accepts_base_schema_and_optional_homologation_table_only() -> None:
    updater._validate_table_names(updater.EXPECTED_TABLES)
    updater._validate_table_names(
        updater.EXPECTED_TABLES | {"product_homologation_profiles"}
    )


def test_preflight_still_rejects_missing_or_unknown_tables() -> None:
    with pytest.raises(SnapshotError, match="turso_schema_mismatch"):
        updater._validate_table_names(updater.EXPECTED_TABLES - {"price_history"})
    with pytest.raises(SnapshotError, match="turso_schema_mismatch"):
        updater._validate_table_names(updater.EXPECTED_TABLES | {"unexpected_table"})
