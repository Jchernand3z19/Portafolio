from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "probar_muestra_sps_la_colonia_intelligent_v1.py"
SPEC = importlib.util.spec_from_file_location("probar_muestra_sps_la_colonia_intelligent_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _request(*, url: str = "https://www.lacolonia.com/", headers=None, payload=None):
    return SimpleNamespace(
        url=url,
        headers=dict(headers or {}),
        post_data_json=payload,
    )


def _sample_product() -> dict:
    return {
        "productId": "100",
        "productName": "Producto de Prueba",
        "productReference": "PROD-100",
        "linkText": "producto-de-prueba",
        "brand": "Marca Prueba",
        "categories": ["/Supermercado/Despensa/"],
        "categoryTree": [
            {"name": "Supermercado"},
            {"name": "Despensa"},
        ],
        "items": [
            {
                "itemId": "SKU-100",
                "name": "500 g",
                "nameComplete": "Producto de Prueba 500 g",
                "ean": "7420000000100",
                "referenceId": [{"Key": "RefId", "Value": "REF-100"}],
                "measurementUnit": "un",
                "unitMultiplier": 1,
                "images": [{"imageUrl": "https://www.lacolonia.com/test.jpg"}],
                "sellers": [
                    {
                        "sellerDefault": True,
                        "sellerId": "1",
                        "commertialOffer": {
                            "Price": 30,
                            "ListPrice": 35,
                            "AvailableQuantity": 8,
                        },
                    }
                ],
            }
        ],
    }


def test_channel_normalization_is_fail_closed() -> None:
    assert module._normalize_channel("1") == "1"
    assert module._normalize_channel(" 02 ") == "2"
    assert module._normalize_channel(3) == "3"
    assert module._normalize_channel(True) is None
    assert module._normalize_channel("abc") is None
    assert module._normalize_channel("0") is None
    assert module._normalize_channel("10000") is None


def test_tracker_requires_same_run_canonical_region_and_one_channel() -> None:
    region = "opaque-sps-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )

    tracker.observe_request(_request(url="https://www.lacolonia.com/?sc=1&regionId=before"))
    tracker.reset_and_enable()
    tracker.observe_request(
        _request(
            payload={"variables": {"regionId": region, "segment": {"channel": "1"}}}
        )
    )

    observed_region, observed_channel = tracker.explicit_context()
    assert observed_region == region
    assert observed_channel == "1"
    assert tracker.fingerprint_verified is True
    assert tracker.channel_observed is True
    assert region not in repr(tracker)


def test_tracker_rejects_wrong_region_fingerprint() -> None:
    expected = "expected-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(expected)
    )
    tracker.reset_and_enable()
    tracker.observe_request(
        _request(payload={"variables": {"regionId": "other-region", "channel": "1"}})
    )

    with pytest.raises(
        module.passive.MvpSampleError,
        match="sps_region_binding_not_observed_same_run",
    ):
        tracker.explicit_context()


def test_tracker_rejects_ambiguous_sales_channels() -> None:
    region = "opaque-sps-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )
    tracker.reset_and_enable()
    tracker.observe_request(
        _request(payload={"variables": {"regionId": region, "channel": "1"}})
    )
    tracker.observe_request(_request(url="https://www.lacolonia.com/?sc=2"))

    with pytest.raises(
        module.passive.MvpSampleError,
        match="sales_channel_ambiguous_same_run",
    ):
        tracker.explicit_context()


def test_v1_url_carries_explicit_region_and_channel_only_for_request() -> None:
    url = module._build_v1_url(
        region_id="opaque-region",
        sales_channel="2",
        sample_size=10,
    )
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.path == "/api/intelligent-search/v1/product-search"
    assert query["regionId"] == ["opaque-region"]
    assert query["sc"] == ["2"]
    assert query["count"] == ["10"]
    assert query["page"] == ["1"]
    assert query["locale"] == ["es-HN"]
    assert query["hideUnavailableItems"] == ["false"]


def test_v1_payload_is_adapted_to_existing_commercial_parser() -> None:
    result = module._parse_v1_payload(
        {"products": [_sample_product()], "recordsFiltered": 1},
        sample_size=10,
    )

    assert result.accepted is True
    assert len(result.products) == 1
    product = result.products[0]
    assert product.source_name == "Producto de Prueba 500 g"
    assert product.source_brand == "Marca Prueba"
    assert product.raw_values["current_price"] == "30"
    assert product.raw_values["reported_regular_price"] == "35"
    assert product.raw_values["is_promotion"] is True
    assert product.raw_values["availability"] == "in_stock"


def test_failure_artifact_never_contains_raw_context() -> None:
    artifact = module._failure_artifact(
        "sales_channel_not_observed_same_run",
        {
            "location_verified_same_run": True,
            "region_binding_fingerprint_verified": True,
            "sales_channel_observed_same_run": False,
            "explicit_product_data_requests": 0,
        },
    )

    assert artifact["capture_strategy"] == "explicit_region_intelligent_search_v1"
    assert artifact["region_binding_fingerprint_verified"] is True
    assert artifact["sales_channel_observed_same_run"] is False
    assert artifact["explicit_product_data_requests"] == 0
    serialized = repr(artifact).casefold()
    assert "regionid" not in serialized
    assert "opaque-region" not in serialized
