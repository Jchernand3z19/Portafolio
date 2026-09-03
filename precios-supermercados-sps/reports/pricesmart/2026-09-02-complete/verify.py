#!/usr/bin/env python3
"""Reproduce the complete PriceSmart HN snapshots and offline delta evidence."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
OLD_REPORT = ROOT / "reports/pricesmart/2026-09-01-full"
DISCOVERY = ROOT / "reports/pricesmart/2026-09-02-discovery-probe/evidence.json"
ENDPOINT = "https://www.pricesmart.com/api/br_discovery/getProductsByKeyword"
CLUBS = ("6603", "6602")
LOCATIONS = {"6603": "pricesmart_sps", "6602": "pricesmart_tgu"}
CHANNELS = {
    "6603": "83a01076-4a4e-4163-9786-c59ef7c7c1a6",
    "6602": "93a6de43-d3c7-4887-a824-44c565dc3101",
}
REDACTED_KEY = "[REDACTED_PUBLIC_CLIENT_KEY]"

sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import actualizar_mvp_sqlite_la_colonia as local  # noqa: E402
import actualizar_mvp_turso_la_colonia as remote  # noqa: E402
from migrar_mvp_pricesmart import fingerprint, target_schema  # noqa: E402
from precios_supermercados.scrapers.pricesmart import parse_catalog_memberships  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def load_archive(destination: Path) -> tuple[bytes, dict]:
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
    expected = {row["path"] for row in manifest["files"]} | {"manifest.json"}
    actual = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    if actual != expected:
        raise ValueError("archive_membership_mismatch")
    for row in manifest["files"]:
        raw = (destination / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or sha(raw) != row["sha256"]:
            raise ValueError("archive_file_hash_mismatch:" + row["path"])
    return archive_bytes, manifest


def remaining_groups(extracted: Path) -> tuple[dict[str, list[dict]], dict]:
    evidence = json.loads(DISCOVERY.read_text())
    roots = {
        row["category_key"]: row for row in evidence["catalog"]["root_plan"]
        if row["category_key"] != "G10D03" and row["num_found"] > 0
    }
    ledger = json.loads((extracted / "live/ledger.json").read_text())
    result = json.loads((extracted / "live/result.json").read_text())
    attempts = ledger.get("attempts")
    if not (
        result.get("complete") is True
        and result.get("post_attempts") == 50
        and result.get("retries") == 0
        and result.get("new_documents") == 3306
        and result.get("elapsed_seconds", 601) <= 600
        and isinstance(attempts, list)
        and len(attempts) == 50
        and ledger.get("aborted_reason") is None
        and ledger.get("authorization", {}).get("prior_fail_closed_post_attempts") == 1
        and ledger.get("authorization", {}).get("partial_probe_windows_reused") is False
    ):
        raise ValueError("capture_result_invalid")

    documents: dict[str, dict[str, list[dict]]] = {club: defaultdict(list) for club in CLUBS}
    seen_windows: dict[str, dict[str, list[int]]] = {club: defaultdict(list) for club in CLUBS}
    for record in attempts:
        club, key, start = record.get("club"), record.get("category_key"), record.get("start")
        if not (
            club in CLUBS and key in roots and type(start) is int
            and record.get("rows") == 200 and record.get("http_status") == 200
            and record.get("valid") is True
        ):
            raise ValueError("page_ledger_invalid")
        request_path = extracted / "live" / record["request_file"]
        response_path = extracted / "live" / record["response_file"]
        request_raw, response_raw = request_path.read_bytes(), response_path.read_bytes()
        if sha(request_raw) != record["request_sha256"] or sha(response_raw) != record["response_sha256"]:
            raise ValueError("page_file_hash_invalid")
        request = json.loads(request_raw)
        response_wrapper = json.loads(response_raw)
        body = request.get("body_raw")
        if not (
            request.get("method") == "POST" and request.get("url") == ENDPOINT
            and request.get("cookie_header_present") is False
            and "Authorization" not in request.get("headers", {})
            and isinstance(body, str) and sha(body.encode()) == request.get("body_sha256")
            and request.get("original_body_sha256")
        ):
            raise ValueError("request_provenance_invalid")
        batch = json.loads(body)
        if not isinstance(batch, list) or len(batch) != 1:
            raise ValueError("request_batch_invalid")
        query = batch[0]
        fields = set(query.get("fl", "").split(","))
        required = {
            f"price_HN_{club}", f"availability_HN_{club}", f"inventory_HN_{club}",
            f"saving_amount_HN_{club}", f"original_price_without_saving_HN_{club}",
        }
        if not (
            query.get("auth_key") == REDACTED_KEY and query.get("q") == key
            and query.get("view_id") == "HN" and query.get("search_type") == "category"
            and query.get("fq") == [] and query.get("start") == start and query.get("rows") == 200
            and required.issubset(fields) and not any("_HN_6604" in field for field in fields)
        ):
            raise ValueError("request_binding_invalid")
        response_body = response_wrapper.get("body_raw")
        if not (
            response_wrapper.get("status") == 200 and isinstance(response_body, str)
            and sha(response_body.encode()) == response_wrapper.get("body_sha256")
            and response_wrapper.get("body_sha256") == record.get("response_body_sha256")
        ):
            raise ValueError("response_hash_invalid")
        payload = json.loads(response_body)
        source = payload["response"]
        expected_count = min(200, roots[key]["num_found"] - start)
        if not (
            source.get("start") == start and source.get("numFound") == roots[key]["num_found"]
            and len(source.get("docs", [])) == expected_count
            and len({str(doc["pid"]) for doc in source["docs"]}) == expected_count
            and isinstance(payload.get("facet_counts", {}).get("facet_fields", {}).get("category"), list)
        ):
            raise ValueError("response_page_invalid")
        documents[club][key].extend(source["docs"])
        seen_windows[club][key].append(start)

    groups: dict[str, list[dict]] = {}
    for club in CLUBS:
        groups[club] = []
        for key, root in roots.items():
            expected_offsets = list(range(0, root["num_found"], 200))
            if sorted(seen_windows[club][key]) != expected_offsets or len(documents[club][key]) != root["num_found"]:
                raise ValueError("root_incomplete:" + club + ":" + key)
            groups[club].append({
                "category_id": key,
                "category_name": root["name"],
                "documents": documents[club][key],
            })
    return groups, {"ledger": ledger, "result": result, "roots": roots}


def build_snapshots(groups: dict[str, list[dict]], capture: dict) -> tuple[list[dict], dict[str, dict]]:
    snapshots, parser_summaries = [], {}
    for club in CLUBS:
        location = LOCATIONS[club]
        old_raw = gzip.decompress((OLD_REPORT / f"{location}.json.gz").read_bytes())
        old = local.validate_snapshot_bytes(old_raw, supermarket_id="pricesmart")
        new_rows, new_details, parser_summary = parse_catalog_memberships(groups[club], club)
        old_pids = {row["product_id"] for row in old["products"]}
        old_skus = {row["source_key"] for row in old["products"]}
        if old_pids & {row["product_id"] for row in new_rows} or old_skus & {row["source_key"] for row in new_rows}:
            raise ValueError("alimentos_remaining_overlap")
        rows = sorted(old["products"] + new_rows, key=lambda row: row["source_key"])
        details = dict(old["source_details"])
        details.update(new_details)
        product_ids = {row["product_id"] for row in rows}
        availability = dict(Counter(row["availability"] for row in rows))
        promotions = {
            "true": sum(row["is_promotion"] is True for row in rows),
            "false": sum(row["is_promotion"] is False for row in rows),
            "unknown_unpriced": sum(row["is_promotion"] is None for row in rows),
        }
        root_counts = {"G10D03": 1124} | {
            group["category_id"]: len(group["documents"]) for group in groups[club]
        }
        snapshot = {
            "result": "success",
            "supermarket_id": "pricesmart",
            "location_id": location,
            "city": "San Pedro Sula" if club == "6603" else "Tegucigalpa",
            "club_id": club,
            "club_name": "San Pedro Sula" if club == "6603" else "Florencia",
            "channel_id": CHANNELS[club],
            "currency": "HNL",
            "scope": "public_ecommerce_club_bound_all_departments",
            "category_id": "ALL_ROOTS",
            "category_name": "Todos los departamentos",
            "catalog_complete": True,
            "validation_passed": True,
            "location_verified_same_run": True,
            "observation_started_at_utc": old["observation_started_at_utc"],
            "observed_at_utc": capture["result"]["finished_at_utc"].replace("+00:00", "Z"),
            "catalog_products_reported": len(product_ids),
            "unique_products_extracted": len(product_ids),
            "skus_extracted": len(rows),
            "skus_with_price": sum(row["current_price"] is not None for row in rows),
            "membership_count": len(product_ids),
            "membership_sha256": sha("\n".join(sorted(product_ids)).encode()),
            "sku_membership_sha256": sha("\n".join(row["source_key"] for row in rows).encode()),
            "availability_counts": availability,
            "promotion_counts": promotions,
            "root_membership_count": 1124 + parser_summary["root_memberships"],
            "root_sku_membership_count": 1127 + parser_summary["sku_memberships"],
            "root_counts": root_counts,
            "reused_alimentos": {
                "snapshot": f"../2026-09-01-full/{location}.json.gz",
                "json_sha256": sha(old_raw),
                "products": 1124,
                "skus": 1127,
            },
            "products": rows,
            "source_details": details,
        }
        local.validate_snapshot_bytes(canonical(snapshot), supermarket_id="pricesmart")
        snapshots.append(snapshot)
        parser_summaries[club] = parser_summary
    if snapshots[0]["membership_sha256"] != snapshots[1]["membership_sha256"]:
        raise ValueError("club_product_membership_mismatch")
    if snapshots[0]["sku_membership_sha256"] != snapshots[1]["sku_membership_sha256"]:
        raise ValueError("club_sku_membership_mismatch")
    return snapshots, parser_summaries


def compare(sps: dict, tgu: dict) -> dict:
    left = {row["source_key"]: row for row in sps["products"]}
    right = {row["source_key"]: row for row in tgu["products"]}
    shared = sorted(left.keys() & right.keys())
    comparable = [key for key in shared if left[key]["current_price"] is not None and right[key]["current_price"] is not None]
    price_all = [key for key in shared if left[key]["current_price"] != right[key]["current_price"]]
    price_comparable = [key for key in comparable if left[key]["current_price"] != right[key]["current_price"]]
    regular = [key for key in shared if left[key]["reported_regular_price"] != right[key]["reported_regular_price"]]
    promotion = [key for key in shared if left[key]["is_promotion"] != right[key]["is_promotion"]]
    availability = [key for key in shared if left[key]["availability"] != right[key]["availability"]]
    availability_only = [
        key for key in availability
        if all(left[key][field] == right[key][field] for field in (
            "current_price", "reported_regular_price", "is_promotion"
        ))
    ]
    return {
        "shared_skus": len(shared),
        "sps_only_skus": len(left.keys() - right.keys()),
        "tgu_only_skus": len(right.keys() - left.keys()),
        "price_comparable_skus": len(comparable),
        "current_price_field_differences": len(price_all),
        "both_priced_price_differences": len(price_comparable),
        "reported_regular_price_differences": len(regular),
        "is_promotion_differences": len(promotion),
        "availability_differences": len(availability),
        "availability_only_differences": len(availability_only),
        "sps_only_priced": sum(left[key]["current_price"] is not None and right[key]["current_price"] is None for key in shared),
        "tgu_only_priced": sum(left[key]["current_price"] is None and right[key]["current_price"] is not None for key in shared),
        "price_difference_examples": [
            {"sku": key, "sps": left[key]["current_price"], "tgu": right[key]["current_price"], "name": left[key]["source_name"]}
            for key in price_comparable[:10]
        ],
    }


def _install_offline_pipeline(path: Path):
    original = remote._pipeline

    def pipeline(url, token, requests):
        if url != "libsql://offline.example" or token != "offline":
            raise ValueError("offline_transport_scope_invalid")
        con = sqlite3.connect(path, isolation_level=None)
        con.execute("PRAGMA foreign_keys=ON")
        results = []

        def execute(statement):
            cursor = con.execute(statement["sql"], [remote._scalar(arg) for arg in statement["args"]])
            return {"rows": [list(row) for row in cursor.fetchall()], "affected_row_count": max(cursor.rowcount, 0)}

        try:
            for request in requests:
                if request["type"] == "close":
                    results.append({"type": "ok", "response": {"type": "close"}})
                elif request["type"] == "execute":
                    results.append({"type": "ok", "response": {"type": "execute", "result": execute(request["stmt"])}})
                else:
                    values, errors = [], []

                    def allowed(condition):
                        if not condition:
                            return True
                        if condition["type"] == "ok":
                            return values[condition["step"]] is not None
                        if condition["type"] == "error":
                            return errors[condition["step"]] is not None
                        return any(allowed(item) for item in condition["conds"])

                    for step in request["batch"]["steps"]:
                        value = error = None
                        if allowed(step.get("condition")):
                            try:
                                value = execute(step["stmt"])
                            except sqlite3.Error as exc:
                                error = {"message": str(exc)}
                        values.append(value)
                        errors.append(error)
                    results.append({"type": "ok", "response": {"type": "batch", "result": {"step_results": values, "step_errors": errors}}})
            return {"results": results}
        finally:
            con.close()

    remote._pipeline = pipeline
    return original


def _market_hash(path: Path, market: str) -> str:
    with sqlite3.connect(path) as con:
        rows = {
            table: con.execute(f"SELECT * FROM {table} WHERE supermarket_id=? ORDER BY 1", (market,)).fetchall()
            for table in remote.EXPECTED_TABLES
        }
    return sha(canonical(rows))


def offline_summary(snapshots: list[dict]) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary) / "offline.sqlite"
        local.initialize_database(database)
        with sqlite3.connect(database) as con:
            con.executemany("INSERT INTO supermarkets VALUES(?,?,?)", [
                ("colonial", "Colonial", "HN"), ("walmart", "Walmart Honduras", "HN")
            ])
            con.executemany("INSERT INTO locations VALUES(?,?,?,?)", [
                ("colonial_sps", "colonial", "San Pedro Sula", "HN"),
                ("walmart_sps", "walmart", "San Pedro Sula", "HN"),
            ])
            for market, location in (
                ("la_colonia", "la_colonia_sps"),
                ("colonial", "colonial_sps"),
                ("walmart", "walmart_sps"),
            ):
                cursor = con.execute(
                    """INSERT INTO products (
                        supermarket_id,source_key_type,source_key,source_catalog_product_id,
                        source_item_id,reference,ean,name,brand,presentation,category
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (market, "item_id", "sentinel", "sentinel", "sentinel", None, None,
                     "Isolation sentinel", None, None, "Test"),
                )
                run_id = "isolation-" + market
                con.execute(
                    "INSERT INTO scrape_runs VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                    (run_id, market, location, "2026-09-01T00:00:00Z", "success", 1, 1, None, "sentinel"),
                )
                con.execute(
                    "INSERT INTO price_history VALUES(?,?,?,?,?,?,?,?,?,NULL,?)",
                    (cursor.lastrowid, market, location, 10000, None, 0, "in_stock", "HNL",
                     "2026-09-01T00:00:00Z", run_id),
                )
            con.commit()
        before = {market: _market_hash(database, market) for market in ("la_colonia", "colonial", "walmart")}
        original = _install_offline_pipeline(database)
        try:
            old_raw = [gzip.decompress((OLD_REPORT / f"{LOCATIONS[club]}.json.gz").read_bytes()) for club in CLUBS]
            baseline = [
                remote.persist_snapshot(raw, database_url="libsql://offline.example", auth_token="offline", run_id=f"baseline-{club}", supermarket_id="pricesmart")
                for raw, club in zip(old_raw, CLUBS, strict=True)
            ]
            loads = [
                remote.persist_snapshot(canonical(snapshot), database_url="libsql://offline.example", auth_token="offline", run_id=f"complete-{club}", supermarket_id="pricesmart")
                for snapshot, club in zip(snapshots, CLUBS, strict=True)
            ]
            state_before_replay = _market_hash(database, "pricesmart")
            replays = [
                remote.persist_snapshot(canonical(snapshot), database_url="libsql://offline.example", auth_token="offline", run_id=f"complete-{club}", supermarket_id="pricesmart")
                for snapshot, club in zip(snapshots, CLUBS, strict=True)
            ]
            state_after_replay = _market_hash(database, "pricesmart")
        finally:
            remote._pipeline = original
        after = {market: _market_hash(database, market) for market in before}
        with sqlite3.connect(database) as con:
            counts = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in remote.EXPECTED_TABLES}
            current_summary = [
                {
                    "location_id": location,
                    "offers": con.execute("SELECT COUNT(*) FROM price_history WHERE supermarket_id='pricesmart' AND location_id=? AND valid_to_utc IS NULL", (location,)).fetchone()[0],
                    "priced": con.execute("SELECT COUNT(*) FROM price_history WHERE supermarket_id='pricesmart' AND location_id=? AND valid_to_utc IS NULL AND current_price_minor IS NOT NULL", (location,)).fetchone()[0],
                    "promotions": con.execute("SELECT COUNT(*) FROM price_history WHERE supermarket_id='pricesmart' AND location_id=? AND valid_to_utc IS NULL AND is_promotion=1", (location,)).fetchone()[0],
                    "unpriced": con.execute("SELECT COUNT(*) FROM price_history WHERE supermarket_id='pricesmart' AND location_id=? AND valid_to_utc IS NULL AND current_price_minor IS NULL", (location,)).fetchone()[0],
                }
                for location in LOCATIONS.values()
            ]
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            foreign = len(con.execute("PRAGMA foreign_key_check").fetchall())
            duplicates = con.execute("SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)").fetchone()[0]
    old_snapshots = [
        json.loads(gzip.decompress((OLD_REPORT / f"{LOCATIONS[club]}.json.gz").read_bytes()))
        for club in CLUBS
    ]
    computed_delta = []
    for old, new in zip(old_snapshots, snapshots, strict=True):
        prior = {row["source_key"]: row for row in old["products"]}
        current_rows = {row["source_key"]: row for row in new["products"]}
        shared = prior.keys() & current_rows.keys()
        commercial = ("current_price", "reported_regular_price", "is_promotion", "availability")
        metadata = tuple(key for key in local.PRODUCT_KEYS if key not in commercial)
        new_rows = [current_rows[key] for key in current_rows.keys() - prior.keys()]
        new_products = {row["product_id"] for row in new_rows}
        computed_delta.append({
            "existing_unchanged": sum(all(prior[key][field] == current_rows[key][field] for field in commercial + metadata) for key in shared),
            "existing_commercial_change": sum(any(prior[key][field] != current_rows[key][field] for field in commercial) for key in shared),
            "metadata_only": sum(
                all(prior[key][field] == current_rows[key][field] for field in commercial)
                and any(prior[key][field] != current_rows[key][field] for field in metadata)
                for key in shared
            ),
            "new_source_products": len(new_products),
            "new_variants_beyond_first": len(new_rows) - len(new_products),
            "new_sku_offers": len(new_rows),
            "absent_from_new_snapshot": len(prior.keys() - current_rows.keys()),
        })
    if computed_delta[0] != computed_delta[1]:
        raise ValueError("club_delta_mismatch")
    return {
        "offline_only": True,
        "turso_access": False,
        "schema_tables": sorted(remote.EXPECTED_TABLES),
        "table_count": len(remote.EXPECTED_TABLES),
        "schema_fingerprint": fingerprint(target_schema()),
        "baseline_loads": baseline,
        "complete_loads": loads,
        "replays": replays,
        "replay_unchanged": state_before_replay == state_after_replay,
        "isolation": {"before": before, "after": after, "unchanged": before == after},
        "counts": counts,
        "pricesmart_current_by_location": current_summary,
        "integrity_check": integrity,
        "foreign_key_violations": foreign,
        "duplicate_open_periods": duplicates,
        "delta_per_location": computed_delta[0],
        "absence_policy": "absence_does_not_imply_out_of_stock",
    }


