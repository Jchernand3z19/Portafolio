from __future__ import annotations

from datetime import datetime, timedelta, timezone

import json

import pytest

from precios_supermercados.analytics_quality import (
    QualityRun,
    QualityStatus,
    assess_comparable_market_window,
    assess_freshness,
)
from precios_supermercados.competitive_analytics import analyze_competition
from precios_supermercados.price_analytics import ComparisonScope, CurrentPriceObservation, analyze_current_prices
from precios_supermercados.product_homologation import SourceProductRecord, homologate_products
from precios_supermercados.rpi_data_marts import (
    MartCommercialState,
    MartOfferDescriptor,
    RpiDataMartError,
    build_rpi_data_marts,
)


AS_OF = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


def inputs(*, stale: bool = False):
    scope = ComparisonScope((("a", "a_sps"), ("b", "b_sps")))
    records = tuple(
        SourceProductRecord(
            source_record_id=f"{retailer}:{index}",
            supermarket_id=retailer,
            source_name="Leche Sula entera 1 L",
            source_brand="Sula",
            source_presentation="1 L",
            source_category="Lácteos",
            barcode="7590002040003",
        )
        for index, retailer in enumerate(("a", "b"), 1)
    )
    prices = {"a:1": 2000, "b:2": 2200}
    analytics = analyze_current_prices(
        homologate_products(records),
        tuple(
            CurrentPriceObservation(record.source_record_id, record.supermarket_id, f"{record.supermarket_id}_sps", prices[record.source_record_id])
            for record in records
        ),
        scope,
    )
    freshness = tuple(
        assess_freshness(
            QualityRun(
                f"{retailer}-run", retailer, f"{retailer}_sps",
                AS_OF - timedelta(hours=30 if stale and retailer == "b" else 2),
                QualityStatus.ACCEPTED,
            ),
            source_id=retailer,
            location_id=f"{retailer}_sps",
            as_of_utc=AS_OF,
            freshness_window=timedelta(hours=24),
        )
        for retailer in ("a", "b")
    )
    competition = analyze_competition(analytics, assess_comparable_market_window(freshness))
    descriptors = tuple(
        MartOfferDescriptor(
            record.source_record_id,
            record.source_name,
            category="Lácteos",
            product_type="Leche",
            brand="Sula",
            variant="Entera",
            presentation="1 L",
        )
        for record in records
    )
    states = tuple(
        MartCommercialState(
            record.source_record_id,
            prices[record.source_record_id],
            2500 if record.supermarket_id == "a" else None,
            record.supermarket_id == "a",
            "in_stock",
            AS_OF - timedelta(hours=2),
        )
        for record in records
    )
    return analytics, competition, descriptors, states, freshness


def test_business_and_consumer_marts_share_safe_inputs_and_metric_truth() -> None:
    marts = build_rpi_data_marts(*inputs())

    assert marts.business["schema"] == "rpi-business-mart/v1"
    assert marts.consumer["schema"] == "rpi-consumer-mart/v1"
    assert marts.business["comparison_status"] == "COMPARABLE"
    assert marts.consumer["comparison_status"] == "COMPARABLE"
    assert marts.consumer["product_count"] == 1
    assert len(marts.business["facts"]["fact_current_comparison"]) == 2
    assert marts.business["coverage"] == marts.consumer["coverage"]
    assert marts.business["source_freshness"] == marts.consumer["source_freshness"]
    assert {row["pci"] for row in marts.business["facts"]["fact_current_comparison"]} == {"95.24", "104.76"}


def test_consumer_mart_preserves_price_and_shopping_descriptors_without_secrets() -> None:
    consumer = build_rpi_data_marts(*inputs()).consumer
    offer = consumer["products"][0]["offers"][0]

    assert offer["current_price"] == "20.00"
    assert offer["reported_regular_price"] == "25.00"
    assert offer["is_promotion"] is True
    assert offer["category"] == "Lácteos"
    assert offer["product_type"] == "Leche"
    assert offer["brand"] == "Sula"
    assert offer["variant"] == "Entera"
    assert offer["presentation"] == "1 L"
    serialized = json.dumps(consumer).casefold()
    for forbidden in ("turso", "database_url", "auth_token", "libsql://"):
        assert forbidden not in serialized


def test_stale_market_keeps_lkg_offers_visible_but_removes_rank_and_pci() -> None:
    marts = build_rpi_data_marts(*inputs(stale=True))
    facts = marts.business["facts"]["fact_current_comparison"]

    assert marts.consumer["comparison_status"] == "INSUFFICIENT_FRESH_COMPARISON"
    assert marts.consumer["product_count"] == 1
    assert "source_data_stale" in marts.consumer["blocked_reasons"]
    assert all(row["rank"] is None and row["pci"] is None for row in facts)
    assert any(row["freshness_status"] == "STALE" for row in facts)


def test_mart_rejects_descriptor_or_price_drift_from_safe_universe() -> None:
    analytics, competition, descriptors, states, freshness = inputs()
    with pytest.raises(RpiDataMartError, match="mart_offer_inputs_not_exact_safe_universe"):
        build_rpi_data_marts(analytics, competition, descriptors[:-1], states, freshness)

    bad_states = (
        MartCommercialState("a:1", 9999, 2500, True, "in_stock", AS_OF),
        states[1],
    )
    with pytest.raises(RpiDataMartError, match="mart_current_price_mismatch"):
        build_rpi_data_marts(analytics, competition, descriptors, bad_states, freshness)
