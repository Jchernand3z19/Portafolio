"""Regresión: current debe reflejar la última evidencia aceptada del mismo estado."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from precios_supermercados.commercial_state import (
    CommercialRunDecision,
    InMemoryCommercialState,
)
from precios_supermercados.enums import AvailabilityStatus, LocationStatus, RunStatus, SourceKeyType
from precios_supermercados.identifiers import generate_state_hash
from precios_supermercados.models import NormalizedOffer, ValidatedOffer


BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _validated(run_id: str, observed_at: datetime) -> ValidatedOffer:
    offer = NormalizedOffer(
        supermarket_id="la-colonia",
        location_id="unknown",
        source_product_id="sp_001",
        source_key_type=SourceKeyType.SKU,
        source_key="SKU-001",
        product_id="prod_001",
        offer_id="of_001",
        source_name="Producto 001",
        product_url="https://example.invalid/producto-001",
        normalized_name="producto 001",
        currency="HNL",
        is_promotion=False,
        availability=AvailabilityStatus.IN_STOCK,
        location_status=LocationStatus.UNKNOWN,
        observed_at_utc=observed_at,
        scrape_run_id=run_id,
        extractor_version=f"extractor-{run_id}",
        schema_version="1",
        source_url=f"https://example.invalid/graphql?run={run_id}",
        normalized_brand="Marca Demo",
        category="Abarrotes",
        subcategory="General",
        variant="Base",
        unit_count=1,
        content_per_unit=Decimal("1"),
        measurement_unit="unit",
        total_content=Decimal("1"),
        current_price=Decimal("30"),
        reported_regular_price=Decimal("35"),
    )
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=observed_at,
    )


def _decision(run_id: str, decided_at: datetime) -> CommercialRunDecision:
    return CommercialRunDecision(
        scrape_run_id=run_id,
        run_status=RunStatus.SUCCESS,
        catalog_accepted=True,
        decided_at_utc=decided_at,
    )


def test_same_hash_refreshes_current_evidence_but_keeps_single_history_period():
    store = InMemoryCommercialState()
    first = _validated("run-1", BASE_TIME)
    second_time = BASE_TIME + timedelta(days=1)
    second = _validated("run-2", second_time)

    store.apply_run(_decision("run-1", BASE_TIME + timedelta(minutes=1)), [first])
    result = store.apply_run(
        _decision("run-2", second_time + timedelta(minutes=1)),
        [second],
    )

    assert result.current_confirmed == 1
    current = store.current("of_001")
    assert current is not None
    assert current.validated_offer == second
    assert current.last_scrape_run_id == "run-2"
    assert current.validated_offer.offer.scrape_run_id == current.last_scrape_run_id
    assert current.first_observed_at_utc == BASE_TIME
    assert current.last_observed_at_utc == second_time

    history = store.history("of_001")
    assert len(history) == 1
    assert history[0].validated_offer == first
    assert history[0].last_confirmed_by_scrape_run_id == "run-2"
    assert history[0].last_observed_at_utc == second_time
