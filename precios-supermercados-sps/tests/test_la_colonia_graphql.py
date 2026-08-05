from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from precios_supermercados.enums import AvailabilityStatus
from precios_supermercados.scrapers.la_colonia import LaColoniaExtractor
from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url

FIXTURE = Path(__file__).parent / "fixtures" / "la_colonia" / "product_search_page.json"
FIXED_TIME = datetime(2026, 8, 5, 4, 30, tzinfo=timezone.utc)


def test_live_url_uses_explicit_public_graphql_query_without_persisted_hash():
    url = build_product_search_url(page=1, page_size=5)
    query = parse_qs(urlsplit(url).query)

    assert urlsplit(url).path == "/_v/segment/graphql/v1"
    assert query["operationName"] == ["productSearchV3"]
    assert "productSearch" in query["query"][0]
    assert "persistedQuery" not in query
    assert json.loads(query["variables"][0])["to"] == 4


def test_positive_price_with_zero_quantity_is_unknown_not_out_of_stock():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    modified = deepcopy(payload)
    offer = modified["data"]["productSearch"]["products"][0]["items"][0]["sellers"][0]["commercialOffer"]
    offer["Price"] = 19.9
    offer["ListPrice"] = 19.9
    offer["AvailableQuantity"] = 0

    extractor = LaColoniaExtractor(clock=lambda: FIXED_TIME)
    result = extractor.parse_payload(
        modified,
        scrape_run_id="run_conflicting_availability",
        source_url=extractor.build_page_url(),
        page_size=5,
    )

    first = result.products[0]
    assert first.raw_values["availability"] == AvailabilityStatus.UNKNOWN.value
    assert first.raw_values["availability_evidence"] == "price_positive_quantity_zero"
    assert "quality:availability_conflict_price_with_zero_quantity" in result.quality_events
