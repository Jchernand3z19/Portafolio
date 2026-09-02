#!/usr/bin/env python3
"""Verify the offline PriceSmart general-catalog preflight evidence."""

from __future__ import annotations

import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path


REPORT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REPORT_DIR.parents[2]
EVIDENCE = json.loads((REPORT_DIR / "evidence.json").read_text())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def visit(value: object, source: str, queries: list[dict], responses: list[dict]) -> None:
    if isinstance(value, dict):
        body_raw = value.get("body_raw")
        if isinstance(body_raw, str):
            try:
                visit(json.loads(body_raw), source, queries, responses)
            except json.JSONDecodeError:
                pass
        if "q" in value and "search_type" in value:
            queries.append(value)
        response = value.get("response")
        if isinstance(response, dict) and isinstance(response.get("docs"), list):
            responses.append(value)
        for child in value.values():
            visit(child, source, queries, responses)
    elif isinstance(value, list):
        for child in value:
            visit(child, source, queries, responses)


def main() -> None:
    queries: list[dict] = []
    responses: list[dict] = []
    commerce_asset: bytes | None = None
    product_html: bytes | None = None

    for archive_record in EVIDENCE["raw_archives"]:
        archive_path = PROJECT_ROOT / archive_record["path"]
        assert archive_path.stat().st_size == archive_record["bytes"]
        assert sha256(archive_path) == archive_record["sha256"]
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                assert extracted is not None
                content = extracted.read()
                if member.name == "raw/08-asset_commerce_vendor.html":
                    commerce_asset = content
                elif member.name == "raw/04-product_516411.html":
                    product_html = content
                if member.name.endswith(".json"):
                    try:
                        visit(json.loads(content), f"{archive_path}:{member.name}", queries, responses)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

    observed = EVIDENCE["discovery_observations"]
    assert len(queries) == observed["query_count"] == 194
    assert len(responses) == observed["response_count"] == 194
    assert {query["q"] for query in queries} == {"G10D03"}
    assert {query["search_type"] for query in queries} == {"category"}
    assert {query["rows"] for query in queries} == {12}
    assert {query["view_id"] for query in queries} == {"HN"}
    assert {response["response"]["numFound"] for response in responses} == {1124}
    assert Counter(len(response["response"]["docs"]) for response in responses) == Counter({12: 192, 8: 2})

    facets = [response["facet_counts"]["facet_fields"]["category"] for response in responses]
    structural_fields = ("cat_id", "cat_name", "crumb", "tree_path", "parent")
    structural_views = {
        json.dumps(
            sorted(
                ({key: row[key] for key in structural_fields} for row in facet),
                key=lambda row: row["cat_id"],
            ),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for facet in facets
    }
    assert len(structural_views) == 1
    assert {len(facet) for facet in facets} == {117}
    canonical = facets[-1]
    category_ids = {row["cat_id"] for row in canonical}
    assert category_ids == {node["category_id"] for node in EVIDENCE["g10d03_taxonomy"]["nodes"]}
    assert [row for row in canonical if not row["parent"]] == [
        {
            "cat_id": "G10D03",
            "cat_name": "Alimentos",
            "crumb": "/G10D03",
            "tree_path": "/G10D03,Alimentos",
            "count": 1124,
            "parent": "",
        }
    ]
    for row in canonical:
        if row["parent"]:
            assert row["parent"] in category_ids
            assert row["crumb"].startswith("/G10D03/")

    for response in responses:
        for document in response["response"]["docs"]:
            assert not any("cat" in key.lower() for key in document)

    assert commerce_asset is not None
    assert hashlib.sha256(commerce_asset).hexdigest() == EVIDENCE["offline_application_contract"]["source_asset_sha256"]
    for token in (
        b"getFacetCategories",
        b"onlyParent",
        b"parent is not defined",
        b"ancestors(id = ",
        b'n.post("/".concat(r,"/").concat(c),t)',
    ):
        assert token in commerce_asset
    assert product_html is not None
    assert b'middlewareUrl:"\\u002Fapi\\u002F"' in product_html
    assert b"G10D53001003" in product_html

    decision = EVIDENCE["decision"]
    assert decision["g10d03_complete"] is True
    assert decision["general_catalog_complete"] is False
    assert decision["root_taxonomy_demonstrated"] is False
    assert decision["full_request_budget_calculable"] is False
    assert decision["existing_alimentos_reusable_without_recrawl"] is True
    print("PriceSmart general-catalog offline preflight evidence: OK")


if __name__ == "__main__":
    main()
