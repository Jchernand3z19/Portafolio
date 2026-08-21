"""Counterexamples de reconciliación para derivaciones comerciales."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from precios_supermercados.commercial_pricing import (
    CommercialPricingError,
    evaluate_real_price_reduction,
)
from precios_supermercados.commercial_state import CommercialRunDecision, InMemoryCommercialState
from precios_supermercados.enums import AvailabilityStatus, LocationStatus, RunStatus, SourceKeyType
from precios_supermercados.identifiers import (
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
)
from precios_supermercados.models import NormalizedOffer, ValidatedOffer


T0 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _validated(run_id: str, observed_at: datetime, price: str) -> ValidatedOffer:
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
        is_promotion=False,
        availability=AvailabilityStatus.IN_STOCK,
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
        current_price=Decimal(price),
        reported_regular_price=Decimal("35"),
    )
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=observed_at,
    )


def _decision(run_id: str, when: datetime) -> CommercialRunDecision:
    return CommercialRunDecision(
        scrape_run_id=run_id,
        run_status=RunStatus.SUCCESS,
        catalog_accepted=True,
        decided_at_utc=when,
    )


def _store_three_periods() -> tuple[InMemoryCommercialState, str]:
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, "30")
    store.apply_run(_decision("run-1", T0 + timedelta(minutes=1)), [first])
    t1 = T0 + timedelta(days=1)
    second = _validated("run-2", t1, "25")
    store.apply_run(_decision("run-2", t1 + timedelta(minutes=1)), [second])
    t2 = t1 + timedelta(days=1)
    third = _validated("run-3", t2, "20")
    store.apply_run(_decision("run-3", t2 + timedelta(minutes=1)), [third])
    return store, first.offer.offer_id


def test_current_opening_timestamp_must_match_open_period():
    store, offer_id = _store_three_periods()
    current = store.current(offer_id)
    assert current is not None
    altered = replace(
        current,
        first_observed_at_utc=current.first_observed_at_utc + timedelta(seconds=1),
    )

    with pytest.raises(CommercialPricingError, match="discrepan en apertura"):
        evaluate_real_price_reduction(altered, store.history(offer_id))


def test_current_last_run_must_match_open_period_confirmation():
    store, offer_id = _store_three_periods()
    current = store.current(offer_id)
    assert current is not None
    altered = replace(current, last_scrape_run_id="run-forged")

    with pytest.raises(CommercialPricingError, match="última ejecución"):
        evaluate_real_price_reduction(altered, store.history(offer_id))


def test_intermediate_open_period_fails_closed():
    store, offer_id = _store_three_periods()
    history = list(store.history(offer_id))
    history[1] = replace(history[1], valid_to_utc=None)

    with pytest.raises(CommercialPricingError, match="abierto intermedio"):
        evaluate_real_price_reduction(store.current(offer_id), history)


def test_nonpositive_historical_interval_fails_closed():
    store, offer_id = _store_three_periods()
    history = list(store.history(offer_id))
    history[0] = replace(history[0], valid_to_utc=history[0].valid_from_utc)

    with pytest.raises(CommercialPricingError, match="intervalo no positivo"):
        evaluate_real_price_reduction(store.current(offer_id), history)


def test_history_observation_cannot_precede_period_opening():
    store, offer_id = _store_three_periods()
    history = list(store.history(offer_id))
    history[0] = replace(
        history[0],
        last_observed_at_utc=history[0].valid_from_utc - timedelta(seconds=1),
    )

    with pytest.raises(CommercialPricingError, match="última observación inválida"):
        evaluate_real_price_reduction(store.current(offer_id), history)


def test_closed_period_observation_cannot_be_after_its_close():
    store, offer_id = _store_three_periods()
    history = list(store.history(offer_id))
    assert history[0].valid_to_utc is not None
    history[0] = replace(
        history[0],
        last_observed_at_utc=history[0].valid_to_utc + timedelta(seconds=1),
    )

    with pytest.raises(CommercialPricingError, match="después de su cierre"):
        evaluate_real_price_reduction(store.current(offer_id), history)
