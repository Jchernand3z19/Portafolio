"""Paiz HN: reconcile accepted public VTEX capture and normalize offers offline."""
from __future__ import annotations

import base64
import hashlib
import json
import tarfile
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SUPERMARKET_ID = "paiz"
SUPERMARKET_NAME = "Paiz"
SCOPE = "public_ecommerce_selected_store_not_universal_city_price"
SALES_CHANNEL = "2"
COUNTRY = "HND"
STORES = {
    "walmarthnsp633": ("paiz_tgu_multiplaza", "Tegucigalpa", "Paiz Multiplaza", 8864),
    "walmarthnsp4010": ("paiz_tgu_proceres", "Tegucigalpa", "Paiz Próceres", 8567),
}
ARCHIVES = {
    "walmarthnsp633": "raw-paiz-multiplaza.tar.gz",
    "walmarthnsp4010": "raw-paiz-proceres.tar.gz",
}


class PaizError(ValueError):
    pass


def require(value: object, reason: str) -> None:
    if not value:
        raise PaizError(reason)


def _money(value: object) -> str:
    require(type(value) in {int, float, str}, "price_type_invalid")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PaizError("price_invalid") from exc
    require(amount.is_finite() and amount >= 0, "price_invalid")
    require(amount * 100 == (amount * 100).to_integral_value(), "price_invalid")
    return format(amount, ".2f")


def _presentation(product: dict) -> str | None:
    preferred = (
        "tamaño (gramaje, volumen)",
        "presentación",
        "presentacion",
        "presentación farmacéutica",
        "presentacion farmaceutica",
    )
    found: dict[str, str] = {}
    for group in product.get("specificationGroups") or []:
        if not isinstance(group, dict):
            continue
        for spec in group.get("specifications") or []:
            if not isinstance(spec, dict):
                continue
            name = str(spec.get("name") or "").strip().lower()
            values = spec.get("values")
            if name and isinstance(values, list):
                clean = [str(v).strip() for v in values if str(v).strip()]
                if clean:
                    found.setdefault(name, "; ".join(clean))
    for key in preferred:
        if key in found:
            return found[key]
    for prop in product.get("properties") or []:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get("name") or "").strip().lower()
        if name in preferred and isinstance(prop.get("values"), list):
            clean = [str(v).strip() for v in prop["values"] if str(v).strip()]
            if clean:
                return "; ".join(clean)
    return None


