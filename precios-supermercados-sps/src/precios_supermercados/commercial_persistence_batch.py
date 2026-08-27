"""Prepara una ejecución comercial para el backend tabular común.

Esta frontera toma una decisión final + ofertas ya validadas, aplica la máquina de
estado en memoria y produce un ``TabularBatch`` atómico con configuración,
current, histórico, registro del run y eventos de calidad. No hace I/O externo.

La identidad canónica cross-source sigue disponible en el modelo lógico, pero sus
tablas físicas se difieren hasta que exista una segunda fuente o un consumidor
que requiera equivalencias reales. La identidad fuente y ``product_id`` siguen
persistidas dentro de current/history, por lo que esta decisión no pierde
trazabilidad ni bloquea una materialización futura.

La validación que puede fallar por ubicación/metadata se ejecuta antes de mutar el
estado en memoria. Un replay ya conocido se rechaza de forma explícita en esta
capa: su reconciliación contra el registro durable requiere el fingerprint
persistido y se implementa por separado, evitando convertir un retry ambiguo en
una segunda escritura.

``extraction_enabled`` controla si se puede iniciar tráfico futuro contra la
fuente. No invalida una observación ya obtenida y comercialmente autorizada. Por
eso esta capa permite persistir evidencia histórica con extracción deshabilitada
si todos los demás invariantes de ubicación siguen demostrados. El serializer
legado todavía reutiliza el gate live; cuando ése sea el único bloqueo se usa una
vista efímera sólo para serialización. Las filas de configuración siempre salen
del catálogo original, por lo que jamás se persiste ``extraction_enabled=True``
por este mecanismo.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Sequence

from .commercial_state import (
    ApplyRunResult,
    CommercialRunDecision,
    CommercialStateError,
    InMemoryCommercialState,
)
from .enums import LocationStatus, RunStatus
from .locations import (
    DEFAULT_LOCATION_CATALOG,
    LocationCatalog,
    LocationConfigError,
    LocationSelectionMode,
    build_location_catalog,
)
from .models import ValidatedOffer
from .tabular_persistence import (
    CFG_LOCATIONS,
    CFG_SUPERMARKETS,
    FACT_OFFER_HISTORY,
    FACT_OFFERS_CURRENT,
    FACT_QUALITY_EVENTS,
    FACT_SCRAPE_RUNS,
    TabularPersistenceError,
    current_offer_row,
    history_offer_row,
    location_config_rows,
    supermarket_config_rows,
    validate_offer_location_for_persistence,
)
from .tabular_records import (
    QualityEventRecord,
    ScrapeRunRecord,
    quality_event_row,
    scrape_run_row,
)
from .tabular_store import TabularBatch, TabularStoreError


class CommercialPersistencePreparationError(ValueError):
    """El run no puede convertirse de forma segura en una transacción durable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PreparedCommercialPersistence:
    """Resultado cerrado listo para entregar al adapter del backend."""

    apply_result: ApplyRunResult
    run_record: ScrapeRunRecord
    batch: TabularBatch
    affected_offer_ids: tuple[str, ...]
    table_row_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "table_row_counts",
            MappingProxyType(dict(self.table_row_counts)),
        )


def _validate_run_location(
    supermarket_id: str,
    location_id: str,
    catalog: LocationCatalog,
) -> None:
    try:
        supermarket = catalog.supermarket(supermarket_id)
        location = catalog.location(location_id)
    except LocationConfigError as exc:
        raise CommercialPersistencePreparationError("run_location_unknown") from exc
    if not supermarket.is_active:
        raise CommercialPersistencePreparationError("run_supermarket_inactive")
    if location.supermarket_id != supermarket_id:
        raise CommercialPersistencePreparationError("run_location_supermarket_mismatch")


def _validate_quality_events(
    quality_events: tuple[QualityEventRecord, ...],
    *,
    scrape_run_id: str,
    supermarket_id: str,
    location_id: str,
) -> None:
    ids: set[str] = set()
    for event in quality_events:
        if not isinstance(event, QualityEventRecord):
            raise CommercialPersistencePreparationError("quality_event_type_invalid")
        if event.quality_event_id in ids:
            raise CommercialPersistencePreparationError("quality_event_id_duplicate")
        ids.add(event.quality_event_id)
        if event.scrape_run_id != scrape_run_id:
            raise CommercialPersistencePreparationError("quality_event_run_mismatch")
        if event.supermarket_id != supermarket_id:
            raise CommercialPersistencePreparationError(
                "quality_event_supermarket_mismatch"
            )
        if event.location_id != location_id:
            raise CommercialPersistencePreparationError("quality_event_location_mismatch")


