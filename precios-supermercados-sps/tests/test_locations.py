from __future__ import annotations

import pytest

from precios_supermercados.locations import (
    DEFAULT_LOCATION_CATALOG,
    LA_COLONIA_SPS,
    LA_COLONIA_TGU,
    LocationCatalog,
    LocationConfig,
    LocationConfigError,
    LocationGranularity,
    LocationSelectionMode,
    SupermarketConfig,
    build_location_catalog,
)


def test_la_colonia_registers_all_currently_known_cities_without_assuming_granularity() -> None:
    locations = DEFAULT_LOCATION_CATALOG.locations_for_supermarket("la_colonia")
    assert {location.location_id for location in locations} == {
        "la_colonia_sps",
        "la_colonia_tgu",
    }
    assert {location.city_name for location in locations} == {
        "San Pedro Sula",
        "Tegucigalpa",
    }
    assert all(location.is_available for location in locations)
    assert all(location.granularity is LocationGranularity.UNKNOWN for location in locations)


def test_initial_scope_contains_only_san_pedro_sula() -> None:
    scoped = DEFAULT_LOCATION_CATALOG.in_scope_locations("la_colonia")
    assert scoped == (LA_COLONIA_SPS,)
    assert LA_COLONIA_TGU.in_scope is False


def test_la_colonia_sps_is_not_enabled_before_granularity_and_binding_are_confirmed() -> None:
    assert DEFAULT_LOCATION_CATALOG.enabled_locations("la_colonia") == ()
    assert (
        DEFAULT_LOCATION_CATALOG.extraction_block_reason("la_colonia_sps")
        == "location_granularity_unconfirmed"
    )
    with pytest.raises(
        LocationConfigError,
        match="location_granularity_unconfirmed",
    ):
        DEFAULT_LOCATION_CATALOG.require_extraction_ready("la_colonia_sps")


def test_out_of_scope_city_stays_blocked_even_if_source_lists_it() -> None:
    assert (
        DEFAULT_LOCATION_CATALOG.extraction_block_reason("la_colonia_tgu")
        == "location_out_of_scope"
    )


def test_la_colonia_location_ids_are_stable_and_city_specific() -> None:
    assert LA_COLONIA_SPS.location_id == "la_colonia_sps"
    assert LA_COLONIA_SPS.city_id == "sps"
    assert LA_COLONIA_TGU.location_id == "la_colonia_tgu"
    assert LA_COLONIA_TGU.city_id == "tgu"


def test_single_city_supermarket_can_be_enabled_without_source_selector_key() -> None:
    supermarket = SupermarketConfig(
        supermarket_id="solo_sps",
        supermarket_name="Solo SPS",
        location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
    )
    location = LocationConfig(
        location_id="solo_sps_sps",
        supermarket_id="solo_sps",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=True,
    )
    catalog = build_location_catalog((supermarket,), (location,))
    assert catalog.require_extraction_ready("solo_sps_sps") == location


def test_any_enabled_location_requires_confirmed_granularity() -> None:
    with pytest.raises(LocationConfigError, match="granularidad desconocida"):
        LocationConfig(
            location_id="x_sps",
            supermarket_id="x",
            city_id="sps",
            city_name="San Pedro Sula",
            granularity=LocationGranularity.UNKNOWN,
            is_available=True,
            in_scope=True,
            extraction_enabled=True,
        )


def test_multi_city_supermarket_cannot_be_enabled_without_confirmed_binding() -> None:
    supermarket = SupermarketConfig(
        supermarket_id="multi",
        supermarket_name="Multi",
        location_selection_mode=LocationSelectionMode.SOURCE_SELECTION_REQUIRED,
    )
    location = LocationConfig(
        location_id="multi_sps",
        supermarket_id="multi",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=True,
    )
    with pytest.raises(LocationConfigError, match="binding técnico confirmado"):
        build_location_catalog((supermarket,), (location,))


