from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from precios_supermercados.enums import AvailabilityStatus, LocationStatus, SourceKeyType
from precios_supermercados.scrapers.base import (
    BlockedResponseError,
    EmptyResponseError,
    HttpResponse,
    HttpStatusError,
    RateLimitedError,
    RobotsPolicyError,
    SafeHttpClient,
    StructureChangedError,
)
from precios_supermercados.scrapers.la_colonia import (
    LOCATION_EVIDENCE,
    LOCATION_ID,
    LaColoniaExtractor,
    decode_search_variables,
)

FIXTURES = Path(__file__).parent / "fixtures" / "la_colonia"
FIXED_TIME = datetime(2026, 8, 5, 4, 30, tzinfo=timezone.utc)


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def build_extractor() -> LaColoniaExtractor:
    return LaColoniaExtractor(clock=lambda: FIXED_TIME)


def parse_fixture(name: str = "product_search_page.json"):
    return build_extractor().parse_payload(
        load_fixture(name),
        scrape_run_id="run_la_colonia_test",
        source_url=build_extractor().build_page_url(),
        page_size=5,
    )


def test_parses_five_products_and_uses_raw_product_contract():
    result = parse_fixture()
    assert result.accepted is True
    assert len(result.products) == 5
    assert result.metrics.products_extracted == 5
    assert result.metrics.products_with_price == 3
    assert all(product.supermarket_id == "la_colonia" for product in result.products)


def test_packaged_product_has_price_brand_category_and_presentation():
    product = parse_fixture().products[0]
    assert product.source_name == "Malteada Sula Chocosula 473 Ml"
    assert product.source_brand == "Sula"
    assert product.source_presentation == "473 Ml"
    assert product.source_category.endswith("Leches saborizadas")
    assert product.raw_values["current_price"] == "19.9"
    assert product.raw_values["availability"] == AvailabilityStatus.IN_STOCK.value


def test_weighted_product_preserves_original_unit_without_conversion():
    product = parse_fixture().products[1]
    assert product.source_name == "Fresa X Lb"
    assert product.source_presentation == "X Lb"
    assert product.raw_values["measurement_unit"] == "lb"
    assert product.raw_values["unit_multiplier"] == "1"
    assert product.raw_values["weighted_product"] is True
    assert product.raw_values["current_price"] == "94.9"


def test_promotional_product_separates_current_and_reported_regular_price():
    product = parse_fixture().products[2]
    assert product.raw_values["current_price"] == "59.9"
    assert product.raw_values["reported_regular_price"] == "99.9"
    assert product.raw_values["is_promotion"] is True
    assert product.raw_values["promotion_evidence"] == ["40%"]


def test_equal_list_price_is_not_reported_as_tachado_or_promotion():
    product = parse_fixture().products[0]
    assert product.raw_values["source_list_price"] == "19.9"
    assert product.raw_values["reported_regular_price"] is None
    assert product.raw_values["is_promotion"] is False


def test_explicit_zero_quantity_is_out_of_stock():
    product = parse_fixture().products[3]
    assert product.raw_values["current_price"] is None
    assert product.raw_values["availability"] == AvailabilityStatus.OUT_OF_STOCK.value


def test_missing_price_and_seller_remain_unknown():
    product = parse_fixture().products[4]
    assert product.raw_values["current_price"] is None
    assert product.raw_values["availability"] == AvailabilityStatus.UNKNOWN.value


def test_missing_brand_category_and_presentation_are_not_invented():
    product = parse_fixture().products[4]
    assert product.source_brand is None
    assert product.source_category is None
    assert product.source_presentation is None
    assert product.image_url is None


def test_source_identity_prefers_internal_item_id():
    product = parse_fixture().products[0]
    assert product.source_key_type is SourceKeyType.INTERNAL_ID
    assert product.source_key == "2001"
    assert product.source_sku == "161729"


def test_product_has_stable_individual_url_and_source_image():
    product = parse_fixture().products[1]
    assert product.product_url == "https://www.lacolonia.com/fresa-x-lb-ref536/p"
    assert product.image_url.startswith("https://lacolonia.vtexassets.com/")


def test_uses_approved_unknown_online_location_values():
    product = parse_fixture().products[0]
    assert product.location_id == LOCATION_ID == "la_colonia_online"
    assert product.location_status is LocationStatus.UNKNOWN
    assert product.location_evidence == LOCATION_EVIDENCE
    assert product.location_confidence is None


def test_pagination_uses_non_overlapping_from_and_to_indices():
    extractor = build_extractor()
    first = decode_search_variables(extractor.build_page_url(page=1, page_size=5))
    second = decode_search_variables(extractor.build_page_url(page=2, page_size=5))
    assert (first["from"], first["to"]) == (0, 4)
    assert (second["from"], second["to"]) == (5, 9)


