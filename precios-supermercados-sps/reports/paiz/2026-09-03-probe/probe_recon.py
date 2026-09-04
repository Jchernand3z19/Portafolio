#!/usr/bin/env python3
"""Bounded public read-only reconnaissance for Paiz Honduras.

This is evidence tooling, not a production scraper. It performs a fixed, sequential
set of GET requests with no retries, writes immutable response bodies and a ledger,
and never follows the work into checkout/login/cart endpoints.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

BASE = "https://www.paiz.com.hn"
REQUESTS = [
    ("home", "/"),
    ("exclusivas", "/Exclusivas"),
    ("catalog-search-one", "/api/catalog_system/pub/products/search?_from=0&_to=0"),
    ("facets-root", "/api/catalog_system/pub/facets/search?map=c"),
    ("segments", "/api/segments"),
]
MAX_REQUESTS = 12
UA = "Mozilla/5.0 (compatible; PreciosSupermercadosSPS-PaizRecon/1.0; read-only)"


def safe_name(tag: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", tag.lower())


def main() -> None:
    out = Path("paiz-recon-artifact")
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    records = []
    for index, (tag, path) in enumerate(REQUESTS, start=1):
        if index > MAX_REQUESTS:
            raise SystemExit("request_budget_exceeded")
        url = BASE + path
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.paiz.com.hn":
            raise SystemExit("origin_not_allowed")
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET")
        started = time.time()
        status = None
        response_url = None
        headers = {}
        body = b""
        error = None
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
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
        except Exception as exc:  # evidence records transport failure without retry
            error = f"{type(exc).__name__}:{exc}"
        elapsed = round(time.time() - started, 3)
        filename = None
        digest = None
        if body:
            digest = hashlib.sha256(body).hexdigest()
            filename = f"{index:02d}-{safe_name(tag)}.body"
            (raw / filename).write_bytes(body)
        record = {
            "index": index,
            "tag": tag,
            "method": "GET",
            "url": url,
            "response_url": response_url,
            "status": status,
            "elapsed_seconds": elapsed,
            "content_type": headers.get("content-type"),
            "content_length_observed": len(body),
            "sha256": digest,
            "file": f"raw/{filename}" if filename else None,
            "headers": headers,
            "error": error,
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    homepage = (raw / "01-home.body").read_text("utf-8", errors="replace") if (raw / "01-home.body").exists() else ""
    needles = ["vtex", "accesscontrollist", "regionId", "sellerId", "storesArr", "__STATE__", "__RUNTIME__", "api/catalog_system", "graphql"]
    evidence = {
        "request_count": len(records),
        "retry_count": 0,
        "concurrency": 1,
        "origin": BASE,
        "homepage_markers": {needle: (needle.lower() in homepage.lower()) for needle in needles},
        "homepage_script_srcs": sorted(set(re.findall(r'<script[^>]+src=[\"\']([^\"\']+)', homepage, flags=re.I)))[:200],
        "records": records,
    }
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
