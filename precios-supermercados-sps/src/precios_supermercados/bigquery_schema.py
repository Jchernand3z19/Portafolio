"""Contrato físico BigQuery del proyecto Precios Supermercados SPS.

El módulo es deliberadamente libre de dependencias de Google Cloud. Define grain,
columnas, claves lógicas, particionamiento y clustering antes de introducir un
cliente externo o realizar escrituras cloud.

BigQuery no sustituye las invariantes del motor comercial. Esta capa describe la
materialización analítica durable que consumirá Dash/Plotly y que debe preservar
supermercado, producto, ubicación, run y tiempo de cada observación.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


PERSISTENT_STORAGE_BACKEND = "bigquery"

_ALLOWED_FIELD_TYPES = frozenset({"STRING", "BOOL", "INT64", "NUMERIC", "TIMESTAMP"})
_ALLOWED_MODES = frozenset({"NULLABLE", "REQUIRED"})
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_CLUSTER_FIELDS = 4


class BigQuerySchemaError(ValueError):
    """El contrato físico BigQuery viola una invariante local."""


@dataclass(frozen=True, slots=True)
class BigQueryColumn:
    """Columna BigQuery independiente del SDK de Google."""

    name: str
    field_type: str
    mode: str = "NULLABLE"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _IDENTIFIER_RE.fullmatch(self.name) is None:
            raise BigQuerySchemaError("column_name_invalid")
        field_type = self.field_type.upper() if isinstance(self.field_type, str) else ""
        if field_type not in _ALLOWED_FIELD_TYPES:
            raise BigQuerySchemaError("column_type_invalid")
        mode = self.mode.upper() if isinstance(self.mode, str) else ""
        if mode not in _ALLOWED_MODES:
            raise BigQuerySchemaError("column_mode_invalid")
        object.__setattr__(self, "field_type", field_type)
        object.__setattr__(self, "mode", mode)


@dataclass(frozen=True, slots=True)
class BigQueryTableSpec:
    """Esquema cerrado y decisiones físicas mínimas de una tabla BigQuery."""

    name: str
    grain: str
    columns: tuple[BigQueryColumn, ...]
    logical_key: tuple[str, ...]
    partition_field: str | None = None
    cluster_fields: tuple[str, ...] = ()
    materialize_initially: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _IDENTIFIER_RE.fullmatch(self.name) is None:
            raise BigQuerySchemaError("table_name_invalid")
        if not isinstance(self.grain, str) or not self.grain.strip():
            raise BigQuerySchemaError("table_grain_invalid")
        if not self.columns:
            raise BigQuerySchemaError("table_columns_empty")
        if any(not isinstance(column, BigQueryColumn) for column in self.columns):
            raise BigQuerySchemaError("table_column_type_invalid")

        names = tuple(column.name for column in self.columns)
        if len(names) != len(set(names)):
            raise BigQuerySchemaError("table_column_duplicate")
        by_name = {column.name: column for column in self.columns}

        if not self.logical_key or len(self.logical_key) != len(set(self.logical_key)):
            raise BigQuerySchemaError("logical_key_invalid")
        if any(field not in by_name for field in self.logical_key):
            raise BigQuerySchemaError("logical_key_field_missing")
        if any(by_name[field].mode != "REQUIRED" for field in self.logical_key):
            raise BigQuerySchemaError("logical_key_must_be_required")

        if self.partition_field is not None:
            partition = by_name.get(self.partition_field)
            if partition is None:
                raise BigQuerySchemaError("partition_field_missing")
            if partition.field_type != "TIMESTAMP":
                raise BigQuerySchemaError("partition_field_must_be_timestamp")

        if len(self.cluster_fields) > _MAX_CLUSTER_FIELDS:
            raise BigQuerySchemaError("cluster_field_limit_exceeded")
        if len(self.cluster_fields) != len(set(self.cluster_fields)):
            raise BigQuerySchemaError("cluster_field_duplicate")
        if any(field not in by_name for field in self.cluster_fields):
            raise BigQuerySchemaError("cluster_field_missing")
        if type(self.materialize_initially) is not bool:
            raise BigQuerySchemaError("materialize_initially_invalid")

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def column(self, name: str) -> BigQueryColumn:
        for column in self.columns:
            if column.name == name:
                return column
        raise BigQuerySchemaError("column_unknown")


def _c(name: str, field_type: str, *, required: bool = False) -> BigQueryColumn:
    return BigQueryColumn(
        name=name,
        field_type=field_type,
        mode="REQUIRED" if required else "NULLABLE",
    )


SUPERMARKETS = BigQueryTableSpec(
    name="supermarkets",
    grain="una fila por supermercado",
    columns=(
        _c("supermarket_id", "STRING", required=True),
        _c("supermarket_name", "STRING", required=True),
        _c("country_code", "STRING", required=True),
        _c("location_selection_mode", "STRING", required=True),
        _c("is_active", "BOOL", required=True),
    ),
    logical_key=("supermarket_id",),
)

LOCATIONS = BigQueryTableSpec(
    name="locations",
    grain="una fila por ubicación comercial",
    columns=(
        _c("location_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("city_id", "STRING", required=True),
        _c("city_name", "STRING", required=True),
        _c("granularity", "STRING", required=True),
        _c("source_location_key", "STRING"),
        _c("is_available", "BOOL", required=True),
        _c("in_scope", "BOOL", required=True),
        _c("technical_binding_confirmed", "BOOL", required=True),
        _c("evidence", "STRING"),
    ),
    logical_key=("location_id",),
    cluster_fields=("supermarket_id", "city_id"),
)

PRODUCTOS = BigQueryTableSpec(
    name="productos",
    grain="una fila por producto/SKU fuente estable dentro de un supermercado",
    columns=(
        _c("source_product_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("product_id", "STRING", required=True),
        _c("source_key_type", "STRING", required=True),
        _c("source_key", "STRING", required=True),
        _c("source_catalog_product_id", "STRING"),
        _c("source_item_id", "STRING"),
        _c("source_sku", "STRING"),
        _c("ean", "STRING"),
        _c("canonical_gtin", "STRING"),
        _c("source_name", "STRING", required=True),
        _c("normalized_name", "STRING", required=True),
        _c("source_brand", "STRING"),
        _c("normalized_brand", "STRING"),
        _c("source_category", "STRING"),
        _c("category", "STRING"),
        _c("subcategory", "STRING"),
        _c("source_presentation", "STRING"),
        _c("presentation_normalized", "STRING", required=True),
        _c("presentation_kind", "STRING"),
        _c("unit_count", "INT64"),
        _c("content_per_unit", "NUMERIC"),
        _c("measurement_unit", "STRING"),
        _c("declared_content", "NUMERIC"),
        _c("content_scope", "STRING"),
        _c("total_content", "NUMERIC"),
        _c("normalization_status", "STRING", required=True),
        _c("normalization_method", "STRING", required=True),
        _c("product_url", "STRING"),
        _c("image_url", "STRING"),
        _c("first_seen_at_utc", "TIMESTAMP"),
        _c("last_seen_at_utc", "TIMESTAMP"),
        _c("last_scrape_run_id", "STRING"),
    ),
    logical_key=("source_product_id",),
    cluster_fields=("supermarket_id", "product_id"),
)

PRECIOS_HISTORICOS = BigQueryTableSpec(
    name="precios_historicos",
    grain="una observación de precio por producto, ubicación y run/instante",
    columns=(
        _c("price_observation_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("location_id", "STRING", required=True),
        _c("source_product_id", "STRING", required=True),
        _c("product_id", "STRING", required=True),
        _c("currency", "STRING", required=True),
        _c("current_price", "NUMERIC", required=True),
        _c("reported_regular_price", "NUMERIC"),
        _c("is_promotion", "BOOL", required=True),
        _c("promotion_evidence", "STRING"),
        _c("observed_at_utc", "TIMESTAMP", required=True),
        _c("scrape_run_id", "STRING", required=True),
        _c("extractor_version", "STRING"),
        _c("schema_version", "STRING"),
    ),
    logical_key=("price_observation_id",),
    partition_field="observed_at_utc",
    cluster_fields=("supermarket_id", "location_id", "source_product_id"),
)

INVENTARIO_HISTORICO = BigQueryTableSpec(
    name="inventario_historico",
    grain="una observación de cantidad/disponibilidad por producto, ubicación, seller y run/instante",
    columns=(
        _c("inventory_observation_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("location_id", "STRING", required=True),
        _c("source_product_id", "STRING", required=True),
        _c("product_id", "STRING", required=True),
        _c("seller_id", "STRING"),
        _c("available_quantity_observed", "NUMERIC"),
        _c("availability", "STRING", required=True),
        _c("availability_evidence", "STRING"),
        _c("quantity_is_exact", "BOOL"),
        _c("observed_at_utc", "TIMESTAMP", required=True),
        _c("scrape_run_id", "STRING", required=True),
        _c("extractor_version", "STRING"),
        _c("schema_version", "STRING"),
    ),
    logical_key=("inventory_observation_id",),
    partition_field="observed_at_utc",
    cluster_fields=("supermarket_id", "location_id", "source_product_id"),
)

SCRAPE_RUNS = BigQueryTableSpec(
    name="scrape_runs",
    grain="una fila por ejecución terminal",
    columns=(
        _c("scrape_run_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("location_id", "STRING", required=True),
        _c("run_status", "STRING", required=True),
        _c("catalog_accepted", "BOOL", required=True),
        _c("started_at_utc", "TIMESTAMP", required=True),
        _c("finished_at_utc", "TIMESTAMP", required=True),
        _c("catalog_products_reported", "INT64"),
        _c("unique_products_observed", "INT64"),
        _c("skus_observed", "INT64"),
        _c("skus_with_price", "INT64"),
        _c("requests_completed", "INT64"),
        _c("catalog_coverage", "NUMERIC"),
        _c("warnings_count", "INT64"),
        _c("errors_count", "INT64"),
        _c("extractor_version", "STRING"),
        _c("schema_version", "STRING"),
        _c("run_evidence_id", "STRING"),
    ),
    logical_key=("scrape_run_id",),
    partition_field="started_at_utc",
    cluster_fields=("supermarket_id", "location_id"),
)

QUALITY_EVENTS = BigQueryTableSpec(
    name="quality_events",
    grain="una fila por evento de calidad auditable",
    columns=(
        _c("quality_event_id", "STRING", required=True),
        _c("scrape_run_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("location_id", "STRING", required=True),
        _c("source_product_id", "STRING"),
        _c("category", "STRING", required=True),
        _c("severity", "STRING", required=True),
        _c("event_code", "STRING", required=True),
        _c("observed_at_utc", "TIMESTAMP", required=True),
    ),
    logical_key=("quality_event_id",),
    partition_field="observed_at_utc",
    cluster_fields=("supermarket_id", "location_id"),
)

NORMALIZATION_OVERRIDES = BigQueryTableSpec(
    name="normalization_overrides",
    grain="una corrección versionada para una identidad/campo fuente",
    columns=(
        _c("override_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("source_product_id", "STRING", required=True),
        _c("source_signature", "STRING", required=True),
        _c("field_name", "STRING", required=True),
        _c("source_value", "STRING"),
        _c("override_value", "STRING", required=True),
        _c("reason", "STRING"),
        _c("active", "BOOL", required=True),
        _c("created_at_utc", "TIMESTAMP"),
        _c("updated_at_utc", "TIMESTAMP"),
    ),
    logical_key=("override_id",),
    cluster_fields=("supermarket_id", "source_product_id"),
)

PRODUCT_MAPPING = BigQueryTableSpec(
    name="product_mapping",
    grain="una relación auditable entre producto fuente y producto canónico",
    columns=(
        _c("source_product_id", "STRING", required=True),
        _c("supermarket_id", "STRING", required=True),
        _c("product_id", "STRING", required=True),
        _c("mapping_status", "STRING", required=True),
        _c("mapping_method", "STRING", required=True),
        _c("canonical_gtin", "STRING"),
        _c("review_reason", "STRING"),
        _c("last_observed_at_utc", "TIMESTAMP"),
        _c("last_scrape_run_id", "STRING"),
    ),
    logical_key=("source_product_id",),
    cluster_fields=("supermarket_id", "product_id"),
    # El contrato existe desde ahora, pero la materialización se difiere hasta que
    # una segunda fuente o un consumidor cross-supermercado la necesite realmente.
    materialize_initially=False,
)


BIGQUERY_TABLE_SPECS: Mapping[str, BigQueryTableSpec] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            SUPERMARKETS,
            LOCATIONS,
            PRODUCTOS,
            PRECIOS_HISTORICOS,
            INVENTARIO_HISTORICO,
            SCRAPE_RUNS,
            QUALITY_EVENTS,
            NORMALIZATION_OVERRIDES,
            PRODUCT_MAPPING,
        )
    }
)

BIGQUERY_TABLE_NAMES = tuple(BIGQUERY_TABLE_SPECS)
INITIAL_BIGQUERY_TABLE_SPECS: Mapping[str, BigQueryTableSpec] = MappingProxyType(
    {
        name: spec
        for name, spec in BIGQUERY_TABLE_SPECS.items()
        if spec.materialize_initially
    }
)
DEFERRED_BIGQUERY_TABLE_SPECS: Mapping[str, BigQueryTableSpec] = MappingProxyType(
    {
        name: spec
        for name, spec in BIGQUERY_TABLE_SPECS.items()
        if not spec.materialize_initially
    }
)


def bigquery_table_spec(name: str) -> BigQueryTableSpec:
    try:
        return BIGQUERY_TABLE_SPECS[name]
    except KeyError as exc:
        raise BigQuerySchemaError("table_unknown") from exc
