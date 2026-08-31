"""Reproduce bounded discovery evidence offline; not a catalog parser or downloader."""
from collections import Counter
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import tarfile
from urllib.parse import urljoin, urlsplit


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Node:
    def __init__(self, tag="root", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return " ".join(c.text() if isinstance(c, Node) else c for c in self.children).strip()

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()


class Html(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]
        self.comments = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].children.append(data.strip())

    def handle_comment(self, data):
        self.comments.append(data)


def inspect_products(body, source_index):
    html = Html(body)
    nodes = list(html.root.walk())
    # This evidence describes unpriced HTML. A changed source must not silently
    # retain that verdict, and commented template prices must never become offers.
    price_nodes = [n for n in nodes if n.has_class("precio_producto") or
                   n.has_class("precio_interno_producto") or n.attrs.get("itemprop") == "price"]
    require(not price_nodes, "Observed price markup: reassess source contract")
    result = []
    for card in (n for n in nodes if n.has_class("item_producto")):
        names = [n.text() for n in card.walk() if n.has_class("nombre_producto")]
        require(names, "Missing product name")
        name, _, code = names[0].partition("Código:")
        links = [n.attrs["href"] for n in card.walk() if n.tag == "a" and n.attrs.get("href")]
        require(links, "Missing product link")
        url = urljoin("https://maxidespensa.com.hn/", links[0])
        suffix = re.search(r"-(\d+)$", urlsplit(url).path)
        require(suffix is not None, "Missing URL identity candidate")
        code = code.strip()
        require(not code or code == suffix[1], "Visible code differs from URL")
        result.append({"source_name": name.strip(), "source_code": code or suffix[1],
                       "identity_evidence": "visible_code_and_url" if code else "url_suffix_only",
                       "source_url": url, "raw_index": source_index,
                       "current_price": None, "reported_regular_price": None,
                       "is_promotion": None, "availability": "unknown",
                       "supermarket_id": None, "location_id": None,
                       "accepted_for_persistence": False})
    require(len({p["source_code"] for p in result}) == len(result), "Duplicate product code")
    return result, sum('class="precio_producto"' in c for c in html.comments)


def inspect_locator(body):
    html = Html(body)
    script = next(n.text() for n in html.root.walk() if n.tag == "script" and "var json =" in n.text())
    tail = re.split(r"var json\s*=\s*", script, maxsplit=1)[1]
    # Captured literal uses a trailing comma. Decode data only, never execute JS.
    stores, _ = json.JSONDecoder().raw_decode(re.sub(r",\s*([}\]])", r"\1", tail))
    require(len({s["title"] for s in stores}) == len(stores), "Duplicate locator title")
    require(all(set(s) == {"title", "formato", "ubicacion", "horario", "geometry"} for s in stores),
            "Changed locator contract")
    formats = {n.attrs["value"]: n.text() for n in html.root.walk()
               if n.tag == "option" and n.attrs.get("value") in {"4", "6"}}
    require(formats == {"4": "Despensa", "6": "Maxi Despensa"}, "Unproven format mapping")
    require('json[i]["formato"] == 4' in script and 'json[i]["formato"] == 6' in script,
            "Missing map-only format filters")
    return stores, formats


def reproduce(archive_path):
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        require(all(m.isfile() and "/" not in m.name for m in members), "Unsafe archive member")
        require(len({m.name for m in members}) == len(members), "Duplicate archive member")
        raw = {m.name: archive.extractfile(m).read() for m in members}
    ledger = json.loads(raw["ledger.json"])
    requests = ledger["requests"]
    require(len(requests) == 21 and ledger["stopped"], "Probe not closed or count changed")
    require(ledger["limit_requests"] == 40 and ledger["concurrency"] == 1, "Budget changed")
    require(Counter(r.get("status", r.get("error")) for r in requests) == {200: 17, 301: 2, "Timeout": 2},
            "Unexpected status totals")
    require(sum(r["retry"] for r in requests) == 1, "Unexpected retries")
    redirects = [r for r in requests if r.get("status") == 301]
    require(all(r["location"].rstrip("/") == requests[0]["url"].rstrip("/") for r in redirects),
            "Redirect no longer reuses captured root")
    starts = [datetime.fromisoformat(r["started_utc"]) for r in requests]
    begin = datetime.fromisoformat(ledger["authorization_start_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(ledger["authorization_end_utc"].replace("Z", "+00:00"))
    require(all(begin <= t < end for t in starts), "Request outside authorization")
    require(all((b-a).total_seconds() >= 1 for a, b in zip(starts, starts[1:])), "Pacing violation")
    require(ledger["elapsed_seconds"] < 900, "Duration exceeded")
    for record in requests:
        require(record["method"] == "GET", "Unexpected mutation")
        require(urlsplit(record["url"]).hostname in {"maxidespensa.com.hn", "centroamerica.walmart.com"},
                "Unexpected origin")
        if "raw" not in record:
            require(record["error"] == "Timeout", "Missing response unexplained")
            continue
        body = raw[record["raw"]]
        require(len(body) == record["published_bytes"], "Published RAW length mismatch")
        require(hashlib.sha256(body).hexdigest() == record["published_sha256"], "Published RAW hash mismatch")
        for node in Html(body.decode()).root.walk():
            if node.tag == "input" and node.attrs.get("name") in {"_csrfToken", "_Token[fields]", "_Token[unlocked]"}:
                require(node.attrs.get("value") in {"", "[REDACTED]"}, "Unredacted form token")
    campaign, comments = inspect_products(raw["06.raw"].decode(), 6)
    regular, _ = inspect_products(raw["09.raw"].decode(), 9)
    inspect_products(raw["10.raw"].decode(), 10)
    inspect_products(raw["19.raw"].decode(), 19)
    stores, formats = inspect_locator(raw["03.raw"].decode())
    products = campaign + regular
    code_counts = Counter(p["source_code"] for p in products)
    return {"authorization": {k: ledger[k] for k in ("authorization_start_utc", "authorization_end_utc")},
            "metrics": {"total_requests": 21, "successful_requests": 17, "redirect_responses": 2,
                        "redirects_followed": 0, "timeouts": 2, "retries": 1, "assets": 1,
                        "duplicate_requests_avoided": len(redirects),
                        "elapsed_seconds": ledger["elapsed_seconds"], "products_extracted": len(products),
                        "unique_code_candidates": len(code_counts),
                        "products_per_product_listing_request": len(products)/2,
                        "requests_per_unique_code_candidate": len(requests)/len(code_counts),
                        "accepted_products": 0, "requests_per_complete_catalog": None},
            "formats": formats, "locator_counts": dict(Counter(s["formato"] for s in stores)),
            "locator_keys": sorted(stores[0]),
            "product_candidates": products, "commented_campaign_price_templates": comments,
            "codes_shared_between_listing_templates": sorted(k for k, v in code_counts.items() if v > 1),
            "commercial_comparison": {"comparable_skus": 0, "current_price_differences": None,
                                      "reported_regular_price_differences": None, "promotion_differences": None,
                                      "availability_only_differences": None,
                                      "decision": "unresolved_no_comparable_commercial_contexts"},
            "technical_verdict": "NO-GO TEMPORAL PARA PRICE TRACKING WEB",
            "online_destination": "unresolved_two_timeouts_no_authentication_conclusion",
            "remote_persistence": False, "new_production_integration": False}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("raw-capture.tar.gz")
    print(json.dumps(reproduce(path), ensure_ascii=False, indent=2))
