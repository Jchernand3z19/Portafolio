#!/usr/bin/env python3
"""Reproduce PriceSmart Discovery totals, taxonomy and full-budget evidence offline."""

from __future__ import annotations

import hashlib
import json
import math
import tarfile
from collections import defaultdict
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
ARCHIVE = REPORT / "raw-capture.tar.gz"
TAXONOMY_REPORT = ROOT / "reports/pricesmart/2026-09-02-taxonomy-probe"
GENERAL_REPORT = ROOT / "reports/pricesmart/2026-09-02-general-catalog-preflight"
ALIMENTOS_ARCHIVE = ROOT / "reports/pricesmart/2026-09-01-full/raw-capture.tar.gz"
ENDPOINT = "https://www.pricesmart.com/api/br_discovery/getProductsByKeyword"
ALIMENTOS_ARCHIVE_SHA256 = "4613c634f584cc3ba157504f5b40cbb04aa94c7c14e65984672babe9e27d1b05"
TAXONOMY_ARCHIVE_SHA256 = "68267bbe876abc6efea726d23e7aa22bc8254bb3798f0f8a3e018d8bd5b34771"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_archive(path: Path) -> tuple[bytes, dict, dict[str, bytes]]:
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


def product_and_skus(docs: list[dict]) -> tuple[set[str], set[str]]:
    products: set[str] = set()
    skus: set[str] = set()
    for doc in docs:
        products.add(str(doc["pid"]))
        variants = doc.get("variants") or []
        variant_skus = {str(row["skuid"]) for row in variants if row.get("skuid") is not None}
        if not variant_skus and doc.get("skuid") is not None:
            variant_skus.add(str(doc["skuid"]))
        skus.update(variant_skus)
    return products, skus