def parse_products(products: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    rows: list[dict] = []
    details: dict[str, dict] = {}
    for product in products:
        pid = product.get("productId")
        require(isinstance(pid, str) and pid.isdigit() and int(pid) > 0, "product_id_invalid")
        items = product.get("items")
        require(isinstance(items, list) and items, "variants_missing")
        presentation = _presentation(product)
        categories = product.get("categories") or []
        for item in items:
            sku = item.get("itemId")
            require(isinstance(sku, str) and sku.isdigit() and int(sku) > 0, "sku_invalid")
            require(sku not in details, "sku_duplicate")
            sellers = item.get("sellers")
            require(isinstance(sellers, list) and len(sellers) == 1, "offer_ambiguous")
            seller = sellers[0]
            offer = seller.get("commertialOffer")
            require(isinstance(offer, dict), "commercial_offer_missing")
            current = _money(offer.get("Price"))
            regular = _money(offer.get("ListPrice"))
            quantity = offer.get("AvailableQuantity")
            require(quantity is None or (type(quantity) in {int, float} and quantity >= 0), "availability_invalid")
            availability = "unknown" if quantity is None else "in_stock" if quantity > 0 else "out_of_stock"
            unpriced = current == regular == "0.00" and quantity == 0
            require(current != "0.00" or unpriced, "zero_price_ambiguous")
            require(Decimal(regular) >= Decimal(current), "regular_below_effective")
            name = item.get("nameComplete") or item.get("name") or product.get("productName")
            require(isinstance(name, str) and name.strip(), "name_missing")
            references = item.get("referenceId") or []
            reference = next((r.get("Value") for r in references if isinstance(r, dict) and r.get("Key") == "RefId"), None)
            rows.append({
                "product_id": pid,
                "item_id": sku,
                "source_key_type": "item_id",
                "source_key": sku,
                "source_name": name.strip(),
                "brand": product.get("brand"),
                "reference": reference,
                "ean": item.get("ean") or None,
                "category": categories[0] if categories else None,
                "presentation": presentation,
                "current_price": None if unpriced else current,
                "reported_regular_price": None if unpriced else regular,
                "is_promotion": None if unpriced else Decimal(regular) > Decimal(current),
                "availability": availability,
            })
            details[sku] = {
                "price_status": "unavailable_zero_offer" if unpriced else "observed",
                "source_price": current,
                "source_list_price": regular,
                "available_quantity_signal": quantity,
                "measurement_unit": item.get("measurementUnit"),
                "unit_multiplier": item.get("unitMultiplier"),
                "seller_id": seller.get("sellerId"),
                "seller_name": seller.get("sellerName"),
            }
    return rows, details


class _RawArchive:
    def __init__(self, directory: Path, seller: str):
        self.seller = seller
        self.tar = tarfile.open(directory / ARCHIVES[seller], "r:gz")
        self.members = {Path(m.name).name: m for m in self.tar.getmembers() if m.isfile()}

    def read_record(self, record: dict) -> bytes:
        path = Path(str(record.get("file") or ""))
        require(not path.is_absolute() and ".." not in path.parts, "unsafe_raw_path")
        require(len(path.parts) >= 3 and path.parts[-2] == self.seller, "raw_scope_mismatch")
        member = self.members.get(path.name)
        require(member is not None, "raw_file_missing:" + str(record.get("tag")))
        stream = self.tar.extractfile(member)
        require(stream is not None, "raw_file_missing:" + str(record.get("tag")))
        raw = stream.read()
        require(hashlib.sha256(raw).hexdigest() == record.get("sha256"), "raw_hash_mismatch")
        return raw

    def close(self) -> None:
        self.tar.close()


def reconcile_capture(directory: str | Path) -> list[dict]:
    directory = Path(directory)
    ledger = json.loads((directory / "requests.json").read_text(encoding="utf-8"))
    evidence = json.loads((directory / "evidence.json").read_text(encoding="utf-8"))
    plan = json.loads((directory / "catalog-plan.json").read_text(encoding="utf-8"))
    require(evidence.get("result") == "success" and evidence.get("completeness"), "capture_not_accepted")
    require(evidence.get("scope") == SCOPE, "scope_mismatch")
    require(evidence.get("automatic_retry_count") == 0 and evidence.get("concurrency") == 1, "capture_safety_mismatch")
    require(evidence.get("total_full_attempt_requests", 1001) <= 1000, "capture_request_budget_exceeded")
    require(evidence.get("geography") == {"sps_active_selector_contexts_observed": 0, "tgu_contexts": 2}, "geography_not_proven")
    records = ledger.get("records")
    require(isinstance(records, list) and len(records) == evidence.get("accepted_response_count"), "ledger_count_mismatch")
    successful = {r.get("tag"): r for r in records if r.get("status") == 200}
    require(len(successful) == len(records), "accepted_ledger_has_failed_request")

    archives = {seller: _RawArchive(directory, seller) for seller in STORES}
    try:
        def body(record: dict) -> bytes:
            tag = str(record.get("tag") or "")
            seller = tag.split("/", 1)[0]
            require(seller in archives, "unknown_seller")
            return archives[seller].read_record(record)

        for record in records:
            url = urlsplit(str(record.get("url") or ""))
            require(record.get("method") == "GET" and url.scheme == "https" and url.netloc == "www.paiz.com.hn", "source_origin_invalid")
            if "/accesscontrollist/" in url.path:
                seller = url.path.split("/accesscontrollist/", 1)[1].split("/", 1)[0]
                query = parse_qs(url.query)
                require(seller in STORES, "seller_scope_invalid")
                require(query.get("regionId") == [base64.b64encode(("SW#" + seller).encode()).decode()], "region_scope_invalid")
                require(query.get("sc") == [SALES_CHANNEL] and query.get("country") == [COUNTRY], "commercial_scope_mismatch")
            body(record)

        snapshots: list[dict] = []
        for seller, (location_id, city, store_name, expected_root) in STORES.items():
            pages = [p for p in plan if p.get("seller") == seller]
            require(pages, "scope_plan_missing")
            before = json.loads(body(successful[f"{seller}/facets-before"]))
            after = json.loads(body(successful[f"{seller}/facets-after"]))
            def cat_counts(doc: dict) -> dict[str, int]:
                roots = [f for f in doc.get("facets", []) if f.get("key") == "category-1"]
                require(len(roots) == 1 and isinstance(roots[0].get("values"), list), "category_root_missing")
                return {str(v["value"]): int(v["quantity"]) for v in roots[0]["values"]}
            counts = cat_counts(before)
            require(counts == cat_counts(after) and sum(counts.values()) == expected_root, "catalog_total_changed")
            ids: set[str] = set()
            sku_ids: set[str] = set()
            partition_ids: dict[str, set[str]] = {}
            partition_totals: dict[str, int] = {}
            rows: list[dict] = []
            source_details: dict[str, dict] = {}
            page_evidence: list[dict] = []
            for page in pages:
                tag = page["tag"]
                require(tag in successful, "page_missing:" + tag)
                record = successful[tag]
                require(record.get("url") == page.get("url") and record.get("sha256") == page.get("sha256"), "plan_ledger_mismatch")
                doc = json.loads(body(record))
                products = doc.get("products")
                require(isinstance(products, list) and len(products) == page.get("expected_count"), "page_count_changed")
                require(doc.get("recordsFiltered") == page.get("expected_total"), "partition_total_changed")
                pids = [p.get("productId") for p in products]
                require(all(isinstance(pid, str) and pid for pid in pids) and len(set(pids)) == len(pids), "product_id_invalid")
                require(not ids.intersection(pids), "product_membership_overlap")
                ids.update(pids)
                category = str(page["category_value"])
                partition_ids.setdefault(category, set()).update(pids)
                partition_totals[category] = int(page["expected_total"])
                incoming, details = parse_products(products)
                require(not sku_ids.intersection(details), "sku_membership_overlap")
                sku_ids.update(details)
                rows.extend(incoming)
                source_details.update(details)
                page_evidence.append({"url": record["url"], "sha256": record["sha256"], "observed_at": record["observed_at"]})
            require({k: len(v) for k, v in partition_ids.items()} == counts, "partition_membership_incomplete")
            require(len(ids) == expected_root and len(rows) == len(sku_ids), "catalog_membership_incomplete")
            require(sum(partition_totals.values()) == expected_root, "catalog_total_mismatch")
            times = [datetime.fromisoformat(str(r["observed_at"]).replace("Z", "+00:00")) for r in page_evidence]
            rows.sort(key=lambda row: row["source_key"])
            snapshots.append({
                "result": "success",
                "supermarket_id": SUPERMARKET_ID,
                "location_id": location_id,
                "city": city,
                "currency": "HNL",
                "scope": SCOPE,
                "seller_id": seller,
                "store_name": store_name,
                "region_id": base64.b64encode(("SW#" + seller).encode()).decode(),
                "sales_channel": SALES_CHANNEL,
                "catalog_complete": True,
                "validation_passed": True,
                "location_verified_same_run": True,
                "observed_at_utc": max(times).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "observation_started_at_utc": min(times).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "catalog_products_reported": expected_root,
                "unique_products_extracted": len(ids),
                "skus_extracted": len(rows),
                "skus_with_price": sum(row["current_price"] is not None for row in rows),
                "membership_count": len(ids),
                "membership_sha256": hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest(),
                "availability_counts": dict(Counter(row["availability"] for row in rows)),
                "promotion_counts": {
                    "promotion": sum(row["is_promotion"] is True for row in rows),
                    "not_promotion": sum(row["is_promotion"] is False for row in rows),
                    "unknown": sum(row["is_promotion"] is None for row in rows),
                },
                "products": rows,
                "source_details": source_details,
                "page_evidence": page_evidence,
            })
        return snapshots
    finally:
        for archive in archives.values():
            archive.close()
