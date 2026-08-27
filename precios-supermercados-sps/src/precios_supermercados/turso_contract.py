"""Contrato físico SQLite/Turso para persistencia operativa de precios SPS.

Turso es un backend operacional, no un warehouse analítico. El contrato conserva
``current`` + periodos de cambio y registra cada run terminal. Los valores de
precio se mantienen también en unidades monetarias menores enteras para evitar
aritmética binaria de punto flotante.

No abre conexiones ni ejecuta I/O externo.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .tabular_persistence import FACT_OFFER_HISTORY, FACT_OFFERS_CURRENT


class TursoContractError(ValueError):
    """El contrato físico Turso es internamente inconsistente."""


@dataclass(frozen=True, slots=True)
class TursoTableSpec:
    name: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    immutable: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise TursoContractError("table_name_invalid")
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise TursoContractError(f"table_columns_invalid:{self.name}")
        if not self.primary_key or not set(self.primary_key).issubset(self.columns):
            raise TursoContractError(f"table_primary_key_invalid:{self.name}")


SCHEMA_VERSION_TABLE = "_schema_version"
CURRENT_SCHEMA_VERSION = 1

SUPERMARKETS = TursoTableSpec(
    name="supermarkets",
    columns=(
        "supermarket_id",
        "supermarket_name",
        "country_code",
        "location_selection_mode",
        "is_active",
    ),
    primary_key=("supermarket_id",),
)

LOCATIONS = TursoTableSpec(
    name="locations",
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

PRODUCTS = TursoTableSpec(
    name="products",
    columns=(
        "product_id",
        "canonical_gtin",
        "identity_kind",
    ),
    primary_key=("product_id",),
)

SOURCE_PRODUCTS = TursoTableSpec(
    name="source_products",
    columns=(
        "source_product_id",
        "supermarket_id",
        "source_key_type",
        "source_key",
        "source_sku",
        "source_name",
        "source_brand",
        "source_presentation",
        "barcode",
        "product_url",
        "image_url",
        "product_id",
        "mapping_status",
        "mapping_method",
        "review_reason",
        "normalized_name",
        "normalized_brand",
        "category",
        "subcategory",
        "variant",
        "unit_count",
        "content_per_unit",
        "measurement_unit",
        "total_content",
        "review_status",
        "last_observed_at_utc",
        "last_scrape_run_id",
    ),
    primary_key=("source_product_id",),
)

# Current/history conservan las columnas backend-neutral para permitir rehidratar
# exactamente el motor comercial. Las columnas *_minor son una proyección física
# adicional para consultas monetarias seguras y no reemplazan la representación
# decimal exacta usada por el dominio.
OFFERS_CURRENT = TursoTableSpec(
    name="offers_current",
    columns=FACT_OFFERS_CURRENT.columns
    + (
        "current_price_minor",
        "reported_regular_price_minor",
        "seller_id",
        "available_quantity_observed",
        "availability_evidence",
        "quantity_is_exact",
    ),
    primary_key=("offer_id",),
)

OFFER_HISTORY = TursoTableSpec(
    name="offer_history",
    columns=FACT_OFFER_HISTORY.columns
    + (
        "current_price_minor",
        "reported_regular_price_minor",
        "seller_id",
        "available_quantity_observed",
        "availability_evidence",
        "quantity_is_exact",
    ),
    primary_key=("offer_history_id",),
)

SCRAPE_RUNS = TursoTableSpec(
    name="scrape_runs",
    columns=(
        "scrape_run_id",
        "run_fingerprint",
        "supermarket_id",
        "location_id",
        "run_status",
        "catalog_accepted",
        "commercial_update_allowed",
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
        "catalog_products_reported",
        "unique_products_extracted",
        "skus_extracted",
        "skus_with_price",
        "catalog_product_coverage",
    ),
    primary_key=("scrape_run_id",),
    immutable=True,
)

QUALITY_EVENTS = TursoTableSpec(
    name="quality_events",
    columns=(
        "quality_event_id",
        "scrape_run_id",
        "supermarket_id",
        "location_id",
        "offer_id",
        "source_product_id",
        "category",
        "severity",
        "event_code",
        "observed_at_utc",
    ),
    primary_key=("quality_event_id",),
    immutable=True,
)

NORMALIZATION_OVERRIDES = TursoTableSpec(
    name="normalization_overrides",
    columns=(
        "override_id",
        "supermarket_id",
        "source_product_id",
        "source_signature",
        "field_name",
        "source_value",
        "override_value",
        "reason",
        "active",
        "created_at_utc",
        "updated_at_utc",
    ),
    primary_key=("override_id",),
)

TURSO_TABLE_SPECS = (
    SUPERMARKETS,
    LOCATIONS,
    PRODUCTS,
    SOURCE_PRODUCTS,
    OFFERS_CURRENT,
    OFFER_HISTORY,
    SCRAPE_RUNS,
    QUALITY_EVENTS,
    NORMALIZATION_OVERRIDES,
)
TURSO_TABLE_NAMES = tuple(spec.name for spec in TURSO_TABLE_SPECS)
TURSO_TABLE_BY_NAME: Mapping[str, TursoTableSpec] = MappingProxyType(
    {spec.name: spec for spec in TURSO_TABLE_SPECS}
)

_BOOL_COLUMNS = frozenset(
    {
        "is_active",
        "is_available",
        "in_scope",
        "extraction_enabled",
        "technical_binding_confirmed",
        "is_promotion",
        "quantity_is_exact",
        "catalog_accepted",
        "commercial_update_allowed",
        "active",
    }
)
_INT_COLUMNS = frozenset(
    {
        "unit_count",
        "current_price_minor",
        "reported_regular_price_minor",
        "products_observed",
        "offers_observed",
        "current_created",
        "current_changed",
        "current_confirmed",
        "offers_ignored",
        "quality_event_count",
        "catalog_products_reported",
        "unique_products_extracted",
        "skus_extracted",
        "skus_with_price",
    }
)

_REQUIRED_BY_TABLE: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        SUPERMARKETS.name: frozenset(
            {"supermarket_id", "supermarket_name", "country_code", "location_selection_mode", "is_active"}
        ),
        LOCATIONS.name: frozenset(
            {
                "location_id",
                "supermarket_id",
                "city_id",
                "city_name",
                "granularity",
                "is_available",
                "in_scope",
                "extraction_enabled",
                "technical_binding_confirmed",
            }
        ),
        PRODUCTS.name: frozenset({"product_id", "identity_kind"}),
        SOURCE_PRODUCTS.name: frozenset(
            {
                "source_product_id",
                "supermarket_id",
                "source_key_type",
                "source_key",
                "source_name",
                "product_id",
                "mapping_status",
                "mapping_method",
                "normalized_name",
                "review_status",
                "last_observed_at_utc",
                "last_scrape_run_id",
            }
        ),
        OFFERS_CURRENT.name: frozenset(
            {
                "offer_id",
                "supermarket_id",
                "supermarket_name",
                "location_id",
                "city_id",
                "city_name",
                "location_granularity",
                "location_status",
                "source_product_id",
                "product_id",
                "source_key_type",
                "source_key",
                "source_name",
                "normalized_name",
                "currency",
                "is_promotion",
                "availability",
                "state_hash",
                "review_status",
                "quality_events_json",
                "offer_scrape_run_id",
                "extractor_version",
                "schema_version",
                "source_url",
                "observed_at_utc",
                "validated_at_utc",
                "first_observed_at_utc",
                "last_observed_at_utc",
                "last_scrape_run_id",
                "product_url",
                "quantity_is_exact",
            }
        ),
        OFFER_HISTORY.name: frozenset(
            {
                "offer_history_id",
                "offer_id",
                "supermarket_id",
                "supermarket_name",
                "location_id",
                "city_id",
                "city_name",
                "location_granularity",
                "location_status",
                "source_product_id",
                "product_id",
                "source_key_type",
                "source_key",
                "source_name",
                "normalized_name",
                "currency",
                "is_promotion",
                "availability",
                "state_hash",
                "change_type",
                "changed_fields_json",
                "review_status",
                "quality_events_json",
                "offer_scrape_run_id",
                "extractor_version",
                "schema_version",
                "source_url",
                "validated_at_utc",
                "valid_from_utc",
                "opened_by_scrape_run_id",
                "last_confirmed_by_scrape_run_id",
                "last_observed_at_utc",
                "product_url",
                "quantity_is_exact",
            }
        ),
        SCRAPE_RUNS.name: frozenset(
            {
                "scrape_run_id",
                "run_fingerprint",
                "supermarket_id",
                "location_id",
                "run_status",
                "catalog_accepted",
                "commercial_update_allowed",
                "started_at_utc",
                "finished_at_utc",
                "products_observed",
                "offers_observed",
                "current_created",
                "current_changed",
                "current_confirmed",
                "offers_ignored",
                "quality_event_count",
            }
        ),
        QUALITY_EVENTS.name: frozenset(
            {
                "quality_event_id",
                "scrape_run_id",
                "supermarket_id",
                "location_id",
                "category",
                "severity",
                "event_code",
                "observed_at_utc",
            }
        ),
        NORMALIZATION_OVERRIDES.name: frozenset(
            {
                "override_id",
                "supermarket_id",
                "source_product_id",
                "source_signature",
                "field_name",
                "override_value",
                "active",
            }
        ),
    }
)


def _column_sql(name: str, *, required: bool) -> str:
    column_type = "INTEGER" if name in _BOOL_COLUMNS or name in _INT_COLUMNS else "TEXT"
    suffix = " NOT NULL" if required else ""
    if name in _BOOL_COLUMNS:
        suffix += f" CHECK ({name} IN (0, 1))"
    if name in {
        "current_price_minor",
        "reported_regular_price_minor",
        "products_observed",
        "offers_observed",
        "current_created",
        "current_changed",
        "current_confirmed",
        "offers_ignored",
        "quality_event_count",
        "catalog_products_reported",
        "unique_products_extracted",
        "skus_extracted",
        "skus_with_price",
    }:
        suffix += f" CHECK ({name} IS NULL OR {name} >= 0)"
    if name == "unit_count":
        suffix += " CHECK (unit_count IS NULL OR unit_count > 0)"
    return f'"{name}" {column_type}{suffix}'


def _create_table_sql(spec: TursoTableSpec) -> str:
    required = _REQUIRED_BY_TABLE[spec.name]
    columns = [_column_sql(name, required=name in required) for name in spec.columns]
    if len(spec.primary_key) == 1:
        key = spec.primary_key[0]
        columns[spec.columns.index(key)] += " PRIMARY KEY"
    else:
        columns.append(
            "PRIMARY KEY (" + ", ".join(f'\"{name}\"' for name in spec.primary_key) + ")"
        )

    constraints: list[str] = []
    if spec is LOCATIONS:
        constraints.append("FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id)")
    elif spec is SOURCE_PRODUCTS:
        constraints.extend(
            (
                "FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id)",
                "UNIQUE (supermarket_id, source_key_type, source_key)",
            )
        )
    elif spec is OFFERS_CURRENT:
        constraints.extend(
            (
                "FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id)",
                "FOREIGN KEY (location_id) REFERENCES locations(location_id)",
                "FOREIGN KEY (source_product_id) REFERENCES source_products(source_product_id)",
                "FOREIGN KEY (last_scrape_run_id) REFERENCES scrape_runs(scrape_run_id)",
                "UNIQUE (supermarket_id, location_id, source_product_id)",
            )
        )
    elif spec is OFFER_HISTORY:
        constraints.extend(
            (
                "FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id)",
                "FOREIGN KEY (location_id) REFERENCES locations(location_id)",
                "FOREIGN KEY (source_product_id) REFERENCES source_products(source_product_id)",
                "FOREIGN KEY (opened_by_scrape_run_id) REFERENCES scrape_runs(scrape_run_id)",
            )
        )
    elif spec is SCRAPE_RUNS:
        constraints.extend(
            (
                "FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id)",
                "FOREIGN KEY (location_id) REFERENCES locations(location_id)",
            )
        )
    elif spec is QUALITY_EVENTS:
        constraints.append("FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(scrape_run_id)")
    elif spec is NORMALIZATION_OVERRIDES:
        constraints.append(
            "FOREIGN KEY (source_product_id) REFERENCES source_products(source_product_id)"
        )
    columns.extend(constraints)
    return f'CREATE TABLE IF NOT EXISTS "{spec.name}" (\n  ' + ",\n  ".join(columns) + "\n) STRICT"


TURSO_SCHEMA_META_SQL = (
    'CREATE TABLE IF NOT EXISTS "_schema_version" ('
    'singleton INTEGER PRIMARY KEY CHECK (singleton = 1), '
    'version INTEGER NOT NULL CHECK (version >= 0), '
    'applied_at_utc TEXT NOT NULL) STRICT'
)

_MIGRATION_1_TABLES = tuple(_create_table_sql(spec) for spec in TURSO_TABLE_SPECS)
_MIGRATION_1_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_locations_supermarket ON locations(supermarket_id)",
    "CREATE INDEX IF NOT EXISTS idx_source_products_supermarket_mapping ON source_products(supermarket_id, mapping_status)",
    "CREATE INDEX IF NOT EXISTS idx_source_products_product ON source_products(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_offers_current_scope ON offers_current(supermarket_id, location_id, source_product_id)",
    "CREATE INDEX IF NOT EXISTS idx_offers_current_product ON offers_current(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_offer_history_offer_time ON offer_history(offer_id, valid_from_utc DESC)",
    "CREATE INDEX IF NOT EXISTS idx_offer_history_scope_time ON offer_history(supermarket_id, location_id, valid_from_utc DESC)",
    "CREATE INDEX IF NOT EXISTS idx_scrape_runs_scope_time ON scrape_runs(supermarket_id, location_id, started_at_utc DESC)",
    "CREATE INDEX IF NOT EXISTS idx_quality_events_run ON quality_events(scrape_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_overrides_source ON normalization_overrides(supermarket_id, source_product_id, active)",
)

TURSO_MIGRATIONS: Mapping[int, tuple[str, ...]] = MappingProxyType(
    {1: _MIGRATION_1_TABLES + _MIGRATION_1_INDEXES}
)
