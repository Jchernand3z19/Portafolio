from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

import precios_supermercados.la_colonia_initial_snapshot as snapshot
from precios_supermercados.bigquery_adapter import BigQueryAdapter, FakeBigQueryClient
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


def test_full_snapshot_builds_and_applies_existing_bigquery_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_snapshot(tmp_path, monkeypatch)
    plan = snapshot.build_la_colonia_initial_snapshot_bigquery_plan(path)

    assert plan.scrape_run_id == LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID
    assert plan.row_counts[PRODUCTOS.name] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert plan.row_counts[PRECIOS_HISTORICOS.name] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert plan.row_counts[INVENTARIO_HISTORICO.name] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert plan.row_counts[PRODUCT_MAPPING.name] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert plan.row_counts[SCRAPE_RUNS.name] == 1
    run = plan.rows[SCRAPE_RUNS.name][0]
    assert run["catalog_accepted"] is True
    assert run["commercial_update_allowed"] is True
    assert run["catalog_products_reported"] == LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS
    assert run["unique_products_extracted"] == LA_COLONIA_INITIAL_SNAPSHOT_PRODUCTS
    assert run["skus_extracted"] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert run["skus_with_price"] == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert run["catalog_product_coverage"] == Decimal("1")
    assert any(
        row["location_id"] == "la_colonia_sps" and row["extraction_enabled"] is False
        for row in plan.rows["locations"]
    )

    client = FakeBigQueryClient()
    adapter = BigQueryAdapter(client, dataset_id="precios_sps")
    adapter.bootstrap()
    result = adapter.apply(plan)

    assert result.exact_run_replay is False
    assert client.count("precios_sps", PRODUCTOS.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", PRECIOS_HISTORICOS.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", INVENTARIO_HISTORICO.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", PRODUCT_MAPPING.name) == LA_COLONIA_INITIAL_SNAPSHOT_OFFERS
    assert client.count("precios_sps", SCRAPE_RUNS.name) == 1

    replay = adapter.apply(plan)
    assert replay.exact_run_replay is True
