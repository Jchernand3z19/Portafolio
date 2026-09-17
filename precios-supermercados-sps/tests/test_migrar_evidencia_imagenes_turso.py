from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import migrar_evidencia_imagenes_turso as migration  # noqa: E402
from actualizar_mvp_sqlite_la_colonia import SnapshotError  # noqa: E402


def state(*, table: bool, indexes: bool = False, count: int = 0) -> dict[str, object]:
    return {
        "table_exists": table,
        "columns": migration.EXPECTED_COLUMNS if table else (),
        "indexes": set(migration.INDEX_NAMES) if indexes else set(),
        "base_counts": {name: 7 for name in migration.BASE_TABLES},
        "image_count": count,
    }


def test_target_schema_creates_valid_temporal_image_table() -> None:
    ddl = migration.target_objects()
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE supermarkets(supermarket_id TEXT PRIMARY KEY);
            CREATE TABLE locations(
                location_id TEXT,
                supermarket_id TEXT,
                PRIMARY KEY(location_id,supermarket_id)
            );
            CREATE TABLE products(
                product_id INTEGER,
                supermarket_id TEXT,
                PRIMARY KEY(product_id,supermarket_id)
            );
            CREATE TABLE scrape_runs(scrape_run_id TEXT PRIMARY KEY);
            """
        )
        con.execute(ddl[migration.TABLE_NAME])
        for name in migration.INDEX_NAMES:
            con.execute(ddl[name])
        columns = tuple(
            row[1] for row in con.execute("PRAGMA table_info(product_images)")
        )
        assert columns == migration.EXPECTED_COLUMNS
    finally:
        con.close()


def test_migration_creates_only_missing_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    states = [state(table=False), state(table=True, indexes=True)]
    captured: list[list[tuple[str, str, tuple[object, ...]]]] = []
    monkeypatch.setattr(migration, "_read_state", lambda *_: states.pop(0))
    monkeypatch.setattr(
        migration,
        "_run_batch",
        lambda _url, _token, steps: captured.append(steps),
    )

    result = migration.migrate_turso("libsql://example", "token")

    assert result["migrated"] is True
    names = [name for name, _, _ in captured[0]]
    assert names == [
        "begin",
        "create_product_images",
        "create_idx_product_images_current",
        "create_idx_product_images_current_primary",
        "commit",
    ]


def test_migration_is_noop_when_schema_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        migration, "_read_state", lambda *_: state(table=True, indexes=True, count=9)
    )
    monkeypatch.setattr(
        migration,
        "_run_batch",
        lambda *_: pytest.fail("ready schema must not be mutated"),
    )
    result = migration.migrate_turso("libsql://example", "token")
    assert result["migrated"] is False
    assert result["image_count"] == 9


def test_migration_rejects_unrecognized_existing_table() -> None:
    invalid = state(table=True)
    invalid["columns"] = ("unexpected",)
    with pytest.raises(SnapshotError, match="product_images_unrecognized_schema"):
        migration.migration_steps(invalid)


def test_migration_requires_credentials() -> None:
    with pytest.raises(SnapshotError, match="turso_credentials_missing"):
        migration.migrate_turso("", "")
