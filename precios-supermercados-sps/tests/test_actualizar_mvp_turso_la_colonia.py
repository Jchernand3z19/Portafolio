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
    # Hrana ejecuta las sentencias anteriores a BEGIN en autocommit. Esta conexión
    # reproduce ese comportamiento y permite comprobar la misma secuencia SQL.
    con = sqlite3.connect(path, isolation_level=None)
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


def test_sequential_locations_clean_temp_staging_in_reused_session(tmp_path: Path) -> None:
    """Regression for Turso run 33646585900: Hrana retained TEMP names after close."""
    path = database(tmp_path / "mvp.db")
    con = sqlite3.connect(path, isolation_level=None)
    try:
        observations = [
            snapshot("2026-09-02T01:00:00Z", [product()], "la_colonia_sps"),
            snapshot("2026-09-02T01:01:00Z", [product()], "la_colonia_tgu"),
        ]
        for index, raw in enumerate(observations, start=1):
            snap = sqlite_updater.validate_snapshot_bytes(raw)
            steps = turso_updater._mutation_steps(
                turso_updater._normalised_json(snap),
                location_id=str(snap["location_id"]),
                observed_at=str(snap["observed_at_utc"]),
                run_id=f"sequential-{index}",
                sku_count=1,
                catalog_count=1,
                artifact_id=None,
                digest=hashlib.sha256(raw).hexdigest(),
            )
            for _, sql, args in steps:
                con.execute(sql, args)
        assert con.execute(
            "SELECT location_id FROM scrape_runs ORDER BY scrape_run_id"
        ).fetchall() == [("la_colonia_sps",), ("la_colonia_tgu",)]
    finally:
        con.close()


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
    begin = next(i for i, step in enumerate(steps) if step[0] == "begin")
    assert begin > 0
    rollback = batch[-1]
    assert rollback["stmt"]["sql"] == "ROLLBACK"
    referenced = {cond["step"] for cond in rollback["condition"]["conds"]}
    assert referenced == set(range(begin + 1, len(steps)))


def test_batch_response_is_parsed_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    steps = [("begin", "BEGIN", ()), ("commit", "COMMIT", ())]
    fake = {
        "results": [
            {
                "type": "ok",
                "response": {
                    "type": "batch",
                    "result": {
                        "step_results": [
                            {"cols": [], "rows": [], "affected_row_count": 0},
                            {"cols": [], "rows": [], "affected_row_count": 0},
                            None,
                        ],
                        "step_errors": [None, None, None],
                    },
                },
            },
            {"type": "ok", "response": {"type": "close"}},
        ]
    }
    monkeypatch.setattr(turso_updater, "_pipeline", lambda *args, **kwargs: fake)
    result = turso_updater._run_batch("libsql://example.turso.io", "token", steps)
    assert result == fake["results"][0]["response"]["result"]["step_results"][:-1]


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


def test_unchanged_catalog_history_check_has_bounded_sql_work(tmp_path: Path) -> None:
    """No volver a recorrer todo incoming por cada periodo sin cambios (N²)."""
    path = database(tmp_path / "mvp.db")
    count = 512
    rows = [product(f"sku-{i}", f"product-{i}", f"item-{i}") for i in range(count)]
    initial = snapshot("2026-08-28T01:00:00Z", rows)
    apply_remote_sql_locally(path, initial, run_id="run-1")
    unchanged = snapshot("2026-08-28T02:00:00Z", rows)
    snap = sqlite_updater.validate_snapshot_bytes(unchanged)
    steps = turso_updater._mutation_steps(
        turso_updater._normalised_json(snap),
        location_id="la_colonia_sps", observed_at=snap["observed_at_utc"],
        run_id="run-2", sku_count=count, catalog_count=count,
        artifact_id=None, digest=hashlib.sha256(unchanged).hexdigest(),
    )
    instructions = 0

    def budget() -> int:
        nonlocal instructions
        instructions += 100
        return int(instructions > count * 100)

    con = sqlite3.connect(path, isolation_level=None)
    try:
        for name, sql, args in steps:
            if name == "close_history":
                # Trabajo real de la VM; no depende de latencia del runner ni de
                # nombres de índices en EXPLAIN. El scan correlacionado agota el límite.
                con.set_progress_handler(budget, 100)
            try:
                con.execute(sql, args)
            finally:
                con.set_progress_handler(None, 0)
        assert instructions > 0
        assert con.execute("SELECT COUNT(*) FROM price_history").fetchone() == (count,)
        assert con.execute("SELECT COUNT(*) FROM scrape_runs").fetchone() == (2,)
        assert con.execute(
            "SELECT COUNT(*) FROM price_history WHERE valid_to_utc IS NOT NULL"
        ).fetchone() == (0,)
    finally:
        con.close()
