#!/usr/bin/env python3
"""Reproduce offline el bloqueo de binding GraphQL público de PriceSmart."""

import datetime as dt
import hashlib
import json
import tarfile
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ARCHIVE = REPORT / "raw-capture.tar.gz"


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
    ledger = json.loads(payload["ledger.json"])
    if sha256(payload["ledger.json"]) != manifest["ledger_sha256"]:
        raise ValueError("ledger_sha256_mismatch")
    for item in manifest["files"]:
        if sha256(payload[item["path"]]) != item["sha256"]:
            raise ValueError(f"file_sha256_mismatch:{item['path']}")
    if len(ledger) != 2:
        raise ValueError("unexpected_post_count")
    requests = []
    responses = []
    for row in ledger:
        request = json.loads(payload[f"raw/{row['request_file']}"])
        response = json.loads(payload[f"raw/{row['response_file']}"])
        if "mutation " in request["query"]:
            raise ValueError("mutation_in_read_only_probe")
        if row["endpoint"] != manifest["authorization"]["endpoint"]:
            raise ValueError("endpoint_mismatch")
        requests.append({
            "endpoint": row["endpoint"],
            "mutation": False,
            "operation": request["operationName"],
            "request_sha256": row["request_sha256"],
            "response_sha256": row["response_sha256"],
        })
        responses.append(response)
    if requests[0]["operation"] != "QueryTypeProbe" or '__type(name: "Query")' not in json.loads(payload[f"raw/{ledger[0]['request_file']}"])["query"]:
        raise ValueError("unexpected_introspection_probe")
    intro_error = responses[0]["errors"][0]
    if ledger[0]["status"] != 400 or intro_error["extensions"]["code"] != "GRAPHQL_VALIDATION_FAILED":
        raise ValueError("unexpected_introspection_response")
    if "introspection is not allowed" not in intro_error["message"]:
        raise ValueError("introspection_not_blocked")
    if requests[1]["operation"] != "FindChannelsProbe":
        raise ValueError("unexpected_find_channels_probe")
    find_response = responses[1]
    find_error = find_response["errors"][0]
    upstream = find_error["extensions"]["response"]
    if ledger[1]["status"] != 200 or find_error["extensions"]["code"] != "BAD_USER_INPUT":
        raise ValueError("unexpected_find_channels_response")
    if find_response.get("data", {}).get("findChannels") is not None:
        raise ValueError("unexpected_commercial_data")
    if upstream["status"] != 404 or upstream["url"] != "https://api.sphere.io/changeme/channels?offset=0&limit=500":
        raise ValueError("unexpected_upstream_binding")
    elapsed = (parse_time(ledger[-1]["finished_at"]) - parse_time(ledger[0]["started_at"])).total_seconds()
    authorization = manifest["authorization"]
    return {
        "schema_version": 1,
        "authorization": authorization,
        "capture": {
            "post_attempts": 2,
            "post_unused": authorization["post_total_max"] - len(ledger),
            "retries": 0,
            "redirects": 0,
            "concurrency": 1,
            "introspection_http_status": ledger[0]["status"],
            "introspection_graphql_code": intro_error["extensions"]["code"],
            "find_channels_http_status": ledger[1]["status"],
            "find_channels_graphql_code": find_error["extensions"]["code"],
            "upstream_status": upstream["status"],
            "upstream_url": upstream["url"],
            "elapsed_seconds": elapsed,
            "closed_reason": manifest["closed_reason"],
        },
        "requests": requests,
        "result": {
            "club_binding_demonstrated": False,
            "find_channels_data": None,
            "price_comparable_skus": 0,
            "current_price_differences": None,
            "reported_regular_price_differences": None,
            "promotion_differences": None,
            "availability_only_differences": None,
            "tgu_granularity": None,
            "pagination_demonstrated": False,
        },
        "decision": {
            "status": "BLOCKED_PUBLIC_GRAPHQL_TENANT_BINDING",
            "reason": "public_graphql_resolver_is_not_bound_to_pricesmart_tenant",
            "public_price_tracking_viable": False,
            "production_scraper": False,
            "full_crawl": False,
            "persistence": False,
            "model_change": False,
            "turso_access": False,
        },
        "raw_archive": {
            "bytes": len(archive_bytes),
            "sha256": sha256(archive_bytes),
            "published_files": len(manifest["files"]),
            "redactions": manifest["redactions"],
        },
    }


if __name__ == "__main__":
    print(json.dumps(reproduce(), ensure_ascii=False, indent=2, sort_keys=True))
