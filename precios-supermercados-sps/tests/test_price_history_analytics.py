from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from precios_supermercados.price_history_analytics import (
    HistoricalPriceObservation,
    PriceHistoryAnalyticsError,
    summarize_price_series,
)


def observation(day: int, price: int, *, location: str = "walmart_sps") -> HistoricalPriceObservation:
    return HistoricalPriceObservation(
        canonical_product_id="prod_gtin_07590002040003",
        supermarket_id="walmart",
        location_id=location,
        observed_at_utc=datetime(2026, 9, day, 12, tzinfo=timezone.utc),
        price_minor=price,
    )


def test_summarize_price_series_reports_variability_and_trend_without_interpolation() -> None:
    summary = summarize_price_series(
        (
            observation(3, 12000),
            observation(1, 10000),
            observation(2, 10000),
            observation(4, 11000),
        )
    )
    assert summary.observation_count == 4
    assert summary.first_price_minor == 10000
    assert summary.last_price_minor == 11000
    assert summary.minimum_price_minor == 10000
    assert summary.maximum_price_minor == 12000
    assert summary.mean_price_minor == 10750
    assert summary.absolute_change_minor == 1000
    assert summary.change_pct == Decimal("10.00")
    assert summary.range_minor == 2000
    assert summary.range_pct_of_min == Decimal("20.00")
    assert summary.distinct_price_count == 3
    assert summary.price_change_count == 2
    assert summary.direction == "up"


def test_history_rejects_mixed_locations_duplicate_timestamps_and_invalid_prices() -> None:
    with pytest.raises(PriceHistoryAnalyticsError, match="history_mixed_identity"):
        summarize_price_series((observation(1, 10000), observation(2, 11000, location="walmart_tgu")))
    with pytest.raises(PriceHistoryAnalyticsError, match="history_duplicate_timestamp"):
        summarize_price_series((observation(1, 10000), observation(1, 11000)))
    with pytest.raises(PriceHistoryAnalyticsError, match="history_price_invalid"):
        observation(1, 0)


def test_history_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(PriceHistoryAnalyticsError, match="history_timestamp_not_timezone_aware"):
        HistoricalPriceObservation(
            canonical_product_id="prod_gtin_07590002040003",
            supermarket_id="walmart",
            location_id="walmart_sps",
            observed_at_utc=datetime(2026, 9, 1, 12),
            price_minor=10000,
        )
