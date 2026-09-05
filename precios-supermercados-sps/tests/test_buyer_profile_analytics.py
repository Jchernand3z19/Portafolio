from __future__ import annotations

import pytest

from precios_supermercados.buyer_profile_analytics import BuyerProfile, analyze_buyer_profile
from precios_supermercados.price_analytics import ComparisonScope, CurrentPriceObservation, PriceAnalyticsError, analyze_current_prices
from precios_supermercados.product_homologation import SourceProductRecord, homologate_products


def product(record_id: str, supermarket: str) -> SourceProductRecord:
    return SourceProductRecord(
        source_record_id=record_id,
        supermarket_id=supermarket,
        source_name="Suavizante Downy Pureza 800 ml",
        source_brand="Downy",
        source_presentation="800 ml",
        barcode="7590002040003",
    )


def analytics():
    homologation = homologate_products((product("colonial:1", "colonial"), product("walmart:2", "walmart")))
    return analyze_current_prices(
        homologation,
        (
            CurrentPriceObservation("colonial:1", "colonial", "colonial_sps", 10000),
            CurrentPriceObservation("walmart:2", "walmart", "walmart_sps", 12000),
        ),
        ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps"))),
    )


def test_buyer_profile_uses_only_comparable_universe() -> None:
    result = analytics()
    canonical_id = result.products[0].canonical_product_id
    profile_result = analyze_buyer_profile(
        result,
        BuyerProfile("hogar-basico", "Hogar básico", {canonical_id: 3}),
    )
    assert profile_result.profile_id == "hogar-basico"
    assert profile_result.basket.product_count == 3
    assert profile_result.basket.cheapest_total_minor == 30000
    assert profile_result.basket.highest_total_minor == 36000


def test_buyer_profile_fails_closed_if_any_requested_product_is_not_comparable() -> None:
    with pytest.raises(PriceAnalyticsError, match="buyer_profile_not_fully_comparable"):
        analyze_buyer_profile(
            analytics(),
            BuyerProfile("familia", "Familia", {"prod_gtin_not_safe": 1}),
        )


def test_buyer_profile_requires_positive_quantities() -> None:
    with pytest.raises(PriceAnalyticsError, match="buyer_profile_quantity_invalid"):
        BuyerProfile("familia", "Familia", {"x": 0})
