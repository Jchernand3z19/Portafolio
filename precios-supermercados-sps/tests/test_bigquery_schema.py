from __future__ import annotations

import pytest

from precios_supermercados.bigquery_schema import (
    BIGQUERY_TABLE_NAMES,
    BIGQUERY_TABLE_SPECS,
    DEFERRED_BIGQUERY_TABLE_SPECS,
    INITIAL_BIGQUERY_TABLE_SPECS,
    INVENTARIO_HISTORICO,
    LOCATIONS,
    NORMALIZATION_OVERRIDES,
    PERSISTENT_STORAGE_BACKEND,
    PRECIOS_HISTORICOS,
    PRODUCTOS,
    PRODUCT_MAPPING,
    QUALITY_EVENTS,
    SCRAPE_RUNS,
    BigQueryColumn,
    BigQuerySchemaError,
    BigQueryTableSpec,
    bigquery_table_spec,
)


EXPECTED_TABLES = (
    "supermarkets",
    "locations",
    "productos",
    "precios_historicos",
    "inventario_historico",
    "scrape_runs",
    "quality_events",
    "normalization_overrides",
    "product_mapping",
)


def test_bigquery_is_selected_persistent_backend_and_table_set_is_closed() -> None:
    assert PERSISTENT_STORAGE_BACKEND == "bigquery"
    assert BIGQUERY_TABLE_NAMES == EXPECTED_TABLES
    assert tuple(BIGQUERY_TABLE_SPECS) == EXPECTED_TABLES
    assert set(INITIAL_BIGQUERY_TABLE_SPECS) == set(EXPECTED_TABLES) - {"product_mapping"}
    assert tuple(DEFERRED_BIGQUERY_TABLE_SPECS) == ("product_mapping",)


def test_product_table_identifies_supermarket_and_product_but_not_city() -> None:
    columns = set(PRODUCTOS.column_names)
    assert {
        "source_product_id",
        "supermarket_id",
        "product_id",
        "source_key_type",
        "source_key",
        "source_name",
        "normalized_name",
        "source_presentation",
        "presentation_normalized",
    }.issubset(columns)
    assert "location_id" not in columns
    assert "city_id" not in columns
    assert "city_name" not in columns
    assert PRODUCTOS.logical_key == ("source_product_id",)


def test_locations_resolve_supermarket_and_city_from_location_id() -> None:
    columns = set(LOCATIONS.column_names)
    assert {"location_id", "supermarket_id", "city_id", "city_name"}.issubset(columns)
    assert LOCATIONS.logical_key == ("location_id",)
    assert LOCATIONS.cluster_fields == ("supermarket_id", "city_id")


@pytest.mark.parametrize("spec", [PRECIOS_HISTORICOS, INVENTARIO_HISTORICO])
def test_observation_facts_link_supermarket_location_product_run_and_time(spec) -> None:
    columns = set(spec.column_names)
    assert {
        "supermarket_id",
        "location_id",
        "source_product_id",
        "product_id",
        "scrape_run_id",
        "observed_at_utc",
    }.issubset(columns)
    assert spec.partition_field == "observed_at_utc"
    assert spec.cluster_fields == (
        "supermarket_id",
        "location_id",
        "source_product_id",
    )


def test_price_history_uses_explicit_price_semantics() -> None:
    columns = set(PRECIOS_HISTORICOS.column_names)
    assert "current_price" in columns
    assert "reported_regular_price" in columns
    assert "is_promotion" in columns
    assert "promotion_evidence" in columns
    assert "previous_price" not in columns
    assert "price" not in columns
    assert "precio" not in columns
    assert PRECIOS_HISTORICOS.column("current_price").mode == "REQUIRED"
    assert PRECIOS_HISTORICOS.column("reported_regular_price").mode == "NULLABLE"


def test_inventory_history_preserves_quantity_and_availability_evidence() -> None:
    columns = set(INVENTARIO_HISTORICO.column_names)
    assert {
        "seller_id",
        "available_quantity_observed",
        "availability",
        "availability_evidence",
        "quantity_is_exact",
    }.issubset(columns)
    assert INVENTARIO_HISTORICO.column("available_quantity_observed").field_type == "NUMERIC"
    assert INVENTARIO_HISTORICO.column("availability").mode == "REQUIRED"


