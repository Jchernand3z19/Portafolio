#!/usr/bin/env python3
"""Reproduce offline la captura CDP y el replay público de PriceSmart Honduras."""

import datetime as dt
import hashlib
import json
import tarfile
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ARCHIVE = REPORT / "raw-capture.tar.gz"
ENDPOINT = "https://www.pricesmart.com/api/br_discovery/getProductsByKeyword"
PAGE = "https://www.pricesmart.com/es-hn/categoria/Alimentos-G10D03/G10D03"
CONTROL_SKU = "479223"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_time(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def reproduce(archive_path=ARCHIVE):
    archive_bytes = archive_path.read_bytes()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        if any(name.startswith("/") or ".." in Path(name).parts for name in members):
            raise ValueError("unsafe_archive_path")
        payload = {name: archive.extractfile(member).read() for name, member in members.items()}

    manifest = json.loads(payload["manifest.json"])
    for item in manifest["files"]:
        if len(payload[item["path"]]) != item["bytes"]:
            raise ValueError(f"file_size_mismatch:{item['path']}")
        if sha256(payload[item["path"]]) != item["sha256"]:
            raise ValueError(f"file_sha256_mismatch:{item['path']}")

    ledger = json.loads(payload["ledger.json"])
    if [row["kind"] for row in ledger] != ["browser_xhr", "direct_replay"]:
        raise ValueError("unexpected_ledger")
    browser_request = json.loads(payload["raw/browser-request.json"])
    browser_response = json.loads(payload["raw/browser-response.json"])
    replay_request = json.loads(payload["raw/replay-request.json"])
    replay_response = json.loads(payload["raw/replay-response.json"])
    page_state = json.loads(payload["raw/page-state.json"])

    allowed_headers = {"Accept", "Content-Type", "Referer"}
    for request in (browser_request, replay_request):
        if request["url"] != ENDPOINT or request["method"] != "POST":
            raise ValueError("unexpected_request")
        if set(request["headers"]) != allowed_headers:
            raise ValueError("unexpected_request_headers")
        if request["cookie_header_present"]:
            raise ValueError("unexpected_cookie")
    if browser_request["body_raw"] != replay_request["body_raw"]:
        raise ValueError("replay_request_mismatch")

    request_body = json.loads(browser_request["body_raw"])
    if len(request_body) != 1:
        raise ValueError("unexpected_batch_size")
    query = request_body[0]
    if query["url"] != PAGE or query["start"] != 0 or query["rows"] != 12:
        raise ValueError("unexpected_catalog_window")
    if query["q"] != "G10D03" or query["search_type"] != "category":
        raise ValueError("unexpected_category_query")
    if query["account_id"] != "7024" or query["domain_key"] != "pricesmart_bloomreach_io_es":
        raise ValueError("unexpected_public_discovery_binding")
    if query["view_id"] != "HN" or "price_HN" not in query["fl"]:
        raise ValueError("unexpected_country_binding")
    if any(key in query for key in ("club", "club_id", "channel", "channel_id")):
        raise ValueError("unexpected_club_binding")

    if browser_response["status"] != 200 or replay_response["status"] != 200:
        raise ValueError("unexpected_http_status")
    if browser_response["body_raw"] != replay_response["body_raw"]:
        raise ValueError("replay_response_mismatch")
    response = json.loads(browser_response["body_raw"])
    docs = response["response"]["docs"]
    if len(docs) != 12 or response["response"]["numFound"] != 1124:
        raise ValueError("unexpected_catalog_result")

    controls = [doc for doc in docs if doc["pid"] == CONTROL_SKU]
    if len(controls) != 1:
        raise ValueError("control_sku_missing")
    control = controls[0]
    if control["master_sku"] != CONTROL_SKU or control["variants"] != [{"skuid": CONTROL_SKU}]:
        raise ValueError("control_identity_mismatch")
    if control["currency"] != "HNL" or control["fractionDigits"] != 2 or control["price_HN"] != 35995:
        raise ValueError("control_price_mismatch")
    if control["availability_HN"] != "true" or control["inventory_HN"] != "in stock":
        raise ValueError("control_availability_mismatch")
    if "original_price_without_saving_HN" in control or "saving_amount_HN" in control:
        raise ValueError("unexpected_regular_price_fields")

    facet_ranges = response["facet_counts"]["facet_ranges"]
    club_price_facet_counts = {
        club_id: sum(bucket["count"] for bucket in facet_ranges[f"price_HN_{club_id}"])
        for club_id in ("6602", "6603", "6604")
    }
    if club_price_facet_counts != {"6602": 1072, "6603": 1078, "6604": 1061}:
        raise ValueError("unexpected_club_price_facets")
    if page_state["delivery_context_text"] != "Seleccionar entrega":
        raise ValueError("unexpected_delivery_context")
    if page_state["control_product_visible_text"]["price"] != "L 359.95":
        raise ValueError("browser_price_mismatch")

    auth = manifest["authorization"]
    live_start = parse_time(auth["live_started_at_utc"])
    live_deadline = parse_time(auth["live_deadline_utc"])
    live_end = parse_time(auth["live_finished_at_utc"])
    elapsed = (live_end - live_start).total_seconds()
    overrun = max(0.0, (live_end - live_deadline).total_seconds())

    body_sha = sha256(browser_response["body_raw"].encode())
    request_sha = sha256(browser_request["body_raw"].encode())
    campaign_ids = control.get("promoid_HN", [])
    return {
        "schema_version": 1,
        "authorization": auth,
        "capture": {
            "browser_sessions": 1,
            "page_loads": 1,
            "captured_network_requests_on_load": 135,
            "retained_relevant_response_bodies": 24,
            "selected_browser_xhr": 1,
            "direct_replays": 1,
            "concurrency": 1,
            "elapsed_seconds": elapsed,
            "duration_cap_compliant": False,
            "duration_overrun_seconds": overrun,
            "retries": 0,
            "redirects_on_selected_requests": 0,
            "cookies_sent_on_selected_requests": 0,
            "captcha_or_rate_limit": False,
            "response_exact_match": True,
            "request_body_sha256": request_sha,
            "response_body_sha256": body_sha,
        },
        "request": {
            "endpoint": ENDPOINT,
            "method": "POST",
            "resource_type": "XHR",
            "headers": browser_request["headers"],
            "body": query,
            "anonymous_public_auth_key_retained": True,
            "cookie_required": False,
            "country_binding": "HN",
            "club_binding": None,
        },
        "response": {
            "http_status": 200,
            "content_type": browser_response["content_type"],
            "catalog_total": 1124,
            "returned_products": 12,
            "club_price_facet_counts": club_price_facet_counts,
        },
        "control_product": {
            "sku": CONTROL_SKU,
            "pid": control["pid"],
            "master_sku": control["master_sku"],
            "title": control["title"],
            "currency": control["currency"],
            "current_price_minor": control["price_HN"],
            "current_price": control["price_HN"] / 100,
            "reported_regular_price": None,
            "reported_regular_price_declared": False,
            "is_promotion": None,
            "price_promotion_declared": False,
            "campaign_ids": campaign_ids,
            "campaign_ids_are_not_price_promotion_proof": True,
            "availability": "in_stock",
            "availability_source": {
                "availability_HN": control["availability_HN"],
                "inventory_HN": control["inventory_HN"],
            },
            "visible_browser_price": page_state["control_product_visible_text"]["price"],
        },
        "club_assessment": {
            "known_public_clubs": {
                "6602": "Florencia",
                "6603": "San Pedro Sula",
                "6604": "El Sauce",
            },
            "page_selected_delivery_context": None,
            "sps_request_binding_demonstrated": False,
            "club_specific_price_values_returned_for_products": False,
            "club_specific_price_facet_names_observed": True,
            "facet_counts_do_not_prove_product_price_binding": True,
            "comparable_skus_between_clubs": 0,
            "tgu_granularity": None,
        },
        "decision": {
            "outcome": "B",
            "status": "PARTIAL_GO_PUBLIC_HN_PRICE_SPS_BINDING_UNPROVEN_PROTOCOL_NONCONFORMING",
            "public_hn_catalog_price_source_demonstrated": True,
            "sps_club_price_source_demonstrated": False,
            "reason": "request_is_country_bound_not_club_bound_and_replay_exceeded_duration_cap",
            "production_scraper": False,
            "parser_or_fixture": False,
            "full_crawl": False,
            "full_crawl_budget": None,
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
    print(json.dumps(reproduce(), ensure_ascii=False, indent=2, sort_keys=True))