def test_known_granularity_but_unconfirmed_binding_has_specific_block_reason() -> None:
    supermarket = SupermarketConfig(
        supermarket_id="multi",
        supermarket_name="Multi",
        location_selection_mode=LocationSelectionMode.SOURCE_SELECTION_REQUIRED,
    )
    location = LocationConfig(
        location_id="multi_sps",
        supermarket_id="multi",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=False,
        technical_binding_confirmed=False,
    )
    catalog = build_location_catalog((supermarket,), (location,))
    assert (
        catalog.extraction_block_reason("multi_sps")
        == "technical_location_binding_unconfirmed"
    )


def test_multi_city_supermarket_can_enable_exact_confirmed_source_key() -> None:
    supermarket = SupermarketConfig(
        supermarket_id="multi",
        supermarket_name="Multi",
        location_selection_mode=LocationSelectionMode.SOURCE_SELECTION_REQUIRED,
    )
    location = LocationConfig(
        location_id="multi_sps",
        supermarket_id="multi",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=True,
        technical_binding_confirmed=True,
        source_location_key="source-city-001",
    )
    catalog = build_location_catalog((supermarket,), (location,))
    assert catalog.require_extraction_ready("multi_sps") == location


def test_confirmed_binding_requires_a_source_location_key() -> None:
    with pytest.raises(LocationConfigError, match="source_location_key"):
        LocationConfig(
            location_id="multi_sps",
            supermarket_id="multi",
            city_id="sps",
            city_name="San Pedro Sula",
            granularity=LocationGranularity.CITY,
            is_available=True,
            in_scope=True,
            extraction_enabled=False,
            technical_binding_confirmed=True,
        )


def test_enabled_location_must_be_available_and_in_scope() -> None:
    with pytest.raises(LocationConfigError, match="no disponible"):
        LocationConfig(
            location_id="x_sps",
            supermarket_id="x",
            city_id="sps",
            city_name="San Pedro Sula",
            granularity=LocationGranularity.CITY,
            is_available=False,
            in_scope=True,
            extraction_enabled=True,
        )
    with pytest.raises(LocationConfigError, match="fuera de alcance"):
        LocationConfig(
            location_id="x_tgu",
            supermarket_id="x",
            city_id="tgu",
            city_name="Tegucigalpa",
            granularity=LocationGranularity.CITY,
            is_available=True,
            in_scope=False,
            extraction_enabled=True,
        )


def test_catalog_rejects_duplicate_location_ids() -> None:
    supermarket = SupermarketConfig(
        supermarket_id="x",
        supermarket_name="X",
        location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
    )
    first = LocationConfig(
        location_id="x_sps",
        supermarket_id="x",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=False,
    )
    second = LocationConfig(
        location_id="x_sps",
        supermarket_id="x",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=False,
    )
    with pytest.raises(LocationConfigError, match="location_id duplicado"):
        LocationCatalog({"x": supermarket}, (first, second))


def test_catalog_rejects_location_for_unknown_supermarket() -> None:
    supermarket = SupermarketConfig(
        supermarket_id="x",
        supermarket_name="X",
        location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
    )
    orphan = LocationConfig(
        location_id="y_sps",
        supermarket_id="y",
        city_id="sps",
        city_name="San Pedro Sula",
        granularity=LocationGranularity.CITY,
        is_available=True,
        in_scope=True,
        extraction_enabled=False,
    )
    with pytest.raises(LocationConfigError, match="supermercado inexistente"):
        LocationCatalog({"x": supermarket}, (orphan,))


def test_build_catalog_rejects_duplicate_supermarket_ids() -> None:
    first = SupermarketConfig(
        supermarket_id="x",
        supermarket_name="X",
        location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
    )
    second = SupermarketConfig(
        supermarket_id="x",
        supermarket_name="X duplicate",
        location_selection_mode=LocationSelectionMode.FIXED_SINGLE_CITY,
    )
    with pytest.raises(LocationConfigError, match="supermarket_id duplicado"):
        build_location_catalog((first, second), ())
