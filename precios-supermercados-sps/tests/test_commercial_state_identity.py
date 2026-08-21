"""Regresiones para evitar contaminación de identidad entre ofertas/runs."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from precios_supermercados.commercial_state import (
    CommercialRunDecision,
    CommercialStateError,
    InMemoryCommercialState,
)
from precios_supermercados.enums import (
    AvailabilityStatus,
    LocationStatus,
    RunStatus,
    SourceKeyType,
)
from precios_supermercados.identifiers import generate_state_hash
from precios_supermercados.models import NormalizedOffer, ValidatedOffer


T0 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _validated(
    run_id: str,
    observed_at: datetime,
    *,
    offer_id: str = "of_001",
    supermarket_id: str = "la-colonia",
    location_id: str = "unknown",
    source_product_id: str = "sp_001",
    source_key: str = "SKU-001",
    product_id: str = "prod_001",
    currency: str = "HNL",
) -> ValidatedOffer:
    offer = NormalizedOffer(
        supermarket_id=supermarket_id,
        location_id=location_id,
        source_product_id=source_product_id,
        source_key_type=SourceKeyType.SKU,
        source_key=source_key,
        product_id=product_id,
        offer_id=offer_id,
        source_name="Producto 001",
        product_url="https://example.invalid/producto-001",
        normalized_name="producto 001",
        currency=currency,
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
        current_price=Decimal("30"),
        reported_regular_price=Decimal("35"),
    )
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=observed_at,
    )


def _accepted(run_id: str, when: datetime) -> CommercialRunDecision:
    return CommercialRunDecision(
        scrape_run_id=run_id,
        run_status=RunStatus.SUCCESS,
        catalog_accepted=True,
        decided_at_utc=when,
    )


def test_existing_offer_id_cannot_move_to_another_location():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0)
    store.apply_run(_accepted("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    moved = _validated("run-2", t1, location_id="otra-ubicacion")

    with pytest.raises(CommercialStateError, match="identidad fuente estable"):
        store.apply_run(_accepted("run-2", t1 + timedelta(minutes=1)), [moved])

    assert store.current("of_001").validated_offer == first
    assert len(store.history("of_001")) == 1
    assert store.applied_run_count == 1


def test_existing_offer_id_cannot_change_source_product_or_source_key():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0)
    store.apply_run(_accepted("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    drifted = _validated(
        "run-2",
        t1,
        source_product_id="sp_999",
        source_key="SKU-999",
    )

    with pytest.raises(CommercialStateError, match="identidad fuente estable"):
        store.apply_run(_accepted("run-2", t1 + timedelta(minutes=1)), [drifted])

    assert store.current_count == 1
    assert store.applied_run_count == 1


def test_same_logical_source_identity_cannot_gain_second_offer_id_later():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, offer_id="of_001")
    store.apply_run(_accepted("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    duplicate_identity = _validated("run-2", t1, offer_id="of_002")

    with pytest.raises(CommercialStateError, match="otro offer_id"):
        store.apply_run(
            _accepted("run-2", t1 + timedelta(minutes=1)),
            [duplicate_identity],
        )

    assert store.current_count == 1
    assert store.current("of_002") is None


def test_same_run_rejects_duplicate_logical_identity_under_distinct_offer_ids():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, offer_id="of_001")
    duplicate = _validated("run-1", T0, offer_id="of_002")

    with pytest.raises(CommercialStateError, match="duplicada"):
        store.apply_run(
            _accepted("run-1", T0 + timedelta(minutes=1)),
            [first, duplicate],
        )

    assert store.current_count == 0
    assert store.applied_run_count == 0


def test_product_mapping_can_change_without_changing_source_identity():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, product_id="prod_pending")
    store.apply_run(_accepted("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    remapped = _validated("run-2", t1, product_id="prod_reviewed")
    result = store.apply_run(
        _accepted("run-2", t1 + timedelta(minutes=1)),
        [remapped],
    )

    assert result.current_confirmed == 1
    current = store.current("of_001")
    assert current is not None
    assert current.validated_offer.offer.product_id == "prod_reviewed"
    assert len(store.history("of_001")) == 1


def test_currency_is_stable_for_the_same_offer_identity():
    store = InMemoryCommercialState()
    first = _validated("run-1", T0, currency="HNL")
    store.apply_run(_accepted("run-1", T0 + timedelta(minutes=1)), [first])

    t1 = T0 + timedelta(days=1)
    changed_currency = _validated("run-2", t1, currency="USD")

    with pytest.raises(CommercialStateError, match="identidad fuente estable"):
        store.apply_run(
            _accepted("run-2", t1 + timedelta(minutes=1)),
            [changed_currency],
        )

    assert store.current("of_001").validated_offer.offer.currency == "HNL"
