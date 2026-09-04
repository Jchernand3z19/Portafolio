#!/usr/bin/env python3
"""Probe only the two active public Tegucigalpa Paiz contexts discovered in SSR."""
from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlsplit

BASE = "https://www.paiz.com.hn"
SC = "2"
STORES = {
    "walmarthnsp633": {"name": "Paiz Multiplaza", "city": "Tegucigalpa", "postal_code": "633001"},
    "walmarthnsp4010": {"name": "Paiz Próceres", "city": "Tegucigalpa", "postal_code": "401001"},
}
MAX_REQUESTS = 8
UA = "Mozilla/5.0 (compatible; PreciosSupermercadosSPS-PaizContext/1.0; read-only)"


def region_id(seller: str) -> str:
    return base64.b64encode(("SW#" + seller).encode()).decode()


def request(tag: str, path: str, query: dict[str, str], out: Path, index: int) -> dict:
    url = BASE + path + "?" + urlencode(query)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "www.paiz.com.hn":
        raise SystemExit("origin_not_allowed")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
    started = time.time(); status = None; body = b""; headers = {}; error = None; response_url = None
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status; response_url = response.geturl(); body = response.read()
            headers = {k.lower(): v for k, v in response.headers.items() if k.lower() != "set-cookie"}
    except urllib.error.HTTPError as exc:
        status = exc.code; response_url = exc.geturl(); body = exc.read(); error = f"http_{exc.code}"
        headers = {k.lower(): v for k, v in exc.headers.items() if k.lower() != "set-cookie"}
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    filename = None; digest = None
    if body:
        filename = f"{index:02d}-{tag}.body"; (out / filename).write_bytes(body); digest = hashlib.sha256(body).hexdigest()
    row = {"index": index, "tag": tag, "method": "GET", "url": url, "response_url": response_url,
           "status": status, "elapsed_seconds": round(time.time()-started, 3), "content_type": headers.get("content-type"),
           "content_length_observed": len(body), "sha256": digest, "file": filename, "headers": headers, "error": error}
    print(json.dumps(row, ensure_ascii=False, sort_keys=True)); return row


def summarize_json(body: bytes) -> dict:
    try:
        doc = json.loads(body)
    except Exception:
        return {"json": False}
    if isinstance(doc, dict):
        return {"json": True, "keys": sorted(doc)[:40], "recordsFiltered": doc.get("recordsFiltered"),
                "product_count": len(doc.get("products", [])) if isinstance(doc.get("products"), list) else None,
                "facet_keys": [f.get("key") for f in doc.get("facets", [])] if isinstance(doc.get("facets"), list) else None}
    return {"json": True, "type": type(doc).__name__, "length": len(doc) if hasattr(doc, "__len__") else None}


def main() -> None:
    root = Path("paiz-context-artifact"); raw = root / "raw"; raw.mkdir(parents=True, exist_ok=True)
    records = []; summaries = {}; index = 0
    for seller, meta in STORES.items():
        rid = region_id(seller)
        common = {"regionId": rid, "sc": SC, "country": "HND"}
        candidates = [
            (f"{seller}-facets", f"/api/io/_v/api/intelligent-search/facets/accesscontrollist/{seller}", common),
            (f"{seller}-products", f"/api/io/_v/api/intelligent-search/product_search/accesscontrollist/{seller}",
             {**common, "count": "2", "page": "1"}),
        ]
        for tag, path, query in candidates:
            index += 1
            if index > MAX_REQUESTS: raise SystemExit("request_budget_exceeded")
            row = request(tag, path, query, raw, index); records.append(row)
            if row["file"]:
                summaries[tag] = summarize_json((raw / row["file"]).read_bytes())
    evidence = {"request_count": len(records), "retry_count": 0, "concurrency": 1, "sales_channel": SC,
                "stores": {s: {**m, "region_id": region_id(s)} for s,m in STORES.items()},
                "summaries": summaries, "records": records}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
