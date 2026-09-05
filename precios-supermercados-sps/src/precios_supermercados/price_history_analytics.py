"""Variabilidad y tendencia de series históricas aceptadas.

Las series deben pertenecer a una identidad canónica ya considerada segura por
la capa de comparación. Este módulo no inventa periodos ni interpola precios.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean
from typing import Iterable


class PriceHistoryAnalyticsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HistoricalPriceObservation:
    canonical_product_id: str
    supermarket_id: str
    location_id: str
    observed_at_utc: datetime
    price_minor: int

    def __post_init__(self) -> None:
        if not self.canonical_product_id.strip() or not self.supermarket_id.strip() or not self.location_id.strip():
            raise PriceHistoryAnalyticsError("history_identity_missing")
        if self.observed_at_utc.tzinfo is None or self.observed_at_utc.utcoffset() is None:
            raise PriceHistoryAnalyticsError("history_timestamp_not_timezone_aware")
        if type(self.price_minor) is not int or self.price_minor <= 0:
            raise PriceHistoryAnalyticsError("history_price_invalid")


@dataclass(frozen=True, slots=True)
class PriceSeriesSummary:
    canonical_product_id: str
    supermarket_id: str
    location_id: str
    observation_count: int
    first_observed_at_utc: datetime
    last_observed_at_utc: datetime
    first_price_minor: int
    last_price_minor: int
    minimum_price_minor: int
    maximum_price_minor: int
    mean_price_minor: int
    absolute_change_minor: int
    change_pct: Decimal
    range_minor: int
    range_pct_of_min: Decimal
    distinct_price_count: int
    price_change_count: int
    direction: str


def _pct(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0.00")
    return (Decimal(numerator) * Decimal(100) / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def summarize_price_series(observations: Iterable[HistoricalPriceObservation]) -> PriceSeriesSummary:
    rows = sorted(observations, key=lambda item: item.observed_at_utc)
    if not rows:
        raise PriceHistoryAnalyticsError("history_empty")
    identity = (rows[0].canonical_product_id, rows[0].supermarket_id, rows[0].location_id)
    if any((row.canonical_product_id, row.supermarket_id, row.location_id) != identity for row in rows):
        raise PriceHistoryAnalyticsError("history_mixed_identity")
    timestamps = [row.observed_at_utc for row in rows]
    if len(set(timestamps)) != len(timestamps):
        raise PriceHistoryAnalyticsError("history_duplicate_timestamp")

    prices = [row.price_minor for row in rows]
    first = prices[0]
    last = prices[-1]
    change = last - first
    direction = "same"
    if change < 0:
        direction = "down"
    elif change > 0:
        direction = "up"
    price_change_count = sum(current != previous for previous, current in zip(prices, prices[1:]))
    minimum = min(prices)
    maximum = max(prices)
    return PriceSeriesSummary(
        canonical_product_id=identity[0],
        supermarket_id=identity[1],
        location_id=identity[2],
        observation_count=len(rows),
        first_observed_at_utc=rows[0].observed_at_utc,
        last_observed_at_utc=rows[-1].observed_at_utc,
        first_price_minor=first,
        last_price_minor=last,
        minimum_price_minor=minimum,
        maximum_price_minor=maximum,
        mean_price_minor=round(mean(prices)),
        absolute_change_minor=change,
        change_pct=_pct(change, first),
        range_minor=maximum - minimum,
        range_pct_of_min=_pct(maximum - minimum, minimum),
        distinct_price_count=len(set(prices)),
        price_change_count=price_change_count,
        direction=direction,
    )
