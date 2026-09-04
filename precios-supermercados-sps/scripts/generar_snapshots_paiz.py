#!/usr/bin/env python3
"""Genera snapshots normalizados de Paiz exclusivamente desde RAW aceptado."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.scrapers.paiz import reconcile_capture  # noqa: E402


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", nargs="?", default="reports/paiz/2026-09-04-full")
    args = parser.parse_args()
    capture = Path(args.capture)
    snapshots = reconcile_capture(capture)
    if len(snapshots) != 2:
        raise SystemExit("paiz_snapshot_count_invalid")
    by_location = {s["location_id"]: s for s in snapshots}
    if set(by_location) != {"paiz_tgu_multiplaza", "paiz_tgu_proceres"}:
        raise SystemExit("paiz_location_set_invalid")

    files = {
        "paiz_tgu_multiplaza": capture / "snapshot-paiz-multiplaza.json",
        "paiz_tgu_proceres": capture / "snapshot-paiz-proceres.json",
    }
    for location, path in files.items():
        dump(path, by_location[location])

    left = {r["source_key"]: r for r in by_location["paiz_tgu_multiplaza"]["products"]}
    right = {r["source_key"]: r for r in by_location["paiz_tgu_proceres"]["products"]}
    shared = set(left) & set(right)
    comparable = [sku for sku in shared if left[sku]["current_price"] is not None and right[sku]["current_price"] is not None]
    price_differences = [sku for sku in comparable if left[sku]["current_price"] != right[sku]["current_price"]]
    commercial_differences = [sku for sku in shared if any(
        left[sku][field] != right[sku][field]
        for field in ("current_price", "reported_regular_price", "is_promotion")
    )]
    context = {
        "result": "success",
        "decision": "keep_tgu_contexts_separate",
        "reason": "catalog_membership_differs; commercial offer differences are measured independently",
        "multiplaza_skus": len(left),
        "proceres_skus": len(right),
        "shared_skus": len(shared),
        "multiplaza_only_skus": len(set(left) - set(right)),
        "proceres_only_skus": len(set(right) - set(left)),
        "shared_priced_skus": len(comparable),
        "shared_current_price_differences": len(price_differences),
        "shared_commercial_differences": len(commercial_differences),
    }
    dump(capture / "context-comparison.json", context)

    controls = []
    for location, snapshot in by_location.items():
        candidates = [r for r in snapshot["products"] if r["current_price"] is not None and r["presentation"]]
        if not candidates:
            candidates = [r for r in snapshot["products"] if r["current_price"] is not None]
        row = next((r for r in candidates if r["is_promotion"] is True), candidates[0])
        controls.append({
            "location_id": location,
            "seller_id": snapshot["seller_id"],
            "product_id": row["product_id"],
            "sku": row["item_id"],
            "name": row["source_name"],
            "brand": row["brand"],
            "presentation": row["presentation"],
            "current_price": row["current_price"],
            "reported_regular_price": row["reported_regular_price"],
            "is_promotion": row["is_promotion"],
            "availability": row["availability"],
            "category": row["category"],
            "context": {"city": snapshot["city"], "store_name": snapshot["store_name"], "region_id": snapshot["region_id"], "sales_channel": snapshot["sales_channel"]},
        })
    dump(capture / "control-products.json", {"result": "success", "products": controls})

    artifact = {
        "result": "success",
        "snapshots": {
            location: {
                "file": str(files[location].name),
                "sha256": hashlib.sha256(files[location].read_bytes()).hexdigest(),
                "catalog_products": by_location[location]["catalog_products_reported"],
                "skus": by_location[location]["skus_extracted"],
                "skus_with_price": by_location[location]["skus_with_price"],
                "availability_counts": by_location[location]["availability_counts"],
                "promotion_counts": by_location[location]["promotion_counts"],
            }
            for location in sorted(files)
        },
        "context_comparison": context,
    }
    dump(capture / "normalized-evidence.json", artifact)
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
