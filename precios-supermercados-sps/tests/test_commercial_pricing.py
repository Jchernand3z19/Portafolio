"""Regla comercial: ahorro real usa histórico aceptado, no precio reportado."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from precios_supermercados.commercial_pricing import evaluate_real_price_reduction
from precios_supermercados.commercial_state import CommercialRunDecision, InMemoryCommercialState
from precios_supermercados.enums import AvailabilityStatus, LocationStatus, RunStatus, SourceKeyType
from precios_supermercados.identifiers import (
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
)
from precios_supermercados.models import NormalizedOffer, ValidatedOffer


T0 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _validated(
    run_id: str,
    observed_at: datetime,
    *,
    current_price: str | None = "30",
    reported_regular_price: str | None = "35",
    is_promotion: bool = False,
    availability: AvailabilityStatus = AvailabilityStatus.IN_STOCK,
) -> ValidatedOffer:
    supermarket_id = "la-colonia"
    location_id = "unknown"
    source_key = "SKU-001"
    source_product_id = generate_source_product_id(
        supermarket_id,
        SourceKeyType.SKU,
        source_key,
    )
    offer_id = generate_offer_id(supermarket_id, location_id, source_product_id)
    offer = NormalizedOffer(
        supermarket_id=supermarket_id,
        location_id=location_id,
        source_product_id=source_product_id,
        source_key_type=SourceKeyType.SKU,
        source_key=source_key,
        product_id="prod_001",
        offer_id=offer_id,
        source_name="Producto 001",
        product_url="https://example.invalid/producto-001",
        normalized_name="producto 001",
        currency="HNL",
        is_promotion=is_promotion,
        availability=availability,
        location_status=LocationStatus.UNKNOWN,
        observed_at_utc=observed_at,
        scrape_run_id=run_id,
        extractor_version="test",
        schema_version="1",
        source_url="https://example.invalid/graphql",
        normalized_brand="Marca",
        category="Categoria",
        subcategory="Subcategoria",
        variant="Base",
        unit_count=1,
        content_per_unit=Decimal("1"),
        measurement_unit="unit",
        total_content=Decimal("1"),
        current_price=(Decimal(current_price) if current_price is not None else None),
        reported_regular_price=(
            Decimal(reported_regular_price)
            if reported_regular_price is not None
            else None
        ),
    )
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=observed_at,
    )


def _decision(
    run_id: str,
    when: datetime,
    *,
    status: RunStatus = RunStatus.SUCCESS,
    accepted: bool = True,
) -> CommercialRunDecision:
    return CommercialRunDecision(
        scrape_run_id=run_id,
        run_status=status,
        catalog_accepted=accepted,
        decided_at_utc=when,
    )


def test_initial_offer_has_no_real_reduction_even_if_source_reports_large_regular_price():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="30", reported_regular_price="100", is_promotion=True)
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.current_price == Decimal("30")
    assert result.previous_accepted_price is None
    assert result.reduction_amount is None
    assert result.reduction_ratio is None
    assert result.is_real_reduction is False


def test_real_reduction_uses_previous_accepted_current_price_not_reported_regular_price():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="30", reported_regular_price="35")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    second = _validated(
        "run-2",
        t1,
        current_price="25",
        reported_regular_price="100",
        is_promotion=True,
    )
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [second])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.previous_accepted_price == Decimal("30")
    assert result.current_price == Decimal("25")
    assert result.reduction_amount == Decimal("5")
    assert result.reduction_ratio == Decimal("5") / Decimal("30")
    assert result.is_real_reduction is True
    assert result.previous_scrape_run_id == "run-1"
    assert result.current_scrape_run_id == "run-2"


def test_source_promotion_without_historical_price_drop_is_not_real_reduction():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="25", reported_regular_price="30")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    second = _validated(
        "run-2",
        t1,
        current_price="25",
        reported_regular_price="100",
        is_promotion=True,
    )
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [second])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.previous_accepted_price == Decimal("25")
    assert result.current_price == Decimal("25")
    assert result.reduction_amount == Decimal("0")
    assert result.reduction_ratio == Decimal("0")
    assert result.is_real_reduction is False


def test_price_increase_is_not_real_reduction_even_with_reported_regular_price():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="20")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    second = _validated("run-2", t1, current_price="25", reported_regular_price="50", is_promotion=True)
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [second])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.previous_accepted_price == Decimal("20")
    assert result.reduction_amount == Decimal("0")
    assert result.reduction_ratio == Decimal("0")
    assert result.is_real_reduction is False


def test_same_hash_confirmation_keeps_previous_period_as_real_reduction_baseline():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="30")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    dropped = _validated("run-2", t1, current_price="25")
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [dropped])

    t2 = t1 + timedelta(days=1)
    confirmed = _validated("run-3", t2, current_price="25")
    store.apply_run(_decision("run-3", t2 + timedelta(minutes=1)), [confirmed])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.previous_accepted_price == Decimal("30")
    assert result.current_price == Decimal("25")
    assert result.reduction_amount == Decimal("5")
    assert result.current_scrape_run_id == "run-3"
    assert result.previous_scrape_run_id == "run-1"


def test_non_price_state_change_with_same_price_becomes_new_immediate_baseline():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="30")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    dropped = _validated("run-2", t1, current_price="25", reported_regular_price="35")
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [dropped])

    t2 = t1 + timedelta(days=1)
    source_reference_changed = _validated(
        "run-3",
        t2,
        current_price="25",
        reported_regular_price="40",
    )
    store.apply_run(_decision("run-3", t2 + timedelta(minutes=1)), [source_reference_changed])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.previous_accepted_price == Decimal("25")
    assert result.current_price == Decimal("25")
    assert result.reduction_amount == Decimal("0")
    assert result.is_real_reduction is False


def test_rejected_run_cannot_create_a_fake_real_reduction():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="30")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    rejected = _validated("run-2", t1, current_price="10", reported_regular_price="100", is_promotion=True)
    store.apply_run(
        _decision(
            "run-2",
            t1 + timedelta(minutes=1),
            status=RunStatus.REJECTED,
            accepted=False,
        ),
        [rejected],
    )

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.current_price == Decimal("30")
    assert result.previous_accepted_price is None
    assert result.is_real_reduction is False


def test_out_of_stock_current_state_does_not_invent_reduction():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, current_price="30")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    unavailable = _validated(
        "run-2",
        t1,
        current_price=None,
        reported_regular_price=None,
        availability=AvailabilityStatus.OUT_OF_STOCK,
    )
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [unavailable])

    result = evaluate_real_price_reduction(store, first.offer.offer_id)

    assert result is not None
    assert result.current_price is None
    assert result.previous_accepted_price == Decimal("30")
    assert result.reduction_amount is None
    assert result.reduction_ratio is None
    assert result.is_real_reduction is False


def test_unknown_offer_has_no_price_comparison():
    assert evaluate_real_price_reduction(InMemoryCommercialState(), "of_missing") is None
