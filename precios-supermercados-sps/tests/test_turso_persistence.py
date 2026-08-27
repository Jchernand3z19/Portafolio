from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from precios_supermercados.commercial_persistence_batch import prepare_new_run_persistence
from precios_supermercados.commercial_state import CommercialRunDecision, InMemoryCommercialState
from precios_supermercados.enums import (
    AvailabilityStatus,
    LocationStatus,
    QualityEventCategory,
    QualityEventSeverity,
    RunStatus,
    SourceKeyType,
)
from precios_supermercados.identifiers import (
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
)
from precios_supermercados.locations import (
    LocationConfig,
    LocationGranularity,
    LocationSelectionMode,
    SupermarketConfig,
    build_location_catalog,
)
from precios_supermercados.models import NormalizedOffer, ValidatedOffer
from precios_supermercados.storage_contract import (
    ACTIVE_STORAGE_BACKEND,
    ACTIVE_STORAGE_TABLE_NAMES,
)
from precios_supermercados.tabular_records import QualityEventRecord
from precios_supermercados.turso_contract import (
    CURRENT_SCHEMA_VERSION,
    OFFER_HISTORY,
    OFFERS_CURRENT,
    TURSO_TABLE_NAMES,
)
from precios_supermercados.turso_persistence import (
    TursoAdapter,
    TursoPersistenceError,
    TursoReplayConflict,
    build_turso_write_plan,
)


BASE = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
EVIDENCE_ID = "crev1_" + "a" * 64


def catalog():
    return build_location_catalog(
        (
            SupermarketConfig(
                supermarket_id="demo",
                supermarket_name="Super Demo",
                location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
            ),
        ),
        (
            LocationConfig(
                location_id="demo_sps",
                supermarket_id="demo",
                city_id="sps",
                city_name="San Pedro Sula",
                granularity=LocationGranularity.CITY,
                is_available=True,
                in_scope=True,
                extraction_enabled=False,
                evidence="turso_test",
            ),
        ),
    )


def validated(
    *,
    run_id: str,
    observed_at: datetime,
    price: str | None = "40",
    availability: AvailabilityStatus = AvailabilityStatus.IN_STOCK,
    brand: str = "Marca",
) -> ValidatedOffer:
    source_key = "SKU-001"
    source_product_id = generate_source_product_id("demo", SourceKeyType.SKU, source_key)
    offer = NormalizedOffer(
        supermarket_id="demo",
        location_id="demo_sps",
        source_product_id=source_product_id,
        source_key_type=SourceKeyType.SKU,
        source_key=source_key,
        product_id=f"prod_pending_{source_product_id}",
        offer_id=generate_offer_id("demo", "demo_sps", source_product_id),
        source_name="Producto demo 1 unidad",
        product_url="https://example.invalid/p/001",
        normalized_name="Producto demo",
        currency="HNL",
        is_promotion=False,
        availability=availability,
        location_status=LocationStatus.INFERRED,
        location_evidence="fixture",
        location_confidence=Decimal("1"),
        observed_at_utc=observed_at,
        scrape_run_id=run_id,
        extractor_version="test",
        schema_version="1",
        source_url="https://example.invalid/catalog",
        normalized_brand=brand,
        category="Demo",
        subcategory="Demo",
        variant="Base",
        unit_count=1,
        content_per_unit=Decimal("1"),
        measurement_unit="unit",
        total_content=Decimal("1"),
        current_price=None if price is None else Decimal(price),
    )
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=observed_at,
    )


def quality_event(run_id: str, *, sequence: int = 0) -> QualityEventRecord:
    return QualityEventRecord.deterministic(
        scrape_run_id=run_id,
        supermarket_id="demo",
        location_id="demo_sps",
        category=QualityEventCategory.QUALITY,
        severity=QualityEventSeverity.INFO,
        event_code="catalog_validated",
        observed_at_utc=BASE,
        sequence=sequence,
    )


def prepare(
    state: InMemoryCommercialState,
    item: ValidatedOffer,
    *,
    accepted: bool = True,
    status: RunStatus = RunStatus.SUCCESS,
    events: tuple[QualityEventRecord, ...] = (),
):
    return prepare_new_run_persistence(
        state,
        CommercialRunDecision(
            scrape_run_id=item.offer.scrape_run_id,
            run_status=status,
            catalog_accepted=accepted,
            decided_at_utc=item.validated_at_utc + timedelta(minutes=1),
        ),
        (item,),
        supermarket_id="demo",
        location_id="demo_sps",
        started_at_utc=item.offer.observed_at_utc - timedelta(seconds=10),
        finished_at_utc=item.offer.observed_at_utc + timedelta(seconds=10),
        products_observed=1,
        offers_observed=1,
        quality_events=events,
        run_evidence_id=EVIDENCE_ID if accepted else None,
        catalog=catalog(),
    )


