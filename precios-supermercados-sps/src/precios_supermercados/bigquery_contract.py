"""Contrato físico BigQuery para Precios de Supermercados SPS.

El dominio no importa el SDK de Google. Este módulo define solamente el esquema
físico, claves lógicas e índices físicos que el adapter debe materializar.
BigQuery no hace cumplir primary keys, por lo que ``logical_key`` es una
invariante del adapter y de sus pruebas de replay.
"""

from __future__ import annotations

from dataclasses import dataclass


class BigQueryContractError(ValueError):
    """El contrato físico BigQuery es internamente inconsistente."""


@dataclass(frozen=True, slots=True)
class BigQueryField:
    name: str
    field_type: str
    required: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise BigQueryContractError("field_name_invalid")
        if self.field_type not in {
            "STRING",
            "BOOL",
            "INT64",
            "NUMERIC",
            "TIMESTAMP",
            "DATE",
            "JSON",
        }:
            raise BigQueryContractError("field_type_invalid")


@dataclass(frozen=True, slots=True)
class BigQueryTableSpec:
    name: str
    fields: tuple[BigQueryField, ...]
    logical_key: tuple[str, ...]
    partition_field: str | None = None
    clustering_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        field_names = tuple(field.name for field in self.fields)
        if not self.name or not self.name.strip():
            raise BigQueryContractError("table_name_invalid")
        if not field_names or len(set(field_names)) != len(field_names):
            raise BigQueryContractError("table_fields_invalid")
        if not self.logical_key or not set(self.logical_key).issubset(field_names):
            raise BigQueryContractError("logical_key_invalid")
        required = {field.name for field in self.fields if field.required}
        if not set(self.logical_key).issubset(required):
            raise BigQueryContractError("logical_key_must_be_required")
        if self.partition_field is not None:
            if self.partition_field not in field_names:
                raise BigQueryContractError("partition_field_missing")
            partition = next(
                field for field in self.fields if field.name == self.partition_field
            )
            if partition.field_type not in {"TIMESTAMP", "DATE"}:
                raise BigQueryContractError("partition_field_type_invalid")
        if len(self.clustering_fields) > 4:
            raise BigQueryContractError("too_many_clustering_fields")
        if not set(self.clustering_fields).issubset(field_names):
            raise BigQueryContractError("clustering_field_missing")

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)


def F(name: str, field_type: str, required: bool = False) -> BigQueryField:
    return BigQueryField(name=name, field_type=field_type, required=required)


SUPERMARKETS = BigQueryTableSpec(
    name="supermarkets",
    fields=(
        F("supermarket_id", "STRING", True),
        F("supermarket_name", "STRING", True),
        F("country_code", "STRING", True),
        F("location_selection_mode", "STRING", True),
        F("is_active", "BOOL", True),
    ),
    logical_key=("supermarket_id",),
)

LOCATIONS = BigQueryTableSpec(
    name="locations",
    fields=(
        F("location_id", "STRING", True),
        F("supermarket_id", "STRING", True),
        F("city_id", "STRING", True),
        F("city_name", "STRING", True),
        F("granularity", "STRING", True),
        F("source_location_key", "STRING"),
        F("is_available", "BOOL", True),
        F("in_scope", "BOOL", True),
        F("extraction_enabled", "BOOL", True),
        F("technical_binding_confirmed", "BOOL", True),
        F("evidence", "STRING"),
    ),
    logical_key=("location_id",),
    clustering_fields=("supermarket_id",),
)

PRODUCTOS = BigQueryTableSpec(
    name="productos",
    fields=(
        F("supermarket_id", "STRING", True),
        F("source_product_id", "STRING", True),
        F("product_id", "STRING", True),
        F("source_key_type", "STRING", True),
        F("source_key", "STRING", True),
        F("source_sku", "STRING"),
        F("source_name", "STRING", True),
        F("normalized_name", "STRING", True),
        F("source_brand", "STRING"),
        F("normalized_brand", "STRING"),
        F("source_presentation", "STRING"),
        F("source_category", "STRING"),
        F("category", "STRING"),
        F("subcategory", "STRING"),
        F("variant", "STRING"),
        F("unit_count", "INT64"),
        F("content_per_unit", "NUMERIC"),
        F("measurement_unit", "STRING"),
        F("total_content", "NUMERIC"),
        F("barcode", "STRING"),
        F("product_url", "STRING", True),
        F("image_url", "STRING"),
        F("review_status", "STRING", True),
        F("first_seen_at_utc", "TIMESTAMP", True),
        F("last_seen_at_utc", "TIMESTAMP", True),
        F("last_scrape_run_id", "STRING", True),
    ),
    logical_key=("supermarket_id", "source_product_id"),
    clustering_fields=("supermarket_id", "normalized_brand", "category"),
)

