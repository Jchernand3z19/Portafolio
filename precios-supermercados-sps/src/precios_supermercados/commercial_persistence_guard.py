"""Guard productivo delante del preparador comercial backend-neutral.

``commercial_persistence_batch.prepare_new_run_persistence`` es una primitiva
interna útil para probar la máquina comercial, pero acepta una
``CommercialRunDecision`` que por sí sola no demuestra autoridad productiva.

Este módulo conserva la entrada explícita para runs **no autoritativos**. Esos
runs pueden registrarse para observabilidad, pero nunca pueden mutar
``current/history``.

La ruta positiva ya no nace de un booleano libre: La Colonia debe pasar por
``commercial_authority`` +
``scrapers.la_colonia_commercial_authority.verify_la_colonia_commercial_authority``.
Esa política exige una atestación Ed25519 independiente ligada a la readiness y
provenance exactas del run. El preparador crudo sigue siendo una primitiva interna
y no una API productiva.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .commercial_persistence_batch import (
    PreparedCommercialPersistence,
    prepare_new_run_persistence,
)
from .commercial_state import CommercialRunDecision, InMemoryCommercialState
from .enums import RunStatus
from .locations import DEFAULT_LOCATION_CATALOG, LocationCatalog
from .models import ValidatedOffer
from .tabular_records import QualityEventRecord


class CommercialPersistenceGuardError(ValueError):
    """La decisión no puede cruzar la frontera productiva de persistencia."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class NonAuthoritativePersistenceDecision:
    """Decisión final explícitamente incapaz de mutar estado comercial."""

    decision: CommercialRunDecision
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.decision, CommercialRunDecision):
            raise CommercialPersistenceGuardError("commercial_decision_invalid")
        if self.decision.run_status is RunStatus.RUNNING:
            raise CommercialPersistenceGuardError("run_not_final")
        if self.decision.catalog_accepted or self.decision.commercial_update_allowed:
            raise CommercialPersistenceGuardError("productive_authority_required")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise CommercialPersistenceGuardError("non_authoritative_reason_required")
        object.__setattr__(self, "reason", self.reason.strip())

    @property
    def scrape_run_id(self) -> str:
        return self.decision.scrape_run_id


def guard_non_authoritative_decision(
    decision: CommercialRunDecision,
    *,
    reason: str,
) -> NonAuthoritativePersistenceDecision:
    """Sella una decisión final únicamente cuando no puede actualizar current/history."""

    return NonAuthoritativePersistenceDecision(decision=decision, reason=reason)


def prepare_non_authoritative_run_persistence(
    state: InMemoryCommercialState,
    guarded_decision: NonAuthoritativePersistenceDecision,
    offers: Sequence[ValidatedOffer],
    *,
    supermarket_id: str,
    location_id: str,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    products_observed: int,
    offers_observed: int,
    quality_events: Sequence[QualityEventRecord] = (),
    run_evidence_id: str | None = None,
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> PreparedCommercialPersistence:
    """Construye un batch durable que sólo puede registrar un run no autoritativo.

    La función vuelve a verificar el tipo guardado en vez de aceptar una decisión
    cruda. Incluso si el status es ``success`` o ``warning``, ``catalog_accepted``
    debe seguir siendo falso, por lo que el preparador subyacente registrará el
    run/eventos y dejará current/history intactos.
    """

    if not isinstance(guarded_decision, NonAuthoritativePersistenceDecision):
        raise CommercialPersistenceGuardError("guarded_decision_required")
    decision = guarded_decision.decision
    if decision.catalog_accepted or decision.commercial_update_allowed:
        # Defensa redundante frente a futuras modificaciones del wrapper.
        raise CommercialPersistenceGuardError("productive_authority_required")

    return prepare_new_run_persistence(
        state,
        decision,
        offers,
        supermarket_id=supermarket_id,
        location_id=location_id,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        products_observed=products_observed,
        offers_observed=offers_observed,
        quality_events=quality_events,
        run_evidence_id=run_evidence_id,
        catalog=catalog,
    )
