"""Walmart HN: normalize public VTEX offers and reconcile captured partitions offline."""
import base64
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STORES = {
    "walmarthnwm947": ("walmart_sps", "San Pedro Sula", "Walmart Boulevard del Norte"),
    "walmarthnwm4041": ("walmart_tgu_ffaa", "Tegucigalpa", "Walmart Boulevard FFAA - Fuerzas Armadas"),
    "walmarthnwm4410": ("walmart_tgu_el_sauce", "Tegucigalpa", "Walmart Las Uvas  - El Sauce"),
}
SCOPE = "public_ecommerce_selected_store_not_universal_city_price"


class WalmartError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise WalmartError(reason)


def money(value):
    require(type(value) in {int, float, str}, "price_type_invalid")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise WalmartError("price_invalid") from exc
    require(amount.is_finite() and amount >= 0 and amount * 100 == (amount * 100).to_integral_value(), "price_invalid")
    return format(amount, ".2f")


def parse_products(products):
    rows, details = [], {}
    for product in products:
        pid = product.get("productId")
        require(isinstance(pid, str) and pid.isdigit() and int(pid) > 0, "product_id_invalid")
        require(isinstance(product.get("items"), list) and product["items"], "variants_missing")
        for item in product["items"]:
            sku = item.get("itemId")
            require(isinstance(sku, str) and sku.isdigit() and int(sku) > 0, "sku_invalid")
            require(sku not in details, "sku_duplicate")
            sellers = item.get("sellers")
            require(isinstance(sellers, list) and len(sellers) == 1, "offer_ambiguous")
            offer = sellers[0]["commertialOffer"]
            current, regular = money(offer.get("Price")), money(offer.get("ListPrice"))
            quantity = offer.get("AvailableQuantity")
            require(quantity is None or (type(quantity) in {int, float} and math.isfinite(quantity) and quantity >= 0), "availability_invalid")
            availability = "unknown" if quantity is None else "in_stock" if quantity > 0 else "out_of_stock"
            unpriced = current == regular == "0.00" and quantity == 0
            require(current != "0.00" or unpriced, "zero_price_ambiguous")
            require(Decimal(regular) >= Decimal(current), "regular_below_effective")
            name = item.get("nameComplete") or item.get("name") or product.get("productName")
            require(isinstance(name, str) and name.strip(), "name_missing")
            references = item.get("referenceId") or []
            reference = next((r.get("Value") for r in references if r.get("Key") == "RefId"), None)
            categories = product.get("categories") or []
            presentation = next(("; ".join(p["values"]) for p in product.get("properties", [])
                                 if p.get("name", "").lower() in {"presentación", "presentacion"}), None)
            rows.append({
                "product_id": pid, "item_id": sku, "source_key_type": "item_id", "source_key": sku,
                "source_name": name.strip(), "brand": product.get("brand"), "reference": reference,
                "ean": item.get("ean") or None, "category": categories[0] if categories else None,
                "presentation": presentation, "current_price": None if unpriced else current,
                "reported_regular_price": None if unpriced else regular,
                "is_promotion": None if unpriced else Decimal(regular) > Decimal(current),
                "availability": availability,
            })
            details[sku] = {"price_status": "unavailable_zero_offer" if unpriced else "observed",
                            "source_price": current, "source_list_price": regular,
                            "available_quantity_signal": quantity,
                            "measurement_unit": item.get("measurementUnit"), "unit_multiplier": item.get("unitMultiplier"),
                            "offer_origin": item.get("offerOrigin"), "seller_id": sellers[0].get("sellerId")}
    return rows, details


class _Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.bodies, self.active = [], False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = True
            self.bodies.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.bodies[-1] += data


def verify_stores(html):
    def walk(value):
        if isinstance(value, dict):
            if "storesArr" in value:
                yield value["storesArr"]
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
    configs = []
    for body in _Scripts(html).bodies:
        try:
            configs.extend(walk(json.loads(body)))
        except ValueError:
            continue
    require(configs, "store_configuration_missing")
    for seller, (_, city, label) in STORES.items():
        for config in configs:
            matches = [s for s in config if s.get("sellerId") == seller]
            require(len(matches) == 1 and matches[0]["name"] == label, "store_configuration_changed")
            require(city in matches[0]["canton"], "store_city_changed")


