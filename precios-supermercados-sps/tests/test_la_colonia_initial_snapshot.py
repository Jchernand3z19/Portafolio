from __future__ import annotations

import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import precios_supermercados.la_colonia_initial_snapshot as snapshot
from precios_supermercados.bigquery_adapter import FakeBigQueryClient
from precios_supermercados.bigquery_contract import (
    INVENTARIO_HISTORICO,
    PRECIOS_HISTORICOS,
    PRODUCT_MAPPING,
    PRODUCTOS,
    SCRAPE_RUNS,
)
from precios_supermercados.commercial_persistence_guard import (
    LA_COLONIA_INITIAL_SNAPSHOT_OFFERS,
    LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS,
    LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID,
)
from precios_supermercados.enums import LocationStatus


def _synthetic_snapshot() -> dict[str, object]:
    rows = []
    for index in range(1, LA_COLONIA_INITIAL_SNAPSHOT_OFFERS + 1):
        product_id = str(
            index
            if index <= LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS
            else index - LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS
        )
        rows.append(
            {
                "availability": "in_stock",
                "brand": "Marca Demo",
                "category": "Supermercado > Prueba",
                "current_price": "10.00",
                "ean": str(index),
                "is_promotion": False,
                "item_id": str(index),
                "presentation": "1 unidad",
                "product_id": product_id,
                "reference": f"REF-{index}",
                "reported_regular_price": None,
                "source_key": str(index),
                "source_key_type": "internal_id",
                "source_name": f"Producto {index} 1 unidad",
            }
        )
    return {
        "result": "success",
        "supermarket_id": "la_colonia",
        "location_id": "la_colonia_sps",
        "catalog_complete": True,
        "validation_passed": True,
        "location_verified_same_run": True,
        "catalog_products_reported": LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS,
        "unique_products_extracted": LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS,
        "skus_extracted": LA_COLONIA_INITIAL_SNAPSHOT_OFFERS,
        "skus_with_price": LA_COLONIA_INITIAL_SNAPSHOT_OFFERS,
        "catalog_product_coverage": 1.0,
        "extraction_enabled": False,
        "observed_at_utc": "2026-08-26T02:40:57Z",
        "products": rows,
    }


def _write_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "full-catalog.json"
    path.write_text(
        json.dumps(_synthetic_snapshot(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(snapshot, "LA_COLONIA_INITIAL_SNAPSHOT_JSON_SHA256", digest)
    return path


def test_real_snapshot_json_digest_is_versioned() -> None:
    assert snapshot.LA_COLONIA_INITIAL_SNAPSHOT_JSON_SHA256 == (
        "2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50"
    )


def test_loader_rejects_any_other_file_before_interpreting_rows(tmp_path: Path) -> None:
    path = tmp_path / "full-catalog.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(snapshot.InitialSnapshotError, match="snapshot_json_digest_mismatch"):
        snapshot.load_la_colonia_initial_snapshot(path)


def test_full_snapshot_shape_converts_to_validated_offers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_snapshot(tmp_path, monkeypatch)

    offers = snapshot.load_la_colonia_initial_snapshot(path)

    assert len(offers) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert len({item.offer.source_product_id for item in offers}) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert all(item.offer.location_status is LocationStatus.CONFIRMED for item in offers)
    assert all(item.offer.location_id == "la_colonia_sps" for item in offers)
    assert all(item.offer.product_url is None for item in offers)
    assert all(item.offer.scrape_run_id == LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID for item in offers)


def test_full_snapshot_entrypoint_applies_and_reconciles_bigquery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_snapshot(tmp_path, monkeypatch)
    client = FakeBigQueryClient()

    result = snapshot.apply_la_colonia_initial_snapshot_bigquery(
        path,
        client=client,
        dataset_id="precios_sps",
    )

    assert result.exact_run_replay is False
    assert client.count("precios_sps", PRODUCTOS.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", PRECIOS_HISTORICOS.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", INVENTARIO_HISTORICO.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", PRODUCT_MAPPING.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", SCRAPE_RUNS.name) == 1

    run = client.get_row(
        "precios_sps",
        SCRAPE_RUNS.name,
        (LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID,),
    )
    assert run is not None
    assert run["catalog_accepted"] is True
    assert run["commercial_update_allowed"] is True
    assert run["catalog_products_reported"] == LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS
    assert run["unique_products_extracted"] == LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS
    assert run["skus_extracted"] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert run["skus_with_price"] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert run["catalog_product_coverage"] == Decimal("1")
    assert any(
        row["location_id"] == "la_colonia_sps" and row["extraction_enabled"] is False
        for row in client.read_rows("precios_sps", "locations")
    )

    replay = snapshot.apply_la_colonia_initial_snapshot_bigquery(
        path,
        client=client,
        dataset_id="precios_sps",
    )
    assert replay.exact_run_replay is True


def test_full_snapshot_entrypoint_applies_rehydrates_and_replays_on_real_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_snapshot(tmp_path, monkeypatch)
    connection = sqlite3.connect(":memory:")

    result = snapshot.apply_la_colonia_initial_snapshot_turso(
        path,
        connection=connection,
    )

    assert result.exact_run_replay is False
    for table in ("source_products", "offers_current", "offer_history"):
        assert connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert connection.execute('SELECT COUNT(*) FROM "scrape_runs"').fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM offers_current WHERE location_id = ?",
        ("la_colonia_sps",),
    ).fetchone()[0] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert connection.execute(
        "SELECT COUNT(*) FROM offers_current WHERE current_price_minor = 1000"
    ).fetchone()[0] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS

    before_history = connection.execute('SELECT COUNT(*) FROM "offer_history"').fetchone()[0]
    replay = snapshot.apply_la_colonia_initial_snapshot_turso(
        path,
        connection=connection,
    )
    assert replay.exact_run_replay is True
    assert connection.execute('SELECT COUNT(*) FROM "offer_history"').fetchone()[0] == before_history
    assert connection.execute('SELECT COUNT(*) FROM "scrape_runs"').fetchone()[0] == 1
    connection.close()
