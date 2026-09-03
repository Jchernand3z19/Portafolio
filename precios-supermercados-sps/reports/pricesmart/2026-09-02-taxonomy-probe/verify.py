#!/usr/bin/env python3
"""Reproduce the PriceSmart HN public root-taxonomy evidence offline."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ARCHIVE = REPORT / "raw-capture.tar.gz"
ENDPOINT = "https://www.pricesmart.com/api/ct/getFacetCategories"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_archive(path: Path = ARCHIVE) -> tuple[bytes, dict, dict[str, bytes]]:
    archive_bytes = path.read_bytes()
    with tarfile.open(path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        if any(name.startswith("/") or ".." in Path(name).parts for name in members):
            raise ValueError("unsafe_archive_path")
        payload = {name: archive.extractfile(member).read() for name, member in members.items()}
    manifest = json.loads(payload["manifest.json"])
    for item in manifest["files"]:
        content = payload[item["path"]]
        if len(content) != item["bytes"] or sha(content) != item["sha256"]:
            raise ValueError(f"archive_member_mismatch:{item['path']}")
    return archive_bytes, manifest, payload


def reproduce(path: Path = ARCHIVE) -> dict:
    archive_bytes, manifest, payload = load_archive(path)
    authorization = json.loads(payload["capture/authorization.json"])
    ledger = json.loads(payload["live/ledger.json"])
    request = json.loads(payload["live/raw/requests/02-root-offset-0000-recovery.json"])
    response = json.loads(payload["live/raw/responses/02-root-offset-0000-recovery.json"])
    result = json.loads(payload["live/result.json"])

    if authorization["endpoint"] != ENDPOINT or authorization["authorized_operation"] != "getFacetCategories":
        raise ValueError("authorization_scope_mismatch")
    if authorization["max_post_attempts"] != 4 or authorization["max_retries"] != 2:
        raise ValueError("authorization_budget_mismatch")
    if ledger["post_attempts"] != 2 or ledger["retries"] != 1 or ledger["remaining_post_budget"] != 2:
        raise ValueError("ledger_budget_mismatch")
    if len(ledger["attempts"]) != 2 or ledger["offsets_requested"] != [0, 0]:
        raise ValueError("ledger_attempt_mismatch")
    initial, recovery = ledger["attempts"]
    if initial["raw_retained"] is not False or recovery["raw_retained"] is not True:
        raise ValueError("recovery_provenance_mismatch")
    if initial["response_body_sha256"] != recovery["response_body_sha256"]:
        raise ValueError("recovery_not_byte_identical")

    if request["method"] != "POST" or request["url"] != ENDPOINT:
        raise ValueError("request_scope_mismatch")
    if request["operation"] != "getFacetCategories" or request["global_authorized_attempt_number"] != 2:
        raise ValueError("request_attempt_mismatch")
    body = json.loads(request["body_raw"])
    if body != [{"onlyParent": True, "limit": 200, "offset": 0}]:
        raise ValueError("request_body_mismatch")
    if sha(request["body_raw"].encode()) != request["body_sha256"]:
        raise ValueError("request_body_hash_mismatch")
    cookies = request["headers"].get("Cookie", "")
    if "6602" in cookies or "6603" in cookies or "6604" in cookies:
        raise ValueError("club_context_not_authorized")
    if {part.split("=", 1)[0] for part in cookies.split("; ")} != {
        "vsf-locale", "vsf-currency", "vsf-country", "vsf-store"
    }:
        raise ValueError("unexpected_cookie_context")

    if response["status"] != 200 or response["error"] is not None:
        raise ValueError("response_status_mismatch")
    response_body = response["body_raw"].encode()
    if sha(response_body) != response["body_sha256"]:
        raise ValueError("response_body_hash_mismatch")
    decoded = json.loads(response_body)
    if decoded.get("errors"):
        raise ValueError("graphql_errors_present")
    categories = decoded["data"]["categories"]["results"]
    if len(categories) != 26 or len(categories) >= 200:
        raise ValueError("root_category_count_mismatch")
    ids = [row["id"] for row in categories]
    keys = [row["key"] for row in categories]
    slugs = [row["slug"] for row in categories]
    if len(set(ids)) != 26 or len(set(keys)) != 26 or len(set(slugs)) != 26:
        raise ValueError("root_category_identity_collision")
    if not all(row["parent"] is None and row["ancestors"] == [] for row in categories):
        raise ValueError("non_root_category_returned")
    if result["categories"] != 26 or result["remaining_post_budget"] != 2:
        raise ValueError("result_mismatch")

    root_categories = [
        {
            "source_order": index,
            "category_id": row["id"],
            "category_key": row["key"],
            "name": row["name"],
            "slug": row["slug"],
            "parent": row["parent"],
            "ancestors": row["ancestors"],
            "meta_description": row["metaDescription"],
        }
        for index, row in enumerate(categories, 1)
    ]
    return {
        "schema_version": 2,
        "raw_archive_sha256": sha(archive_bytes),
        "run": {
            "endpoint": ENDPOINT,
            "operation": "getFacetCategories",
            "context": "HN/es-HN",
            "post_attempts": 2,
            "http_200": 2,
            "retries": 1,
            "remaining_post_budget": 2,
            "concurrency": 1,
            "offsets_requested": [0, 0],
            "offset_200_requested": False,
            "categories_returned": 26,
            "initial_response_body_sha256": initial["response_body_sha256"],
            "recovery_response_body_sha256": response["body_sha256"],
            "byte_identical_recovery": True,
            "captcha_or_rate_limit": False,
            "authentication_required": False,
            "unexpected_contract": False,
            "recovery_elapsed_seconds": result["elapsed_seconds"],
            "recovery_started_at_utc": result["started_at_utc"],
            "recovery_finished_at_utc": result["finished_at_utc"],
        },
        "request": {
            "method": "POST",
            "endpoint": ENDPOINT,
            "body": body,
            "body_sha256": request["body_sha256"],
        },
        "response": {
            "status": 200,
            "body_bytes": response["body_bytes"],
            "body_sha256": response["body_sha256"],
            "top_level_keys": sorted(decoded),
            "categories_container_keys": sorted(decoded["data"]["categories"]),
        },
        "taxonomy": {
            "root_categories_returned": 26,
            "requested_limit": 200,
            "short_page_terminal": True,
            "offset_200_required": False,
            "unique_ids": 26,
            "unique_keys": 26,
            "unique_slugs": 26,
            "all_parent_null": True,
            "all_ancestors_empty": True,
            "root_keys_sha256": sha(json.dumps(keys, ensure_ascii=False, separators=(",", ":")).encode()),
            "root_ids_sha256": sha(json.dumps(ids, separators=(",", ":")).encode()),
            "categories": root_categories,
        },
        "scope_boundary": {
            "products_requested": 0,
            "discovery_requests": 0,
            "browser_requests": 0,
            "assets_requested": 0,
            "turso_operations": 0,
            "child_taxonomy_observed": False,
            "product_counts_observed": False,
            "overlap_observed": False,
        },
        "decision": {
            "root_taxonomy_demonstrated": True,
            "root_category_count": 26,
            "g10d03_existing_snapshot_reusable": True,
            "general_catalog_complete": False,
            "minimal_partitions_determined": False,
            "full_request_budget_calculable": False,
            "next_gate": "bounded Discovery totals and page-size probe for 25 uncaptured roots",
        },
        "next_probe_preflight": {
            "endpoint": "https://www.pricesmart.com/api/br_discovery/getProductsByKeyword",
            "probe_club": "6603",
            "excluded_clubs": ["6602", "6604"],
            "root_categories_total": 26,
            "already_measured_root_keys": ["G10D03"],
            "remaining_root_keys": [key for key in keys if key != "G10D03"],
            "remaining_root_count": 25,
            "base_requests_for_one_count_sample_each": 25,
            "count_sample_rows": 12,
            "count_sample_start": 0,
            "page_size_test_selection": "largest_remaining_root_with_numFound_at_least_200",
            "page_size_candidates_descending": [200, 100, 50],
            "g10d03_page_size_fallback_allowed": False,
            "page_size_characterization_requests_max": 3,
            "maximum_returned_product_documents": 500,
            "retry_reserve": 3,
            "maximum_post_attempts": 31,
        },
    }


def main() -> None:
    observed = reproduce()
    expected = json.loads((REPORT / "evidence.json").read_text())
    if observed != expected:
        raise SystemExit("evidence_mismatch")
    print("PriceSmart HN root-taxonomy probe evidence: OK")


if __name__ == "__main__":
    main()
