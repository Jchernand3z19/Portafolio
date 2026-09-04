"""Pruebas offline del contrato demostrado de Comisariato Los Andes SPS."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from precios_supermercados.scrapers.comisariato_los_andes import (
    CATALOG_ENDPOINT,
    IMAGE_BASE,
    LOCATION_ID,
    LosAndesError,
    PAGE_SIZE,
    STORE_ID,
    build_catalog_request,
    build_store_request,
    parse_catalog_page,
    parse_products,
    reconcile_capture,
)

FIXTURE = Path(__file__).parent / "fixtures/comisariato_los_andes/catalog_page_sample.json"


def source_product(**updates):
    product = {
        "availibilityCount": 8,
        "brandId": 9,
        "brandName": "Marca",
        "code": "0001-000000000000123",
        "discount": None,
        "discountTwo": None,
        "images": [{"active": "1", "fileName": "p.webp", "position": 0}],
        "is_adult": "0",
        "listPrice": 0,
        "materialGroupCode": "100",
        "materialGroupName": "ABARROTES",
        "name": "Producto de prueba",
        "newPrice": 10,
        "oldPrice": None,
        "price": 10,
        "stock": 8,
        "unitMeasureCode": "UN",
        "unitMeasureName": "Unidad",
    }
    product.update(updates)
    return product


def test_request_contract_is_sps_store_bound_and_bounded():
    assert build_store_request() == {
        "business_partner": 1,
        "cityCode": None,
        "pickPosition": "PD",
    }
    url, body = build_catalog_request(200)
    assert url == f"{CATALOG_ENDPOINT}?skip=200&take={PAGE_SIZE}"
    assert body["businessPartner"] == 1
    assert body["storeId"] == STORE_ID == 1
    assert body["officeCode"] == "00"
    assert body["type"] == "PD"
    assert body["source"] == "WEB"
    assert body["hidden"] == "0"
    with pytest.raises(LosAndesError, match="take_above_verified_page_size"):
        build_catalog_request(0, PAGE_SIZE + 1)


def test_proven_sample_normalizes_identity_price_availability_and_image():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed = parse_catalog_page(payload, expected_skip=0, take=6)
    assert parsed["total_items"] == 6646
    assert parsed["total_pages"] == 1108
    assert len(parsed["rows"]) == 6
    by_code = {row["source_key"]: row for row in parsed["rows"]}
    first = by_code["0001-000099001005224"]
    assert first["source_key_type"] == "sku"
    assert first["product_id"] == first["item_id"] == first["source_key"]
    assert first["current_price"] == "149.95"
    assert first["reported_regular_price"] is None
    assert first["is_promotion"] is False
    assert first["availability"] == "in_stock"
    assert first["brand"] == "Marca COMANDES"
    assert first["category"] == "READY TO GO"
    assert parsed["source_details"][first["source_key"]]["image_url"] == (
        IMAGE_BASE + "_0001_Ready_to_go_aderezo_para_ensaladas_-_99001005224_74ae411_2b2f61b.webp"
    )
    unavailable = by_code["0001-000000007400051"]
    assert unavailable["availability"] == "out_of_stock"
    assert unavailable["current_price"] == "18.90"


def test_explicit_regular_price_is_the_only_promotion_evidence():
    product = source_product(oldPrice=12, newPrice=9.5, price=9.5)
    rows, details = parse_products([product])
    row = rows[0]
    assert (row["current_price"], row["reported_regular_price"], row["is_promotion"]) == (
        "9.50",
        "12.00",
        True,
    )
    assert details[row["source_key"]]["regular_price_evidence"] == ["oldPrice"]


def test_list_price_can_corrobate_regular_price_without_overwriting_effective_price():
    product = source_product(oldPrice=12, listPrice=12, newPrice=9.5, price=9.5)
    rows, details = parse_products([product])
    row = rows[0]
    assert row["current_price"] == "9.50"
    assert row["reported_regular_price"] == "12.00"
    assert details[row["source_key"]]["regular_price_evidence"] == ["oldPrice", "listPrice"]


@pytest.mark.parametrize(
    "updates,reason",
    [
        ({"code": ""}, "source_code_invalid"),
        ({"name": ""}, "source_name_invalid"),
        ({"newPrice": -1, "price": -1}, "new_price_invalid"),
        ({"newPrice": 10, "price": 9}, "new_price_price_mismatch"),
        ({"newPrice": 10, "price": 10, "oldPrice": 9}, "oldPrice_below_current"),
        ({"newPrice": 10, "price": 10, "oldPrice": 12, "listPrice": 13}, "regular_price_signals_conflict"),
        ({"discount": 5}, "discount_without_regular_price_evidence"),
        ({"availibilityCount": -1}, "availability_signal_invalid"),
    ],
)
def test_ambiguous_or_invalid_source_signals_fail_closed(updates, reason):
    with pytest.raises(LosAndesError, match=reason):
        parse_products([source_product(**updates)])


def test_unpriced_product_requires_explicit_out_of_stock_signal():
    rows, details = parse_products([
        source_product(availibilityCount=0, newPrice=0, price=0, oldPrice=None, listPrice=0)
    ])
    row = rows[0]
    assert row["availability"] == "out_of_stock"
    assert row["current_price"] is None
    assert row["reported_regular_price"] is None
    assert row["is_promotion"] is None
    assert details[row["source_key"]]["price_status"] == "unavailable_unpriced"
    with pytest.raises(LosAndesError, match="unpriced_without_out_of_stock_signal"):
        parse_products([source_product(availibilityCount=None, newPrice=0, price=0)])


def test_missing_availability_is_preserved_as_unknown_when_price_exists():
    rows, details = parse_products([source_product(availibilityCount=None)])
    assert rows[0]["availability"] == "unknown"
    assert details[rows[0]["source_key"]]["source_availibility_count"] is None


def test_duplicate_source_code_is_rejected():
    product = source_product()
    with pytest.raises(LosAndesError, match="source_code_duplicate"):
        parse_products([product, copy.deepcopy(product)])


def test_page_metadata_must_match_offset_and_page_size():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    broken = copy.deepcopy(payload)
    broken["currentPage"] = 2
    with pytest.raises(LosAndesError, match="current_page_mismatch"):
        parse_catalog_page(broken, expected_skip=0, take=6)


def test_complete_capture_reconciles_only_from_hashed_raw(tmp_path):
    products = [
        source_product(code="0001-000000000000001", availibilityCount=3),
        source_product(code="0001-000000000000002", availibilityCount=0, name="Otro producto"),
    ]
    payload = {
        "currentPage": 1,
        "data": products,
        "itemPerPage": 100,
        "totalItems": 2,
        "totalPages": 1,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    response_name = "page-00000.json"
    (tmp_path / response_name).write_bytes(raw)
    url, body = build_catalog_request(0, 100)
    ledger = {
        "closed": True,
        "supermarket_id": "comisariato_los_andes",
        "location_id": LOCATION_ID,
        "store_id": 1,
        "office_code": "00",
        "location_two_code": 501,
        "concurrency": 1,
        "request_count": 2,
        "retry_count": 0,
        "final_total_items": 2,
        "pages": [
            {
                "skip": 0,
                "take": 100,
                "status": 200,
                "retries": 0,
                "url": url,
                "request_body": body,
                "response_file": response_name,
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "observed_at_utc": "2026-09-04T01:30:00Z",
            }
        ],
    }
    (tmp_path / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    snapshot = reconcile_capture(tmp_path)
    assert snapshot["catalog_complete"] is True
    assert snapshot["catalog_products_reported"] == 2
    assert snapshot["unique_products_extracted"] == 2
    assert snapshot["availability_counts"] == {"in_stock": 1, "out_of_stock": 1}
    assert snapshot["promotion_counts"] == {"promotion": 0, "not_promotion": 2, "unknown": 0}

    tampered = raw + b" "
    (tmp_path / response_name).write_bytes(tampered)
    with pytest.raises(LosAndesError, match="raw_file_hash_mismatch"):
        reconcile_capture(tmp_path)
