#!/usr/bin/env python3
"""Reproduce offline el gate de endpoint del probe GraphQL PriceSmart."""

import hashlib
import json
import tarfile
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ARCHIVE = REPORT / "raw-capture.tar.gz"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


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
    response = payload[f"raw/{row['response_file']}"]
    if request["operationName"] != "channels" or "query channels" not in request["query"]:
        raise ValueError("unexpected_graphql_operation")
    if "mutation " in request["query"]:
        raise ValueError("mutation_in_read_only_probe")
    if set(request["variables"]) != {"where", "limit", "offset", "acceptLanguage"}:
        raise ValueError("unexpected_channels_variables")
    if row["endpoint"] != manifest["authorization"]["endpoint"]:
        raise ValueError("endpoint_mismatch")
    if row["status"] != 404 or b"Cannot POST /" not in response:
        raise ValueError("unexpected_endpoint_response")
    return {
        "schema_version": 1,
        "authorization": manifest["authorization"],
        "capture": {
            "post_attempts": 1,
            "retries": 0,
            "redirects": 0,
            "concurrency": 1,
            "operation": "channels",
            "http_status": 404,
            "response_content_type": row["content_type"],
            "response_body": "Cannot POST /",
            "elapsed_seconds": 0.2964,
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
            "graphql_reached": False,
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
            "status": "STOPPED_OTHER_ENDPOINT_PATH_REQUIRED",
            "next_path_inference": "/graphql",
            "next_path_verified": False,
            "reason": "authorized_root_path_returned_404_and_other_paths_were_not_authorized",
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
