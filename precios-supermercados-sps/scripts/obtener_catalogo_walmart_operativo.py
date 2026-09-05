#!/usr/bin/env python3
"""Captura read-only completa de los tres contextos Walmart Honduras demostrados."""
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
from urllib.parse import parse_qs, urlencode, urlsplit

from precios_supermercados.scrapers.walmart import SCOPE, STORES, parse_products, verify_stores

BASE = "https://www.walmart.com.hn"
COUNTRY = "HND"
SALES_CHANNEL = "1"
PAGE_SIZE = 100
RECOVERY_PAGE_SIZE = 50
DEFAULT_DELAY = 1.0
DEFAULT_MAX_RETRIES = 2
MAX_RETRIES_HARD = 2
MAX_REQUESTS_HARD = 700
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
UA = "Mozilla/5.0 (compatible; PreciosSupermercadosSPS-Walmart/1.0; read-only)"
CATEGORY2_PARTITIONS = {"articulos-para-el-hogar", "ropa-y-zapateria"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def region_id(seller: str) -> str:
    return base64.b64encode(("SW#" + seller).encode()).decode()


def facet_counts(doc: dict, key: str) -> dict[str, int]:
    facets = doc.get("facets")
    if not isinstance(facets, list):
        raise RuntimeError("facets_missing")
    matches = [facet for facet in facets if isinstance(facet, dict) and facet.get("key") == key]
    if len(matches) != 1 or not isinstance(matches[0].get("values"), list):
        raise RuntimeError(f"{key}_missing_or_ambiguous")
    result: dict[str, int] = {}
    for value in matches[0]["values"]:
        if not isinstance(value, dict):
            raise RuntimeError(f"{key}_value_invalid")
        name, quantity = value.get("value"), value.get("quantity")
        if not isinstance(name, str) or not name or type(quantity) is not int or quantity <= 0 or name in result:
            raise RuntimeError(f"{key}_value_invalid")
        result[name] = quantity
    if not result:
        raise RuntimeError(f"{key}_empty")
    return result


def validate_context_url(url: str, seller: str) -> None:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    if parsed.scheme != "https" or parsed.netloc != "www.walmart.com.hn":
        raise RuntimeError("origin_not_allowed")
    if f"/accesscontrollist/{seller}" not in parsed.path:
        raise RuntimeError("selector_scope_changed")
    if query.get("regionId") != [region_id(seller)]:
        raise RuntimeError("region_scope_changed")
    if query.get("sc") != [SALES_CHANNEL] or query.get("country") != [COUNTRY]:
        raise RuntimeError("commercial_scope_changed")


def _retryable(status: int | None, error: str | None) -> bool:
    if status in RETRYABLE_HTTP_STATUSES:
        return True
    if status is not None or not error:
        return False
    return error.startswith(("URLError:", "TimeoutError:", "ConnectionError:", "OSError:"))


class Capture:
    def __init__(self, raw_dir: Path, delay: float, max_requests: int, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.raw_dir = raw_dir
        self.delay = delay
        self.max_requests = max_requests
        self.max_retries = max_retries
        self.records: list[dict] = []
        self.retry_count = 0
        self.started = time.monotonic()

    def _budget(self) -> None:
        if len(self.records) >= self.max_requests:
            raise RuntimeError("request_budget_exceeded")

    def _record(
        self,
        tag: str,
        method: str,
        url: str,
        response_url: str | None,
        status: int | None,
        body: bytes,
        error: str | None,
        start: float,
    ) -> dict:
        digest = hashlib.sha256(body).hexdigest() if body else None
        raw_path = None
        if body:
            target = self.raw_dir / (tag.replace("/", "__") + ".raw")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            raw_path = str(target)
        record = {
            "index": len(self.records) + 1,
            "tag": tag,
            "method": method,
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
        return record

    def _request(
        self,
        tag: str,
        url: str,
        headers: dict[str, str],
        *,
        seller: str | None = None,
    ) -> tuple[bytes, dict]:
        for attempt in range(self.max_retries + 1):
            self._budget()
            request = urllib.request.Request(url, headers=headers, method="GET")
            body, status, response_url, error, start = b"", None, None, None, time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    status, response_url, body = response.status, response.geturl(), response.read()
            except urllib.error.HTTPError as exc:
                status, response_url, body, error = exc.code, exc.geturl(), exc.read(), f"http_{exc.code}"
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}:{exc}"

            if response_url:
                if seller is None:
                    if urlsplit(response_url).netloc != "www.walmart.com.hn":
                        error = error or "home_redirect_outside_origin"
                else:
                    try:
                        validate_context_url(response_url, seller)
                    except RuntimeError as exc:
                        error = error or str(exc)

            record_tag = tag if attempt == 0 else f"{tag}/retry-{attempt}"
            record = self._record(record_tag, "GET", url, response_url, status, body, error, start)
            if self.delay:
                time.sleep(self.delay)
            if status == 200 and error is None:
                return body, record
            if attempt >= self.max_retries or not _retryable(status, error):
                raise RuntimeError(f"request_failed:{tag}:{status}:{error}")
            self.retry_count += 1
        raise AssertionError("retry_loop_exhausted")

    def home(self) -> tuple[str, dict]:
        body, record = self._request("home", BASE + "/", {"User-Agent": UA})
        try:
            return body.decode("utf-8"), record
        except UnicodeDecodeError as exc:
            raise RuntimeError("home_response_not_text") from exc

    def get(self, seller: str, tag: str, path: str, query: dict[str, str]) -> tuple[dict, dict]:
        url = BASE + path + "?" + urlencode(query)
        validate_context_url(url, seller)
        body, record = self._request(
            tag,
            url,
            {"User-Agent": UA, "Accept": "application/json"},
            seller=seller,
        )
        try:
            doc = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"response_not_json:{tag}") from exc
        if not isinstance(doc, dict):
            raise RuntimeError(f"response_shape_invalid:{tag}")
        return doc, record


def common_query(seller: str) -> dict[str, str]:
    return {"regionId": region_id(seller), "sc": SALES_CHANNEL, "country": COUNTRY}


def _page_products(
    capture: Capture,
    seller: str,
    tag: str,
    path: str,
    common: dict[str, str],
    expected_total: int,
    page: int,
) -> tuple[list[dict], list[dict]]:
    expected_count = min(PAGE_SIZE, expected_total - (page - 1) * PAGE_SIZE)
    doc, record = capture.get(
        seller,
        tag,
        path,
        {**common, "count": str(PAGE_SIZE), "page": str(page)},
    )
    products = doc.get("products")
    if doc.get("recordsFiltered") != expected_total or not isinstance(products, list):
        raise RuntimeError(f"page_total_changed:{tag}")
    ids = [product.get("productId") for product in products if isinstance(product, dict)]
    page_valid = len(products) == expected_count and len(ids) == len(products) and len(set(ids)) == len(ids)
    if page_valid:
        return products, [record]
    if expected_count != PAGE_SIZE:
        raise RuntimeError(f"page_count_or_duplicate:{tag}")

    recovered: list[dict] = []
    evidence: list[dict] = []
    first_recovery_page = (page - 1) * (PAGE_SIZE // RECOVERY_PAGE_SIZE) + 1
    for offset in range(PAGE_SIZE // RECOVERY_PAGE_SIZE):
        recovery_page = first_recovery_page + offset
        part, part_record = capture.get(
            seller,
            f"{tag}/recovery-{offset + 1}",
            path,
            {**common, "count": str(RECOVERY_PAGE_SIZE), "page": str(recovery_page)},
        )
        part_products = part.get("products")
        if (
            part.get("recordsFiltered") != expected_total
            or not isinstance(part_products, list)
            or len(part_products) != RECOVERY_PAGE_SIZE
        ):
            raise RuntimeError(f"page_recovery_incomplete:{tag}")
        recovered.extend(part_products)
        evidence.append(part_record)
    recovered_ids = [product.get("productId") for product in recovered if isinstance(product, dict)]
    if len(recovered_ids) != PAGE_SIZE or len(set(recovered_ids)) != PAGE_SIZE:
        raise RuntimeError(f"page_recovery_duplicate:{tag}")
    return recovered, evidence


def capture_store(capture: Capture, seller: str, location_id: str, city: str, store_name: str, home_sha: str) -> dict:
    common = common_query(seller)
    facets_root = f"/api/io/_v/api/intelligent-search/facets/accesscontrollist/{seller}"
    search_root = f"/api/io/_v/api/intelligent-search/product_search/accesscontrollist/{seller}"
    before, before_record = capture.get(seller, f"{seller}/facets-before", facets_root, common)
    category1 = facet_counts(before, "category-1")
    root_total = sum(category1.values())
    root_before, root_before_record = capture.get(
        seller, f"{seller}/root-before", search_root, {**common, "count": "1", "page": "1"}
    )
    if root_before.get("recordsFiltered") != root_total or len(root_before.get("products", [])) != 1:
        raise RuntimeError(f"root_total_disagrees_with_facets:{seller}")

    product_ids: set[str] = set()
    sku_ids: set[str] = set()
    rows: list[dict] = []
    source_details: dict[str, dict] = {}
    page_evidence: list[dict] = []

    for category, expected_total in category1.items():
        partitions: list[tuple[str, int]] = [(f"category-1/{category}", expected_total)]
        if category in CATEGORY2_PARTITIONS:
            facet_path = f"{facets_root}/category-1/{category}"
            child_doc, _ = capture.get(seller, f"{seller}/{category}/category2-facets", facet_path, common)
            children = facet_counts(child_doc, "category-2")
            if sum(children.values()) != expected_total:
                raise RuntimeError(f"category2_total_mismatch:{seller}:{category}")
            partitions = [(f"category-1/{category}/category-2/{child}", count) for child, count in children.items()]

        category_members: set[str] = set()
        for relative, partition_total in partitions:
            path = f"{search_root}/{relative}"
            pages = math.ceil(partition_total / PAGE_SIZE)
            partition_members: set[str] = set()
            for page in range(1, pages + 1):
                tag = f"{seller}/{relative}/page-{page:03d}"
                products, records = _page_products(capture, seller, tag, path, common, partition_total, page)
                ids = [product.get("productId") for product in products]
                if any(not isinstance(pid, str) or not pid for pid in ids):
                    raise RuntimeError(f"product_id_invalid:{tag}")
                if partition_members.intersection(ids) or category_members.intersection(ids) or product_ids.intersection(ids):
                    raise RuntimeError(f"product_membership_overlap:{tag}")
                incoming, details = parse_products(products)
                if sku_ids.intersection(details):
                    raise RuntimeError(f"sku_membership_overlap:{tag}")
                partition_members.update(ids)
                category_members.update(ids)
                product_ids.update(ids)
                sku_ids.update(details)
                rows.extend(incoming)
                source_details.update(details)
                page_evidence.extend(
                    {
                        "tag": item["tag"],
                        "url": item["url"],
                        "sha256": item["sha256"],
                        "observed_at": item["observed_at"],
                    }
                    for item in records
                )
            if len(partition_members) != partition_total:
                raise RuntimeError(f"partition_membership_incomplete:{seller}:{relative}")
        if len(category_members) != expected_total:
            raise RuntimeError(f"category_membership_incomplete:{seller}:{category}")

    after, after_record = capture.get(seller, f"{seller}/facets-after", facets_root, common)
    if facet_counts(after, "category-1") != category1:
        raise RuntimeError(f"catalog_changed_during_capture:{seller}")
    root_after, root_after_record = capture.get(
        seller, f"{seller}/root-after", search_root, {**common, "count": "1", "page": "1"}
    )
    if root_after.get("recordsFiltered") != root_total or len(root_after.get("products", [])) != 1:
        raise RuntimeError(f"root_changed_during_capture:{seller}")
    if len(product_ids) != root_total or len(rows) != len(sku_ids):
        raise RuntimeError(f"catalog_membership_incomplete:{seller}")

    times = [datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")) for item in page_evidence]
    rows.sort(key=lambda row: row["source_key"])
    return {
        "result": "success",
        "supermarket_id": "walmart",
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
            "selector": seller,
            "region_id": region_id(seller),
            "sales_channel": SALES_CHANNEL,
            "country": COUNTRY,
            "home_configuration_sha256": home_sha,
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
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    args = parser.parse_args()
    if not args.live_read_only or not args.allow_full_catalog:
        raise SystemExit("explicit_live_full_catalog_authorization_required")
    if args.delay_seconds < 0.5:
        raise SystemExit("delay_too_small")
    if args.max_requests <= 0 or args.max_requests > MAX_REQUESTS_HARD:
        raise SystemExit("request_budget_invalid")
    if args.max_retries < 0 or args.max_retries > MAX_RETRIES_HARD:
        raise SystemExit("retry_budget_invalid")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    args.raw_directory.mkdir(parents=True, exist_ok=True)
    args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    capture = Capture(args.raw_directory, args.delay_seconds, args.max_requests, args.max_retries)
    snapshots: list[dict] = []
    error = None
    try:
        home, home_record = capture.home()
        verify_stores(home)
        home_sha = str(home_record["sha256"])
        for seller, (location_id, city, store_name) in STORES.items():
            snapshots.append(capture_store(capture, seller, location_id, city, store_name, home_sha))
        names = {
            "walmart_sps": "sps",
            "walmart_tgu_ffaa": "tgu-ffaa",
            "walmart_tgu_el_sauce": "tgu-el-sauce",
        }
        for snapshot in snapshots:
            target = args.output_directory / f"snapshot-walmart-{names[snapshot['location_id']]}.json"
            target.write_text(
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}:{exc}"

    evidence = {
        "result": "success" if error is None else "failed",
        "scope": SCOPE,
        "concurrency": 1,
        "automatic_retry_count": capture.retry_count,
        "max_retries_per_request": args.max_retries,
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
    args.evidence_output.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    (args.evidence_output.parent / "requests.json").write_text(
        json.dumps({"records": capture.records}, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    if error is not None:
        raise SystemExit(error)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
