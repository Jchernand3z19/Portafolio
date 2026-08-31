"""Reproduce this full-catalog TGU comparison offline; no downloader or SQL."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import runpy
import sys
import tarfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
from actualizar_mvp_sqlite_la_colonia import validate_snapshot_bytes
from precios_supermercados.scrapers.walmart import parse_products

LOCATIONS = ("walmart_tgu_ffaa", "walmart_tgu_el_sauce")
COMMERCIAL = ("current_price", "reported_regular_price", "is_promotion")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def classify(a, b):
    """NULL is missing price evidence, never an equal or different known price."""
    comparable = all(r[f] is not None for r in (a, b) for f in COMMERCIAL)
    differences = [f for f in COMMERCIAL if
        (a[f] != b[f] if f == "is_promotion" else Decimal(a[f]) != Decimal(b[f]))] if comparable else []
    availability_differs = a["availability"] != b["availability"]
    if comparable:
        category = "commercial_difference" if differences else "availability_only" if availability_differs else "equal_observed_state"
    else:
        category = "both_prices_missing" if a["current_price"] is None and b["current_price"] is None else "one_price_missing"
    return {"commercial_comparable": comparable, "commercial_differences": differences,
            "availability_differs": availability_differs, "classification": category}


def verified_inputs(report):
    evidence = json.loads((report / "evidence.json").read_text())
    snapshots, indexes, input_hashes = {}, {}, {}
    for location in LOCATIONS:
        name = location + ".json.gz"
        compressed = (report / name).read_bytes()
        require(hashlib.sha256(compressed).hexdigest() == evidence["artifacts"][name]["sha256"], "snapshot_archive_hash_mismatch")
        raw = gzip.decompress(compressed)
        expected = next(s for s in evidence["snapshots"] if s["location_id"] == location)
        require(hashlib.sha256(raw).hexdigest() == expected["json_sha256"], "snapshot_hash_mismatch")
        snap = validate_snapshot_bytes(raw, supermarket_id="walmart")
        require(snap["location_id"] == location, "location_mismatch")
        snapshots[location] = snap
        indexes[location] = {r["source_key"]: r for r in snap["products"]}
        input_hashes[name] = {"compressed_sha256": evidence["artifacts"][name]["sha256"], "json_sha256": expected["json_sha256"]}
    archive_path = report / "raw-capture.tar.gz"
    archive_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    require(archive_sha == evidence["artifacts"][archive_path.name]["sha256"], "raw_archive_hash_mismatch")
    source = {loc: {} for loc in LOCATIONS}
    with tarfile.open(archive_path) as archive:
        ledger = json.load(archive.extractfile("requests.json"))
        records = {(r["url"], r["sha256"]): r for r in ledger["records"] if r.get("status") == 200}
        for location, snap in snapshots.items():
            for page in snap["page_evidence"]:
                record = records[(page["url"], page["sha256"])]
                url = urlsplit(record["url"]); query = parse_qs(url.query)
                require(url.scheme == "https" and url.netloc == "www.walmart.com.hn"
                        and "/accesscontrollist/" + snap["seller_id"] + "/" in url.path
                        and query.get("regionId") == [snap["region_id"]]
                        and query.get("sc") == ["1"] and query.get("country") == ["HND"], "raw_context_mismatch")
                raw = archive.extractfile(record["file"]).read()
                require(hashlib.sha256(raw).hexdigest() == page["sha256"], "raw_page_hash_mismatch")
                require(record["observed_at"] == page["observed_at"], "raw_time_mismatch")
                rows, details = parse_products(json.loads(raw)["products"])
                for row in rows:
                    sku = row["source_key"]
                    require(sku not in source[location] and row == indexes[location].get(sku), "raw_snapshot_disagreement")
                    require(details[sku] == snap["source_details"][sku], "raw_source_details_disagreement")
                    source[location][sku] = {"url": record["url"], "sha256": record["sha256"],
                        "raw_file": record["file"], "observed_at": record["observed_at"]}
            require(source[location].keys() == indexes[location].keys(), "raw_membership_mismatch")
    return snapshots, indexes, source, input_hashes, archive_sha


def reproduce(report=REPORT):
    report = Path(report)
    snapshots, indexes, source, input_hashes, archive_sha = verified_inputs(report)
    a, b = (indexes[loc] for loc in LOCATIONS)
    shared = sorted(a.keys() & b.keys())
    # Source keys must also agree on available identifying metadata, not just names.
    for sku in shared:
        for field in ("product_id", "item_id", "ean", "reference"):
            require(not (a[sku][field] and b[sku][field]) or a[sku][field] == b[sku][field], "shared_identity_conflict")
        for field in ("measurement_unit", "unit_multiplier"):
            require(snapshots[LOCATIONS[0]]["source_details"][sku].get(field)
                    == snapshots[LOCATIONS[1]]["source_details"][sku].get(field), "shared_unit_conflict")
    classifications = {sku: classify(a[sku], b[sku]) for sku in shared}
    comparable = [sku for sku, c in classifications.items() if c["commercial_comparable"]]
    different = [sku for sku, c in classifications.items() if c["commercial_differences"]]
    proof = report.parent / "2026-08-31-probe"
    control = runpy.run_path(str(proof / "verify.py"))["reproduce"](proof / "raw-capture.tar.gz")
    require(control == json.loads((proof / "evidence.json").read_text()), "probe_control_changed")
    # Existing region-only control is a causal anchor, not 255 independent controls.
    require("68100" in different and a["68100"]["current_price"] == b["68100"]["current_price"] == "1895.00"
            and a["68100"]["reported_regular_price"] == "2195.00"
            and b["68100"]["reported_regular_price"] == "1895.00", "full_does_not_reproduce_regional_control")
    stream = io.StringIO(newline="")
    columns = ["sku", "product_id", "name", "classification", "commercial_comparable",
               "current_price_differs", "reported_regular_price_differs", "is_promotion_differs", "availability_differs"]
    columns += [f"{short}_{f}" for short in ("ffaa", "el_sauce") for f in (*COMMERCIAL, "availability", "page_sha256", "observed_at")]
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for sku, c in classifications.items():
        row = {"sku": sku, "product_id": a[sku]["product_id"], "name": a[sku]["source_name"],
               **{k: c[k] for k in ("classification", "commercial_comparable", "availability_differs")},
               **{f+"_differs": f in c["commercial_differences"] if c["commercial_comparable"] else None for f in COMMERCIAL}}
        for short, location in zip(("ffaa", "el_sauce"), LOCATIONS):
            row.update({short+"_"+f: indexes[location][sku][f] for f in (*COMMERCIAL, "availability")})
            row[short+"_page_sha256"] = source[location][sku]["sha256"]
            row[short+"_observed_at"] = source[location][sku]["observed_at"]
        writer.writerow(row)
    csv_raw = stream.getvalue().encode()
    summary = {
        "mode": "OFFLINE_FULL_SNAPSHOTS_AND_EXISTING_RAW_NO_NEW_LIVE_NO_TURSO",
        "inputs": input_hashes, "raw_archive_sha256": archive_sha,
        "identity_and_unit_conflicts": 0,
        "contexts": {loc: {k: snap[k] for k in ("location_id", "seller_id", "region_id", "scope", "observation_started_at_utc", "observed_at_utc", "skus_extracted")} for loc, snap in snapshots.items()},
        "counts": {"shared_skus": len(shared), "only_ffaa": len(a.keys()-b.keys()), "only_el_sauce": len(b.keys()-a.keys()),
            "commercially_comparable": len(comparable), "commercially_equal": len(comparable)-len(different),
            "commercially_different": len(different),
            **{f+"_differences": sum(f in c["commercial_differences"] for c in classifications.values()) for f in COMMERCIAL},
            "availability_differences_all_shared": sum(c["availability_differs"] for c in classifications.values()),
            "availability_only_with_commercial_equality": sum(c["classification"] == "availability_only" for c in classifications.values()),
            "one_price_missing": sum(c["classification"] == "one_price_missing" for c in classifications.values()),
            "both_prices_missing": sum(c["classification"] == "both_prices_missing" for c in classifications.values()),
            "commercial_differences_in_stock_both": sum(a[k]["availability"] == b[k]["availability"] == "in_stock" for k in different),
            "raw_skus_verified": sum(len(v) for v in source.values()), "raw_pages_verified": sum(len(s["page_evidence"]) for s in snapshots.values())},
        "difference_patterns": dict(sorted(Counter(" + ".join(c["commercial_differences"]) for c in classifications.values() if c["commercial_differences"]).items())),
        "availability_pairs": dict(sorted(Counter(a[k]["availability"]+" -> "+b[k]["availability"] for k in shared).items())),
        "not_comparable": {"ffaa_missing_only": [k for k in shared if a[k]["current_price"] is None and b[k]["current_price"] is not None],
                           "el_sauce_missing_only": [k for k in shared if b[k]["current_price"] is None and a[k]["current_price"] is not None],
                           "both_missing": [k for k in shared if a[k]["current_price"] is None and b[k]["current_price"] is None]},
        "not_shared": {"only_ffaa": sorted(a.keys()-b.keys()), "only_el_sauce": sorted(b.keys()-a.keys())},
        "commercial_differences": [{"sku": k, "product_id": a[k]["product_id"], "name": a[k]["source_name"], "ean": a[k]["ean"],
            "different_fields": classifications[k]["commercial_differences"],
            **{loc: {"values": {f: indexes[loc][k][f] for f in (*COMMERCIAL, "availability")}, "source": source[loc][k]} for loc in LOCATIONS}} for k in different],
        "causal_anchor": {"sku": "68100", "probe_archive_sha256": control["raw_archive_sha256"],
            "probe_requests": [7,8,9,10,12], "changed_variable_in_requests_9_and_12": "regionId", "reproduced_in_full": True},
        "decision": "keep_two_commercial_contexts_for_production_persistence",
        "production_locations": list(LOCATIONS), "availability_used_to_justify_separation": False,
        "limitations": ["Snapshots are close in time but not simultaneous; no per-SKU region-only experiment for all differences.",
                        "The existing causal control and its repetition in full demonstrate at least one context-specific commercial difference.",
                        "NULL prices and absent SKUs do not prove price equality or inequality; stock alone does not determine granularity.",
                        "Replaying RAW is not a second real observation, new live verification or productive Turso persistence."],
        "row_audit": {"file": "tgu-comparison.csv.gz", "rows": len(shared), "uncompressed_sha256": hashlib.sha256(csv_raw).hexdigest()},
    }
    return summary, csv_raw


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result, csv_raw = reproduce()
    if args.check:
        require(result == json.loads((REPORT / "tgu-comparison.json").read_text()), "comparison_changed")
        require(csv_raw == gzip.decompress((REPORT / "tgu-comparison.csv.gz").read_bytes()), "comparison_csv_changed")
    else:
        (REPORT / "tgu-comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        (REPORT / "tgu-comparison.csv.gz").write_bytes(gzip.compress(csv_raw, mtime=0))
    print(json.dumps({"counts": result["counts"], "decision": result["decision"]}, ensure_ascii=False))