def _validate_archived_offer_location(
    offer,
    catalog: LocationCatalog,
) -> None:
    """Completa el preflight cuando el único bloqueo live es extracción apagada."""

    try:
        location = catalog.location(offer.location_id)
        supermarket = catalog.supermarket(offer.supermarket_id)
    except LocationConfigError as exc:
        raise TabularPersistenceError("location_unknown") from exc
    if location.supermarket_id != offer.supermarket_id:
        raise TabularPersistenceError("location_id pertenece a otro supermarket_id")
    if offer.location_status is LocationStatus.UNKNOWN:
        raise TabularPersistenceError("location_status_unknown")
    if (
        supermarket.location_selection_mode
        is LocationSelectionMode.SOURCE_SELECTION_REQUIRED
        and offer.location_status is not LocationStatus.CONFIRMED
    ):
        raise TabularPersistenceError(
            "multi_location_offer_requires_confirmed_location"
        )


def _validate_offer_location_for_commercial_persistence(
    offer,
    catalog: LocationCatalog,
) -> None:
    """Valida ubicación durable sin convertir persistencia en permiso de tráfico."""

    try:
        validate_offer_location_for_persistence(offer, catalog)
        return
    except TabularPersistenceError as exc:
        if str(exc) != "extraction_disabled":
            raise
    # ``require_extraction_ready`` sólo emite extraction_disabled después de
    # validar supermercado activo, disponibilidad, scope, granularidad y binding.
    # Falta completar los checks que el serializer original ejecuta después.
    _validate_archived_offer_location(offer, catalog)


def _serialization_catalog_for_archived_location(
    catalog: LocationCatalog,
    location_id: str,
) -> LocationCatalog:
    """Crea una vista efímera para serializers que aún consultan el gate live."""

    location = catalog.location(location_id)
    if location.extraction_enabled:
        return catalog
    enabled_location = replace(location, extraction_enabled=True)
    locations = tuple(
        enabled_location if item.location_id == location_id else item
        for item in catalog.locations
    )
    return build_location_catalog(tuple(catalog.supermarkets.values()), locations)


def _preflight_offers(
    offers: tuple[ValidatedOffer, ...],
    *,
    decision: CommercialRunDecision,
    supermarket_id: str,
    location_id: str,
    catalog: LocationCatalog,
) -> None:
    for item in offers:
        if not isinstance(item, ValidatedOffer):
            raise CommercialPersistencePreparationError("validated_offer_type_invalid")
        offer = item.offer
        if offer.scrape_run_id != decision.scrape_run_id:
            raise CommercialPersistencePreparationError("offer_run_mismatch")
        if offer.supermarket_id != supermarket_id:
            raise CommercialPersistencePreparationError("offer_supermarket_mismatch")
        if offer.location_id != location_id:
            raise CommercialPersistencePreparationError("offer_location_mismatch")
        if decision.commercial_update_allowed:
            try:
                _validate_offer_location_for_commercial_persistence(offer, catalog)
            except TabularPersistenceError as exc:
                raise CommercialPersistencePreparationError(
                    "offer_location_not_persistable"
                ) from exc


def _preflight_run_record(
    *,
    decision: CommercialRunDecision,
    supermarket_id: str,
    location_id: str,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    products_observed: int,
    offers_observed: int,
    quality_event_count: int,
    run_evidence_id: str | None,
) -> None:
    """Fuerza validación de metadata antes de tocar ``state``."""

    try:
        ScrapeRunRecord(
            scrape_run_id=decision.scrape_run_id,
            supermarket_id=supermarket_id,
            location_id=location_id,
            run_status=decision.run_status,
            catalog_accepted=decision.catalog_accepted,
            started_at_utc=started_at_utc,
            finished_at_utc=finished_at_utc,
            products_observed=products_observed,
            offers_observed=offers_observed,
            quality_event_count=quality_event_count,
            run_evidence_id=run_evidence_id,
        )
    except TabularPersistenceError as exc:
        raise CommercialPersistencePreparationError("run_metadata_invalid") from exc


