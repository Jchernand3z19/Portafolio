from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo_v2 as operational_v2  # noqa: E402
from precios_supermercados.scrapers.base import EmptyResponseError  # noqa: E402


def _result(
    *,
    accepted: bool = False,
    events: tuple[str, ...] = ("quality:partial_product_page",),
    structural_events: int = 0,
    errors: int = 0,
    skus_extracted: int = 49,
    skus_with_price: int = 49,
) -> SimpleNamespace:
    return SimpleNamespace(
        accepted=accepted,
        quality_events=events,
        metrics=SimpleNamespace(
            structural_events=structural_events,
            errors=errors,
            skus_extracted=skus_extracted,
            skus_with_price=skus_with_price,
        ),
    )


def _empty_payload(total: int) -> dict[str, object]:
    return {
        "data": {
            "productSearch": {
                "recordsFiltered": total,
                "products": [],
            }
        }
    }


def test_partial_page_can_reach_bucket_recovery_when_semantically_valid() -> None:
    assert operational_v2._partial_page_is_safe_for_bucket_recovery(_result()) is True


def test_structural_event_remains_fail_closed() -> None:
    assert (
        operational_v2._partial_page_is_safe_for_bucket_recovery(
            _result(structural_events=1)
        )
        is False
    )


def test_parse_error_remains_fail_closed() -> None:
    assert (
        operational_v2._partial_page_is_safe_for_bucket_recovery(_result(errors=1))
        is False
    )


def test_missing_prices_remain_fail_closed() -> None:
    assert (
        operational_v2._partial_page_is_safe_for_bucket_recovery(
            _result(skus_with_price=0)
        )
        is False
    )


def test_other_rejection_without_partial_page_remains_fail_closed() -> None:
    assert (
        operational_v2._partial_page_is_safe_for_bucket_recovery(
            _result(events=("quality:missing_all_prices",))
        )
        is False
    )


def test_empty_page_can_reach_reverse_recovery_without_contributing_products() -> None:
    extractor = operational_v2.RecoveryAwareLaColoniaExtractor()
    result = extractor.parse_payload(
        _empty_payload(101),
        scrape_run_id="offline-test",
        source_url="https://www.lacolonia.com/_v/segment/graphql/v1",
        page_size=50,
    )

    assert result.accepted is True
    assert result.products == ()
    assert result.metrics.products_discovered == 101
    assert result.metrics.products_returned == 0
    assert result.quality_events == ("quality:empty_product_page_recovery",)


def test_empty_page_with_nonpositive_total_remains_fail_closed() -> None:
    extractor = operational_v2.RecoveryAwareLaColoniaExtractor()
    with pytest.raises(EmptyResponseError):
        extractor.parse_payload(
            _empty_payload(0),
            scrape_run_id="offline-test",
            source_url="https://www.lacolonia.com/_v/segment/graphql/v1",
            page_size=50,
        )
