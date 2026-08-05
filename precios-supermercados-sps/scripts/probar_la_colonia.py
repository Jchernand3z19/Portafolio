#!/usr/bin/env python3
"""Ejecuta una prueba live limitada del catálogo público de La Colonia."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.scrapers.base import ScraperError  # noqa: E402
from precios_supermercados.scrapers.la_colonia import LaColoniaExtractor  # noqa: E402
from precios_supermercados.scrapers.la_colonia_graphql import (  # noqa: E402
    build_product_search_url,
)


def _sanitized_graphql_diagnostic(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Expone solo estructura y mensajes de error, nunca el cuerpo completo."""

    errors = payload.get("errors")
    sanitized_errors: list[dict[str, Any]] = []
    if isinstance(errors, list):
        for item in errors[:5]:
            if isinstance(item, Mapping):
                sanitized_errors.append(
                    {
                        "message": item.get("message"),
                        "extensions": item.get("extensions"),
                    }
                )
            else:
                sanitized_errors.append({"message": str(item)})
    return {
        "top_level_keys": sorted(str(key) for key in payload.keys()),
        "errors": sanitized_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, choices=range(3, 6))
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("live_la_colonia_%Y%m%dT%H%M%SZ")
    extractor = LaColoniaExtractor()
    source_url = build_product_search_url(page=args.page, page_size=args.limit)
    try:
        payload = extractor.client.get_json(source_url)
        if not isinstance(payload.get("data"), Mapping):
            print(
                json.dumps(
                    {
                        "accepted": False,
                        "error": "La respuesta GraphQL no contiene data.",
                        "diagnostic": _sanitized_graphql_diagnostic(payload),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        result = extractor.parse_payload(
            payload,
            scrape_run_id=run_id,
            source_url=source_url,
            page_size=args.limit,
        )
    except ScraperError as exc:
        print(json.dumps({"accepted": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    sample = []
    for product in result.products:
        values = product.raw_values
        sample.append(
            {
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
                "location_id": product.location_id,
                "location_status": product.location_status.value,
            }
        )

    output = {
        "accepted": result.accepted,
        "source_url_path": "/_v/segment/graphql/v1",
        "metrics": result.metrics.as_dict(),
        "quality_events": result.quality_events,
        "products": sample,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
