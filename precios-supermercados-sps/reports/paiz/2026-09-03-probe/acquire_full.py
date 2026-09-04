#!/usr/bin/env python3
"""One authorized, bounded, public read-only full capture for active Paiz TGU contexts."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

BASE = "https://www.paiz.com.hn"
SC = "2"
COUNT = 100
MAX_REQUESTS = 900
UA = "Mozilla/5.0 (compatible; PreciosSupermercadosSPS-PaizFull/1.0; read-only)"
OUT = Path("reports/paiz/2026-09-04-full")
STORES = {
    "walmarthnsp633": {
        "location_id": "paiz_tgu_multiplaza",
        "store_name": "Paiz Multiplaza",
        "city": "Tegucigalpa",
        "postal_code": "633001",
        "expected_root": 8864,
    },
    "walmarthnsp4010": {
        "location_id": "paiz_tgu_proceres",
        "store_name": "Paiz Próceres",
        "city": "Tegucigalpa",
        "postal_code": "401001",
        "expected_root": 8567,
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


def observed_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Capture:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.started = time.monotonic()

    def get(self, seller: str, tag: str, path: str, query: dict[str, str]) -> tuple[dict, dict]:
        if len(self.records) >= MAX_REQUESTS:
            raise RuntimeError("request_budget_exceeded")
        url = BASE + path + "?" + urlencode(query)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.paiz.com.hn":
            raise RuntimeError("origin_not_allowed")
        started = time.monotonic()
        status = None
        response_url = None
        headers: dict[str, str] = {}
        body = b""
        error = None
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                status = response.status
                response_url = response.geturl()
                headers = {k.lower(): v for k, v in response.headers.items() if k.lower() != "set-cookie"}
                body = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            response_url = exc.geturl()
            headers = {k.lower(): v for k, v in exc.headers.items() if k.lower() != "set-cookie"}
            body = exc.read()
            error = f"http_{exc.code}"
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        stamp = observed_at()
        digest = hashlib.sha256(body).hexdigest() if body else None
        filename = None
        if body:
            raw_dir = OUT / "raw" / seller
            raw_dir.mkdir(parents=True, exist_ok=True)
            filename = tag.replace("/", "__") + ".json"
            (raw_dir / filename).write_bytes(body)
        row = {
            "index": len(self.records) + 1,
            "tag": tag,
            "method": "GET",
            "url": url,
            "response_url": response_url,
            "status": status,
            "observed_at": stamp,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "content_type": headers.get("content-type"),
            "content_length_observed": len(body),
            "sha256": digest,
            "file": f"raw/{seller}/{filename}" if filename else None,
            "headers": headers,
            "error": error,
        }
        self.records.append(row)
        print(json.dumps({k: row[k] for k in ("index", "tag", "status", "elapsed_seconds", "content_length_observed", "sha256", "error")}, sort_keys=True))
        if status != 200 or error:
            raise RuntimeError(f"request_failed:{tag}:{status}:{error}")
        try:
            doc = json.loads(body)
        except ValueError as exc:
            raise RuntimeError(f"response_not_json:{tag}") from exc
        if not isinstance(doc, dict):
            raise RuntimeError(f"response_shape_invalid:{tag}")
        return doc, row


def category_counts(doc: dict) -> dict[str, int]:
    facets = doc.get("facets")
    if not isinstance(facets, list):
        raise RuntimeError("facets_missing")
    roots = [f for f in facets if f.get("key") == "category-1"]
    if len(roots) != 1 or not isinstance(roots[0].get("values"), list):
        raise RuntimeError("category_1_missing_or_ambiguous")
    result = {}
    for value in roots[0]["values"]:
        key, qty = value.get("value"), value.get("quantity")
        if not isinstance(key, str) or not key or type(qty) is not int or qty <= 0 or key in result:
            raise RuntimeError("category_1_value_invalid")
        result[key] = qty
    return result


def common_query(seller: str) -> dict[str, str]:
    return {"regionId": region_id(seller), "sc": SC, "country": "HND"}


def main() -> None:
    if OUT.exists():
        raise SystemExit("output_must_be_new")
    OUT.mkdir(parents=True)
    capture = Capture()
    plan: list[dict] = []
    store_evidence: dict[str, dict] = {}
    for seller, meta in STORES.items():
        common = common_query(seller)
        facets_path = f"/api/io/_v/api/intelligent-search/facets/accesscontrollist/{seller}"
        root_path = f"/api/io/_v/api/intelligent-search/product_search/accesscontrollist/{seller}"
        before, before_row = capture.get(seller, f"{seller}/facets-before", facets_path, common)
        before_counts = category_counts(before)
        if before_counts != EXPECTED_CATEGORY_COUNTS[seller]:
            raise RuntimeError(f"pre_full_category_counts_changed:{seller}")
        if sum(before_counts.values()) != meta["expected_root"]:
            raise RuntimeError(f"pre_full_root_sum_changed:{seller}")
        root_before, root_before_row = capture.get(seller, f"{seller}/root-before", root_path, {**common, "count": "1", "page": "1"})
        if root_before.get("recordsFiltered") != meta["expected_root"] or len(root_before.get("products", [])) != 1:
            raise RuntimeError(f"pre_full_root_changed:{seller}")

        all_ids: set[str] = set()
        all_skus: set[str] = set()
        partitions: dict[str, dict] = {}
        for category, expected_total in before_counts.items():
            path = f"{root_path}/category-1/{category}"
            pages = math.ceil(expected_total / COUNT)
            ids: set[str] = set()
            skus: set[str] = set()
            for page in range(1, pages + 1):
                expected_count = min(COUNT, expected_total - (page - 1) * COUNT)
                tag = f"{seller}/category-1/{category}/page-{page:03d}"
                doc, row = capture.get(seller, tag, path, {**common, "count": str(COUNT), "page": str(page)})
                products = doc.get("products")
                if doc.get("recordsFiltered") != expected_total or not isinstance(products, list) or len(products) != expected_count:
                    raise RuntimeError(f"page_count_changed:{tag}")
                page_ids = []
                page_skus = []
                for product in products:
                    pid = product.get("productId")
                    if not isinstance(pid, str) or not pid:
                        raise RuntimeError(f"product_id_invalid:{tag}")
                    page_ids.append(pid)
                    items = product.get("items")
                    if not isinstance(items, list) or not items:
                        raise RuntimeError(f"items_missing:{tag}:{pid}")
                    for item in items:
                        sku = item.get("itemId")
                        if not isinstance(sku, str) or not sku:
                            raise RuntimeError(f"item_id_invalid:{tag}:{pid}")
                        page_skus.append(sku)
                if len(page_ids) != len(set(page_ids)) or ids.intersection(page_ids) or all_ids.intersection(page_ids):
                    raise RuntimeError(f"product_membership_overlap:{tag}")
                if len(page_skus) != len(set(page_skus)) or skus.intersection(page_skus) or all_skus.intersection(page_skus):
                    raise RuntimeError(f"sku_membership_overlap:{tag}")
                ids.update(page_ids); skus.update(page_skus)
                plan.append({
                    "tag": tag, "seller": seller, "category_key": "category-1", "category_value": category,
                    "page": page, "count": COUNT, "expected_count": expected_count, "expected_total": expected_total,
                    "url": row["url"], "sha256": row["sha256"], "observed_at": row["observed_at"],
                })
            if len(ids) != expected_total:
                raise RuntimeError(f"partition_membership_incomplete:{seller}:{category}")
            all_ids.update(ids); all_skus.update(skus)
            partitions[category] = {"products": len(ids), "skus": len(skus), "pages": pages}
        if len(all_ids) != meta["expected_root"] or sum(v["products"] for v in partitions.values()) != meta["expected_root"]:
            raise RuntimeError(f"catalog_membership_incomplete:{seller}")

        after, after_row = capture.get(seller, f"{seller}/facets-after", facets_path, common)
        after_counts = category_counts(after)
        if after_counts != before_counts:
            raise RuntimeError(f"post_full_category_counts_changed:{seller}")
        root_after, root_after_row = capture.get(seller, f"{seller}/root-after", root_path, {**common, "count": "1", "page": "1"})
        if root_after.get("recordsFiltered") != meta["expected_root"] or len(root_after.get("products", [])) != 1:
            raise RuntimeError(f"post_full_root_changed:{seller}")
        store_evidence[seller] = {
            **meta,
            "region_id": region_id(seller),
            "sales_channel": SC,
            "products": len(all_ids),
            "skus": len(all_skus),
            "category_counts": before_counts,
            "partitions": partitions,
            "facet_before_sha256": before_row["sha256"],
            "facet_after_sha256": after_row["sha256"],
            "root_before_sha256": root_before_row["sha256"],
            "root_after_sha256": root_after_row["sha256"],
        }

    ledger = {
        "origin": BASE,
        "method": "GET",
        "concurrency": 1,
        "retry_count": 0,
        "request_budget_this_capture": MAX_REQUESTS,
        "request_count": len(capture.records),
        "records": capture.records,
    }
    evidence = {
        "result": "success",
        "scope": "public_ecommerce_selected_store_not_universal_city_price",
        "geography": {"tgu_contexts": 2, "sps_active_selector_contexts_observed": 0},
        "request_count": len(capture.records),
        "retry_count": 0,
        "concurrency": 1,
        "page_size": COUNT,
        "elapsed_seconds": round(time.monotonic() - capture.started, 3),
        "stores": store_evidence,
        "completeness": "category-1 exhaustive partition; pre/post facets and root totals stable; exact per-page and unique membership reconciled",
    }
    (OUT / "requests.json").write_text(json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    (OUT / "catalog-plan.json").write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    (OUT / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
