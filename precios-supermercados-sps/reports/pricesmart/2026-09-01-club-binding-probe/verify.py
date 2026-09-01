#!/usr/bin/env python3
"""Reproduce offline PriceSmart club binding and commercial comparison."""

import hashlib
import json
import math
import statistics
import tarfile
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ARCHIVE = REPORT / "raw-capture.tar.gz"
ENDPOINT = "https://www.pricesmart.com/api/br_discovery/getProductsByKeyword"
PAGE = "https://www.pricesmart.com/es-hn/categoria/Alimentos-G10D03/G10D03"
CONTROL_SKU = "479223"
CLUBS = {
    "6602": {
        "name": "Florencia",
        "city": "TGU",
        "channel_id": "93a6de43-d3c7-4887-a824-44c565dc3101",
    },
    "6603": {
        "name": "San Pedro Sula",
        "city": "SPS",
        "channel_id": "83a01076-4a4e-4163-9786-c59ef7c7c1a6",
    },
    "6604": {
        "name": "El Sauce",
        "city": "TGU",
        "channel_id": "03544f88-d635-4711-b10c-e040ece7cfe6",
    },
}
ORDER = ("6603", "6602", "6604")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_archive(path=ARCHIVE):
    archive_bytes = path.read_bytes()
    with tarfile.open(path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        if any(name.startswith("/") or ".." in Path(name).parts for name in members):
            raise ValueError("unsafe_archive_path")
        payload = {name: archive.extractfile(member).read() for name, member in members.items()}
    manifest = json.loads(payload["manifest.json"])
    for item in manifest["files"]:
        value = payload[item["path"]]
        if len(value) != item["bytes"]:
            raise ValueError(f"file_size_mismatch:{item['path']}")
        if sha256(value) != item["sha256"]:
            raise ValueError(f"file_sha256_mismatch:{item['path']}")
    return archive_bytes, manifest, payload


def parse_request(payload, context):
    item = json.loads(payload[f"raw/requests/{context}.json"])
    if item["method"] != "POST" or item["url"] != ENDPOINT:
        raise ValueError(f"unexpected_request:{context}")
    if set(item["headers"]) != {"Accept", "Content-Type", "Referer", "Cookie"}:
        raise ValueError(f"unexpected_headers:{context}")
    if item["headers"]["Referer"] != PAGE:
        raise ValueError(f"unexpected_referer:{context}")
    body = json.loads(item["body_raw"])
    if len(body) != 1:
        raise ValueError(f"unexpected_batch:{context}")
    query = body[0]
    if query["view_id"] != "HN" or query["q"] != "G10D03":
        raise ValueError(f"unexpected_country_query:{context}")
    if query["rows"] != 12 or query["start"] != 0 or query["url"] != PAGE:
        raise ValueError(f"unexpected_window:{context}")
    if any(key in query for key in ("club", "club_id", "channel", "channel_id")):
        raise ValueError(f"invented_binding:{context}")
    if context == "national":
        if "price_HN" not in query["fl"] or any(f"_HN_{club}" in query["fl"] for club in CLUBS):
            raise ValueError("unexpected_national_fields")
    else:
        required = {
            f"price_HN_{context}",
            f"availability_HN_{context}",
            f"inventory_HN_{context}",
            f"saving_amount_HN_{context}",
            f"original_price_without_saving_HN_{context}",
        }
        if not required.issubset(set(query["fl"].split(","))):
            raise ValueError(f"missing_club_fields:{context}")
        cookies = item["cookie_values"]
        if cookies.get("vsf-selected-club") != context or cookies.get("vsf-provider-club-id") != context:
            raise ValueError(f"cookie_binding_mismatch:{context}")
    return item, query


def parse_response(payload, context):
    item = json.loads(payload[f"raw/responses/{context}.json"])
    if item["status"] != 200 or not item["content_type"].startswith("application/json"):
        raise ValueError(f"unexpected_response:{context}")
    body = json.loads(item["body_raw"])
    if body["response"]["numFound"] != 1124 or len(body["response"]["docs"]) != 12:
        raise ValueError(f"unexpected_catalog_result:{context}")
    return item, body


def availability(doc, club):
    available = doc.get(f"availability_HN_{club}") == "true"
    stock = doc.get(f"inventory_HN_{club}") == "in stock"
    return "in_stock" if available and stock else "out_of_stock"


def commercial_row(doc, club):
    price = doc.get(f"price_HN_{club}")
    regular = doc.get(f"original_price_without_saving_HN_{club}")
    saving = doc.get(f"saving_amount_HN_{club}")
    promotion = True if regular is not None and saving is not None and saving > 0 else None
    return {
        "current_price_minor": price,
        "reported_regular_price_minor": regular,
        "is_promotion": promotion,
        "availability": availability(doc, club),
        "source": {
            "price": price,
            "regular_price": regular,
            "saving_amount": saving,
            "availability": doc.get(f"availability_HN_{club}"),
            "inventory": doc.get(f"inventory_HN_{club}"),
            "campaign_ids": doc.get("promoid_HN", []),
        },
    }


def pair_metrics(rows, left, right):
    shared = len(rows)
    price_comparable = [row for row in rows if row[left]["current_price_minor"] is not None and row[right]["current_price_minor"] is not None]
    price_differences = [row["sku"] for row in price_comparable if row[left]["current_price_minor"] != row[right]["current_price_minor"]]
    availability_differences = [row["sku"] for row in rows if row[left]["availability"] != row[right]["availability"]]
    availability_only = [
        row["sku"] for row in price_comparable
        if row[left]["current_price_minor"] == row[right]["current_price_minor"]
        and row[left]["reported_regular_price_minor"] == row[right]["reported_regular_price_minor"]
        and row[left]["is_promotion"] == row[right]["is_promotion"]
        and row[left]["availability"] != row[right]["availability"]
    ]
    return {
        "shared_skus": shared,
        "price_comparable_skus": len(price_comparable),
        "price_differences": len(price_differences),
        "price_difference_skus": price_differences,
        "regular_price_differences": 0,
        "promotion_differences": 0,
        "availability_differences": len(availability_differences),
        "availability_difference_skus": availability_differences,
        "availability_only_differences": len(availability_only),
        "availability_only_skus": availability_only,
        "commercially_uncomparable_skus": shared - len(price_comparable),
    }


def reproduce(archive_path=ARCHIVE):
    archive_bytes, manifest, payload = load_archive(archive_path)
    ledger = json.loads(payload["ledger.json"])
    if [row["context"] for row in ledger] != ["national", *ORDER]:
        raise ValueError("unexpected_ledger_order")

    requests = {}
    responses = {}
    bodies = {}
    for context in ("national", *ORDER):
        requests[context], _ = parse_request(payload, context)
        responses[context], bodies[context] = parse_response(payload, context)

    expected_previous_channels = {
        "6603": "6f60e06b-3db0-44fe-bb5c-396d7459d1ff",
        "6602": CLUBS["6603"]["channel_id"],
        "6604": CLUBS["6602"]["channel_id"],
    }
    for club, previous in expected_previous_channels.items():
        if requests[club]["cookie_values"].get("vsf-channel") != previous:
            raise ValueError(f"unexpected_previous_channel:{club}")

    snapshots = {
        name: json.loads(payload[f"raw/snapshots/{name}.json"])
        for name in ("before-sps", "after-sps", "before-florencia", "after-florencia", "before-el-sauce", "after-el-sauce")
    }
    for club, suffix in (("6603", "sps"), ("6602", "florencia"), ("6604", "el-sauce")):
        after = snapshots[f"after-{suffix}"]
        if after["selected_club"] != int(club) or after["selected_club_description"] != CLUBS[club]["name"]:
            raise ValueError(f"visible_binding_mismatch:{club}")
        if after["cookie_values"]["vsf-channel"] != CLUBS[club]["channel_id"]:
            raise ValueError(f"channel_binding_mismatch:{club}")

    doc_maps = {club: {doc["pid"]: doc for doc in bodies[club]["response"]["docs"]} for club in ORDER}
    sku_sets = [set(items) for items in doc_maps.values()]
    if not all(items == sku_sets[0] for items in sku_sets[1:]):
        raise ValueError("club_sku_identity_mismatch")
    shared = sorted(sku_sets[0])
    rows = []
    for sku in shared:
        identities = {(doc_maps[club][sku]["pid"], doc_maps[club][sku]["master_sku"]) for club in ORDER}
        if identities != {(sku, sku)}:
            raise ValueError(f"identity_mismatch:{sku}")
        row = {"sku": sku, "title": doc_maps["6603"][sku]["title"]}
        for club in ORDER:
            row[club] = commercial_row(doc_maps[club][sku], club)
        rows.append(row)

    all_price_comparable = [row for row in rows if all(row[club]["current_price_minor"] is not None for club in ORDER)]
    all_price_differences = [
        row["sku"] for row in all_price_comparable
        if len({row[club]["current_price_minor"] for club in ORDER}) != 1
    ]
    if len(rows) != 12 or len(all_price_comparable) != 11 or all_price_differences:
        raise ValueError("unexpected_price_comparison")
    if any(row[club]["reported_regular_price_minor"] is not None for row in rows for club in ORDER):
        raise ValueError("unexpected_regular_price")
    if any(row[club]["is_promotion"] is not None for row in rows for club in ORDER):
        raise ValueError("unexpected_promotion_claim")

    control = next(row for row in rows if row["sku"] == CONTROL_SKU)
    if any(control[club]["current_price_minor"] != 35995 for club in ORDER):
        raise ValueError("control_price_mismatch")
    if any(control[club]["availability"] != "in_stock" for club in ORDER):
        raise ValueError("control_availability_mismatch")

    replay = json.loads(payload["raw/replays.json"])
    browser_raw = {club: responses[club]["body_raw"] for club in ORDER}
    replay_results = []
    for item in replay["replays"]:
        club = item["club"]
        if item["request"]["cookieHeaderPresent"] or item["response"]["status"] != 200:
            raise ValueError(f"unexpected_replay:{club}")
        if json.loads(item["response"]["bodyRaw"]) != json.loads(browser_raw[club]):
            raise ValueError(f"replay_semantic_mismatch:{club}")
        replay_results.append({
            "club": club,
            "http_status": item["response"]["status"],
            "cookie_header_present": False,
            "semantic_json_match": True,
            "byte_exact_match": item["response"]["bodyRaw"] == browser_raw[club],
            "browser_body_sha256": sha256(browser_raw[club].encode()),
            "replay_body_sha256": sha256(item["response"]["bodyRaw"].encode()),
            "canonical_json_sha256": sha256(json.dumps(json.loads(browser_raw[club]), sort_keys=True, separators=(",", ":")).encode()),
        })

    pagination_raw = json.loads(payload["raw/pagination-probes.json"])
    expected_probes = [("6603", 12, 12), ("6602", 12, 12), ("6602", 1116, 8)]
    pagination_results = []
    for item, (club, start, returned) in zip(pagination_raw["probes"], expected_probes):
        if item["club"] != club or item["start"] != start or item["rows"] != 12:
            raise ValueError("unexpected_pagination_probe")
        if item["request"]["cookieHeaderPresent"] or item["response"]["status"] != 200:
            raise ValueError("unexpected_pagination_response")
        query = json.loads(item["request"]["bodyRaw"])[0]
        body = json.loads(item["response"]["bodyRaw"])
        docs = body["response"]["docs"]
        if query["start"] != start or query["rows"] != 12:
            raise ValueError("pagination_request_mismatch")
        if body["response"]["start"] != start or body["response"]["numFound"] != 1124 or len(docs) != returned:
            raise ValueError("pagination_result_mismatch")
        if start == 12 and set(doc["pid"] for doc in docs) & set(doc_maps[club]):
            raise ValueError("pagination_overlap_page_1_page_2")
        pagination_results.append({
            "club": club,
            "start": start,
            "rows": 12,
            "returned_products": returned,
            "catalog_total": 1124,
            "http_status": 200,
            "page_1_overlap": 0,
            "elapsed_seconds": item["elapsedSeconds"],
            "response_bytes": len(item["response"]["bodyRaw"].encode()),
        })

    page_count = math.ceil(1124 / 12)
    if page_count != 94 or (page_count - 1) * 12 != 1116:
        raise ValueError("pagination_math_mismatch")
    measured_seconds = [item["elapsedSeconds"] for item in replay["replays"]] + [item["elapsedSeconds"] for item in pagination_raw["probes"]]
    non_last_response_bytes = [
        len(responses[club]["body_raw"].encode()) for club in ORDER
    ] + [
        len(item["response"]["bodyRaw"].encode())
        for item in pagination_raw["probes"] if item["start"] == 12
    ]
    mean_response_bytes = round(statistics.mean(non_last_response_bytes))

    pairwise = {
        "florencia_vs_el_sauce": pair_metrics(rows, "6602", "6604"),
        "sps_vs_florencia": pair_metrics(rows, "6603", "6602"),
        "sps_vs_el_sauce": pair_metrics(rows, "6603", "6604"),
    }
    if pairwise["florencia_vs_el_sauce"]["availability_only_differences"] != 2:
        raise ValueError("unexpected_tgu_availability_only_count")

    return {
        "schema_version": 1,
        "authorization": manifest["authorization"],
        "capture": manifest["capture"],
        "binding": {
            "demonstrated": True,
            "endpoint": ENDPOINT,
            "country_view_id": "HN",
            "known_public_clubs": CLUBS,
            "preference_cookies": ["vsf-selected-club", "vsf-provider-club-id", "vsf-selected-shipping-method"],
            "club_field_pattern": "<field>_HN_<club_id>",
            "request_club_field_examples": {
                club: [f"price_HN_{club}", f"availability_HN_{club}", f"inventory_HN_{club}"]
                for club in ORDER
            },
            "channel_cookie_lags_triggering_request": True,
            "club_body_binding_replays_without_cookie": True,
        },
        "response": {
            "catalog_total": 1124,
            "returned_products_per_context": 12,
            "shared_sku_identities": len(rows),
            "all_three_price_comparable_skus": len(all_price_comparable),
            "all_three_price_differences": len(all_price_differences),
            "regular_price_values_declared": 0,
            "regular_price_differences": 0,
            "promotion_values_declared": 0,
            "promotion_differences": 0,
            "campaign_ids_are_not_price_promotion_proof": True,
        },
        "control_product": control,
        "pairwise_comparison": pairwise,
        "comparison_rows": rows,
        "replays": replay_results,
        "pagination": {
            "validated": True,
            "model": "start_offset_plus_rows",
            "catalog_total": 1124,
            "rows_per_request": 12,
            "pages_per_context": page_count,
            "last_start": 1116,
            "last_page_products": 8,
            "probes": pagination_results,
            "measured_request_seconds_min": min(measured_seconds),
            "measured_request_seconds_median": statistics.median(measured_seconds),
            "measured_request_seconds_max": max(measured_seconds),
            "mean_non_last_response_bytes": mean_response_bytes,
        },
        "full_crawl_preflight": {
            "authorized": False,
            "contexts": ["6603", "6602"],
            "pages_per_context": 94,
            "base_post_requests": 188,
            "retry_budget": 20,
            "maximum_post_requests": 208,
            "concurrency": 1,
            "proposed_duration_minutes": 30,
            "estimated_raw_response_bytes_before_compression": mean_response_bytes * 188,
            "full_crawl_requires_separate_authorization": True,
        },
        "decision": {
            "outcome": "B",
            "status": "GO_CLUB_BINDING_PRICE_EQUIVALENT_SAMPLE_AVAILABILITY_VARIES",
            "club_binding_demonstrated": True,
            "sps_independent_binding_demonstrated": True,
            "price_equivalent_across_all_clubs_in_sample": True,
            "tgu_granularity": "ONE_REPRESENTATIVE_CONTEXT",
            "tgu_representative_club": "6602",
            "tgu_representative_name": "Florencia",
            "el_sauce_separate_commercial_context": False,
            "production_contexts_recommended": ["6603", "6602"],
            "availability_does_not_justify_extra_tgu_context": True,
            "production_scraper": False,
            "full_crawl": False,
            "persistence": False,
            "model_change": False,
            "turso_access": False,
            "additional_live_traffic": False,
        },
        "raw_archive": {
            "bytes": len(archive_bytes),
            "sha256": sha256(archive_bytes),
            "published_files": len(payload),
            "redactions": manifest["redactions"],
        },
    }


if __name__ == "__main__":
    result = reproduce()
    expected = json.loads((REPORT / "evidence.json").read_text())
    if result != expected:
        raise SystemExit("evidence_mismatch")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
