from __future__ import annotations

from decimal import Decimal

import pytest

from precios_supermercados.price_analytics import (
    ComparisonScope,
    CurrentPriceObservation,
    PriceAnalyticsError,
    analyze_current_prices,
    analyze_subbasket,
)
from precios_supermercados.product_homologation import SourceProductRecord, homologate_products


def product(
    record_id: str,
    supermarket: str,
    name: str,
    *,
    brand: str,
    presentation: str,
    barcode: str,
) -> SourceProductRecord:
    return SourceProductRecord(
        source_record_id=record_id,
        supermarket_id=supermarket,
        source_name=name,
        source_brand=brand,
        source_presentation=presentation,
        barcode=barcode,
    )


def safe_fixture():
    records = (
        product("colonial:downy", "colonial", "Suavizante Downy Pureza 800 ml", brand="Downy", presentation="800 ml", barcode="7590002040003"),
        product("walmart:downy", "walmart", "Downy Suavizante Pureza 800 ML", brand="Downy", presentation="800 ml", barcode="07590002040003"),
        product("colonial:arroz", "colonial", "Arroz Progreso Blanco 1 lb", brand="Progreso", presentation="1 lb", barcode="7501031311309"),
        product("walmart:arroz", "walmart", "Progreso Arroz Blanco 454 g", brand="Progreso", presentation="454 g", barcode="07501031311309"),
    )
    homologation = homologate_products(records)
    observations = (
        CurrentPriceObservation("colonial:downy", "colonial", "colonial_sps", 10000),
        CurrentPriceObservation("walmart:downy", "walmart", "walmart_sps", 12000),
        CurrentPriceObservation("colonial:arroz", "colonial", "colonial_sps", 2000),
        CurrentPriceObservation("walmart:arroz", "walmart", "walmart_sps", 1800),
    )
    scope = ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps")))
    return homologation, observations, scope


def test_current_analytics_uses_only_safe_common_universe() -> None:
    homologation, observations, scope = safe_fixture()
    result = analyze_current_prices(homologation, observations, scope)

    assert len(result.products) == 2
    downy = next(item for item in result.products if item.canonical_gtin == "07590002040003")
    assert downy.best_supermarket_id == "colonial"
    assert downy.best_price == Decimal("100.00")
    assert downy.savings_vs_highest == Decimal("20.00")
    assert downy.savings_vs_highest_pct == Decimal("16.67")

    basket = result.common_basket
    assert basket.product_count == 2
    assert basket.denominator_definition == "products_comparable_and_priced_in_every_supermarket_in_scope"
    assert basket.totals == (("colonial", Decimal("120.00")), ("walmart", Decimal("138.00")))
    assert basket.cheapest_supermarket_id == "colonial"
    assert basket.savings_vs_highest_minor == 1800


def test_missing_price_removes_product_from_common_basket_instead_of_imputing() -> None:
    homologation, observations, scope = safe_fixture()
    observations = tuple(item for item in observations if item.source_record_id != "walmart:arroz")
    result = analyze_current_prices(homologation, observations, scope)

    assert len(result.products) == 1
    assert any(reason == "price_missing_in_scope" for _, reason in result.excluded_groups)
    assert result.common_basket.product_count == 1


def test_unsafe_commercial_variant_never_enters_savings_or_basket() -> None:
    records = (
        product("a", "colonial", "Café Passion Especial 1 lb", brand="Passion", presentation="1 lb", barcode="7590002040003"),
        product("b", "walmart", "Café Passion Jaguar 1 lb", brand="Passion", presentation="1 lb", barcode="07590002040003"),
    )
    result = analyze_current_prices(
        homologate_products(records),
        (
            CurrentPriceObservation("a", "colonial", "colonial_sps", 21599),
            CurrentPriceObservation("b", "walmart", "walmart_sps", 29950),
        ),
        ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps"))),
    )
    assert result.products == ()
    assert result.common_basket.product_count == 0
    assert result.common_basket.totals_minor == (("colonial", 0), ("walmart", 0))
    assert result.excluded_groups[0][1] == "not_comparable"


def test_subbasket_supports_explicit_quantities_only_inside_common_universe() -> None:
    homologation, observations, scope = safe_fixture()
    result = analyze_current_prices(homologation, observations, scope)
    ids = [item.canonical_product_id for item in result.products]
    sub = analyze_subbasket(result, {ids[0]: 2, ids[1]: 3})

    assert sub.product_count == 5
    assert sub.denominator_definition == "explicit_quantities_drawn_only_from_current_common_comparable_universe"
    assert sub.cheapest_total_minor > 0

    with pytest.raises(PriceAnalyticsError, match="subbasket_product_not_in_common_universe"):
        analyze_subbasket(result, {"prod_gtin_unknown": 1})


def test_scope_rejects_duplicate_supermarket_and_observation_rejects_bad_price() -> None:
    with pytest.raises(PriceAnalyticsError, match="comparison_scope_supermarket_duplicate"):
        ComparisonScope((("walmart", "a"), ("walmart", "b")))
    with pytest.raises(PriceAnalyticsError, match="price_minor_invalid"):
        CurrentPriceObservation("x", "walmart", "a", -1)