def bootstrapped():
    connection = sqlite3.connect(":memory:")
    adapter = TursoAdapter(connection)
    assert adapter.bootstrap() == CURRENT_SCHEMA_VERSION
    return connection, adapter


def count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def test_turso_is_the_active_physical_contract():
    assert ACTIVE_STORAGE_BACKEND == "turso"
    assert ACTIVE_STORAGE_TABLE_NAMES == TURSO_TABLE_NAMES
    assert OFFERS_CURRENT.name in TURSO_TABLE_NAMES
    assert OFFER_HISTORY.name in TURSO_TABLE_NAMES


def test_bootstrap_creates_strict_schema_foreign_keys_and_version():
    connection, _ = bootstrapped()
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert set(TURSO_TABLE_NAMES).issubset(tables)
    assert "_schema_version" in tables
    assert connection.execute(
        "SELECT version FROM _schema_version WHERE singleton = 1"
    ).fetchone()[0] == CURRENT_SCHEMA_VERSION
    table_list = {
        row[1]: row
        for row in connection.execute("PRAGMA table_list").fetchall()
    }
    assert table_list[OFFERS_CURRENT.name][-1] == 1  # STRICT


def test_first_load_exact_replay_and_read_back_rehydrate():
    state = InMemoryCommercialState()
    prepared = prepare(
        state,
        validated(run_id="run-1", observed_at=BASE),
        events=(quality_event("run-1"),),
    )
    plan = build_turso_write_plan(prepared)
    connection, adapter = bootstrapped()

    result = adapter.apply(plan)

    assert result.exact_run_replay is False
    assert count(connection, "offers_current") == 1
    assert count(connection, "offer_history") == 1
    assert count(connection, "scrape_runs") == 1
    assert count(connection, "quality_events") == 1
    current = connection.execute(
        "SELECT current_price, current_price_minor, quantity_is_exact "
        "FROM offers_current"
    ).fetchone()
    assert current == ("40", 4000, 0)

    replay = adapter.apply(plan)
    assert replay.exact_run_replay is True
    assert count(connection, "offer_history") == 1
    snapshot = adapter.read_back(supermarket_id="demo", location_id="demo_sps").rehydrate()
    assert len(snapshot.current) == 1
    live = next(iter(snapshot.current.values()))
    assert live.validated_offer.offer.current_price == Decimal("40")
    assert live.last_scrape_run_id == "run-1"


def test_unchanged_daily_run_updates_current_but_not_change_history():
    state = InMemoryCommercialState()
    first = build_turso_write_plan(
        prepare(state, validated(run_id="run-1", observed_at=BASE))
    )
    connection, adapter = bootstrapped()
    adapter.apply(first)

    second_time = BASE + timedelta(days=1)
    second = build_turso_write_plan(
        prepare(state, validated(run_id="run-2", observed_at=second_time))
    )
    result = adapter.apply(second)

    assert count(connection, "scrape_runs") == 2
    assert count(connection, "offers_current") == 1
    assert count(connection, "offer_history") == 1
    assert result.history_confirmations_skipped == 1
    assert connection.execute(
        "SELECT last_scrape_run_id FROM offers_current"
    ).fetchone()[0] == "run-2"

    snapshot = adapter.read_back(supermarket_id="demo", location_id="demo_sps").rehydrate()
    live = next(iter(snapshot.current.values()))
    period = next(iter(snapshot.history.values()))[0]
    assert live.last_scrape_run_id == "run-2"
    assert period.last_confirmed_by_scrape_run_id == "run-2"
    assert period.last_observed_at_utc == second_time