def reproduce() -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        archive_bytes, manifest = load_archive(Path(temporary))
        groups, capture = remaining_groups(Path(temporary))
        snapshots, parser_summaries = build_snapshots(groups, capture)
    snapshot_evidence = []
    for snapshot in snapshots:
        filename = f"{snapshot['location_id']}.json.gz"
        compressed = (REPORT / filename).read_bytes()
        raw = gzip.decompress(compressed)
        if raw != canonical(snapshot):
            raise ValueError("snapshot_artifact_mismatch:" + filename)
        local.validate_snapshot_bytes(raw, supermarket_id="pricesmart")
        snapshot_evidence.append({
            "file": filename,
            "gzip_bytes": len(compressed),
            "gzip_sha256": sha(compressed),
            "json_bytes": len(raw),
            "json_sha256": sha(raw),
            "unique_products": snapshot["unique_products_extracted"],
            "skus": snapshot["skus_extracted"],
            "priced_skus": snapshot["skus_with_price"],
            "availability_counts": snapshot["availability_counts"],
            "promotion_counts": snapshot["promotion_counts"],
        })
    sql_raw = (REPORT / "offline-sql-summary.json").read_bytes()
    sql = offline_summary(snapshots)
    if json.loads(sql_raw) != sql:
        raise ValueError("offline_sql_artifact_mismatch")
    return {
        "schema_version": 1,
        "authorization": {
            "endpoint": ENDPOINT,
            "clubs": list(CLUBS),
            "excluded_club": "6604",
            "base_posts": 50,
            "retries": 0,
            "concurrency": 1,
            "alimentos_recrawled": False,
            "turso": False,
        },
        "capture": {
            "complete": True,
            "post_attempts_this_run": capture["result"]["post_attempts"],
            "prior_fail_closed_posts": 1,
            "global_post_attempts": capture["result"]["post_attempts"] + 1,
            "retries": capture["result"]["retries"],
            "successful_pages": 50,
            "returned_documents": capture["result"]["new_documents"],
            "elapsed_seconds": capture["result"]["elapsed_seconds"],
            "started_at_utc": capture["result"]["started_at_utc"],
            "finished_at_utc": capture["result"]["finished_at_utc"],
            "roots_completed_per_club": len(capture["roots"]),
        },
        "raw_archive": {
            "bytes": len(archive_bytes),
            "sha256": sha(archive_bytes),
            "published_files": len(manifest["files"]) + 1,
            "redactions": manifest["redactions"],
        },
        "completeness": {
            "taxonomy_roots": 26,
            "nonempty_roots": 24,
            "empty_roots": 2,
            "reused_alimentos_products_per_club": 1124,
            "remaining_root_memberships_per_club": 1653,
            "all_root_memberships_per_club": 2777,
            "unique_products_per_club": 2766,
            "all_root_sku_memberships_per_club": 6115,
            "unique_skus_per_club": 6078,
            "cross_root_products_per_club": parser_summaries["6603"]["cross_root_products"],
            "duplicate_product_memberships_per_club": parser_summaries["6603"]["duplicate_product_memberships"],
            "duplicate_sku_memberships_per_club": parser_summaries["6603"]["duplicate_sku_memberships"],
            "pagination_holes": 0,
            "unexpected_page_repeats": 0,
        },
        "snapshots": snapshot_evidence,
        "sps_vs_florencia": compare(*snapshots),
        "offline_persistence": {
            "artifact": "offline-sql-summary.json",
            "bytes": len(sql_raw),
            "sha256": sha(sql_raw),
            "five_tables": sql["table_count"] == 5,
            "replay_unchanged": sql["replay_unchanged"],
            "isolation_unchanged": sql["isolation"]["unchanged"],
            "integrity_check": sql["integrity_check"],
            "foreign_key_violations": sql["foreign_key_violations"],
            "duplicate_open_periods": sql["duplicate_open_periods"],
            "delta_per_location": sql["delta_per_location"],
            "turso_access": sql["turso_access"],
        },
        "decision": {
            "status": "READY_FOR_COMPLETE_TURSO_DELTA_AFTER_SEPARATE_AUTHORIZATION",
            "catalog_scope": "ALL_PUBLIC_DEPARTMENTS",
            "catalog_complete": True,
            "production_contexts": ["pricesmart_sps", "pricesmart_tgu"],
            "reason": "115 reproducible current-price differences among jointly priced SKUs",
            "el_sauce_included": False,
            "turso_executed": False,
        },
    }


if __name__ == "__main__":
    result = reproduce()
    if result != json.loads((REPORT / "evidence.json").read_text()):
        raise SystemExit("evidence_mismatch")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
