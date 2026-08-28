from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actualizar_mvp_sqlite_la_colonia as sqlite_updater  # noqa: E402
import actualizar_mvp_turso_la_colonia as turso_updater  # noqa: E402


def product(
    key: str = "sku-1", pid: str = "product-1", item: str = "item-1",
    price: str = "100.00", availability: str = "in_stock",
) -> dict[str, object]:
    return {
        "availability": availability, "brand": "Marca", "category": "Categoria",
        "current_price": price, "ean": f"ean-{key}", "is_promotion": price != "100.00",
        "item_id": item, "presentation": None, "product_id": pid, "reference": f"ref-{key}",
        "reported_regular_price": "100.00" if price != "100.00" else None,
        "source_key": key, "source_key_type": "item_id", "source_name": f"Producto {key}",
    }


def snapshot(
    when: str, rows: list[dict[str, object]], location: str = "la_colonia_sps"
) -> bytes:
    total = len({str(row["product_id"]) for row in rows})
    return json.dumps({
        "result": "success", "supermarket_id": "la_colonia", "location_id": location,
        "city": sqlite_updater.LOCATIONS[location], "catalog_complete": True,
        "validation_passed": True, "location_verified_same_run": True,
        "observed_at_utc": when, "skus_extracted": len(rows), "skus_with_price": len(rows),
        "catalog_products_reported": total, "unique_products_extracted": total, "products": rows,
    }, separators=(",", ":")).encode()


def database(path: Path) -> Path:
    sqlite_updater.initialize_database(path)
    return path


def apply_remote_sql_locally(
    path: Path, raw: bytes, *, run_id: str, artifact_id: str = "artifact"
) -> None:
    snap = sqlite_updater.validate_snapshot_bytes(raw)
    steps = turso_updater._mutation_steps(
        turso_updater._normalised_json(snap),
        location_id=str(snap["location_id"]),
        observed_at=str(snap["observed_at_utc"]),
        run_id=run_id,
        sku_count=len(snap["products"]),
        catalog_count=int(snap["catalog_products_reported"]),
        artifact_id=artifact_id,
        digest=hashlib.sha256(raw).hexdigest(),
    )
    con = sqlite3.connect(path)
    try:
        for _, sql, args in steps:
            con.execute(sql, args)
    finally:
        con.close()


def dump(path: Path) -> dict[str, list[tuple[object, ...]]]:
    con = sqlite3.connect(path)
    try:
        result = {}
        for table in turso_updater.EXPECTED_TABLES:
            rows = [tuple(row) for row in con.execute(f"SELECT * FROM {table}").fetchall()]
            result[table] = sorted(rows, key=repr)
        return result
    finally:
        con.close()


def test_set_based_turso_sql_matches_sqlite_updater(tmp_path: Path) -> None:
    reference = database(tmp_path / "reference.db")
    candidate = database(tmp_path / "candidate.db")
    initial = snapshot("2026-08-28T01:00:00Z", [product()])
    for path in (reference, candidate):
        sqlite_updater.apply_snapshot(
            path, initial, run_id="run-1", source_artifact_id="artifact-1"
        )

    observations = [
        snapshot("2026-08-28T02:00:00Z", [product()]),
        snapshot("2026-08-28T03:00:00Z", [
            product(price="90.00", availability="out_of_stock"),
            product("sku-2", "product-2", "item-2"),
        ]),
        snapshot("2026-08-28T04:00:00Z", [
            product(price="90.00", availability="out_of_stock"),
            product("sku-2", "product-2", "item-2"),
        ], location="la_colonia_tgu"),
    ]
    for index, raw in enumerate(observations, start=2):
        run_id = f"run-{index}"
        artifact = f"artifact-{index}"
        sqlite_updater.apply_snapshot(
            reference, raw, run_id=run_id, source_artifact_id=artifact
        )
        apply_remote_sql_locally(candidate, raw, run_id=run_id, artifact_id=artifact)
        assert dump(candidate) == dump(reference)


def test_mutation_batch_is_atomic_chain() -> None:
    raw = snapshot("2026-08-28T02:00:00Z", [product()])
    snap = sqlite_updater.validate_snapshot_bytes(raw)
    steps = turso_updater._mutation_steps(
        turso_updater._normalised_json(snap),
        location_id="la_colonia_sps", observed_at=snap["observed_at_utc"],
        run_id="run-2", sku_count=1, catalog_count=1,
        artifact_id=None, digest=hashlib.sha256(raw).hexdigest(),
    )
    request = turso_updater._batch_request(steps)
    batch = request["batch"]["steps"]
    assert batch[0].get("condition") is None
    for index in range(1, len(steps)):
        assert batch[index]["condition"] == {"type": "ok", "step": index - 1}
    rollback = batch[-1]
    assert rollback["stmt"]["sql"] == "ROLLBACK"
    referenced = {cond["step"] for cond in rollback["condition"]["conds"]}
    assert referenced == set(range(1, len(steps)))


def test_out_of_order_change_is_rejected_before_persistent_mutation(tmp_path: Path) -> None:
    path = database(tmp_path / "mvp.db")
    initial = snapshot("2026-08-28T03:00:00Z", [product()])
    sqlite_updater.apply_snapshot(path, initial, run_id="run-1")

    older_change = snapshot("2026-08-28T02:00:00Z", [product(price="90.00")])
    before = dump(path)
    with pytest.raises(sqlite3.IntegrityError):
        apply_remote_sql_locally(path, older_change, run_id="run-2")
    assert dump(path) == before


def test_exact_replay_short_circuits_remote_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = snapshot("2026-08-28T02:00:00Z", [product()])
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(
        turso_updater, "_preflight",
        lambda *args, **kwargs: {
            "location_id": "la_colonia_sps", "run_status": "success", "sha": digest
        },
    )

    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("no debe mutar Turso en replay exacto")

    monkeypatch.setattr(turso_updater, "_run_batch", unexpected)
    result = turso_updater.persist_snapshot(
        raw, database_url="libsql://example.turso.io",
        auth_token="token", run_id="run-2",
    )
    assert result["replayed"] is True
