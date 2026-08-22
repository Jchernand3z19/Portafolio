from __future__ import annotations

import math

import pytest

from precios_supermercados.tabular_persistence import TABLE_SPECS
from precios_supermercados.tabular_store import TabularBatch, TabularStoreError


def row_with_value(value):
    spec = TABLE_SPECS["fact_quality_events"]
    row = {column: None for column in spec.columns}
    row["quality_event_id"] = "qe-cell"
    row["event_code"] = value
    return row


@pytest.mark.parametrize("value", [["mutable"], {"nested": True}, object()])
def test_batch_rejects_mutable_or_object_cells(value) -> None:
    with pytest.raises(TabularStoreError, match="celda no escalar"):
        TabularBatch({"fact_quality_events": (row_with_value(value),)})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_batch_rejects_non_finite_float_cells(value: float) -> None:
    with pytest.raises(TabularStoreError, match="celda no escalar/finita"):
        TabularBatch({"fact_quality_events": (row_with_value(value),)})


def test_batch_accepts_sheet_compatible_scalar_cells() -> None:
    spec = TABLE_SPECS["fact_quality_events"]
    row = {column: None for column in spec.columns}
    row.update(
        {
            "quality_event_id": "qe-cell",
            "scrape_run_id": "run-1",
            "supermarket_id": "demo",
            "location_id": "demo_sps",
            "offer_id": None,
            "category": "quality",
            "severity": "info",
            "event_code": "ok",
            "observed_at_utc": "2026-08-22T18:00:00.000Z",
        }
    )
    batch = TabularBatch({"fact_quality_events": (row,)})
    assert batch.row_count == 1