def reconcile_capture(directory):
    directory = Path(directory)
    ledger = json.loads((directory / "requests.json").read_text())
    records = ledger["records"]
    successful = {r["tag"]: r for r in records if r.get("status") == 200}
    for record in records:
        url = urlsplit(record["url"])
        require(record["method"] == "GET" and url.scheme == "https" and url.netloc == "www.walmart.com.hn", "source_origin_invalid")
        if "/accesscontrollist/" in url.path:
            seller = url.path.split("/accesscontrollist/")[1].split("/")[0]
            query = parse_qs(url.query)
            require(seller in STORES and query.get("regionId") == [base64.b64encode(("SW#"+seller).encode()).decode()]
                    and query.get("sc") == ["1"] and query.get("country") == ["HND"], "commercial_scope_mismatch")
    def body(record):
        name = Path(record["file"])
        require(not name.is_absolute() and ".." not in name.parts, "unsafe_raw_path")
        raw = (directory / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == record["sha256"], "raw_hash_mismatch")
        return raw
    for record in records:
        if record.get("file"):
            body(record)
    verify_stores(body(successful["fresh-store-configuration"]).decode())
    plan = json.loads((directory / "catalog-plan.json").read_text())
    repartitions = json.loads((directory / "partition-recovery.json").read_text()) if (directory / "partition-recovery.json").exists() else []
    for repair in repartitions:
        original = [p for p in plan if urlsplit(p["url"]).path == repair["original_path"]]
        require(original and len({p["expected_total"] for p in original}) == 1, "repartition_original_invalid")
        total = original[0]["expected_total"]
        old_ids = {p["productId"] for page in original for p in json.loads(body(successful[page["tag"]]))["products"]}
        require(len(old_ids) < total, "repartition_of_complete_scope_forbidden")
        facets = json.loads(body(successful[repair["facets_tag"]]))
        children = next(f["values"] for f in facets["facets"] if f["key"] == "category-2")
        require(sum(c["quantity"] for c in children) == total, "repartition_count_mismatch")
        filename = Path(repair["replacement_plan"])
        require(len(filename.parts) == 1, "unsafe_plan_path")
        replacement = json.loads((directory / filename).read_text())
        expected_paths = {repair["original_path"] + "/category-2/" + c["value"]: c["quantity"] for c in children}
        require({urlsplit(p["url"]).path for p in replacement} == set(expected_paths), "repartition_paths_mismatch")
        require(all(p["expected_total"] == expected_paths[urlsplit(p["url"]).path] for p in replacement), "repartition_total_mismatch")
        new_ids = {p["productId"] for page in replacement for p in json.loads(body(successful[page["tag"]]))["products"]}
        require(old_ids <= new_ids and len(new_ids) == total, "repartition_membership_incomplete")
        index = plan.index(original[0])
        plan = [p for p in plan if p not in original]
        plan[index:index] = replacement
    recovery = json.loads((directory / "recovery.json").read_text()) if (directory / "recovery.json").exists() else []
    for repair in recovery:
        original = next(p for p in plan if p["tag"] == repair["original_tag"])
        old_url = urlsplit(original["url"])
        old_query = parse_qs(old_url.query)
        old_count, old_page = int(old_query["count"][0]), int(old_query["page"][0])
        old_ids = {p["productId"] for p in json.loads(body(successful[original["tag"]]))["products"]}
        duplicated = set()
        if repair.get("overlap_with"):
            other = next(p for p in plan if p["tag"] == repair["overlap_with"])
            require(urlsplit(other["url"]).path == old_url.path, "overlap_scope_changed")
            duplicated = old_ids & {p["productId"] for p in json.loads(body(successful[other["tag"]]))["products"]}
        require(len(old_ids) < original["expected_count"] or duplicated, "recovery_of_complete_page_forbidden")
        fixed, ranges, recovered_ids = [], [], set()
        for tag in repair["replacement_tags"]:
            row = successful[tag]
            url = urlsplit(row["url"])
            query = parse_qs(url.query)
            require(url.path == old_url.path and {k: v for k, v in query.items() if k not in {"count", "page"}} ==
                    {k: v for k, v in old_query.items() if k not in {"count", "page"}}, "recovery_scope_changed")
            count, page = int(query["count"][0]), int(query["page"][0])
            ranges.extend(range((page-1)*count, page*count))
            recovered_ids.update(p["productId"] for p in json.loads(body(row))["products"])
            fixed.append({"tag": tag, "url": row["url"], "expected_count": count,
                          "expected_total": original["expected_total"], "scope_seller": repair["original_tag"].split('/')[0]})
        require(sorted(ranges) == list(range((old_page-1)*old_count, (old_page-1)*old_count+original["expected_count"])), "recovery_window_changed")
        require(old_ids - duplicated <= recovered_ids and len(recovered_ids) == original["expected_count"], "recovery_membership_incomplete")
        index = plan.index(original)
        plan[index:index+1] = fixed
    snapshots = []
    for seller, (location, city, _) in STORES.items():
        pages = [p for p in plan if p["tag"].startswith(seller + "/") or p.get("scope_seller") == seller]
        require(pages, "scope_plan_missing")
        roots = [json.loads(body(successful[seller + "-root-" + phase])) for phase in ["before", "after"]]
        facets = [{f["key"]: f["values"] for f in root["facets"]} for root in roots]
        counts = [{v["value"]: v["quantity"] for v in f["category-1"]} for f in facets]
        require(counts[0] == counts[1], "catalog_total_changed")
        home = [json.loads(body(successful[seller + "-home-" + phase])) for phase in ["before", "after"]]
        home_counts = [{v["value"]: v["quantity"] for f in doc["facets"] if f["key"] == "category-2" for v in f["values"]} for doc in home]
        require(home_counts[0] == home_counts[1] and sum(home_counts[0].values()) == counts[0]["articulos-para-el-hogar"], "home_partition_changed")
        expected = sum(counts[0].values())
        ids, sku_ids, rows, source_details, page_evidence = set(), set(), [], {}, []
        partition_ids, partition_totals = {}, {}
        for page in pages:
            require(page["tag"] in successful, "page_missing:" + page["tag"])
            record = successful[page["tag"]]
            require(record["url"] == page["url"], "page_url_mismatch")
            url = urlsplit(record["url"])
            query = parse_qs(url.query)
            require(url.netloc == "www.walmart.com.hn" and url.scheme == "https", "source_origin_invalid")
            require("/accesscontrollist/" + seller + "/" in url.path, "membership_scope_mismatch")
            require(query.get("regionId") == [base64.b64encode(("SW#" + seller).encode()).decode()]
                    and query.get("sc") == ["1"] and query.get("country") == ["HND"], "commercial_scope_mismatch")
            doc = json.loads(body(record))
            pids = [p["productId"] for p in doc["products"]]
            require(len(pids) == page["expected_count"] and len(set(pids)) == len(pids), "page_count_or_duplicate")
            require(doc["recordsFiltered"] == page["expected_total"], "partition_total_changed")
            require(not ids.intersection(pids), "product_membership_overlap:" + page["tag"] + ":" + ",".join(sorted(ids.intersection(pids))))
            ids.update(pids)
            partition_ids.setdefault(url.path, set()).update(pids)
            partition_totals[url.path] = page["expected_total"]
            incoming, details = parse_products(doc["products"])
            require(not sku_ids.intersection(details), "sku_membership_overlap")
            sku_ids.update(details)
            rows.extend(incoming)
            source_details.update(details)
            page_evidence.append({k: record[k] for k in ["url", "sha256", "observed_at"]})
        require(all(len(v) == partition_totals[k] for k, v in partition_ids.items()), "partition_membership_incomplete")
        departments = Counter()
        for path, total in partition_totals.items():
            require("/category-1/" in path, "department_missing")
            departments[path.split("/category-1/")[1].split("/")[0]] += total
        require(dict(departments) == counts[0], "department_coverage_incomplete")
        require(len(ids) == expected and sum(partition_totals.values()) == expected, "catalog_membership_incomplete")
        times = [datetime.fromisoformat(r["observed_at"]) for r in page_evidence]
        rows.sort(key=lambda r: r["source_key"])
        snapshots.append({"result": "success", "supermarket_id": "walmart", "location_id": location,
            "city": city, "currency": "HNL", "scope": SCOPE, "seller_id": seller,
            "region_id": base64.b64encode(("SW#" + seller).encode()).decode(), "sales_channel": "1",
            "catalog_complete": True, "validation_passed": True, "location_verified_same_run": True,
            "observed_at_utc": max(times).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "observation_started_at_utc": min(times).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "catalog_products_reported": expected, "unique_products_extracted": len(ids),
            "skus_extracted": len(rows), "skus_with_price": sum(r["current_price"] is not None for r in rows),
            "membership_count": len(ids), "membership_sha256": hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest(),
            "availability_counts": dict(Counter(r["availability"] for r in rows)),
            "products": rows, "source_details": source_details, "page_evidence": page_evidence})
    return snapshots