def prepare_new_run_persistence(
    state: InMemoryCommercialState,
    decision: CommercialRunDecision,
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
    """Aplica un run final nuevo y construye su transacción tabular completa.

    ``state`` es el estado efímero de la ejecución. Si el backend falla después,
    el caller debe descartar esa instancia y rehidratar desde el backend antes de
    reintentar; nunca debe considerar la memoria local como autoridad durable.
    """

    if not isinstance(state, InMemoryCommercialState):
        raise CommercialPersistencePreparationError("commercial_state_invalid")
    if not isinstance(decision, CommercialRunDecision):
        raise CommercialPersistencePreparationError("commercial_decision_invalid")
    if decision.run_status is RunStatus.RUNNING:
        raise CommercialPersistencePreparationError("run_not_final")
    if not isinstance(catalog, LocationCatalog):
        raise CommercialPersistencePreparationError("location_catalog_invalid")
    if isinstance(offers, (str, bytes)) or not isinstance(offers, Sequence):
        raise CommercialPersistencePreparationError("offers_sequence_invalid")
    if isinstance(quality_events, (str, bytes)) or not isinstance(
        quality_events, Sequence
    ):
        raise CommercialPersistencePreparationError("quality_events_sequence_invalid")

    offer_values = tuple(offers)
    quality_values = tuple(quality_events)
    _validate_run_location(supermarket_id, location_id, catalog)
    _validate_quality_events(
        quality_values,
        scrape_run_id=decision.scrape_run_id,
        supermarket_id=supermarket_id,
        location_id=location_id,
    )
    _preflight_offers(
        offer_values,
        decision=decision,
        supermarket_id=supermarket_id,
        location_id=location_id,
        catalog=catalog,
    )
    _preflight_run_record(
        decision=decision,
        supermarket_id=supermarket_id,
        location_id=location_id,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        products_observed=products_observed,
        offers_observed=offers_observed,
        quality_event_count=len(quality_values),
        run_evidence_id=run_evidence_id,
    )

    try:
        apply_result = state.apply_run(decision, offer_values)
    except CommercialStateError as exc:
        raise CommercialPersistencePreparationError("commercial_transition_rejected") from exc

    if apply_result.replayed:
        raise CommercialPersistencePreparationError(
            "replayed_run_requires_durable_reconciliation"
        )

    try:
        run_record = ScrapeRunRecord.from_apply_result(
            supermarket_id=supermarket_id,
            location_id=location_id,
            run_status=decision.run_status,
            catalog_accepted=decision.catalog_accepted,
            started_at_utc=started_at_utc,
            finished_at_utc=finished_at_utc,
            products_observed=products_observed,
            offers_observed=offers_observed,
            quality_event_count=len(quality_values),
            apply_result=apply_result,
            run_evidence_id=run_evidence_id,
        )

        affected_offer_ids = tuple(
            sorted({item.offer.offer_id for item in offer_values})
        )
        current_rows: list[Mapping[str, object]] = []
        history_rows: list[Mapping[str, object]] = []
        if decision.commercial_update_allowed:
            serialization_catalog = _serialization_catalog_for_archived_location(
                catalog,
                location_id,
            )
            for offer_id in affected_offer_ids:
                current = state.current(offer_id)
                if current is None:
                    raise CommercialPersistencePreparationError(
                        "commercial_current_missing_after_apply"
                    )
                current_rows.append(current_offer_row(current, serialization_catalog))
                history_rows.extend(
                    history_offer_row(period, serialization_catalog)
                    for period in state.history(offer_id)
                )

        rows = {
            CFG_SUPERMARKETS.name: supermarket_config_rows(catalog),
            CFG_LOCATIONS.name: location_config_rows(catalog),
            FACT_OFFERS_CURRENT.name: tuple(current_rows),
            FACT_OFFER_HISTORY.name: tuple(history_rows),
            FACT_SCRAPE_RUNS.name: (scrape_run_row(run_record, catalog),),
            FACT_QUALITY_EVENTS.name: tuple(
                quality_event_row(event, catalog) for event in quality_values
            ),
        }
        batch = TabularBatch(rows=rows)
    except CommercialPersistencePreparationError:
        raise
    except (TabularPersistenceError, TabularStoreError) as exc:
        raise CommercialPersistencePreparationError(
            "tabular_batch_build_failed"
        ) from exc

    return PreparedCommercialPersistence(
        apply_result=apply_result,
        run_record=run_record,
        batch=batch,
        affected_offer_ids=affected_offer_ids,
        table_row_counts=MappingProxyType(
            {table_name: len(table_rows) for table_name, table_rows in batch.rows.items()}
        ),
    )
