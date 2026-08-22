from __future__ import annotations

import pytest

from precios_supermercados.google_sheets_adapter import (
    WorkbookSnapshot,
    snapshot_row_counts,
)
from precios_supermercados.google_sheets_plan import parse_spreadsheet_metadata
from precios_supermercados.google_sheets_state_loader import (
    GoogleSheetsStateLoaderError,
    load_commercial_state_from_google_sheets,
)
from precios_supermercados.tabular_store import InMemoryTabularStore


class SnapshotAdapter:
    def __init__(self, snapshot: WorkbookSnapshot):
        self.snapshot = snapshot

    def load_snapshot(self):
        return self.snapshot


def empty_metadata():
    return parse_spreadsheet_metadata({"sheets": []})


def test_loader_recomputes_and_rejects_forged_row_counts() -> None:
    store = InMemoryTabularStore()
    forged_counts = dict(snapshot_row_counts(store))
    forged_counts["fact_scrape_runs"] = 99
    snapshot = WorkbookSnapshot(
        metadata=empty_metadata(),
        store=store,
        row_counts=forged_counts,
        requested_ranges=(),
    )

    with pytest.raises(
        GoogleSheetsStateLoaderError,
        match="workbook_row_counts_mismatch",
    ):
        load_commercial_state_from_google_sheets(SnapshotAdapter(snapshot))


def test_loader_rejects_snapshot_with_non_tabular_store() -> None:
    snapshot = WorkbookSnapshot(
        metadata=empty_metadata(),
        store=object(),  # type: ignore[arg-type]
        row_counts={},
        requested_ranges=(),
    )

    with pytest.raises(
        GoogleSheetsStateLoaderError,
        match="workbook_store_invalid",
    ):
        load_commercial_state_from_google_sheets(SnapshotAdapter(snapshot))


def test_loader_rejects_malformed_requested_ranges() -> None:
    store = InMemoryTabularStore()
    snapshot = WorkbookSnapshot(
        metadata=empty_metadata(),
        store=store,
        row_counts=snapshot_row_counts(store),
        requested_ranges=("",),
    )

    with pytest.raises(
        GoogleSheetsStateLoaderError,
        match="workbook_requested_ranges_invalid",
    ):
        load_commercial_state_from_google_sheets(SnapshotAdapter(snapshot))
