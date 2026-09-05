from __future__ import annotations

from decimal import Decimal

import pytest

from precios_supermercados.price_analytics import (
    ComparisonScope,
    CurrentPriceObservation,
    PriceAnalyticsError,
    analyze_current_prices,
)
from precios_supermercados.price_change_analytics import compare_runs
from precios_supermercados.product_homologation import SourceProductRecord, homologate_products


def product(record_id: str, supermarket: str, price_name: str) -> SourceProductRecord:
    return SourceProductRecord(
        source_record_id=record_id,
        supermarket_id=supermarket,
        source_name=price_name,
        source_brand="Downy",
        source_presentation="800 ml",
        barcode="7590002040003",
    )


def run(colonial_price: int, walmart_price: int):
    homologation = homologate_products(
        (
            product("colonial:1", "colonial", "Suavizante Downy Pureza 800 ml"),
            product("walmart:2", "walmart", "Downy Suavizante Pureza 800 ml"),
        )
    )
    scope = ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps")))
    return analyze_current_prices(
        homologation,
        (
            CurrentPriceObservation("colonial:1", "colonial", "colonial_sps", colonial_price),
            CurrentPriceObservation("walmart:2", "walmart", "walmart_sps", walmart_price),
        ),
        scope,
    )


def test_compare_runs_reports_offer_and_basket_changes() -> None:
    previous = run(10000, 12000)
    current = run(11000, 11900)
    change = compare_runs(previous, current)

    assert change.common_products_both_runs == 1
    assert change.added_to_common_universe == ()
    assert change.removed_from_common_universe == ()
    assert len(change.changed_offers) == 2
    colonial = next(item for item in change.changed_offers if item.supermarket_id == "colonial")
    assert colonial.change_minor == 1000
    assert colonial.change == Decimal("10.00")
    assert colonial.change_pct == Decimal("10.00")
    assert len(change.basket_changes) == 2
    assert change.cheapest_supermarket_previous == "colonial"
    assert change.cheapest_supermarket_current == "colonial"


def test_compare_runs_refuses_different_location_scope() -> None:
    previous = run(10000, 12000)
    homologation = homologate_products(
        (
            product("colonial:1", "colonial", "Suavizante Downy Pureza 800 ml"),
            product("walmart:2", "walmart", "Downy Suavizante Pureza 800 ml"),
        )
    )
    current = analyze_current_prices(
        homologation,
        (
            CurrentPriceObservation("colonial:1", "colonial", "colonial_sps", 10000),
            CurrentPriceObservation("walmart:2", "walmart", "walmart_tgu", 12000),
        ),
        ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_tgu"))),
    )
    with pytest.raises(PriceAnalyticsError, match="run_comparison_scope_mismatch"):
        compare_runs(previous, current)