PRECIOS_HISTORICOS = BigQueryTableSpec(
    name="precios_historicos",
    fields=(
        F("price_observation_id", "STRING", True),
        F("supermarket_id", "STRING", True),
        F("location_id", "STRING", True),
        F("source_product_id", "STRING", True),
        F("product_id", "STRING", True),
        F("currency", "STRING", True),
        F("current_price", "NUMERIC"),
        F("reported_regular_price", "NUMERIC"),
        F("is_promotion", "BOOL", True),
        F("promotion_evidence", "STRING"),
        F("observed_at_utc", "TIMESTAMP", True),
        F("scrape_run_id", "STRING", True),
        F("extractor_version", "STRING", True),
        F("schema_version", "STRING", True),
    ),
    logical_key=("price_observation_id",),
    partition_field="observed_at_utc",
    clustering_fields=("supermarket_id", "location_id", "source_product_id"),
)

INVENTARIO_HISTORICO = BigQueryTableSpec(
    name="inventario_historico",
    fields=(
        F("inventory_observation_id", "STRING", True),
        F("supermarket_id", "STRING", True),
        F("location_id", "STRING", True),
        F("source_product_id", "STRING", True),
        F("product_id", "STRING", True),
        F("seller_id", "STRING"),
        F("available_quantity_observed", "NUMERIC"),
        F("availability", "STRING", True),
        F("availability_evidence", "STRING"),
        F("quantity_is_exact", "BOOL", True),
        F("observed_at_utc", "TIMESTAMP", True),
        F("scrape_run_id", "STRING", True),
        F("extractor_version", "STRING", True),
        F("schema_version", "STRING", True),
    ),
    logical_key=("inventory_observation_id",),
    partition_field="observed_at_utc",
    clustering_fields=("supermarket_id", "location_id", "source_product_id"),
)

SCRAPE_RUNS = BigQueryTableSpec(
    name="scrape_runs",
    fields=(
        F("scrape_run_id", "STRING", True),
        F("run_fingerprint", "STRING", True),
        F("run_evidence_id", "STRING"),
        F("supermarket_id", "STRING", True),
        F("location_id", "STRING", True),
        F("run_status", "STRING", True),
        F("catalog_accepted", "BOOL", True),
        F("commercial_update_allowed", "BOOL", True),
        F("started_at_utc", "TIMESTAMP", True),
        F("finished_at_utc", "TIMESTAMP", True),
        F("products_observed", "INT64", True),
        F("offers_observed", "INT64", True),
        F("quality_event_count", "INT64", True),
        F("current_created", "INT64", True),
        F("current_changed", "INT64", True),
        F("current_confirmed", "INT64", True),
        F("offers_ignored", "INT64", True),
        F("catalog_products_reported", "INT64"),
        F("unique_products_extracted", "INT64"),
        F("skus_extracted", "INT64"),
        F("skus_with_price", "INT64"),
        F("catalog_product_coverage", "NUMERIC"),
        F("extractor_version", "STRING"),
        F("schema_version", "STRING"),
    ),
    logical_key=("scrape_run_id",),
    partition_field="started_at_utc",
    clustering_fields=("supermarket_id", "location_id", "run_status"),
)

QUALITY_EVENTS = BigQueryTableSpec(
    name="quality_events",
    fields=(
        F("quality_event_id", "STRING", True),
        F("scrape_run_id", "STRING", True),
        F("supermarket_id", "STRING", True),
        F("location_id", "STRING", True),
        F("source_product_id", "STRING"),
        F("offer_id", "STRING"),
        F("category", "STRING", True),
        F("severity", "STRING", True),
        F("event_code", "STRING", True),
        F("observed_at_utc", "TIMESTAMP", True),
    ),
    logical_key=("quality_event_id",),
    partition_field="observed_at_utc",
    clustering_fields=("supermarket_id", "location_id", "event_code"),
)

NORMALIZATION_OVERRIDES = BigQueryTableSpec(
    name="normalization_overrides",
    fields=(
        F("override_id", "STRING", True),
        F("supermarket_id", "STRING", True),
        F("source_product_id", "STRING", True),
        F("source_signature", "STRING", True),
        F("field_name", "STRING", True),
        F("source_value", "STRING"),
        F("override_value", "STRING"),
        F("reason", "STRING", True),
        F("status", "STRING", True),
        F("created_at_utc", "TIMESTAMP", True),
        F("updated_at_utc", "TIMESTAMP", True),
    ),
    logical_key=("override_id",),
    clustering_fields=("supermarket_id", "source_product_id", "status"),
)

PRODUCT_MAPPING = BigQueryTableSpec(
    name="product_mapping",
    fields=(
        F("supermarket_id", "STRING", True),
        F("source_product_id", "STRING", True),
        F("product_id", "STRING", True),
        F("mapping_status", "STRING", True),
        F("mapping_method", "STRING", True),
        F("canonical_gtin", "STRING"),
        F("review_reason", "STRING"),
        F("last_observed_at_utc", "TIMESTAMP", True),
        F("last_scrape_run_id", "STRING", True),
    ),
    logical_key=("supermarket_id", "source_product_id"),
    clustering_fields=("supermarket_id", "mapping_status"),
)

BIGQUERY_TABLE_SPECS = (
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
BIGQUERY_TABLE_BY_NAME = {table.name: table for table in BIGQUERY_TABLE_SPECS}
BIGQUERY_TABLE_NAMES = tuple(table.name for table in BIGQUERY_TABLE_SPECS)

if len(BIGQUERY_TABLE_BY_NAME) != len(BIGQUERY_TABLE_SPECS):
    raise BigQueryContractError("table_names_duplicate")
