from __future__ import annotations

from copy import deepcopy

import pytest

from precios_supermercados.google_sheets_plan import (
    GoogleSheetsPlanError,
    SheetMetadata,
    SpreadsheetMetadata,
    build_atomic_workbook_plan,
    parse_spreadsheet_metadata,
)
from precios_supermercados.tabular_persistence import (
    FACT_OFFERS_CURRENT,
    TABLE_SPECS,
    location_config_rows,
    supermarket_config_rows,
)
from precios_supermercados.tabular_store import InMemoryTabularStore, TabularBatch


def configured_store() -> InMemoryTabularStore:
    store = InMemoryTabularStore()
    store.apply(
        TabularBatch(
            {
                "cfg_supermarkets": supermarket_config_rows(),
                "cfg_locations": location_config_rows(),
            }
        )
    )
    return store


def blank_current(offer_id: str, *, source_name: str = "Producto") -> dict:
    row = {column: None for column in FACT_OFFERS_CURRENT.columns}
    row.update(
        {
            "offer_id": offer_id,
            "supermarket_id": "demo",
            "supermarket_name": "Demo",
            "location_id": "demo_sps",
            "city_id": "sps",
            "city_name": "San Pedro Sula",
            "source_name": source_name,
        }
    )
    return row


def requests_of(plan, kind: str):
    return [request[kind] for request in plan.payload["requests"] if kind in request]


def test_empty_spreadsheet_bootstraps_all_managed_tabs_in_one_payload() -> None:
    store = configured_store()
    plan = build_atomic_workbook_plan(store, SpreadsheetMetadata({}))

    payload = plan.payload
    assert payload["includeSpreadsheetInResponse"] is False
    add_sheets = requests_of(plan, "addSheet")
    assert len(add_sheets) == len(TABLE_SPECS)
    assert {item["properties"]["title"] for item in add_sheets} == set(TABLE_SPECS)
    assert len(set(plan.sheet_ids.values())) == len(TABLE_SPECS)
    assert plan.row_counts["cfg_supermarkets"] == 1
    assert plan.row_counts["cfg_locations"] == 2
    assert plan.row_counts["fact_offers_current"] == 0
    assert plan.payload_bytes == len(plan.payload_json.encode("utf-8"))


def test_headers_are_written_frozen_and_bold() -> None:
    plan = build_atomic_workbook_plan(configured_store(), SpreadsheetMetadata({}))
    current_id = plan.sheet_ids["fact_offers_current"]

    add = next(
        item for item in requests_of(plan, "addSheet")
        if item["properties"]["title"] == "fact_offers_current"
    )
    assert add["properties"]["gridProperties"]["frozenRowCount"] == 1
    assert add["properties"]["gridProperties"]["rowCount"] == 1
    assert add["properties"]["gridProperties"]["columnCount"] == len(
        FACT_OFFERS_CURRENT.columns
    )

    update = next(
        item for item in requests_of(plan, "updateCells")
        if item["range"]["sheetId"] == current_id
    )
    header = update["rows"][0]["values"]
    assert [cell["userEnteredValue"]["stringValue"] for cell in header] == list(
        FACT_OFFERS_CURRENT.columns
    )

    bold = next(
        item for item in requests_of(plan, "repeatCell")
        if item["range"]["sheetId"] == current_id
    )
    assert bold["cell"]["userEnteredFormat"]["textFormat"]["bold"] is True


def test_existing_managed_tabs_are_reused_and_extra_tabs_are_preserved() -> None:
    metadata = SpreadsheetMetadata(
        {
            "fact_offers_current": SheetMetadata(7, "fact_offers_current", 1000, 60),
            "Mis notas": SheetMetadata(99, "Mis notas", 200, 10),
        }
    )
    plan = build_atomic_workbook_plan(configured_store(), metadata)
    assert plan.sheet_ids["fact_offers_current"] == 7
    assert 99 not in plan.sheet_ids.values()
    assert not any("deleteSheet" in request for request in plan.payload["requests"])

    properties = next(
        item for item in requests_of(plan, "updateSheetProperties")
        if item["properties"]["sheetId"] == 7
    )
    grid = properties["properties"]["gridProperties"]
    assert grid["rowCount"] == 1
    assert grid["columnCount"] == len(FACT_OFFERS_CURRENT.columns)
    assert grid["frozenRowCount"] == 1