def test_metrics_discover_pages_from_records_filtered():
    result = parse_fixture()
    assert result.metrics.products_discovered == 25
    assert result.metrics.pages_discovered == 5
    assert result.metrics.pages_processed == 1
    assert result.metrics.page_coverage == pytest.approx(0.2)


def test_duplicate_item_id_is_deduplicated():
    payload = load_fixture("product_search_page.json")
    duplicate = deepcopy(payload["data"]["productSearch"]["products"][0])
    payload["data"]["productSearch"]["products"].insert(1, duplicate)
    result = build_extractor().parse_payload(
        payload,
        scrape_run_id="run_duplicate",
        source_url=build_extractor().build_page_url(),
        page_size=5,
    )
    assert len(result.products) == 5
    assert result.metrics.duplicate_products == 1
    assert "quality:duplicate_source_key" in result.quality_events


def test_empty_response_is_rejected():
    with pytest.raises(EmptyResponseError):
        parse_fixture("empty_response.json")


def test_structural_change_is_rejected():
    with pytest.raises(StructureChangedError, match="productSearch"):
        parse_fixture("structure_changed.json")


def test_graphql_errors_are_reported_as_structural_change():
    payload = {"data": {}, "errors": [{"message": "PersistedQueryNotFound"}]}
    with pytest.raises(StructureChangedError, match="GraphQL"):
        build_extractor().parse_payload(
            payload,
            scrape_run_id="run_error",
            source_url=build_extractor().build_page_url(),
            page_size=5,
        )


def test_page_without_any_price_is_not_accepted():
    payload = load_fixture("product_search_page.json")
    for product in payload["data"]["productSearch"]["products"]:
        for item in product["items"]:
            for seller in item["sellers"]:
                seller["commercialOffer"]["Price"] = 0
                seller["commercialOffer"]["ListPrice"] = 0
                seller["commercialOffer"]["AvailableQuantity"] = 0
    result = build_extractor().parse_payload(
        payload,
        scrape_run_id="run_no_prices",
        source_url=build_extractor().build_page_url(),
        page_size=5,
    )
    assert result.accepted is False
    assert result.metrics.products_with_price == 0
    assert "quality:missing_all_prices" in result.quality_events


def test_client_blocks_robots_excluded_routes_before_transport():
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        raise AssertionError("No debe ejecutarse el transporte")

    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=("/api", "/busca", "/buscapagina"),
        user_agent="test",
        transport=transport,
    )
    for url in (
        "https://www.lacolonia.com/api/catalog_system/pub/products/search",
        "https://www.lacolonia.com/buscapagina?PageNumber=1",
        "https://www.lacolonia.com/busca?q=arroz",
    ):
        with pytest.raises(RobotsPolicyError):
            client.get(url)
    assert calls == []


def test_client_blocks_mobile_domain():
    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=("/api",),
        user_agent="test",
        transport=lambda *_: None,
    )
    with pytest.raises(RobotsPolicyError, match="Host"):
        client.get("https://mobile.lacolonia.com/supermercado")


def test_client_stops_on_403_and_captcha():
    forbidden = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=("/api",),
        user_agent="test",
        transport=lambda url, headers, timeout: HttpResponse(403, url, {}, b"blocked"),
    )
    with pytest.raises(BlockedResponseError):
        forbidden.get("https://www.lacolonia.com/_v/segment/graphql/v1")
    captcha = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=("/api",),
        user_agent="test",
        transport=lambda url, headers, timeout: HttpResponse(200, url, {}, b"CAPTCHA"),
    )
    with pytest.raises(BlockedResponseError):
        captcha.get("https://www.lacolonia.com/_v/segment/graphql/v1")


def test_client_retries_few_times_on_server_error():
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        return HttpResponse(500, url, {}, b"error")

    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=("/api",),
        user_agent="test",
        max_retries=2,
        retry_delay_seconds=0,
        transport=transport,
        sleeper=lambda _: None,
    )
    with pytest.raises(HttpStatusError) as error:
        client.get("https://www.lacolonia.com/_v/segment/graphql/v1")
    assert error.value.status_code == 500
    assert len(calls) == 3


def test_client_respects_429_and_then_stops():
    sleeps = []
    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=("/api",),
        user_agent="test",
        max_retries=1,
        retry_delay_seconds=0,
        transport=lambda url, headers, timeout: HttpResponse(
            429, url, {"Retry-After": "2"}, b"rate limited"
        ),
        sleeper=sleeps.append,
    )
    with pytest.raises(RateLimitedError):
        client.get("https://www.lacolonia.com/_v/segment/graphql/v1")
    assert 2.0 in sleeps


def test_live_limit_cannot_exceed_five_products():
    with pytest.raises(ValueError, match="entre 1 y 5"):
        build_extractor().build_page_url(page_size=6)
