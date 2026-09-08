"""Build deterministic B2B and B2C marts from one safe analytical result."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from .analytics_quality import FreshnessAssessment, MarketWindowStatus
from .competitive_analytics import CompetitiveAnalyticsResult
from .price_analytics import AnalyticsResult
from .price_history_analytics import HistoricalPriceObservation, summarize_price_series, summarize_price_windows
from .promotion_analytics import PromotionPriceObservation, analyze_promotions


class RpiDataMartError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MartOfferDescriptor:
    source_record_id: str
    product_name: str
    category: str | None = None
    product_type: str | None = None
    brand: str | None = None
    variant: str | None = None
    presentation: str | None = None

    def __post_init__(self) -> None:
        if not self.source_record_id.strip() or not self.product_name.strip():
            raise RpiDataMartError("mart_descriptor_identity_missing")


@dataclass(frozen=True, slots=True)
class MartCommercialState:
    source_record_id: str
    current_price_minor: int
    reported_regular_price_minor: int | None
    is_promotion: bool
    availability: str
    observed_at_utc: datetime

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise RpiDataMartError("mart_commercial_identity_missing")
        if type(self.current_price_minor) is not int or self.current_price_minor <= 0:
            raise RpiDataMartError("mart_current_price_invalid")
        if self.reported_regular_price_minor is not None and (
            type(self.reported_regular_price_minor) is not int
            or self.reported_regular_price_minor <= 0
        ):
            raise RpiDataMartError("mart_regular_price_invalid")
        if not isinstance(self.is_promotion, bool):
            raise RpiDataMartError("mart_promotion_invalid")
        if self.availability not in {"in_stock", "unknown"}:
            raise RpiDataMartError("mart_offer_not_buyable")
        if self.observed_at_utc.tzinfo is None or self.observed_at_utc.utcoffset() is None:
            raise RpiDataMartError("mart_observed_at_not_timezone_aware")
        object.__setattr__(self, "observed_at_utc", self.observed_at_utc.astimezone(timezone.utc))


@dataclass(frozen=True, slots=True)
class MartHistoricalState:
    source_record_id: str
    current_price_minor: int
    reported_regular_price_minor: int | None
    is_promotion: bool
    observed_at_utc: datetime

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise RpiDataMartError("mart_history_identity_missing")
        if type(self.current_price_minor) is not int or self.current_price_minor <= 0:
            raise RpiDataMartError("mart_history_price_invalid")
        if self.reported_regular_price_minor is not None and (
            type(self.reported_regular_price_minor) is not int
            or self.reported_regular_price_minor <= 0
        ):
            raise RpiDataMartError("mart_history_regular_price_invalid")
        if not isinstance(self.is_promotion, bool):
            raise RpiDataMartError("mart_history_promotion_invalid")
        if self.observed_at_utc.tzinfo is None or self.observed_at_utc.utcoffset() is None:
            raise RpiDataMartError("mart_history_observed_at_not_timezone_aware")
        object.__setattr__(self, "observed_at_utc", self.observed_at_utc.astimezone(timezone.utc))


@dataclass(frozen=True, slots=True)
class RpiDataMarts:
    business: dict[str, Any]
    consumer: dict[str, Any]


def _money(minor: int | None) -> str | None:
    if minor is None:
        return None
    return format((Decimal(minor) / Decimal(100)).quantize(Decimal("0.01")), "f")


def _money_decimal_minor(minor: Decimal | None) -> str | None:
    if minor is None:
        return None
    return format((minor / Decimal(100)).quantize(Decimal("0.01")), "f")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unique_by_id(values: Iterable[Any], field: str, error: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        identity = getattr(value, field)
        if identity in result:
            raise RpiDataMartError(error)
        result[identity] = value
    return result


def _history_by_source(
    historical_states: Iterable[MartHistoricalState],
    safe_ids: set[str],
) -> dict[str, tuple[MartHistoricalState, ...]]:
    grouped: dict[str, list[MartHistoricalState]] = {}
    for state in historical_states:
        if state.source_record_id not in safe_ids:
            raise RpiDataMartError("mart_history_not_safe_universe")
        grouped.setdefault(state.source_record_id, []).append(state)
    result: dict[str, tuple[MartHistoricalState, ...]] = {}
    for source_record_id, rows in grouped.items():
        ordered = tuple(sorted(rows, key=lambda item: item.observed_at_utc))
        if len({item.observed_at_utc for item in ordered}) != len(ordered):
            raise RpiDataMartError("mart_history_duplicate_timestamp")
        result[source_record_id] = ordered
    return result


def _historical_summary(
    *,
    canonical_product_id: str,
    supermarket_id: str,
    location_id: str,
    current_state: MartCommercialState,
    history: tuple[MartHistoricalState, ...],
    as_of_utc: datetime,
) -> dict[str, Any]:
    if not history:
        history = (
            MartHistoricalState(
                current_state.source_record_id,
                current_state.current_price_minor,
                current_state.reported_regular_price_minor,
                current_state.is_promotion,
                current_state.observed_at_utc,
            ),
        )
    latest = history[-1]
    if (
        latest.current_price_minor != current_state.current_price_minor
        or latest.reported_regular_price_minor != current_state.reported_regular_price_minor
        or latest.is_promotion != current_state.is_promotion
        or latest.observed_at_utc != current_state.observed_at_utc
    ):
        raise RpiDataMartError("mart_history_current_state_mismatch")
    if latest.observed_at_utc > as_of_utc:
        raise RpiDataMartError("mart_history_after_as_of")

    historical_rows = tuple(
        HistoricalPriceObservation(
            canonical_product_id,
            supermarket_id,
            location_id,
            item.observed_at_utc,
            item.current_price_minor,
        )
        for item in history
    )
    promotion_rows = tuple(
        PromotionPriceObservation(
            canonical_product_id,
            supermarket_id,
            location_id,
            item.observed_at_utc,
            item.current_price_minor,
            item.is_promotion,
            item.reported_regular_price_minor,
        )
        for item in history
    )
    series = summarize_price_series(historical_rows)
    windows = {
        item.window_days: item
        for item in summarize_price_windows(
            historical_rows,
            as_of_utc=as_of_utc,
            windows=(30, 90),
        )
    }
    promotion = analyze_promotions(promotion_rows, as_of_utc=as_of_utc)

    def window_payload(days: int) -> dict[str, Any]:
        window = windows[days]
        return {
            "status": "available" if window.sufficient_history else "insufficient_history",
            "observation_count": window.observation_count,
            "average": _money(window.mean_price_minor),
            "median": _money_decimal_minor(window.median_price_minor),
            "minimum": _money(window.minimum_price_minor),
            "maximum": _money(window.maximum_price_minor),
            "current_vs_average_pct": _decimal(window.current_vs_average_pct),
            "current_vs_minimum_pct": _decimal(window.current_vs_minimum_pct),
        }

    return {
        "observation_count": series.observation_count,
        "first_observed_at": _iso(series.first_observed_at_utc),
        "last_observed_at": _iso(series.last_observed_at_utc),
        "observed_minimum": _money(series.minimum_price_minor),
        "observed_maximum": _money(series.maximum_price_minor),
        "previous_price": _money(promotion.previous_price_minor),
        "current_vs_previous_pct": _decimal(promotion.current_vs_previous_pct),
        "days_since_last_change": _decimal(series.days_since_last_change),
        "historical_position": promotion.historical_position.value,
        "historical_price_reduction": promotion.historical_price_reduction,
        "source_discount_depth_pct": _decimal(promotion.source_discount_depth_pct),
        "windows": {
            "30d": window_payload(30),
            "90d": window_payload(90),
        },
    }


def build_rpi_data_marts(
    analytics: AnalyticsResult,
    competition: CompetitiveAnalyticsResult,
    descriptors: Iterable[MartOfferDescriptor],
    commercial_states: Iterable[MartCommercialState],
    source_freshness: Iterable[FreshnessAssessment],
    historical_states: Iterable[MartHistoricalState] = (),
) -> RpiDataMarts:
    """Project the same trusted inputs to private business and public consumer marts."""

    freshness_values = tuple(source_freshness)
    descriptor_by_id = _unique_by_id(descriptors, "source_record_id", "mart_descriptor_duplicate")
    state_by_id = _unique_by_id(commercial_states, "source_record_id", "mart_commercial_state_duplicate")
    freshness_by_scope = {
        (item.source_id, item.location_id): item for item in freshness_values
    }
    if len(freshness_by_scope) != len(freshness_values):
        raise RpiDataMartError("mart_freshness_scope_duplicate")
    if len(freshness_by_scope) != len(analytics.scope.locations):
        raise RpiDataMartError("mart_freshness_scope_cardinality_mismatch")
    if set(freshness_by_scope) != set(analytics.scope.locations):
        raise RpiDataMartError("mart_freshness_scope_mismatch")
    if {
        _iso(item.as_of_utc) for item in freshness_values
    } != {competition.coverage.as_of}:
        raise RpiDataMartError("mart_freshness_as_of_mismatch")
    if {
        item.freshness_window_hours for item in freshness_values
    } != {competition.coverage.freshness_window_hours}:
        raise RpiDataMartError("mart_freshness_window_mismatch")

    safe_offers = [offer for product in analytics.products for offer in product.offers]
    safe_ids = {offer.source_record_id for offer in safe_offers}
    if set(descriptor_by_id) != safe_ids or set(state_by_id) != safe_ids:
        raise RpiDataMartError("mart_offer_inputs_not_exact_safe_universe")
    history_by_id = _history_by_source(historical_states, safe_ids)

    competitive_by_id = {
        item.canonical_product_id: item for item in competition.products
    }
    if competition.comparison_status is MarketWindowStatus.COMPARABLE:
        if set(competitive_by_id) != {product.canonical_product_id for product in analytics.products}:
            raise RpiDataMartError("mart_competition_products_mismatch")
    elif competitive_by_id:
        raise RpiDataMartError("mart_blocked_competition_must_be_empty")

    product_dimensions: list[dict[str, Any]] = []
    fact_rows: list[dict[str, Any]] = []
    consumer_products: list[dict[str, Any]] = []
    category_names: set[str] = set()
    brand_names: set[str] = set()
    as_of_utc = freshness_values[0].as_of_utc if freshness_values else datetime.now(timezone.utc)
    for product in analytics.products:
        product_dimensions.append(
            {
                "canonical_product_id": product.canonical_product_id,
                "canonical_gtin": product.canonical_gtin,
            }
        )
        competitive = competitive_by_id.get(product.canonical_product_id)
        competitive_offers = (
            {}
            if competitive is None
            else {item.source_record_id: item for item in competitive.offers}
        )
        consumer_offers: list[dict[str, Any]] = []
        for offer in product.offers:
            descriptor = descriptor_by_id[offer.source_record_id]
            state = state_by_id[offer.source_record_id]
            if state.current_price_minor != offer.price_minor:
                raise RpiDataMartError("mart_current_price_mismatch")
            freshness = freshness_by_scope[(offer.supermarket_id, offer.location_id)]
            metric = competitive_offers.get(offer.source_record_id)
            if descriptor.category:
                category_names.add(descriptor.category)
            if descriptor.brand:
                brand_names.add(descriptor.brand)
            common = {
                "canonical_product_id": product.canonical_product_id,
                "canonical_gtin": product.canonical_gtin,
                "source_product_id": offer.source_record_id,
                "supermarket_id": offer.supermarket_id,
                "location_id": offer.location_id,
                "category": descriptor.category,
                "product_type": descriptor.product_type,
                "product_name": descriptor.product_name,
                "brand": descriptor.brand,
                "variant": descriptor.variant,
                "presentation": descriptor.presentation,
                "current_price": _money(state.current_price_minor),
                "reported_regular_price": _money(state.reported_regular_price_minor),
                "is_promotion": state.is_promotion,
                "availability": state.availability,
                "observed_at": _iso(state.observed_at_utc),
                "last_successful_run": freshness.last_successful_run_id,
                "source_last_successful_at": _iso(freshness.observed_at_utc),
                "data_age_hours": freshness.data_age_hours,
                "freshness_status": freshness.freshness_status.value,
            }
            fact_rows.append(
                {
                    **common,
                    "rank": None if metric is None else metric.rank,
                    "pci": None if metric is None else format(metric.pci, "f"),
                    "market_min": None if competitive is None else _money(competitive.market_min_minor),
                    "market_max": None if competitive is None else _money(competitive.market_max_minor),
                    "market_mean": None if competitive is None else _money_decimal_minor(competitive.market_mean_minor),
                    "market_median": None if competitive is None else _money_decimal_minor(competitive.market_median_minor),
                    "spread_abs": None if competitive is None else _money(competitive.spread_abs_minor),
                    "spread_pct": None if competitive is None else format(competitive.spread_pct, "f"),
                }
            )
            consumer_offers.append(
                {
                    **common,
                    "rank": None if metric is None else metric.rank,
                    "is_best_price": metric is not None and metric.rank == 1,
                    "historical_summary": _historical_summary(
                        canonical_product_id=product.canonical_product_id,
                        supermarket_id=offer.supermarket_id,
                        location_id=offer.location_id,
                        current_state=state,
                        history=history_by_id.get(offer.source_record_id, ()),
                        as_of_utc=as_of_utc,
                    ),
                }
            )
        consumer_products.append(
            {
                "canonical_product_id": product.canonical_product_id,
                "canonical_gtin": product.canonical_gtin,
                "recommended_source_product_ids": sorted(
                    row["source_product_id"]
                    for row in consumer_offers
                    if row["is_best_price"]
                ),
                "offers": sorted(consumer_offers, key=lambda row: (row["supermarket_id"], row["location_id"])),
            }
        )

    freshness_rows = [
        {
            "supermarket_id": item.source_id,
            "location_id": item.location_id,
            "last_successful_run": item.last_successful_run_id,
            "observed_at": _iso(item.observed_at_utc),
            "data_age_hours": item.data_age_hours,
            "freshness_status": item.freshness_status.value,
        }
        for item in sorted(freshness_values, key=lambda row: (row.source_id, row.location_id))
    ]
    coverage = {
        "comparable_count": competition.coverage.comparable_count,
        "valid_price_count": competition.coverage.valid_price_count,
        "excluded_count": competition.coverage.excluded_count,
        "coverage_pct": format(competition.coverage.coverage_pct, "f"),
        "as_of": competition.coverage.as_of,
        "freshness_window_hours": competition.coverage.freshness_window_hours,
    }
    scope = [
        {"supermarket_id": supermarket, "location_id": location}
        for supermarket, location in analytics.scope.locations
    ]
    business = {
        "schema": "rpi-business-mart/v1",
        "comparison_policy": "fail_closed_strong_identity_and_commercial_consistency",
        "comparison_status": competition.comparison_status.value,
        "blocked_reasons": list(competition.blocked_reasons),
        "currency": "HNL",
        "scope": scope,
        "source_freshness": freshness_rows,
        "coverage": coverage,
        "dimensions": {
            "dim_product": sorted(product_dimensions, key=lambda row: row["canonical_product_id"]),
            "dim_retailer": [{"supermarket_id": item[0]} for item in analytics.scope.locations],
            "dim_location": scope,
            "dim_category": [{"category": value} for value in sorted(category_names)],
            "dim_brand": [{"brand": value} for value in sorted(brand_names)],
        },
        "facts": {
            "fact_current_comparison": sorted(
                fact_rows,
                key=lambda row: (row["canonical_product_id"], row["supermarket_id"], row["location_id"]),
            ),
            "fact_basket_cost": [
                {
                    "supermarket_id": supermarket,
                    "location_id": analytics.scope.location_by_supermarket[supermarket],
                    "total": _money(total),
                    "product_count": analytics.common_basket.product_count,
                    "is_complete": analytics.common_basket.product_count > 0,
                }
                for supermarket, total in analytics.common_basket.totals_minor
            ],
            "fact_metric_coverage": [coverage],
        },
    }
    consumer = {
        "schema": "rpi-consumer-mart/v2",
        "comparison_policy": business["comparison_policy"],
        "comparison_status": business["comparison_status"],
        "blocked_reasons": business["blocked_reasons"],
        "currency": "HNL",
        "scope": scope,
        "as_of": competition.coverage.as_of,
        "freshness_window_hours": competition.coverage.freshness_window_hours,
        "source_freshness": freshness_rows,
        "coverage": coverage,
        "product_count": len(consumer_products),
        "products": sorted(consumer_products, key=lambda row: row["canonical_product_id"]),
    }
    return RpiDataMarts(business=business, consumer=consumer)
