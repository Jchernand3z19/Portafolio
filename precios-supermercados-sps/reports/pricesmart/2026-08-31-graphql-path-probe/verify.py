#!/usr/bin/env python3
"""Reproduce offline el cierre por incompatibilidad de esquema PriceSmart."""

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
    if len(ledger) != 1:
        raise ValueError("unexpected_post_count")
    row = ledger[0]
    request = json.loads(payload[f"raw/{row['request_file']}"])
    response = json.loads(payload[f"raw/{row['response_file']}"])
    if request["operationName"] != "channels" or "query channels" not in request["query"]:
        raise ValueError("unexpected_graphql_operation")
    if "mutation " in request["query"]:
        raise ValueError("mutation_in_read_only_probe")
    if set(request["variables"]) != {"where", "limit", "offset", "acceptLanguage"}:
        raise ValueError("unexpected_channels_variables")
    if row["endpoint"] != manifest["authorization"]["endpoint"]:
        raise ValueError("endpoint_mismatch")
    if row["status"] != 400:
        raise ValueError("unexpected_endpoint_response")
    errors = response.get("errors") or []
    messages = [error.get("message") for error in errors]
    codes = sorted({error.get("extensions", {}).get("code") for error in errors})
    required = {
        'Unknown type "Locale".',
        'Cannot query field "channels" on type "Query". Did you mean "findChannels"?',
        'Unknown type "Point". Did you mean "Int", "Link", or "Price"?',
    }
    if set(messages) != required or codes != ["GRAPHQL_VALIDATION_FAILED"]:
        raise ValueError("unexpected_graphql_validation_errors")
    elapsed = (parse_time(row["finished_at"]) - parse_time(row["started_at"])).total_seconds()
    authorization = manifest["authorization"]
    post_unused = authorization["post_total_max"] - len(ledger)
    return {
        "schema_version": 1,
        "authorization": authorization,
        "capture": {
            "post_attempts": 1,
            "post_unused": post_unused,
            "retries": 0,
            "redirects": 0,
            "concurrency": 1,
            "operation": "channels",
            "http_status": 400,
            "response_content_type": row["content_type"],
            "graphql_error_codes": codes,
            "graphql_error_messages": messages,
            "elapsed_seconds": elapsed,
            "closed_reason": manifest["closed_reason"],
        },
        "request": {
            "endpoint": row["endpoint"],
            "headers_public": manifest["request_headers_public"],
            "variables": request["variables"],
            "request_sha256": row["request_sha256"],
            "response_sha256": row["response_sha256"],
            "mutation": False,
        },
        "result": {
            "graphql_reached": True,
            "graphql_data": False,
            "club_binding_demonstrated": False,
            "price_comparable_skus": 0,
            "current_price_differences": None,
            "reported_regular_price_differences": None,
            "promotion_differences": None,
            "availability_only_differences": None,
            "pagination_demonstrated": False,
        },
        "decision": {
            "status": "STOPPED_UNAUTHORIZED_SCHEMA_OPERATION_REQUIRED",
            "next_operation_observed": "findChannels",
            "next_operation_was_authorized": False,
            "reason": "authorized_channels_field_absent_and_adapting_to_findChannels_requires_new_scope",
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
