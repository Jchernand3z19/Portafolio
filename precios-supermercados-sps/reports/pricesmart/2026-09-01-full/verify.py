#!/usr/bin/env python3
"""Reproduce the PriceSmart full-capture, snapshots and offline SQL evidence."""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import tarfile
import tempfile
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from actualizar_mvp_sqlite_la_colonia import validate_snapshot_bytes  # noqa: E402
from migrar_mvp_pricesmart import fingerprint, target_schema  # noqa: E402
from precios_supermercados.scrapers.pricesmart import reconcile_capture  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_archive(destination: Path):
    archive_path = REPORT / "raw-capture.tar.gz"
    archive_bytes = archive_path.read_bytes()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if any(not member.isfile() or Path(member.name).is_absolute() or ".." in Path(member.name).parts for member in members):
            raise ValueError("unsafe_archive_member")
        for member in members:
            output = destination / member.name
            output.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("archive_member_missing")
            output.write_bytes(source.read())
    manifest = json.loads((destination / "manifest.json").read_text())
    expected = {item["path"] for item in manifest["files"]} | {"manifest.json"}
    actual = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    if actual != expected:
        raise ValueError("archive_membership_mismatch")
    for item in manifest["files"]:
        raw = (destination / item["path"]).read_bytes()
        if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
            raise ValueError("archive_file_hash_mismatch:" + item["path"])
    return archive_bytes, manifest


def comparison(sps: dict, tgu: dict) -> dict:
    left = {row["source_key"]: row for row in sps["products"]}
    right = {row["source_key"]: row for row in tgu["products"]}
    shared = sorted(left.keys() & right.keys())
    comparable = [key for key in shared if left[key]["current_price"] is not None and right[key]["current_price"] is not None]
    price_differences = [key for key in comparable if left[key]["current_price"] != right[key]["current_price"]]
    regular_differences = [key for key in shared if left[key]["reported_regular_price"] != right[key]["reported_regular_price"]]
    promotion_differences = [key for key in shared if left[key]["is_promotion"] != right[key]["is_promotion"]]
    availability_differences = [key for key in shared if left[key]["availability"] != right[key]["availability"]]
    availability_only = [
        key for key in shared
        if left[key]["current_price"] == right[key]["current_price"]
        and left[key]["reported_regular_price"] == right[key]["reported_regular_price"]
        and left[key]["is_promotion"] == right[key]["is_promotion"]
        and left[key]["availability"] != right[key]["availability"]
    ]
    return {
        "shared_skus": len(shared),
        "price_comparable_skus": len(comparable),
        "price_differences": len(price_differences),
        "regular_price_differences": len(regular_differences),
        "promotion_differences": len(promotion_differences),
        "availability_differences": len(availability_differences),
        "availability_only_differences": len(availability_only),
        "sps_only_priced": sum(left[key]["current_price"] is not None and right[key]["current_price"] is None for key in shared),
        "tgu_only_priced": sum(left[key]["current_price"] is None and right[key]["current_price"] is not None for key in shared),
        "price_difference_examples": [
            {
                "sku": key,
                "sps": left[key]["current_price"],
                "tgu": right[key]["current_price"],
                "name": left[key]["source_name"],
            }
            for key in price_differences[:10]
        ],
    }


def reproduce() -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        extracted = Path(temporary)
        archive_bytes, manifest = load_archive(extracted)
        snapshots = reconcile_capture(extracted / "live")
    snapshot_evidence = []
    for snapshot, expected in zip(snapshots, manifest["snapshots"], strict=True):
        compressed = (REPORT / expected["file"]).read_bytes()
        raw = gzip.decompress(compressed)
        if (
            len(compressed) != expected["gzip_bytes"]
            or sha(compressed) != expected["gzip_sha256"]
            or len(raw) != expected["json_bytes"]
            or sha(raw) != expected["json_sha256"]
            or json.loads(raw) != snapshot
        ):
            raise ValueError("snapshot_artifact_mismatch")
        validate_snapshot_bytes(raw, supermarket_id="pricesmart")
        snapshot_evidence.append({
            **expected,
            "catalog_products": snapshot["catalog_products_reported"],
            "unique_products": snapshot["unique_products_extracted"],
            "skus": snapshot["skus_extracted"],
            "priced_skus": snapshot["skus_with_price"],
            "availability_counts": snapshot["availability_counts"],
            "promotion_counts": snapshot["promotion_counts"],
            "membership_sha256": snapshot["membership_sha256"],
            "sku_membership_sha256": snapshot["sku_membership_sha256"],
            "observed_at_utc": snapshot["observed_at_utc"],
        })
    sql_bytes = (REPORT / "offline-sql-summary.json").read_bytes()
    sql = json.loads(sql_bytes)
    if not (
        sql["offline_only"] is True
        and sql["turso_access"] is False
        and sql["table_count"] == 5
        and sql["integrity_check"] == "ok"
        and sql["foreign_key_violations"] == 0
        and sql["duplicate_open_periods"] == 0
        and sql["isolation"]["unchanged"] is True
        and sql["replay"]["unchanged"] is True
        and sql["migration"]["data_preserved"] is True
        and sql["migration"]["target_fingerprint"] == fingerprint(target_schema())
    ):
        raise ValueError("offline_sql_evidence_invalid")
    return {
        "schema_version": 1,
        "authorization": {
            "clubs": ["6603", "6602"],
            "excluded_club": "6604",
            "maximum_http_posts": 208,
            "concurrency": 1,
            "maximum_minutes": 30,
            "turso": False,
            "recurrence": False,
        },
        "capture": manifest["capture"],
        "tls_preflight": manifest["tls_preflight"],
        "raw_archive": {
            "bytes": len(archive_bytes),
            "sha256": sha(archive_bytes),
            "published_files": len(manifest["files"]) + 1,
            "redactions": manifest["redactions"],
        },
        "snapshots": snapshot_evidence,
        "sps_vs_tgu": comparison(*snapshots),
        "offline_persistence": {
            "artifact": "offline-sql-summary.json",
            "bytes": len(sql_bytes),
            "sha256": sha(sql_bytes),
            "schema_tables": sql["schema_tables"],
            "schema_fingerprint": sql["migration"]["target_fingerprint"],
            "pricesmart_current_by_location": sql["pricesmart_current_by_location"],
            "isolation_markets": sql["isolation"]["markets"],
            "isolation_unchanged": sql["isolation"]["unchanged"],
            "replay_unchanged": sql["replay"]["unchanged"],
            "migration_data_preserved": sql["migration"]["data_preserved"],
            "integrity_check": sql["integrity_check"],
            "foreign_key_violations": sql["foreign_key_violations"],
            "duplicate_open_periods": sql["duplicate_open_periods"],
            "turso_access": sql["turso_access"],
        },
        "decision": {
            "status": "READY_FOR_FIRST_TURSO_LOAD_AFTER_SEPARATE_AUTHORIZATION",
            "catalog_scope": "G10D03_ALIMENTOS",
            "catalog_scope_complete": True,
            "all_website_departments_claimed": False,
            "production_contexts": ["pricesmart_sps", "pricesmart_tgu"],
            "el_sauce_included": False,
            "parser_complete": True,
            "snapshots_validated": True,
            "offline_persistence_validated": True,
            "turso_executed": False,
            "recurrence_created": False,
        },
    }


if __name__ == "__main__":
    result = reproduce()
    expected = json.loads((REPORT / "evidence.json").read_text())
    if result != expected:
        raise SystemExit("evidence_mismatch")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