def test_runs_and_quality_events_are_scoped_to_supermarket_and_location() -> None:
    for spec in (SCRAPE_RUNS, QUALITY_EVENTS):
        columns = set(spec.column_names)
        assert {"supermarket_id", "location_id"}.issubset(columns)
    assert SCRAPE_RUNS.partition_field == "started_at_utc"
    assert QUALITY_EVENTS.partition_field == "observed_at_utc"


def test_normalization_overrides_are_bound_to_source_product_signature() -> None:
    columns = set(NORMALIZATION_OVERRIDES.column_names)
    assert {
        "supermarket_id",
        "source_product_id",
        "source_signature",
        "field_name",
        "source_value",
        "override_value",
        "active",
    }.issubset(columns)


def test_product_mapping_is_defined_but_deferred_until_cross_source_need() -> None:
    assert PRODUCT_MAPPING.materialize_initially is False
    assert PRODUCT_MAPPING.logical_key == ("source_product_id",)
    assert {"supermarket_id", "source_product_id", "product_id"}.issubset(
        PRODUCT_MAPPING.column_names
    )


def test_table_lookup_is_closed() -> None:
    assert bigquery_table_spec("productos") is PRODUCTOS
    with pytest.raises(BigQuerySchemaError, match="table_unknown"):
        bigquery_table_spec("otra_tabla")


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"name": "bad-name", "field_type": "STRING"}, "column_name_invalid"),
        ({"name": "ok", "field_type": "FLOAT64"}, "column_type_invalid"),
        ({"name": "ok", "field_type": "STRING", "mode": "REPEATED"}, "column_mode_invalid"),
    ],
)
def test_column_contract_rejects_unsupported_shapes(kwargs, code: str) -> None:
    with pytest.raises(BigQuerySchemaError, match=code):
        BigQueryColumn(**kwargs)


def test_table_contract_rejects_duplicate_columns() -> None:
    with pytest.raises(BigQuerySchemaError, match="table_column_duplicate"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=(
                BigQueryColumn("id", "STRING", "REQUIRED"),
                BigQueryColumn("id", "STRING", "REQUIRED"),
            ),
            logical_key=("id",),
        )


def test_table_contract_requires_logical_key_columns_to_exist_and_be_required() -> None:
    with pytest.raises(BigQuerySchemaError, match="logical_key_field_missing"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=(BigQueryColumn("id", "STRING", "REQUIRED"),),
            logical_key=("missing",),
        )

    with pytest.raises(BigQuerySchemaError, match="logical_key_must_be_required"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=(BigQueryColumn("id", "STRING"),),
            logical_key=("id",),
        )


def test_table_contract_rejects_invalid_partitioning() -> None:
    with pytest.raises(BigQuerySchemaError, match="partition_field_missing"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=(BigQueryColumn("id", "STRING", "REQUIRED"),),
            logical_key=("id",),
            partition_field="observed_at",
        )

    with pytest.raises(BigQuerySchemaError, match="partition_field_must_be_timestamp"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=(
                BigQueryColumn("id", "STRING", "REQUIRED"),
                BigQueryColumn("observed_at", "STRING"),
            ),
            logical_key=("id",),
            partition_field="observed_at",
        )


def test_table_contract_rejects_invalid_clustering() -> None:
    columns = (BigQueryColumn("id", "STRING", "REQUIRED"),)
    with pytest.raises(BigQuerySchemaError, match="cluster_field_missing"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=columns,
            logical_key=("id",),
            cluster_fields=("missing",),
        )

    many_columns = tuple(
        [BigQueryColumn("id", "STRING", "REQUIRED")]
        + [BigQueryColumn(f"c{index}", "STRING") for index in range(5)]
    )
    with pytest.raises(BigQuerySchemaError, match="cluster_field_limit_exceeded"):
        BigQueryTableSpec(
            name="demo",
            grain="una fila",
            columns=many_columns,
            logical_key=("id",),
            cluster_fields=("c0", "c1", "c2", "c3", "c4"),
        )
