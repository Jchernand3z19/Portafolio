from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import migrar_mvp_paiz as paiz  # noqa: E402
import migrar_mvp_pricesmart as pricesmart  # noqa: E402
import migrar_mvp_turso_walmart_pricesmart as migration  # noqa: E402
import migrar_mvp_walmart as walmart  # noqa: E402
from actualizar_mvp_sqlite_la_colonia import SnapshotError  # noqa: E402


def _rows(rows):
    return [[name, sql] for name, sql in rows]


def _state(rows, count=7):
    return {
        "schema": _rows(rows),
        "counts": {table: count for table in migration.BASE_TABLES},
    }


def test_next_stage_recognizes_walmart_then_pricesmart_schema():
    assert migration._next_stage(_rows(walmart.target_schema())) == "pricesmart"
    assert migration._next_stage(_rows(pricesmart.target_schema())) is None


def test_next_stage_recognizes_post_paiz_schema_as_already_ready():
    rows = []
    for name, sql in pricesmart.target_schema():
        if name == "price_history":
            sql = sql.replace(paiz.OLD_FRAGMENT, paiz.NEW_FRAGMENT, 1)
        elif name == paiz.LOCATION_INDEX_NAME:
            sql = paiz.NEW_LOCATION_INDEX_SQL
        rows.append([name, sql])
    assert migration._next_stage(rows) is None


def test_next_stage_rejects_unknown_schema(monkeypatch):
    rows = _rows(walmart.target_schema())
    monkeypatch.setattr(walmart, "schema_ready", lambda _: False)
    monkeypatch.setattr(walmart, "fingerprint", lambda _: "unexpected")
    with pytest.raises(SnapshotError, match="walmart_unrecognized_pre_migration_schema"):
        migration._next_stage(rows)


def test_next_stage_accepts_only_exact_legacy_fingerprint_for_walmart(monkeypatch):
    rows = _rows(walmart.target_schema())
    monkeypatch.setattr(walmart, "schema_ready", lambda _: False)
    monkeypatch.setattr(walmart, "fingerprint", lambda _: walmart.LEGACY_FINGERPRINT)
    assert migration._next_stage(rows) == "walmart"


def test_migrate_turso_runs_only_pending_pricesmart_stage(monkeypatch):
    states = [
        _state(walmart.target_schema()),
        _state(pricesmart.target_schema()),
    ]
    calls = []

    monkeypatch.setattr(migration, "_read_state", lambda *_: states.pop(0))
    monkeypatch.setattr(migration, "_run_batch", lambda url, token, steps: calls.append((url, token, steps)))

    result = migration.migrate_turso("libsql://example", "token")

    assert result["schema_ready"] is True
    assert result["migrated"] is True
    assert result["stages"] == ["pricesmart"]
    assert len(calls) == 1
    assert calls[0][2] == pricesmart.migration_steps()


def test_migrate_turso_fails_closed_if_row_counts_change(monkeypatch):
    before = _state(walmart.target_schema(), count=7)
    after = _state(pricesmart.target_schema(), count=7)
    after["counts"] = dict(after["counts"])
    after["counts"]["price_history"] = 6
    states = [before, after]

    monkeypatch.setattr(migration, "_read_state", lambda *_: states.pop(0))
    monkeypatch.setattr(migration, "_run_batch", lambda *_: [])

    with pytest.raises(SnapshotError, match="mvp_turso_migration_row_count_mismatch:pricesmart"):
        migration.migrate_turso("libsql://example", "token")


def test_migrate_turso_requires_credentials():
    with pytest.raises(SnapshotError, match="turso_credentials_missing"):
        migration.migrate_turso("", "")
