#!/usr/bin/env python3
"""Resume the authorized Paiz full from accepted RAW of failed run 33833487039.

Only missing/invalid responses are requested. Valid RAW is reused byte-for-byte.
There are no automatic retries and concurrency remains one.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

BASE = "https://www.paiz.com.hn"
SC = "2"
COUNT = 100
MAX_NEW_REQUESTS = 300
UA = "Mozilla/5.0 (compatible; PreciosSupermercadosSPS-PaizFullRecovery/1.0; read-only)"
OUT = Path("reports/paiz/2026-09-04-full")
RAW = OUT / "raw"
FAILED = OUT / "failed-attempts"
SOURCE_RUN_ID = 33833487039
SOURCE_ARTIFACT_ID = 9922521379
SOURCE_ARTIFACT_SHA256 = "d3858f10493ace31f870f04a72cc8a35e17e810f6da2cd6c8320aa56eb4568ab"
STORES = {
    "walmarthnsp633": {
        "location_id": "paiz_tgu_multiplaza", "store_name": "Paiz Multiplaza",
        "city": "Tegucigalpa", "postal_code": "633001", "expected_root": 8864,
    },
    "walmarthnsp4010": {
        "location_id": "paiz_tgu_proceres", "store_name": "Paiz Próceres",
        "city": "Tegucigalpa", "postal_code": "401001", "expected_root": 8567,
    },
}
EXPECTED_CATEGORY_COUNTS = {
    "walmarthnsp633": {
        "abarrotes": 2060, "higiene-y-belleza": 1835, "limpieza": 999,
        "articulos-para-el-hogar": 492, "jugos-y-bebidas": 483, "lacteos": 451,
        "farmacia": 385, "cervezas-vinos-y-licores": 360, "carnes-embutidos-y-mariscos": 341,
        "bebes-y-ninos": 314, "panaderia-y-tortilleria": 252, "alimentos-congelados": 182,
        "frutas-y-verduras": 173, "mascota": 172, "anthistaminicos": 140, "juguetes": 88,
        "ropa-y-zapateria": 69, "autos": 59, "deportes": 9,
    },
    "walmarthnsp4010": {
        "abarrotes": 2025, "higiene-y-belleza": 1780, "limpieza": 951,
        "jugos-y-bebidas": 476, "articulos-para-el-hogar": 458, "lacteos": 448,
        "farmacia": 352, "cervezas-vinos-y-licores": 341, "carnes-embutidos-y-mariscos": 327,
        "bebes-y-ninos": 300, "panaderia-y-tortilleria": 252, "mascota": 181,
        "alimentos-congelados": 171, "frutas-y-verduras": 150, "anthistaminicos": 146,
        "juguetes": 76, "ropa-y-zapateria": 68, "autos": 59, "deportes": 6,
    },
}


def region_id(seller: str) -> str:
    return base64.b64encode(("SW#" + seller).encode()).decode()


def iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def filename(tag: str) -> str:
    return tag.replace("/", "__") + ".json"


def parse_doc(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_bytes())
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def category_counts(doc: dict) -> dict[str, int]:
    facets = doc.get("facets")
    if not isinstance(facets, list):
        raise RuntimeError("facets_missing")
    roots = [f for f in facets if f.get("key") == "category-1"]
    if len(roots) != 1 or not isinstance(roots[0].get("values"), list):
        raise RuntimeError("category_1_missing_or_ambiguous")
    result: dict[str, int] = {}
    for value in roots[0]["values"]:
        key, qty = value.get("value"), value.get("quantity")
        if not isinstance(key, str) or not key or type(qty) is not int or qty <= 0 or key in result:
            raise RuntimeError("category_1_value_invalid")
        result[key] = qty
    return result


def common_query(seller: str) -> dict[str, str]:
    return {"regionId": region_id(seller), "sc": SC, "country": "HND"}


class Capture:
    def __init__(self) -> None:
        self.accepted: list[dict] = []
        self.failed: list[dict] = []
        self.new_requests = 0
        self.reused = 0
        self.started = time.monotonic()

    def _valid_existing(self, tag: str, path: Path) -> dict | None:
        doc = parse_doc(path)
        if doc is None:
            return None
        self.reused += 1
        raw = path.read_bytes()
        return {
            "doc": doc,
            "record": {
                "tag": tag, "method": "GET", "status": 200,
                "observed_at": iso_mtime(path), "sha256": hashlib.sha256(raw).hexdigest(),
                "content_length_observed": len(raw), "file": f"raw/{path.parent.name}/{path.name}",
                "acquisition": f"reused_from_artifact_{SOURCE_ARTIFACT_ID}",
            },
        }

    def get(self, seller: str, tag: str, path: str, query: dict[str, str]) -> tuple[dict, dict]:
        url = BASE + path + "?" + urlencode(query)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.paiz.com.hn":
            raise RuntimeError("origin_not_allowed")
        target = RAW / seller / filename(tag)
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = self._valid_existing(tag, target) if target.exists() else None
        if existing is not None:
            record = {**existing["record"], "url": url}
            self.accepted.append(record)
            return existing["doc"], record

        if target.exists():
            FAILED.mkdir(parents=True, exist_ok=True)
            failed_name = f"run-{SOURCE_RUN_ID}__{filename(tag)}"
            raw = target.read_bytes()
            saved = FAILED / failed_name
            shutil.move(target, saved)
            self.failed.append({
                "tag": tag, "status": "invalid_raw_from_failed_attempt",
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "file": f"failed-attempts/{failed_name}", "source_run_id": SOURCE_RUN_ID,
            })

        if self.new_requests >= MAX_NEW_REQUESTS:
            raise RuntimeError("recovery_request_budget_exceeded")
        self.new_requests += 1
        started = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
        status = None; body = b""; headers: dict[str, str] = {}; error = None; response_url = None
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                status = response.status; response_url = response.geturl(); body = response.read()
                headers = {k.lower(): v for k, v in response.headers.items() if k.lower() != "set-cookie"}
        except urllib.error.HTTPError as exc:
            status = exc.code; response_url = exc.geturl(); body = exc.read(); error = f"http_{exc.code}"
            headers = {k.lower(): v for k, v in exc.headers.items() if k.lower() != "set-cookie"}
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        stamp = now(); digest = hashlib.sha256(body).hexdigest() if body else None
        record = {
            "tag": tag, "method": "GET", "url": url, "response_url": response_url, "status": status,
            "observed_at": stamp, "elapsed_seconds": round(time.monotonic() - started, 3),
            "content_type": headers.get("content-type"), "content_length_observed": len(body),
            "sha256": digest, "file": f"raw/{seller}/{target.name}" if body else None,
            "headers": headers, "error": error, "acquisition": "recovery_run",
        }
        print(json.dumps({k: record[k] for k in ("tag", "status", "elapsed_seconds", "content_length_observed", "sha256", "error")}, sort_keys=True))
        if status != 200 or error:
            if body:
                FAILED.mkdir(parents=True, exist_ok=True)
                failed_name = f"recovery__{filename(tag)}"
                (FAILED / failed_name).write_bytes(body)
                record["failed_file"] = f"failed-attempts/{failed_name}"
            self.failed.append(record)
            raise RuntimeError(f"request_failed:{tag}:{status}:{error}")
        target.write_bytes(body)
        doc = parse_doc(target)
        if doc is None:
            self.failed.append(record)
            raise RuntimeError(f"response_not_json:{tag}")
        self.accepted.append(record)
        return doc, record


def validate_page(doc: dict, expected_total: int, expected_count: int, tag: str) -> tuple[list[str], list[str]]:
    products = doc.get("products")
    if doc.get("recordsFiltered") != expected_total or not isinstance(products, list) or len(products) != expected_count:
        raise RuntimeError(f"page_count_changed:{tag}")
    product_ids: list[str] = []
    sku_ids: list[str] = []
    for product in products:
        pid = product.get("productId")
        if not isinstance(pid, str) or not pid:
            raise RuntimeError(f"product_id_invalid:{tag}")
        product_ids.append(pid)
        items = product.get("items")
        if not isinstance(items, list) or not items:
            raise RuntimeError(f"items_missing:{tag}:{pid}")
        for item in items:
            sku = item.get("itemId")
            if not isinstance(sku, str) or not sku:
                raise RuntimeError(f"item_id_invalid:{tag}:{pid}")
            sku_ids.append(sku)
    if len(product_ids) != len(set(product_ids)) or len(sku_ids) != len(set(sku_ids)):
        raise RuntimeError(f"page_membership_duplicate:{tag}")
    return product_ids, sku_ids


def main() -> None:
    if not RAW.exists():
        raise SystemExit("partial_raw_missing")
    capture = Capture(); plan: list[dict] = []; store_evidence: dict[str, dict] = {}
    for seller, meta in STORES.items():
        common = common_query(seller)
        facets_path = f"/api/io/_v/api/intelligent-search/facets/accesscontrollist/{seller}"
        root_path = f"/api/io/_v/api/intelligent-search/product_search/accesscontrollist/{seller}"
        before, before_row = capture.get(seller, f"{seller}/facets-before", facets_path, common)
        before_counts = category_counts(before)
        if before_counts != EXPECTED_CATEGORY_COUNTS[seller] or sum(before_counts.values()) != meta["expected_root"]:
            raise RuntimeError(f"pre_full_counts_changed:{seller}")
        root_before, root_before_row = capture.get(seller, f"{seller}/root-before", root_path, {**common, "count": "1", "page": "1"})
        if root_before.get("recordsFiltered") != meta["expected_root"] or len(root_before.get("products", [])) != 1:
            raise RuntimeError(f"pre_full_root_changed:{seller}")

        all_ids: set[str] = set(); all_skus: set[str] = set(); partitions: dict[str, dict] = {}
        for category, expected_total in before_counts.items():
            category_path = f"{root_path}/category-1/{category}"
            pages = math.ceil(expected_total / COUNT); ids: set[str] = set(); skus: set[str] = set()
            for page in range(1, pages + 1):
                expected_count = min(COUNT, expected_total - (page - 1) * COUNT)
                tag = f"{seller}/category-1/{category}/page-{page:03d}"
                doc, row = capture.get(seller, tag, category_path, {**common, "count": str(COUNT), "page": str(page)})
                page_ids, page_skus = validate_page(doc, expected_total, expected_count, tag)
                if ids.intersection(page_ids) or all_ids.intersection(page_ids):
                    raise RuntimeError(f"product_membership_overlap:{tag}")
                if skus.intersection(page_skus) or all_skus.intersection(page_skus):
                    raise RuntimeError(f"sku_membership_overlap:{tag}")
                ids.update(page_ids); skus.update(page_skus)
                plan.append({
                    "tag": tag, "seller": seller, "category_key": "category-1", "category_value": category,
                    "page": page, "count": COUNT, "expected_count": expected_count, "expected_total": expected_total,
                    "url": row["url"], "sha256": row["sha256"], "observed_at": row["observed_at"],
                    "acquisition": row["acquisition"],
                })
            if len(ids) != expected_total:
                raise RuntimeError(f"partition_membership_incomplete:{seller}:{category}")
            all_ids.update(ids); all_skus.update(skus)
            partitions[category] = {"products": len(ids), "skus": len(skus), "pages": pages}
        if len(all_ids) != meta["expected_root"] or sum(v["products"] for v in partitions.values()) != meta["expected_root"]:
            raise RuntimeError(f"catalog_membership_incomplete:{seller}")

        after, after_row = capture.get(seller, f"{seller}/facets-after", facets_path, common)
        if category_counts(after) != before_counts:
            raise RuntimeError(f"post_full_category_counts_changed:{seller}")
        root_after, root_after_row = capture.get(seller, f"{seller}/root-after", root_path, {**common, "count": "1", "page": "1"})
        if root_after.get("recordsFiltered") != meta["expected_root"] or len(root_after.get("products", [])) != 1:
            raise RuntimeError(f"post_full_root_changed:{seller}")
        store_evidence[seller] = {
            **meta, "region_id": region_id(seller), "sales_channel": SC,
            "products": len(all_ids), "skus": len(all_skus), "category_counts": before_counts,
            "partitions": partitions, "facet_before_sha256": before_row["sha256"],
            "facet_after_sha256": after_row["sha256"], "root_before_sha256": root_before_row["sha256"],
            "root_after_sha256": root_after_row["sha256"],
        }

    accepted = []
    for index, record in enumerate(capture.accepted, 1):
        accepted.append({"index": index, **record})
    ledger = {
        "origin": BASE, "method": "GET", "concurrency": 1, "automatic_retry_count": 0,
        "source_failed_run_id": SOURCE_RUN_ID, "source_partial_artifact_id": SOURCE_ARTIFACT_ID,
        "source_partial_artifact_sha256": SOURCE_ARTIFACT_SHA256,
        "accepted_response_count": len(accepted), "reused_response_count": capture.reused,
        "new_request_count": capture.new_requests, "failed_attempts": capture.failed, "records": accepted,
    }
    observation_times = [r["observed_at"] for r in accepted]
    evidence = {
        "result": "success", "scope": "public_ecommerce_selected_store_not_universal_city_price",
        "geography": {"tgu_contexts": 2, "sps_active_selector_contexts_observed": 0},
        "accepted_response_count": len(accepted), "reused_response_count": capture.reused,
        "recovery_request_count": capture.new_requests, "prior_failed_run_request_count": 69,
        "total_full_attempt_requests": 69 + capture.new_requests, "automatic_retry_count": 0,
        "concurrency": 1, "page_size": COUNT, "elapsed_recovery_seconds": round(time.monotonic() - capture.started, 3),
        "observed_from_utc": min(observation_times), "observed_to_utc": max(observation_times),
        "stores": store_evidence,
        "completeness": "category-1 exhaustive partition; pre/post facets and root totals stable; exact per-page and unique product/SKU membership reconciled",
        "recovery": "valid RAW from failed run reused byte-for-byte; only missing/invalid responses requested",
    }
    (OUT / "requests.json").write_text(json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    (OUT / "catalog-plan.json").write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    (OUT / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