def test_existing_filters_are_cleared_before_resize_and_only_data_tabs_get_filter() -> None:
    metadata = SpreadsheetMetadata(
        {
            "cfg_supermarkets": SheetMetadata(10, "cfg_supermarkets", 50, 10),
            "fact_offers_current": SheetMetadata(11, "fact_offers_current", 50, 50),
        }
    )
    plan = build_atomic_workbook_plan(configured_store(), metadata)
    payload = plan.payload["requests"]

    clear_index = next(
        index for index, request in enumerate(payload)
        if request.get("clearBasicFilter", {}).get("sheetId") == 10
    )
    resize_index = next(
        index for index, request in enumerate(payload)
        if request.get("updateSheetProperties", {}).get("properties", {}).get("sheetId") == 10
    )
    assert clear_index < resize_index

    filtered_ids = {
        item["filter"]["range"]["sheetId"] for item in requests_of(plan, "setBasicFilter")
    }
    assert plan.sheet_ids["cfg_supermarkets"] in filtered_ids
    assert plan.sheet_ids["cfg_locations"] in filtered_ids
    assert plan.sheet_ids["fact_offers_current"] not in filtered_ids


def test_source_text_that_looks_like_formula_is_written_as_literal_string() -> None:
    store = configured_store()
    store.apply(
        TabularBatch(
            {
                "fact_offers_current": (
                    blank_current("offer-1", source_name='=IMPORTXML("https://evil.invalid")'),
                )
            }
        )
    )
    plan = build_atomic_workbook_plan(store, SpreadsheetMetadata({}))
    sheet_id = plan.sheet_ids["fact_offers_current"]
    update = next(
        item for item in requests_of(plan, "updateCells")
        if item["range"]["sheetId"] == sheet_id
    )
    source_name_index = FACT_OFFERS_CURRENT.columns.index("source_name")
    cell = update["rows"][1]["values"][source_name_index]
    assert cell == {
        "userEnteredValue": {
            "stringValue": '=IMPORTXML("https://evil.invalid")'
        }
    }
    assert "formulaValue" not in cell["userEnteredValue"]


def test_plan_payload_property_returns_fresh_copy() -> None:
    plan = build_atomic_workbook_plan(configured_store(), SpreadsheetMetadata({}))
    first = plan.payload
    original_count = len(first["requests"])
    first["requests"].clear()
    assert len(plan.payload["requests"]) == original_count


def test_new_sheet_ids_avoid_all_existing_ids() -> None:
    metadata = SpreadsheetMetadata(
        {
            "Extra 1": SheetMetadata(1000, "Extra 1", 10, 10),
            "Extra 2": SheetMetadata(1001, "Extra 2", 10, 10),
            "Extra 3": SheetMetadata(1002, "Extra 3", 10, 10),
        }
    )
    plan = build_atomic_workbook_plan(configured_store(), metadata)
    assert min(plan.sheet_ids.values()) >= 1003


def test_parse_spreadsheet_metadata_uses_only_properties_needed_by_planner() -> None:
    payload = {
        "spreadsheetId": "abc",
        "sheets": [
            {
                "properties": {
                    "sheetId": 123,
                    "title": "cfg_supermarkets",
                    "index": 0,
                    "gridProperties": {
                        "rowCount": 100,
                        "columnCount": 20,
                        "frozenRowCount": 1,
                    },
                },
                "ignored": {"anything": True},
            }
        ],
    }
    parsed = parse_spreadsheet_metadata(payload)
    assert parsed.sheets["cfg_supermarkets"] == SheetMetadata(
        123, "cfg_supermarkets", 100, 20
    )


def test_metadata_rejects_duplicate_sheet_ids_and_incomplete_grid() -> None:
    with pytest.raises(GoogleSheetsPlanError, match="sheet_id duplicado"):
        SpreadsheetMetadata(
            {
                "a": SheetMetadata(1, "a", 10, 10),
                "b": SheetMetadata(1, "b", 10, 10),
            }
        )
    with pytest.raises(GoogleSheetsPlanError, match="gridProperties"):
        parse_spreadsheet_metadata(
            {"sheets": [{"properties": {"sheetId": 1, "title": "x"}}]}
        )


def test_plan_does_not_mutate_store_or_metadata() -> None:
    store = configured_store()
    metadata_payload = {
        "sheets": [
            {
                "properties": {
                    "sheetId": 1,
                    "title": "Mis notas",
                    "gridProperties": {"rowCount": 20, "columnCount": 5},
                }
            }
        ]
    }
    before = deepcopy(metadata_payload)
    metadata = parse_spreadsheet_metadata(metadata_payload)
    counts_before = {name: store.count(name) for name in TABLE_SPECS}
    build_atomic_workbook_plan(store, metadata)
    assert metadata_payload == before
    assert {name: store.count(name) for name in TABLE_SPECS} == counts_before
