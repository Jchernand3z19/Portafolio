#!/usr/bin/env python3
"""Ejecuta una prueba live limitada del catálogo público de La Colonia."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.models import RawProduct  # noqa: E402
from precios_supermercados.scrapers.base import ScraperError  # noqa: E402
from precios_supermercados.scrapers.la_colonia import LaColoniaExtractor  # noqa: E402


DIRECTED_PROBES: tuple[tuple[str, str], ...] = (
    ("weighted", "fresa"),
    ("promotional", "churros"),
    ("multi_sku", "coca cola"),
)


def _sanitized_product(product: RawProduct) -> dict[str, Any]:
    values = product.raw_values
    return {
        "source_key_type": product.source_key_type.value,
        "source_key": product.source_key,
        "source_name": product.source_name,
        "product_url": product.product_url,
        "source_brand": product.source_brand,
        "source_presentation": product.source_presentation,
        "source_category": product.source_category,
        "current_price": values.get("current_price"),
        "reported_regular_price": values.get("reported_regular_price"),
        "is_promotion": values.get("is_promotion"),
        "availability": values.get("availability"),
        "weighted_product": values.get("weighted_product"),
        "product_id": values.get("product_id"),
        "location_id": product.location_id,
        "location_status": product.location_status.value,
    }


def _multi_sku_matches(products: tuple[RawProduct, ...]) -> list[RawProduct]:
    grouped: dict[str, list[RawProduct]] = defaultdict(list)
    for product in products:
        product_id = str(product.raw_values.get("product_id") or "")
        if product_id:
            grouped[product_id].append(product)
    return [sku for group in grouped.values() if len(group) > 1 for sku in group]


def _probe_matches(kind: str, products: tuple[RawProduct, ...]) -> list[RawProduct]:
    if kind == "weighted":
        return [product for product in products if product.raw_values.get("weighted_product")]
    if kind == "promotional":
        return [product for product in products if product.raw_values.get("is_promotion")]
    if kind == "multi_sku":
        return _multi_sku_matches(products)
    return []


def _execute_probe(
    extractor: LaColoniaExtractor,
    *,
    run_id: str,
    kind: str,
    search_text: str,
    product_limit: int,
) -> dict[str, Any]:
    try:
        result = extractor.extract_page(
            scrape_run_id=f"{run_id}_{kind}",
            page=1,
            page_size=product_limit,
            full_text=search_text,
        )
    except ScraperError as exc:
        return {
            "kind": kind,
            "search_text": search_text,
            "found": False,
            "error": str(exc),
        }

    matches = _probe_matches(kind, result.products)
    return {
        "kind": kind,
        "search_text": search_text,
        "found": bool(matches),
        "products_requested": result.metrics.products_requested,
        "products_returned": result.metrics.products_returned,
        "skus_returned": result.metrics.skus_returned,
        "skus_extracted": result.metrics.skus_extracted,
        "matching_skus": len(matches),
        "sample": [_sanitized_product(product) for product in matches[:3]],
        "quality_events": result.quality_events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--directed-limit", type=int, default=3, choices=range(1, 4))
    parser.add_argument("--skip-directed", action="store_true")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("live_la_colonia_%Y%m%dT%H%M%SZ")
    extractor = LaColoniaExtractor()
    try:
        result = extractor.extract_page(
            scrape_run_id=run_id,
            page=args.page,
            page_size=args.products,
        )
    except ScraperError as exc:
        print(json.dumps({"accepted": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    weighted_skus = sum(
        1 for product in result.products if product.raw_values.get("weighted_product")
    )
    promotional_skus = sum(
        1 for product in result.products if product.raw_values.get("is_promotion")
    )

    directed_probes: list[dict[str, Any]] = []
    if not args.skip_directed:
        for kind, search_text in DIRECTED_PROBES:
            directed_probes.append(
                _execute_probe(
                    extractor,
                    run_id=run_id,
                    kind=kind,
                    search_text=search_text,
                    product_limit=args.directed_limit,
                )
            )

    metrics = result.metrics
    output = {
        "accepted": result.accepted,
        "source_url_path": "/_v/segment/graphql/v1",
        "products_requested": metrics.products_requested,
        "products_returned": metrics.products_returned,
        "skus_returned": metrics.skus_returned,
        "skus_extracted": metrics.skus_extracted,
        "skus_with_price": metrics.skus_with_price,
        "weighted_skus": weighted_skus,
        "promotional_skus": promotional_skus,
        "duplicate_skus": metrics.duplicate_skus,
        "errors": metrics.errors,
        "structural_events": metrics.structural_events,
        "products_discovered": metrics.products_discovered,
        "pages_discovered": metrics.pages_discovered,
        "quality_events": result.quality_events,
        "products": [_sanitized_product(product) for product in result.products],
        "directed_probes": directed_probes,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