def alimentos_identities() -> tuple[set[str], set[str]]:
    if sha(ALIMENTOS_ARCHIVE.read_bytes()) != ALIMENTOS_ARCHIVE_SHA256:
        raise ValueError("alimentos_archive_hash_mismatch")
    products: set[str] = set()
    skus: set[str] = set()
    with tarfile.open(ALIMENTOS_ARCHIVE, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.startswith("live/raw/responses/"):
                continue
            if "-6603-" not in Path(member.name).name:
                continue
            record = json.loads(archive.extractfile(member).read())
            payload = json.loads(record["body_raw"])
            page_products, page_skus = product_and_skus(payload["response"]["docs"])
            products.update(page_products)
            skus.update(page_skus)
    if len(products) != 1124 or len(skus) != 1127:
        raise ValueError("alimentos_identity_count_mismatch")
    return products, skus


def reproduce(path: Path = ARCHIVE) -> dict:
    archive_bytes, manifest, payload = load_archive(path)
    ledger = json.loads(payload["live/ledger.json"])
    result = json.loads(payload["live/result.json"])
    authorization = json.loads(payload["capture/authorization.json"])
    taxonomy_evidence = json.loads((TAXONOMY_REPORT / "evidence.json").read_text())
    general_evidence = json.loads((GENERAL_REPORT / "evidence.json").read_text())
    if sha((TAXONOMY_REPORT / "raw-capture.tar.gz").read_bytes()) != TAXONOMY_ARCHIVE_SHA256:
        raise ValueError("root_taxonomy_archive_hash_mismatch")

    if authorization["endpoint"] != ENDPOINT or authorization["club"] != "6603":
        raise ValueError("authorization_scope_mismatch")
    if authorization["excluded_clubs"] != ["6602", "6604"]:
        raise ValueError("excluded_club_mismatch")
    if authorization["max_post_attempts"] != 31 or authorization["max_retries"] != 3:
        raise ValueError("authorization_budget_mismatch")
    if authorization["max_documents_returned"] != 500 or authorization["concurrency"] != 1:
        raise ValueError("authorization_document_or_concurrency_mismatch")
    if result["post_attempts"] != 26 or result["retries"] != 0:
        raise ValueError("result_attempt_mismatch")
    if result["remaining_post_budget"] != 5 or result["documents_returned"] != 455:
        raise ValueError("result_budget_mismatch")
    if ledger["post_attempts"] != 26 or len(ledger["attempts"]) != 26:
        raise ValueError("ledger_attempt_mismatch")
    if ledger["aborted_reason"] is not None or ledger["documents_returned"] != 455:
        raise ValueError("ledger_completion_mismatch")

    roots = taxonomy_evidence["taxonomy"]["categories"]
    root_by_key = {row["category_key"]: row for row in roots}
    pending_keys = [row["category_key"] for row in roots if row["category_key"] != "G10D03"]
    if authorization["pending_root_keys"] != pending_keys or len(pending_keys) != 25:
        raise ValueError("pending_root_scope_mismatch")

    decoded_by_attempt: dict[int, dict] = {}
    request_by_attempt: dict[int, dict] = {}
    for attempt in ledger["attempts"]:
        number = attempt["attempt_number"]
        request_record = json.loads(payload[f"live/{attempt['request_file']}"])
        response_record = json.loads(payload[f"live/{attempt['response_file']}"])
        if request_record["url"] != ENDPOINT or request_record["method"] != "POST":
            raise ValueError("request_endpoint_mismatch")
        if request_record["cookie_header_present"] or "Authorization" in request_record["headers"]:
            raise ValueError("request_header_scope_mismatch")
        query = json.loads(request_record["body_raw"])[0]
        if query.pop("auth_key") != "[REDACTED_PUBLIC_CLIENT_KEY]":
            raise ValueError("public_client_key_not_redacted")
        if query["q"] == "G10D03" or query["q"] not in pending_keys:
            raise ValueError("request_category_out_of_scope")
        if query["start"] != 0 or query["view_id"] != "HN" or query["search_type"] != "category":
            raise ValueError("query_contract_mismatch")
        if query["fq"] != [] or query["rows"] not in {12, 200, 100, 50}:
            raise ValueError("query_window_mismatch")
        fields = set(query["fl"].split(","))
        if "price_HN_6603" not in fields or any(
            any(f"_HN_{club}" in field for club in ("6602", "6604")) for field in fields
        ):
            raise ValueError("query_club_projection_mismatch")
        if sha(request_record["body_raw"].encode()) != request_record["body_sha256"]:
            raise ValueError("published_request_hash_mismatch")
        if response_record["status"] != 200 or response_record["error"] is not None:
            raise ValueError("response_status_mismatch")
        response_body = response_record["body_raw"].encode()
        if sha(response_body) != response_record["body_sha256"]:
            raise ValueError("response_body_hash_mismatch")
        decoded = json.loads(response_body)
        response = decoded["response"]
        docs = response["docs"]
        if response["start"] != 0 or len(docs) != min(query["rows"], response["numFound"]):
            raise ValueError("response_window_mismatch")
        if len({doc["pid"] for doc in docs}) != len(docs):
            raise ValueError("duplicate_product_within_page")
        if not isinstance(decoded["facet_counts"]["facet_fields"]["category"], list):
            raise ValueError("category_facet_missing")
        decoded_by_attempt[number] = decoded
        request_by_attempt[number] = query

    base_attempts = [row for row in ledger["attempts"] if row["phase"] == "base"]
    size_attempts = [row for row in ledger["attempts"] if row["phase"] == "page_size"]
    if len(base_attempts) != 25 or len(size_attempts) != 1:
        raise ValueError("phase_attempt_count_mismatch")
    if [row["category_key"] for row in base_attempts] != pending_keys:
        raise ValueError("base_root_order_mismatch")
    if any(row["rows"] != 12 or not row["valid"] for row in base_attempts):
        raise ValueError("base_request_invalid")
    size_attempt = size_attempts[0]
    if size_attempt["category_key"] != "H30D22" or size_attempt["rows"] != 200:
        raise ValueError("page_size_selection_mismatch")
    size_payload = decoded_by_attempt[size_attempt["attempt_number"]]
    if size_payload["response"]["numFound"] != 315 or len(size_payload["response"]["docs"]) != 200:
        raise ValueError("page_size_result_mismatch")

    totals: dict[str, int] = {}
    facet_nodes_by_query: dict[str, list[dict]] = {}
    products_by_root: dict[str, set[str]] = defaultdict(set)
    skus_by_root: dict[str, set[str]] = defaultdict(set)
    node_structures: dict[str, dict] = {}
    node_owners: dict[str, set[str]] = defaultdict(set)
    foreign_root_signals: list[dict] = []
    for attempt in base_attempts:
        key = attempt["category_key"]
        decoded = decoded_by_attempt[attempt["attempt_number"]]
        total = decoded["response"]["numFound"]
        facets = decoded["facet_counts"]["facet_fields"]["category"]
        totals[key] = total
        facet_nodes_by_query[key] = facets
        page_products, page_skus = product_and_skus(decoded["response"]["docs"])
        products_by_root[key].update(page_products)
        skus_by_root[key].update(page_skus)
        roots_in_facet = [row for row in facets if row.get("parent", "") == ""]
        if sum(row["count"] for row in roots_in_facet) != total:
            raise ValueError(f"root_facet_count_not_reconciled:{key}")
        for row in roots_in_facet:
            if row["cat_id"] != key:
                foreign_root_signals.append({
                    "query_root": key,
                    "facet_root": row["cat_id"],
                    "facet_root_name": row["cat_name"],
                    "count": row["count"],
                })
        local_ids = {row["cat_id"] for row in facets}
        for row in facets:
            parent = row.get("parent") or None
            if parent is not None and parent not in local_ids:
                raise ValueError(f"facet_orphan:{key}:{row['cat_id']}")
            structure = {
                "category_id": row["cat_id"],
                "name": row["cat_name"],
                "parent_id": parent,
                "crumb": row["crumb"],
                "tree_path": row["tree_path"],
                "level": len([part for part in row["crumb"].split("/") if part]),
            }
            prior = node_structures.get(row["cat_id"])
            if prior is not None and prior != structure:
                raise ValueError(f"taxonomy_structure_collision:{row['cat_id']}")
            node_structures[row["cat_id"]] = structure
            node_owners[row["cat_id"]].add(key)

    page_products, page_skus = product_and_skus(size_payload["response"]["docs"])
    products_by_root["H30D22"].update(page_products)
    skus_by_root["H30D22"].update(page_skus)

    expected_totals = {key: result["base"][key]["num_found"] for key in pending_keys}
    if totals != expected_totals or sum(totals.values()) != 1653:
        raise ValueError("root_total_mismatch")
    if sum(value > 0 for value in totals.values()) != 23:
        raise ValueError("nonempty_root_count_mismatch")

    food_nodes = general_evidence["g10d03_taxonomy"]["nodes"]
    for row in food_nodes:
        structure = {
            "category_id": row["category_id"],
            "name": row["name"],
            "parent_id": row["parent_id"],
            "crumb": row["crumb"],
            "tree_path": row["tree_path"],
            "level": row["level"],
        }
        if structure["category_id"] in node_structures:
            raise ValueError("alimentos_taxonomy_collision")
        node_structures[structure["category_id"]] = structure
    for row in roots:
        node_structures.setdefault(row["category_key"], {
            "category_id": row["category_key"],
            "name": row["name"],
            "parent_id": None,
            "crumb": f"/{row['category_key']}",
            "tree_path": f"/{row['category_key']},{row['name']}",
            "level": 1,
        })
    parent_ids = {row["parent_id"] for row in node_structures.values() if row["parent_id"]}
    if any(parent not in node_structures for parent in parent_ids):
        raise ValueError("combined_taxonomy_orphan")
    if len(node_structures) != 546 or len(parent_ids) != 89:
        raise ValueError("combined_taxonomy_count_mismatch")

    product_memberships: dict[str, list[str]] = defaultdict(list)
    sku_memberships: dict[str, list[str]] = defaultdict(list)
    for key in pending_keys:
        for product in sorted(products_by_root[key]):
            product_memberships[product].append(key)
        for sku in sorted(skus_by_root[key]):
            sku_memberships[sku].append(key)
    product_overlaps = {key: value for key, value in product_memberships.items() if len(value) > 1}
    sku_overlaps = {key: value for key, value in sku_memberships.items() if len(value) > 1}
    alimentos_products, alimentos_skus = alimentos_identities()
    sampled_products = set(product_memberships)
    sampled_skus = set(sku_memberships)

    root_plan = []
    for root in roots:
        key = root["category_key"]
        if key == "G10D03":
            root_plan.append({
                "category_key": key,
                "name": root["name"],
                "num_found": 1124,
                "source": "existing_complete_snapshot",
                "full_pages_at_rows_200": None,
                "new_sps_requests": 0,
                "new_tgu_requests": 0,
                "sps_offsets": [],
                "tgu_offsets": [],
                "child_partition_required": False,
            })
            continue
        total = totals[key]
        tgu_offsets = list(range(0, total, 200))
        if total <= 12:
            sps_offsets = []
        elif key == "H30D22":
            sps_offsets = [200]
        elif key == "F10D40":
            sps_offsets = [0, 200]
        else:
            sps_offsets = [12]
        root_plan.append({
            "category_key": key,
            "name": root["name"],
            "num_found": total,
            "source": "discovery_probe",
            "facet_nodes": len(facet_nodes_by_query[key]),
            "full_pages_at_rows_200": math.ceil(total / 200),
            "new_sps_requests": len(sps_offsets),
            "new_tgu_requests": len(tgu_offsets),
            "sps_offsets": sps_offsets,
            "tgu_offsets": tgu_offsets,
            "child_partition_required": False,
        })
    sps_requests = sum(row["new_sps_requests"] for row in root_plan)
    tgu_requests = sum(row["new_tgu_requests"] for row in root_plan)
    if sps_requests != 21 or tgu_requests != 25:
        raise ValueError("full_request_plan_mismatch")

    gross_sample_products = sum(len(value) for value in products_by_root.values())
    gross_sample_skus = sum(len(value) for value in skus_by_root.values())
    sku_projection = 1127.0
    for key, total in totals.items():
        product_count = len(products_by_root[key])
        if product_count:
            sku_projection += total * len(skus_by_root[key]) / product_count

    return {
        "schema_version": 1,
        "raw_archive_sha256": sha(archive_bytes),
        "linked_evidence": {
            "root_taxonomy_archive_sha256": TAXONOMY_ARCHIVE_SHA256,
            "alimentos_full_archive_sha256": ALIMENTOS_ARCHIVE_SHA256,
        },
        "run": {
            "endpoint": ENDPOINT,
            "club": "6603",
            "excluded_clubs": ["6602", "6604"],
            "started_at_utc": result["started_at_utc"],
            "finished_at_utc": result["finished_at_utc"],
            "elapsed_seconds": result["elapsed_seconds"],
            "post_attempts": 26,
            "http_200": 26,
            "retries": 0,
            "remaining_post_budget": 5,
            "documents_returned": 455,
            "concurrency": 1,
            "captcha_or_rate_limit": False,
            "authentication_required": False,
            "unexpected_contract": False,
            "request_auth_key_redacted_in_published_raw": True,
            "session_cookies": 0,
            "authorization_headers": 0,
        },
        "pagination": {
            "largest_remaining_root": "H30D22",
            "largest_remaining_num_found": 315,
            "requested_rows": 200,
            "returned_documents": 200,
            "accepted_on_first_candidate": True,
            "unused_candidates": [100, 50],
            "useful_page_size_demonstrated": 200,
            "prior_offset_pagination_evidence": {
                "category_key": "G10D03",
                "rows": 12,
                "maximum_start": 1116,
                "pages_per_club": 94,
            },
        },
        "catalog": {
            "root_category_count": 26,
            "remaining_roots_measured": 25,
            "remaining_nonempty_roots": 23,
            "remaining_empty_roots": ["U11D13", "J10D44"],
            "remaining_num_found_sum": 1653,
            "alimentos_num_found": 1124,
            "gross_product_observations_per_club": 2777,
            "gross_product_observations_both_clubs": 5554,
            "root_plan": root_plan,
        },
        "taxonomy": {
            "combined_unique_nodes": 546,
            "root_nodes": 26,
            "observed_parent_nodes": 89,
            "observed_leaf_nodes": 457,
            "maximum_level": max(row["level"] for row in node_structures.values()),
            "orphan_nodes": 0,
            "structure_collisions": 0,
            "new_facet_unique_nodes": len({
                row["cat_id"] for rows in facet_nodes_by_query.values() for row in rows
            }),
            "new_facet_observations": sum(len(rows) for rows in facet_nodes_by_query.values()),
            "facet_nodes_shared_between_root_queries": sum(len(value) > 1 for value in node_owners.values()),
            "nodes": [node_structures[key] for key in sorted(node_structures)],
        },
        "overlap": {
            "probe_documents_returned_including_repeated_h30_window": 455,
            "sampled_product_memberships": gross_sample_products,
            "sampled_unique_products": len(sampled_products),
            "identity_proven_cross_root_products": len(product_overlaps),
            "cross_root_product_memberships": product_overlaps,
            "sampled_sku_memberships": gross_sample_skus,
            "sampled_unique_skus": len(sampled_skus),
            "identity_proven_cross_root_skus": len(sku_overlaps),
            "cross_root_sku_memberships": sku_overlaps,
            "sampled_product_overlap_with_alimentos": len(sampled_products & alimentos_products),
            "sampled_sku_overlap_with_alimentos": len(sampled_skus & alimentos_skus),
            "foreign_root_facet_signals": foreign_root_signals,
            "foreign_root_facet_signal_count": sum(row["count"] for row in foreign_root_signals),
            "exact_full_overlap_demonstrated": False,
            "gross_unique_product_upper_bound_per_club": 2777,
            "facet_signal_point_estimate_unique_products_per_club": 2766,
        },
        "sku_estimate": {
            "alimentos_exact_skus_per_club": 1127,
            "sampled_remaining_unique_products": len(sampled_products),
            "sampled_remaining_unique_skus": len(sampled_skus),
            "sample_ratio_projection_sku_observations_per_club": round(sku_projection),
            "confidence": "low_until_full_due_variant_heavy_F10D40_sample",
        },
        "partition_decision": {
            "productive_root_partitions_total": 24,
            "existing_complete_partitions": ["G10D03"],
            "remaining_direct_root_partitions": [key for key in pending_keys if totals[key] > 0],
            "empty_roots": [key for key in pending_keys if totals[key] == 0],
            "child_partitions_required": [],
            "reason": "largest root has 315 products, rows=200 is accepted, and prior start pagination advances through a larger parent",
        },
        "full_budget": {
            "endpoint": ENDPOINT,
            "clubs": ["6603", "6602"],
            "excluded_club": "6604",
            "rows": 200,
            "new_sps_base_requests_reusing_probe": 21,
            "new_florencia_base_requests": 25,
            "base_post_requests": 46,
            "retry_reserve": 5,
            "maximum_post_attempts": 51,
            "concurrency": 1,
            "maximum_duration_seconds": 600,
            "new_product_documents_expected": 2875,
            "alimentos_recrawl_requests": 0,
            "stop_if_num_found_changes": True,
            "turso_operations": 0,
        },
        "decision": {
            "full_budget_calculable": True,
            "general_catalog_complete": False,
            "next_gate": "explicit remaining full authorization",
        },
    }


def main() -> None:
    observed = reproduce()
    expected = json.loads((REPORT / "evidence.json").read_text())
    if observed != expected:
        raise SystemExit("evidence_mismatch")
    print("PriceSmart HN Discovery probe evidence: OK")


if __name__ == "__main__":
    main()
