"""Reproduce this captured probe offline; not a production parser or downloader."""
import base64
import hashlib
import json
import math
import sys
import tarfile
from collections import Counter
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class HtmlEvidence(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.scripts = []
        self.text = []
        self.script = False
        self.hidden = 0
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg"}:
            self.hidden += 1
        if tag == "script":
            self.script = True
            self.scripts.append([dict(attrs), ""])

    def handle_endtag(self, tag):
        if tag in {"script", "style", "svg"}:
            self.hidden -= 1
        if tag == "script":
            self.script = False

    def handle_data(self, data):
        if self.script:
            self.scripts[-1][1] += data
        elif not self.hidden and data.strip():
            self.text.append(data.strip())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def rows(document):
    products = document if isinstance(document, list) else document["products"]
    result = {}
    for product in products:
        for item in product["items"]:
            require(len(item["sellers"]) == 1, "Ambiguous offer in probe")
            seller = item["sellers"][0]
            offer = seller["commertialOffer"]
            current = Decimal(str(offer["Price"]))
            regular = Decimal(str(offer["ListPrice"]))
            require(current.is_finite() and current >= 0, "Invalid effective price")
            require(regular.is_finite() and regular >= current, "Invalid list price")
            key = item["itemId"]
            require(key and key not in result, "Duplicate/missing SKU")
            # A positive public offer is not an exact physical inventory count.
            quantity = offer.get("AvailableQuantity")
            unpriced = current == 0 and regular == 0 and quantity == 0
            require(current > 0 or unpriced, "Ambiguous zero-price offer")
            availability = "unknown" if quantity is None else (
                "in_stock" if quantity > 0 else "out_of_stock"
            )
            result[key] = {
                "supermarket_id": "walmart", "source_key_type": "item_id",
                "source_key": key, "source_catalog_product_id": product["productId"],
                "source_name": product["productName"], "source_brand": product.get("brand"),
                "source_ean": item.get("ean"), "categories": product["categories"],
                "source_measurement_unit": item.get("measurementUnit"),
                "source_unit_multiplier": item.get("unitMultiplier"),
                "current_price": None if unpriced else str(current),
                "reported_regular_price": None if unpriced else str(regular),
                "is_promotion": None if unpriced else regular > current,
                "availability": availability,
                "source_price": str(current), "source_list_price": str(regular),
                "price_status": "unavailable_zero_offer" if unpriced else "observed",
                "source_seller_id": seller["sellerId"],
                "source_offer_origin": item.get("offerOrigin"),
            }
    return result


def reproduce(archive_path):
    with tarfile.open(archive_path, "r:gz") as archive:
        require(all(m.isfile() and "/" not in m.name for m in archive), "Unsafe archive member")
        raw = {m.name: archive.extractfile(m).read() for m in archive}
    ledger = json.loads(raw["ledger.json"])
    requests = ledger["requests"]
    require(len(requests) == 20, "Unexpected request count")
    require(len({r["url"] for r in requests}) == 20, "Unexpected duplicate request")
    require(not any(r["retry"] for r in requests), "Unexpected retry")
    for request in requests:
        body = raw[request["raw"]]
        require(len(body) == request["bytes"], "RAW length mismatch")
        require(hashlib.sha256(body).hexdigest() == request["sha256"], "RAW hash mismatch")
        require(request["method"] == "GET", "Unexpected mutation")
        parsed = urlsplit(request["url"])
        require(parsed.hostname in {"www.walmart.com.hn", "walmarthn.vtexassets.com"}, "Unexpected host")
        require(not any(p in parsed.path for p in ["/checkout", "/sessions", "/pvt/"]), "Unexpected endpoint")
    starts = [datetime.fromisoformat(r["started_utc"]) for r in requests]
    require(all((b-a).total_seconds() >= 1 for a, b in zip(starts, starts[1:])), "Pacing violation")
    require(ledger["elapsed_seconds"] < 600, "Duration exceeded")
    require(Counter(r["status"] for r in requests) == {200: 17, 206: 2, 400: 1}, "Unexpected status")

    documents = {int(name[:2]): json.loads(body) for name, body in raw.items()
                 if name.endswith(".raw") and int(name[:2]) not in {1, 4, 11, 16}}
    home = HtmlEvidence(raw["01.raw"].decode())
    script_urls = {attrs.get("src") for attrs, _ in home.scripts}
    for number in [4, 11]:
        require(requests[number-1]["url"] in script_urls, "Script not linked by HTML")
    configs = []
    for _, body in home.scripts:
        try:
            document = json.loads(body)
        except ValueError:
            continue
        configs.extend(node["storesArr"] for node in walk(document) if "storesArr" in node)
    require(len(configs) == 2, "Unexpected store configuration")
    sellers = ["walmarthnwm947", "walmarthnwm4041", "walmarthnwm4410"]
    stores = {seller: next(s for s in configs[0] if s["sellerId"] == seller) for seller in sellers}
    require(sum(s["canton"] == "San Pedro Sula" for s in configs[0]) == 1, "SPS selector changed")
    selector = raw["04.raw"].decode()
    require('regionId:btoa("SW#".concat(U[H].sellerId))' in selector, "Region formula changed")
    require('value:"accesscontrollist=".concat(t,";")' in selector, "Store facet changed")
    for number, seller in zip([6, 7, 8], sellers):
        url = requests[number-1]["url"]
        region = parse_qs(urlsplit(url).query)["regionId"][0]
        require(base64.b64decode(region).decode() == "SW#"+seller, "Wrong region binding")
        require("/accesscontrollist/"+seller in url, "Wrong membership binding")

    samples = {n: rows(documents[n]) for n in [2, 3, 5, 6, 7, 8, 9, 10, 12, 19, 20]}
    require(len(samples[2]) == 1 and all(len(samples[n]) == 50 for n in [3, 6, 7, 8]), "Sample size mismatch")
    banana = samples[2]["37305"]
    require(Decimal(banana["current_price"]) == Decimal("9.5"), "First product changed")
    pdp = HtmlEvidence(raw["16.raw"].decode())
    require("L.9.50" in " ".join(pdp.text), "Rendered price mismatch")
    require(banana["source_ean"] in " ".join(pdp.text), "Rendered EAN mismatch")
    require(banana["source_name"] in " ".join(pdp.text), "Rendered name mismatch")
    require(documents[2][0]["items"][0]["sellers"][0]["commertialOffer"]["FullSellingPrice"] == 2.37,
            "Weighted-price counterexample changed")

    shared = sorted(samples[7].keys() & samples[8].keys())
    require(len(shared) == 41, "TGU intersection changed")
    fields = ["current_price", "reported_regular_price", "is_promotion", "availability"]
    differences = {f: [k for k in shared if samples[7][k][f] != samples[8][k][f]] for f in fields}
    require(differences == {"current_price": [], "reported_regular_price": ["68100"],
                            "is_promotion": ["68100"], "availability": []}, "TGU comparison changed")
    for number, regular in [(7, "2195.0"), (8, "1895.0"), (9, "2195.0"), (10, "1895.0"), (12, "1895.0")]:
        row = samples[number]["68100"]
        require(row["reported_regular_price"] == regular and row["current_price"] == "1895.0", "Price reproduction failed")
    control_before, control_after = [urlsplit(requests[n-1]["url"]) for n in [9, 12]]
    require(control_before.path == control_after.path, "Membership changed in causal control")
    before, after = [parse_qs(url.query) for url in [control_before, control_after]]
    require([k for k in before if before[k] != after[k]] == ["regionId"], "Control changed more than region")

    child_keys = {v["value"] for f in documents[18]["facets"] if f["key"] == "category-2" for v in f["values"]}
    estimates = {}
    for number, seller in zip([13, 14, 15], sellers):
        facets = {f["key"]: f["values"] for f in documents[number]["facets"]}
        total = documents[number-7]["recordsFiltered"]
        require(sum(v["quantity"] for v in facets["category-1"]) == total, "Department totals mismatch")
        large = [v for v in facets["category-1"] if v["quantity"] > 2500]
        require(len(large) == 1 and large[0]["value"] == "articulos-para-el-hogar", "Unexpected large department")
        children = [v for v in facets["category-2"] if v["value"] in child_keys]
        require(sum(v["quantity"] for v in children) == large[0]["quantity"], "Child totals mismatch")
        partitions = [v for v in facets["category-1"] if v["quantity"] <= 2500] + children
        estimates[seller] = {"indexed_products": total, "partitions": len(partitions),
                             "estimated_pages_50": sum(math.ceil(v["quantity"]/50) for v in partitions),
                             "category_2_only_missing": total-sum(v["quantity"] for v in facets["category-2"])}
    require(documents[17]["error"] == "INVALID_PARAMETERS", "Pagination boundary changed")
    require(documents[19]["recordsFiltered"] == documents[20]["recordsFiltered"] == 409, "Partition total mismatch")
    require(len(samples[19]) == 50 and len(samples[20]) == 9, "First/last partition page mismatch")
    require(not samples[19].keys() & samples[20].keys(), "First and last page overlap")
    unique_skus = set().union(*(r.keys() for r in samples.values()))

    return {
        "status": "probe_verified_not_full_catalog", "remote_persistence": False,
        "authorization_start_utc": ledger["authorization_start_utc"],
        "authorization_end_utc": ledger["authorization_end_utc"],
        "raw_archive_sha256": hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
        "acquisition": {"requests": 20, "successful_requests": 19, "expected_boundary_errors": 1,
                        "retries": 0, "concurrency": 1, "elapsed_seconds": ledger["elapsed_seconds"],
                        "body_bytes": sum(r["bytes"] for r in requests),
                        "sku_observations": sum(len(r) for r in samples.values()),
                        "distinct_skus": len(unique_skus), "distinct_skus_per_request": len(unique_skus)/20,
                        "requests_per_distinct_sku": 20/len(unique_skus), "requests_per_complete_catalog": None,
                        "duplicate_http_requests": 0, "repeated_sku_observations": sum(len(r) for r in samples.values())-len(unique_skus),
                        "duplicate_requests_avoided": None,
                        "first_request_utc": requests[0]["started_utc"], "last_request_utc": requests[-1]["started_utc"]},
        "stores": stores, "first_product": banana,
        "samples": {s: list(samples[n].values()) for n, s in zip([3, 6, 7, 8], ["unbound"]+sellers)},
        "tgu_comparison": {"shared_skus": shared, "differences": differences,
                           "shared_categories": dict(sorted(Counter(samples[7][k]["categories"][-1] for k in shared).items())),
                           "unmatched_each_side": 9, "decision": "separate_commercial_contexts",
                           "region_only_control_requests": [9, 12]},
        "full_estimates": estimates,
        "unpriced_partition_rows": [r for n in [19, 20] for r in samples[n].values() if r["current_price"] is None],
        "limits": ["Not a full catalog or accepted persistence snapshot", "No second independent observation",
                   "Public offer availability, not exact physical inventory", "Generic seller 1 is not the location identity",
                   "TGU child partition hierarchy still needs contextual confirmation during full preflight",
                   "Maximum supported page_size above 50 was not probed", "Response bodies saved decoded by requests; headers not archived"],
    }


if __name__ == "__main__":
    path = Path(__file__).with_name("raw-capture.tar.gz")
    result = reproduce(path)
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        require(result == json.loads(Path(__file__).with_name("evidence.json").read_text()), "Derived evidence differs")
        print("Verified: 20 RAW hashes, 200 sample rows, 41 shared TGU SKUs, regional price control, pagination and estimates")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
