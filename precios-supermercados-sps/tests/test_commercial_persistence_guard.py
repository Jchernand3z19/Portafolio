from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from precios_supermercados.commercial_persistence_guard import (
    CommercialPersistenceGuardError,
    NonAuthoritativePersistenceDecision,
    guard_non_authoritative_decision,
    prepare_non_authoritative_run_persistence,
)
from precios_supermercados.commercial_state import (
    CommercialRunDecision,
    InMemoryCommercialState,
)
from precios_supermercados.enums import RunStatus
from precios_supermercados.locations import (
    LocationConfig,
    LocationGranularity,
    LocationSelectionMode,
    SupermarketConfig,
    build_location_catalog,
)


BASE = datetime(2026, 8, 22, 20, 0, tzinfo=timezone.utc)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = PROJECT_ROOT.parent
RAW_PREPARER = "prepare_new_run_persistence"


def demo_catalog():
    supermarket = SupermarketConfig(
        supermarket_id="demo",
        supermarket_name="Super Demo",
        location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
    )
    location = LocationConfig(
        location_id="demo_sps",
        supermarket_id="demo",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=True,
        evidence="fixed_city_test",
    )
    return build_location_catalog((supermarket,), (location,))


def decision(
    *,
    status: RunStatus = RunStatus.REJECTED,
    accepted: bool = False,
) -> CommercialRunDecision:
    return CommercialRunDecision(
        scrape_run_id="run-guard-001",
        run_status=status,
        catalog_accepted=accepted,
        decided_at_utc=BASE + timedelta(minutes=2),
    )


def test_guard_accepts_only_final_non_authoritative_decision() -> None:
    guarded = guard_non_authoritative_decision(
        decision(),
        reason="catalog_authority_not_available",
    )

    assert isinstance(guarded, NonAuthoritativePersistenceDecision)
    assert guarded.scrape_run_id == "run-guard-001"
    assert guarded.decision.catalog_accepted is False
    assert guarded.decision.commercial_update_allowed is False
    assert guarded.reason == "catalog_authority_not_available"


@pytest.mark.parametrize("status", (RunStatus.SUCCESS, RunStatus.WARNING))
def test_guard_rejects_any_decision_that_would_mutate_commercial_state(
    status: RunStatus,
) -> None:
    with pytest.raises(
        CommercialPersistenceGuardError,
        match="productive_authority_required",
    ):
        guard_non_authoritative_decision(
            decision(status=status, accepted=True),
            reason="caller_claimed_acceptance",
        )


def test_guard_rejects_running_and_blank_reason() -> None:
    with pytest.raises(CommercialPersistenceGuardError, match="run_not_final"):
        guard_non_authoritative_decision(
            decision(status=RunStatus.RUNNING, accepted=False),
            reason="not_final",
        )

    with pytest.raises(
        CommercialPersistenceGuardError,
        match="non_authoritative_reason_required",
    ):
        guard_non_authoritative_decision(decision(), reason="   ")


def test_guarded_success_without_catalog_acceptance_records_run_only() -> None:
    state = InMemoryCommercialState()
    guarded = guard_non_authoritative_decision(
        decision(status=RunStatus.SUCCESS, accepted=False),
        reason="productive_catalog_authority_missing",
    )

    prepared = prepare_non_authoritative_run_persistence(
        state,
        guarded,
        (),
        supermarket_id="demo",
        location_id="demo_sps",
        started_at_utc=BASE,
        finished_at_utc=BASE + timedelta(minutes=1),
        products_observed=0,
        offers_observed=0,
        catalog=demo_catalog(),
    )

    assert prepared.apply_result.commercial_update_allowed is False
    assert prepared.apply_result.mutated is False
    assert prepared.run_record.catalog_accepted is False
    assert prepared.table_row_counts["fact_offers_current"] == 0
    assert prepared.table_row_counts["fact_offer_history"] == 0
    assert prepared.table_row_counts["fact_scrape_runs"] == 1
    assert state.current_count == 0
    assert state.applied_run_count == 1


def test_preparer_refuses_raw_decision_even_when_it_is_non_authoritative() -> None:
    with pytest.raises(
        CommercialPersistenceGuardError,
        match="guarded_decision_required",
    ):
        prepare_non_authoritative_run_persistence(
            InMemoryCommercialState(),
            decision(),  # type: ignore[arg-type]
            (),
            supermarket_id="demo",
            location_id="demo_sps",
            started_at_utc=BASE,
            finished_at_utc=BASE + timedelta(minutes=1),
            products_observed=0,
            offers_observed=0,
            catalog=demo_catalog(),
        )


def test_operational_code_cannot_bypass_guard_with_raw_preparer() -> None:
    """Scripts/workflows y módulos nuevos deben usar fronteras auditadas.

    El preparador crudo sólo puede vivir en su módulo backend-neutral, el guard
    no autoritativo y la política autoritativa específica de La Colonia. Tests
    pueden usarlo directamente para validar la máquina interna, pero no forman
    parte del código operativo escaneado aquí.
    """

    allowed = {
        PROJECT_ROOT
        / "src/precios_supermercados/commercial_persistence_batch.py",
        PROJECT_ROOT
        / "src/precios_supermercados/commercial_persistence_guard.py",
        PROJECT_ROOT
        / "src/precios_supermercados/scrapers/la_colonia_commercial_authority.py",
    }
    candidates = [
        *sorted((PROJECT_ROOT / "src").rglob("*.py")),
        *sorted((PROJECT_ROOT / "scripts").rglob("*.py")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yml")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yaml")),
    ]

    violations = []
    for path in candidates:
        if path in allowed:
            continue
        if RAW_PREPARER in path.read_text(encoding="utf-8"):
            violations.append(str(path.relative_to(MONOREPO_ROOT)))

    assert violations == []