def test_real_price_change_closes_previous_period_and_opens_one_new_period():
    state = InMemoryCommercialState()
    connection, adapter = bootstrapped()
    adapter.apply(
        build_turso_write_plan(
            prepare(state, validated(run_id="run-1", observed_at=BASE, price="40"))
        )
    )
    adapter.apply(
        build_turso_write_plan(
            prepare(
                state,
                validated(
                    run_id="run-2",
                    observed_at=BASE + timedelta(days=1),
                    price="40",
                ),
            )
        )
    )
    changed_at = BASE + timedelta(days=2)
    result = adapter.apply(
        build_turso_write_plan(
            prepare(
                state,
                validated(run_id="run-3", observed_at=changed_at, price="35.50"),
            )
        )
    )

    assert count(connection, "offer_history") == 2
    assert connection.execute(
        "SELECT current_price_minor FROM offers_current"
    ).fetchone()[0] == 3550
    periods = connection.execute(
        "SELECT current_price, valid_to_utc, closed_by_scrape_run_id "
        "FROM offer_history ORDER BY valid_from_utc"
    ).fetchall()
    assert periods[0][0] == "40"
    assert periods[0][1] is not None
    assert periods[0][2] == "run-3"
    assert periods[1][0] == "35.5"
    assert periods[1][1] is None
    assert result.updated >= 2

    snapshot = adapter.read_back(supermarket_id="demo", location_id="demo_sps").rehydrate()
    assert len(next(iter(snapshot.history.values()))) == 2


def test_rejected_run_is_ledger_only_and_cannot_mutate_commercial_state():
    state = InMemoryCommercialState()
    connection, adapter = bootstrapped()
    accepted = build_turso_write_plan(
        prepare(state, validated(run_id="run-ok", observed_at=BASE))
    )
    adapter.apply(accepted)
    before_current = connection.execute(
        "SELECT state_hash, last_scrape_run_id FROM offers_current"
    ).fetchone()

    rejected_item = validated(
        run_id="run-rejected",
        observed_at=BASE + timedelta(days=1),
        price="1",
    )
    rejected = build_turso_write_plan(
        prepare(
            state,
            rejected_item,
            accepted=False,
            status=RunStatus.REJECTED,
        )
    )
    adapter.apply(rejected)

    assert count(connection, "scrape_runs") == 2
    assert count(connection, "offer_history") == 1
    assert connection.execute(
        "SELECT state_hash, last_scrape_run_id FROM offers_current"
    ).fetchone() == before_current


def test_divergent_run_replay_is_rejected():
    state = InMemoryCommercialState()
    connection, adapter = bootstrapped()
    plan = build_turso_write_plan(
        prepare(state, validated(run_id="run-1", observed_at=BASE))
    )
    adapter.apply(plan)

    connection.execute(
        "UPDATE scrape_runs SET run_fingerprint = ? WHERE scrape_run_id = ?",
        ("c" * 64, "run-1"),
    )
    connection.commit()
    with pytest.raises(TursoReplayConflict):
        adapter.apply(plan)


def test_partial_failure_rolls_back_run_and_all_prior_writes():
    state = InMemoryCommercialState()
    item = validated(run_id="run-rejected", observed_at=BASE)
    prepared = prepare(state, item, accepted=False, status=RunStatus.REJECTED)
    override = {
        "override_id": "ov_missing",
        "supermarket_id": "demo",
        "source_product_id": "sp_missing",
        "source_signature": "sig",
        "field_name": "normalized_brand",
        "source_value": "X",
        "override_value": "Y",
        "reason": "test",
        "active": True,
        "created_at_utc": "2026-08-27T12:00:00.000Z",
        "updated_at_utc": "2026-08-27T12:00:00.000Z",
    }
    plan = build_turso_write_plan(prepared, normalization_overrides=(override,))
    connection, adapter = bootstrapped()

    with pytest.raises(TursoPersistenceError, match="transaction_failed"):
        adapter.apply(plan)

    assert count(connection, "scrape_runs") == 0
    assert count(connection, "normalization_overrides") == 0


def test_critical_current_lookup_uses_index():
    _, adapter = bootstrapped()
    plan = adapter.explain_query_plan(
        "SELECT offer_id FROM offers_current "
        "WHERE supermarket_id = ? AND location_id = ? AND source_product_id = ?",
        ("demo", "demo_sps", "sp"),
    )
    detail = " | ".join(plan).upper()
    assert "SEARCH" in detail
    assert "USING" in detail
    assert "SCAN OFFERS_CURRENT" not in detail


def test_subcent_currency_value_fails_closed():
    state = InMemoryCommercialState()
    prepared = prepare(
        state,
        validated(run_id="run-subcent", observed_at=BASE, price="40.001"),
    )
    with pytest.raises(TursoPersistenceError, match="subcent_precision"):
        build_turso_write_plan(prepared)
