#!/usr/bin/env python3
"""Verify the recorded PriceSmart complete production operation offline."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]


def reproduce() -> dict:
    evidence = json.loads((REPORT / "evidence.json").read_text())
    loads = evidence["loads"]
    if len(loads) != 2 or [row["club_id"] for row in loads] != ["6603", "6602"]:
        raise ValueError("production_scope_invalid")
    for load in loads:
        raw = gzip.decompress((ROOT / load["snapshot_file"]).read_bytes())
        snapshot = json.loads(raw)
        if (
            hashlib.sha256(raw).hexdigest() != load["snapshot_json_sha256"]
            or snapshot["club_id"] != load["club_id"]
            or snapshot["location_id"] != load["location_id"]
            or snapshot["catalog_products_reported"] != load["catalog_products"]
            or snapshot["skus_extracted"] != load["products_processed"]
            or load["history_opened"] + load["history_unchanged"] != load["products_processed"]
            or load["history_closed"] != 0
            or load["new_periods_bound_to_run"] != load["history_opened"]
            or load["prior_alimentos_periods_open"] != 1127
        ):
            raise ValueError("production_load_invalid:" + load["location_id"])
    usage = evidence["usage"]
    before = usage["before"]
    sps = usage["after_sps_and_scoped_verification"]
    final_usage = usage["after_florencia_and_final_verification"]
    if not (
        sps["delta_rows_read"] == sps["rows_read"] - before["rows_read"]
        and sps["delta_rows_written"] == sps["rows_written"] - before["rows_written"]
        and final_usage["delta_from_sps_rows_read"] == final_usage["rows_read"] - sps["rows_read"]
        and final_usage["delta_from_sps_rows_written"] == final_usage["rows_written"] - sps["rows_written"]
        and final_usage["total_delta_rows_read"] == final_usage["rows_read"] - before["rows_read"]
        and final_usage["total_delta_rows_written"] == final_usage["rows_written"] - before["rows_written"]
        and final_usage["remaining_rows_read"] == usage["limits"]["rows_read"] - final_usage["rows_read"]
        and final_usage["remaining_rows_written"] == usage["limits"]["rows_written"] - final_usage["rows_written"]
        and usage["anomalous"] is False
    ):
        raise ValueError("usage_arithmetic_invalid")
    final = evidence["final_state"]
    if not (
        final["schema_tables"] == 5
        and final["counts"] == {
            "supermarkets": 4, "locations": 8, "products": 40824,
            "price_history": 84230, "scrape_runs": 15,
        }
        and final["pricesmart"] == {
            "unique_skus": 6078, "unique_source_products": 2766,
            "current_periods": 12156, "closed_periods": 0, "runs": 4,
        }
        and final["alimentos_periods_preserved_open_per_location"] == 1127
        and final["artificial_alimentos_history"] == 0
        and final["duplicate_current_periods"] == 0
        and final["foreign_key_violations"] == 0
        and final["integrity_check"] == "ok"
        and final["other_supermarkets_preserved"] is True
        and evidence["decision"]["status"] == "PRICESMART_COMPLETE_IN_PRODUCTION"
        and evidence["decision"]["token_stored_locally"] is False
    ):
        raise ValueError("final_state_invalid")
    return evidence


if __name__ == "__main__":
    print(json.dumps(reproduce(), ensure_ascii=False, indent=2, sort_keys=True))
