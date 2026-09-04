#!/usr/bin/env python3
"""Captura read-only completa de los dos contextos TGU probados de Paiz."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from precios_supermercados.scrapers.paiz import parse_products

BASE = "https://www.paiz.com.hn"
COUNTRY = "HND"
SALES_CHANNEL = "2"
PAGE_SIZE = 100
DEFAULT_DELAY = 1.0
MAX_REQUESTS_HARD = 500
UA = "Mozilla/5.0 (compatible; PreciosSupermercadosSPS-Paiz/1.0; read-only)"
SCOPE = "public_ecommerce_selected_store_not_universal_city_price"
STORES = {
    "walmarthnsp633": ("paiz_tgu_multiplaza", "Tegucigalpa", "Paiz Multiplaza"),
    "walmarthnsp4010": ("paiz_tgu_proceres", "Tegucigalpa", "Paiz Próceres"),
}


def region_id(seller: str) -> str:
    return base64.b64encode(("SW#" + seller).encode()).decode()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def category_counts(doc: dict) -> dict[str, int]:
    facets = doc.get("facets")
    if not isinstance(facets, list):
        raise RuntimeError("facets_missing")
    roots = [facet for facet in facets if isinstance(facet, dict) and facet.get("key") == "category-1"]
    if len(roots) != 1 or not isinstance(roots[0].get("values"), list):
        raise RuntimeError("category_1_missing_or_ambiguous")
    result: dict[str, int] = {}
    for value in roots[0]["values"]:
        if not isinstance(value, dict):
            raise RuntimeError("category_1_value_invalid")
        key, quantity = value.get("value"), value.get("quantity")
        if not isinstance(key, str) or not key or type(quantity) is not int or quantity <= 0 or key in result:
            raise RuntimeError("category_1_value_invalid")
        result[key] = quantity
    if not result:
        raise RuntimeError("category_1_empty")
    return result


class Capture:
    def __init__(self, raw_dir: Path, delay: float, max_requests: int) -> None:
        self.raw_dir = raw_dir
        self.delay = delay
        self.max_requests = max_requests
        self.records: list[dict] = []
        self.started = time.monotonic()

    def get(self, seller: str, tag: str, path: str, query: dict[str, str]) -> tuple[dict, dict]:
        if len(self.records) >= self.max_requests:
            raise RuntimeError("request_budget_exceeded")
        url = BASE + path + "?" + urlencode(query)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.paiz.com.hn":
            raise RuntimeError("origin_not_allowed")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Accept": "application/json"},
            method="GET",
        )
        start = time.monotonic()
        status = None
        response_url = None
        body = b""
        error = None
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                status = response.status
                response_url = response.geturl()
                body = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            response_url = exc.geturl()
            body = exc.read()
            error = f"http_{exc.code}"
        except Exception as exc:  # noqa: BLE001 - evidence must preserve transport failure
            error = f"{type(exc).__name__}:{exc}"
        final = urlsplit(response_url or url)
        if final.scheme != "https" or final.netloc != "www.paiz.com.hn":
            error = error or "redirect_origin_not_allowed"
        digest = hashlib.sha256(body).hexdigest() if body else None
        raw_path = None
        if body:
            seller_dir = self.raw_dir / seller
            seller_dir.mkdir(parents=True, exist_ok=True)
            filename = tag.replace("/", "__") + ".json"
            target = seller_dir / filename
            target.write_bytes(body)
            raw_path = str(target)
        record = {
            "index": len(self.records) + 1,
            "tag": tag,
            "method": "GET",
            "url": url,
            "response_url": response_url,
            "status": status,
            "observed_at": utc_now(),
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "content_length_observed": len(body),
            "sha256": digest,
            "file": raw_path,
            "error": error,
        }
        self.records.append(record)
        if self.delay:
            time.sleep(self.delay)
        if status != 200 or error:
            raise RuntimeError(f"request_failed:{tag}:{status}:{error}")
        try:
            doc = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"response_not_json:{tag}") from exc
        if not isinstance(doc, dict):
            raise RuntimeError(f"response_shape_invalid:{tag}")
        return doc, record


def _common(seller: str) -> dict[str, str]:
    return {"regionId": region_id(seller), "sc": SALES_CHANNEL, "country": COUNTRY}


def capture_store(capture: Capture, seller: str, location_id: str, city: str, store_name: str) -> dict:
    common = _common(seller)
    facets_path = f"/api/io/_v/api/intelligent-search/facets/accesscontrollist/{seller}"
    root_path = f"/api/io/_v/api/intelligent-search/product_search/accesscontrollist/{seller}"
    before, before_record = capture.get(seller, f"{seller}/facets-before", facets_path, common)
    counts = category_counts(before)
    root_total = sum(counts.values())
    root_before, root_before_record = capture.get(
        seller, f"{seller}/root-before", root_path, {**common, "count": "1", "page": "1"}
    )
    if root_before.get("recordsFiltered") != root_total or len(root_before.get("products", [])) != 1:
        raise RuntimeError(f"root_total_disagrees_with_facets:{seller}")

    product_ids: set[str] = set()
    sku_ids: set[str] = set()
    rows: list[dict] = []
    source_details: dict[str, dict] = {}
    page_evidence: list[dict] = []
    for category, expected_total in counts.items():
        path = f"{root_path}/category-1/{category}"
        pages = math.ceil(expected_total / PAGE_SIZE)
        partition_ids: set[str] = set()
        for page in range(1, pages + 1):
            expected_count = min(PAGE_SIZE, expected_total - (page - 1) * PAGE_SIZE)
            tag = f"{seller}/category-1/{category}/page-{page:03d}"
            doc, record = capture.get(
                seller, tag, path, {**common, "count": str(PAGE_SIZE), "page": str(page)}
            )
            products = doc.get("products")
            if doc.get("recordsFiltered") != expected_total or not isinstance(products, list) or len(products) != expected_count:
                raise RuntimeError(f"page_count_changed:{tag}")
            ids = [product.get("productId") for product in products if isinstance(product, dict)]
            if len(ids) != len(products) or any(not isinstance(pid, str) or not pid for pid in ids):
                raise RuntimeError(f"product_id_invalid:{tag}")
            if len(ids) != len(set(ids)) or partition_ids.intersection(ids) or product_ids.intersection(ids):
                raise RuntimeError(f"product_membership_overlap:{tag}")
            incoming, details = parse_products(products)
            if sku_ids.intersection(details):
                raise RuntimeError(f"sku_membership_overlap:{tag}")
            if any(detail.get("seller_id") != seller for detail in details.values()):
                raise RuntimeError(f"seller_scope_changed:{tag}")
            partition_ids.update(ids)
            product_ids.update(ids)
            sku_ids.update(details)
            rows.extend(incoming)
            source_details.update(details)
            page_evidence.append({
                "url": record["url"],
                "sha256": record["sha256"],
                "observed_at": record["observed_at"],
            })
        if len(partition_ids) != expected_total:
            raise RuntimeError(f"partition_membership_incomplete:{seller}:{category}")

    after, after_record = capture.get(seller, f"{seller}/facets-after", facets_path, common)
    if category_counts(after) != counts:
        raise RuntimeError(f"catalog_changed_during_capture:{seller}")
    root_after, root_after_record = capture.get(
        seller, f"{seller}/root-after", root_path, {**common, "count": "1", "page": "1"}
    )
    if root_after.get("recordsFiltered") != root_total or len(root_after.get("products", [])) != 1:
        raise RuntimeError(f"root_changed_during_capture:{seller}")
    if len(product_ids) != root_total or len(rows) != len(sku_ids):
        raise RuntimeError(f"catalog_membership_incomplete:{seller}")

    times = [datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")) for item in page_evidence]
    rows.sort(key=lambda row: row["source_key"])
    return {
        "result": "success",
        "supermarket_id": "paiz",
        "location_id": location_id,
        "city": city,
        "currency": "HNL",
        "scope": SCOPE,
        "seller_id": seller,
        "store_name": store_name,
        "region_id": region_id(seller),
        "sales_channel": SALES_CHANNEL,
        "catalog_complete": True,
        "validation_passed": True,
        "location_verified_same_run": True,
        "observed_at_utc": max(times).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "observation_started_at_utc": min(times).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "catalog_products_reported": root_total,
        "unique_products_extracted": len(product_ids),
        "skus_extracted": len(rows),
        "skus_with_price": sum(row["current_price"] is not None for row in rows),
        "membership_count": len(product_ids),
        "membership_sha256": hashlib.sha256("\n".join(sorted(product_ids)).encode()).hexdigest(),
        "availability_counts": dict(Counter(row["availability"] for row in rows)),
        "promotion_counts": {
            "promotion": sum(row["is_promotion"] is True for row in rows),
            "not_promotion": sum(row["is_promotion"] is False for row in rows),
            "unknown": sum(row["is_promotion"] is None for row in rows),
        },
        "products": rows,
        "source_details": source_details,
        "page_evidence": page_evidence,
        "binding_evidence": {
            "facet_before_sha256": before_record["sha256"],
            "facet_after_sha256": after_record["sha256"],
            "root_before_sha256": root_before_record["sha256"],
            "root_after_sha256": root_after_record["sha256"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--allow-full-catalog", action="store_true")
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--raw-directory", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--max-requests", type=int, default=MAX_REQUESTS_HARD)
    args = parser.parse_args()
    if not args.live_read_only or not args.allow_full_catalog:
        raise SystemExit("explicit_live_full_catalog_authorization_required")
    if args.delay_seconds < 0.5:
        raise SystemExit("delay_too_small")
    if args.max_requests <= 0 or args.max_requests > MAX_REQUESTS_HARD:
        raise SystemExit("request_budget_invalid")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    args.raw_directory.mkdir(parents=True, exist_ok=True)
    args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    capture = Capture(args.raw_directory, args.delay_seconds, args.max_requests)
    snapshots: list[dict] = []
    error = None
    try:
        for seller, (location_id, city, store_name) in STORES.items():
            snapshots.append(capture_store(capture, seller, location_id, city, store_name))
        for snapshot in snapshots:
            suffix = "multiplaza" if snapshot["location_id"].endswith("multiplaza") else "proceres"
            target = args.output_directory / f"snapshot-paiz-{suffix}.json"
            target.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - failure evidence is part of the contract
        error = f"{type(exc).__name__}:{exc}"
    evidence = {
        "result": "success" if error is None else "failed",
        "scope": SCOPE,
        "concurrency": 1,
        "automatic_retry_count": 0,
        "request_budget": args.max_requests,
        "request_count": len(capture.records),
        "elapsed_seconds": round(time.monotonic() - capture.started, 3),
        "stores": [
            {
                "location_id": snapshot["location_id"],
                "seller_id": snapshot["seller_id"],
                "catalog_products_reported": snapshot["catalog_products_reported"],
                "skus_extracted": snapshot["skus_extracted"],
                "skus_with_price": snapshot["skus_with_price"],
            }
            for snapshot in snapshots
        ],
        "error": error,
    }
    args.evidence_output.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    (args.evidence_output.parent / "requests.json").write_text(
        json.dumps({"records": capture.records}, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    if error is not None:
        raise SystemExit(error)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
