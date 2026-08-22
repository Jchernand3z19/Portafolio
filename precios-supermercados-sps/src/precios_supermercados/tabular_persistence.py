"""Contrato tabular común para persistencia y revisión humana.

No escribe en Google Sheets ni en otro backend. Define las columnas canónicas que
compartirán todos los supermercados y serializa current/history sin perder la
identidad de supermercado y ubicación.

La capa es fail-closed respecto a ubicación: una oferta no puede convertirse en
fila persistible si su ubicación no está habilitada en ``LocationCatalog`` o si
una fuente multiubicación no demuestra una asignación confirmada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from .commercial_state import CurrentCommercialOffer, OfferHistoryPeriod
from .enums import LocationStatus
from .locations import (
    DEFAULT_LOCATION_CATALOG,
    LocationCatalog,
    LocationConfig,
    LocationConfigError,
    LocationSelectionMode,
)
from .models import NormalizedOffer, ValidatedOffer


class TabularPersistenceError(ValueError):
    """Una fila no cumple el contrato tabular persistible."""


@dataclass(frozen=True, slots=True)
class TableSpec:
    """Esquema cerrado de una tabla lógica compartida."""

    name: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise TabularPersistenceError("name no puede estar vacío")
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise TabularPersistenceError("columns debe ser único y no vacío")
        if not self.primary_key or not set(self.primary_key).issubset(self.columns):
            raise TabularPersistenceError("primary_key debe existir en columns")


CFG_SUPERMARKETS = TableSpec(
    name="cfg_supermarkets",
    columns=(
        "supermarket_id",
        "supermarket_name",
        "country_code",
        "location_selection_mode",
        "is_active",
    ),
    primary_key=("supermarket_id",),
)

CFG_LOCATIONS = TableSpec(
    name="cfg_locations",
    columns=(
        "location_id",
        "supermarket_id",
        "city_id",
        "city_name",
        "granularity",
        "source_location_key",
        "is_available",
        "in_scope",
        "extraction_enabled",
        "technical_binding_confirmed",
        "evidence",
    ),
    primary_key=("location_id",),
)

FACT_OFFERS_CURRENT = TableSpec(
    name="fact_offers_current",
    columns=(
        "offer_id",
        "supermarket_id",
        "supermarket_name",
        "location_id",
        "city_id",
        "city_name",
        "location_granularity",
        "source_product_id",
        "product_id",
        "source_key_type",
        "source_key",
        "source_sku",
        "source_name",
        "normalized_name",
        "source_brand",
        "normalized_brand",
        "source_presentation",
        "category",
        "subcategory",
        "variant",
        "unit_count",
        "content_per_unit",
        "measurement_unit",
        "total_content",
        "currency",
        "current_price",
        "reported_regular_price",
        "is_promotion",
        "availability",
        "unit_price",
        "unit_price_basis",
        "state_hash",
        "review_status",
        "observed_at_utc",
        "first_observed_at_utc",
        "last_observed_at_utc",
        "last_scrape_run_id",
        "product_url",
        "image_url",
    ),
    primary_key=("offer_id",),
)

FACT_OFFER_HISTORY = TableSpec(
    name="fact_offer_history",
    columns=(
        "offer_history_id",
        "offer_id",
        "supermarket_id",
        "supermarket_name",
        "location_id",
        "city_id",
        "city_name",
        "location_granularity",
        "source_product_id",
        "product_id",
        "source_key_type",
        "source_key",
        "source_sku",
        "source_name",
        "normalized_name",
        "source_brand",
        "normalized_brand",
        "source_presentation",
        "category",
        "subcategory",
        "variant",
        "unit_count",
        "content_per_unit",
        "measurement_unit",
        "total_content",
        "currency",
        "current_price",
        "reported_regular_price",
        "is_promotion",
        "availability",
        "unit_price",
        "unit_price_basis",
        "state_hash",
        "change_type",
        "changed_fields_json",
        "review_status",
        "valid_from_utc",
        "valid_to_utc",
        "opened_by_scrape_run_id",
        "closed_by_scrape_run_id",
        "last_confirmed_by_scrape_run_id",
        "last_observed_at_utc",
        "product_url",
        "image_url",
    ),
    primary_key=("offer_history_id",),
)

FACT_SCRAPE_RUNS = TableSpec(
    name="fact_scrape_runs",
    columns=(
        "scrape_run_id",
        "supermarket_id",
        "location_id",
        "run_status",
        "catalog_accepted",
        "started_at_utc",
        "finished_at_utc",
        "products_observed",
        "offers_observed",
        "current_created",
        "current_changed",
        "current_confirmed",
        "offers_ignored",
        "quality_event_count",
        "run_evidence_id",
    ),
    primary_key=("scrape_run_id",),
)

FACT_QUALITY_EVENTS = TableSpec(
    name="fact_quality_events",
    columns=(
        "quality_event_id",
        "scrape_run_id",
        "supermarket_id",
        "location_id",
        "offer_id",
        "category",
        "severity",
        "event_code",
        "observed_at_utc",
    ),
    primary_key=("quality_event_id",),
)

TABLE_SPECS: Mapping[str, TableSpec] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            CFG_SUPERMARKETS,
            CFG_LOCATIONS,
            FACT_OFFERS_CURRENT,
            FACT_OFFER_HISTORY,
            FACT_SCRAPE_RUNS,
            FACT_QUALITY_EVENTS,
        )
    }
)


def _enum_text(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    rendered = format(normalized, "f")
    return "0" if rendered in {"", "-0"} else rendered


def _utc_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise TabularPersistenceError("datetime sin zona horaria")
    if value.utcoffset().total_seconds() != 0:
        raise TabularPersistenceError("datetime debe estar en UTC")
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _closed_row(spec: TableSpec, values: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(values).difference(spec.columns)
    missing = set(spec.columns).difference(values)
    if unknown or missing:
        raise TabularPersistenceError(
            f"fila {spec.name} no coincide con esquema; missing={sorted(missing)} "
            f"unknown={sorted(unknown)}"
        )
    row = {column: values[column] for column in spec.columns}
    if any(row[column] in (None, "") for column in spec.primary_key):
        raise TabularPersistenceError(f"primary key vacía en {spec.name}")
    return row


def supermarket_config_rows(
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> tuple[dict[str, Any], ...]:
    """Serializa una sola tabla de supermercados para todas las fuentes."""

    rows = []
    for supermarket_id in sorted(catalog.supermarkets):
        supermarket = catalog.supermarkets[supermarket_id]
        rows.append(
            _closed_row(
                CFG_SUPERMARKETS,
                {
                    "supermarket_id": supermarket.supermarket_id,
                    "supermarket_name": supermarket.supermarket_name,
                    "country_code": supermarket.country_code,
                    "location_selection_mode": supermarket.location_selection_mode.value,
                    "is_active": supermarket.is_active,
                },
            )
        )
    return tuple(rows)


def location_config_rows(
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> tuple[dict[str, Any], ...]:
    """Serializa todas las ubicaciones en una tabla común."""

    rows = []
    for location in sorted(catalog.locations, key=lambda value: value.location_id):
        rows.append(
            _closed_row(
                CFG_LOCATIONS,
                {
                    "location_id": location.location_id,
                    "supermarket_id": location.supermarket_id,
                    "city_id": location.city_id,
                    "city_name": location.city_name,
                    "granularity": location.granularity.value,
                    "source_location_key": location.source_location_key,
                    "is_available": location.is_available,
                    "in_scope": location.in_scope,
                    "extraction_enabled": location.extraction_enabled,
                    "technical_binding_confirmed": location.technical_binding_confirmed,
                    "evidence": location.evidence,
                },
            )
        )
    return tuple(rows)


def validate_offer_location_for_persistence(
    offer: NormalizedOffer,
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> LocationConfig:
    """Impide persistir una oferta bajo una ciudad no demostrada."""

    if not isinstance(offer, NormalizedOffer):
        raise TabularPersistenceError("offer debe ser NormalizedOffer")
    try:
        location = catalog.require_extraction_ready(offer.location_id)
    except LocationConfigError as exc:
        raise TabularPersistenceError(str(exc)) from exc
    if location.supermarket_id != offer.supermarket_id:
        raise TabularPersistenceError(
            "location_id pertenece a otro supermarket_id"
        )
    if offer.location_status is LocationStatus.UNKNOWN:
        raise TabularPersistenceError("location_status_unknown")
    supermarket = catalog.supermarket(offer.supermarket_id)
    if (
        supermarket.location_selection_mode
        is LocationSelectionMode.SOURCE_SELECTION_REQUIRED
        and offer.location_status is not LocationStatus.CONFIRMED
    ):
        raise TabularPersistenceError(
            "multi_location_offer_requires_confirmed_location"
        )
    return location


def _offer_base_row(
    validated: ValidatedOffer,
    catalog: LocationCatalog,
) -> dict[str, Any]:
    if not isinstance(validated, ValidatedOffer):
        raise TabularPersistenceError("validated debe ser ValidatedOffer")
    offer = validated.offer
    location = validate_offer_location_for_persistence(offer, catalog)
    supermarket = catalog.supermarket(offer.supermarket_id)
    return {
        "offer_id": offer.offer_id,
        "supermarket_id": offer.supermarket_id,
        "supermarket_name": supermarket.supermarket_name,
        "location_id": offer.location_id,
        "city_id": location.city_id,
        "city_name": location.city_name,
        "location_granularity": location.granularity.value,
        "source_product_id": offer.source_product_id,
        "product_id": offer.product_id,
        "source_key_type": offer.source_key_type.value,
        "source_key": offer.source_key,
        "source_sku": offer.source_sku,
        "source_name": offer.source_name,
        "normalized_name": offer.normalized_name,
        "source_brand": offer.source_brand,
        "normalized_brand": offer.normalized_brand,
        "source_presentation": offer.source_presentation,
        "category": offer.category,
        "subcategory": offer.subcategory,
        "variant": offer.variant,
        "unit_count": offer.unit_count,
        "content_per_unit": _decimal_text(offer.content_per_unit),
        "measurement_unit": offer.measurement_unit,
        "total_content": _decimal_text(offer.total_content),
        "currency": offer.currency,
        "current_price": _decimal_text(offer.current_price),
        "reported_regular_price": _decimal_text(offer.reported_regular_price),
        "is_promotion": offer.is_promotion,
        "availability": offer.availability.value,
        "unit_price": _decimal_text(offer.unit_price),
        "unit_price_basis": offer.unit_price_basis,
        "state_hash": validated.state_hash,
        "review_status": validated.review_status.value,
        "product_url": offer.product_url,
        "image_url": offer.image_url,
    }


def current_offer_row(
    current: CurrentCommercialOffer,
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> dict[str, Any]:
    """Fila única por oferta actual, compartida entre supermercados."""

    if not isinstance(current, CurrentCommercialOffer):
        raise TabularPersistenceError("current debe ser CurrentCommercialOffer")
    validated = current.validated_offer
    offer = validated.offer
    row = _offer_base_row(validated, catalog)
    row.update(
        {
            "observed_at_utc": _utc_text(offer.observed_at_utc),
            "first_observed_at_utc": _utc_text(current.first_observed_at_utc),
            "last_observed_at_utc": _utc_text(current.last_observed_at_utc),
            "last_scrape_run_id": current.last_scrape_run_id,
        }
    )
    return _closed_row(FACT_OFFERS_CURRENT, row)


def history_offer_row(
    period: OfferHistoryPeriod,
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> dict[str, Any]:
    """Fila inmutable de histórico; un cambio real abre un nuevo periodo."""

    if not isinstance(period, OfferHistoryPeriod):
        raise TabularPersistenceError("period debe ser OfferHistoryPeriod")
    row = _offer_base_row(period.validated_offer, catalog)
    row.pop("offer_id")
    row.update(
        {
            "offer_history_id": period.offer_history_id,
            "offer_id": period.offer_id,
            "change_type": period.change_type.value,
            "changed_fields_json": json.dumps(
                list(period.changed_fields),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "valid_from_utc": _utc_text(period.valid_from_utc),
            "valid_to_utc": _utc_text(period.valid_to_utc),
            "opened_by_scrape_run_id": period.opened_by_scrape_run_id,
            "closed_by_scrape_run_id": period.closed_by_scrape_run_id,
            "last_confirmed_by_scrape_run_id": period.last_confirmed_by_scrape_run_id,
            "last_observed_at_utc": _utc_text(period.last_observed_at_utc),
        }
    )
    return _closed_row(FACT_OFFER_HISTORY, row)
