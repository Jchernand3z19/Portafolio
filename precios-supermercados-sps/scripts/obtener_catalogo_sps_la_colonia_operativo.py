#!/usr/bin/env python3
"""Obtiene el catálogo SPS completo sin volver a ejecutar la radiografía.

El flujo operativo selecciona San Pedro Sula con el contrato DOM ya aprendido.
Para evitar la ventana VTEX de ~2,500 productos usa categorías cuando caben y
sólo divide por marca las ramas de categoría que siguen siendo demasiado grandes.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_particionado as base  # noqa: E402
import obtener_catalogo_sps_la_colonia_particionado_v2 as frontier  # noqa: E402
import obtener_catalogo_sps_la_colonia_particionado_v3 as brand  # noqa: E402
from precios_supermercados.scrapers.la_colonia_location import (  # noqa: E402
    LocationInitializationError,
    ensure_operational_city,
)

CAPTURE_STRATEGY = "operational_city_same_context_hybrid_partitions_productSearchV3"
PARTITION_STRATEGY = "category_frontier_with_brand_fallback"
LOCATION_VERIFICATION_METHOD = "structural_exact_city_control"
CATEGORY_KEY = re.compile(r"category-(\d+)\Z")
MAX_PLANNER_FACET_REQUESTS = 24


@dataclass(frozen=True, slots=True)
class HybridPartition:
    path: tuple[tuple[str, str], ...]
    quantity: int
    strategy: str


def _facet_url(selected_facets: Sequence[Mapping[str, str]]) -> str:
    variables = {
        "query": "supermercado",
        "fullText": "",
        "selectedFacets": [dict(item) for item in selected_facets],
        "from": 0,
        "to": 0,
    }
    return base._params(base.CATEGORY_TREE_OPERATION, base.CATEGORY_TREE_QUERY, variables)


def _fetch_normalized_facets(
    context: Any,
    selected_facets: Sequence[Mapping[str, str]],
    diagnostic: dict[str, Any],
) -> tuple[Mapping[str, Any], int]:
    diagnostic["planner_facet_requests"] += 1
    if diagnostic["planner_facet_requests"] > MAX_PLANNER_FACET_REQUESTS:
        raise base.full.FullCatalogError(
            "planner_facet_request_budget_exceeded", diagnostic=diagnostic
        )
    response = context.request.get(
        _facet_url(selected_facets),
        timeout=base.FACET_REQUEST_TIMEOUT_MS,
        fail_on_status_code=False,
    )
    payload = base._read_json_response(response, diagnostic, kind="catalog_facets")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise base.full.FullCatalogError("catalog_facets_data_missing", diagnostic=diagnostic)
    try:
        normalized = base.LaColoniaFacetDiscoveryAdapter._normalize_tree(data)
        total = int(normalized["recordsFiltered"])
    except Exception as exc:
        raise base.full.FullCatalogError(
            "catalog_facets_not_usable", diagnostic=diagnostic
        ) from exc
    if normalized.get("sampling") is not False:
        raise base.full.FullCatalogError(
            "catalog_facets_sampling_detected", diagnostic=diagnostic
        )
    return normalized, total


def _positive_children(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    children = node.get("children")
    if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
        return []
    return [
        child
        for child in children
        if isinstance(child, Mapping)
        and isinstance(child.get("quantity"), int)
        and not isinstance(child.get("quantity"), bool)
        and int(child.get("quantity")) > 0
    ]


def _plan_hybrid_partitions(
    context: Any,
    normalized: Mapping[str, Any],
    *,
    root_total: int,
    page_size: int,
    diagnostic: dict[str, Any],
) -> tuple[HybridPartition, ...]:
    try:
        roots = frontier._category_values(normalized)
    except Exception as exc:
        diagnostic["frontier_error"] = str(exc)[:120]
        raise base.full.FullCatalogError(
            "category_frontier_not_usable", diagnostic=diagnostic
        ) from exc

    partitions: list[HybridPartition] = []

    def split_by_brand(
        path: tuple[tuple[str, str], ...],
        quantity: int,
    ) -> int:
        selected = base._partition_facets(path)
        scoped, scoped_total = _fetch_normalized_facets(context, selected, diagnostic)
        if scoped_total != quantity:
            diagnostic["partition_expected_total"] = quantity
            diagnostic["partition_observed_total"] = scoped_total
            raise base.full.FullCatalogError(
                "scoped_category_total_mismatch", diagnostic=diagnostic
            )
        try:
            brand_values = brand._brand_values(scoped)
            brand_partitions = brand._build_brand_frontier(
                brand_values,
                search_window=base.SEARCH_WINDOW_MAX_PRODUCTS,
                max_partitions=base.MAX_PLANNED_PRODUCT_REQUESTS,
            )
        except Exception as exc:
            diagnostic["frontier_error"] = str(exc)[:120]
            raise base.full.FullCatalogError(
                "category_brand_fallback_not_usable", diagnostic=diagnostic
            ) from exc

        covered = sum(item.quantity for item in brand_partitions)
        if covered < quantity:
            diagnostic["partition_expected_total"] = quantity
            diagnostic["partition_observed_total"] = covered
            raise base.full.FullCatalogError(
                "brand_frontier_below_category_total", diagnostic=diagnostic
            )
        for item in brand_partitions:
            partitions.append(
                HybridPartition(
                    path=(*path, *item.path),
                    quantity=item.quantity,
                    strategy="category_brand",
                )
            )
        diagnostic["oversized_category_brand_splits"] += 1
        return covered

    def walk(
        node: Mapping[str, Any],
        *,
        parent_path: tuple[tuple[str, str], ...],
        parent_level: int | None,
    ) -> int:
        raw_key = node.get("key")
        raw_value = node.get("value")
        key = raw_key.strip() if isinstance(raw_key, str) else ""
        value = raw_value.strip() if isinstance(raw_value, str) else ""
        match = CATEGORY_KEY.fullmatch(key)
        if not match or not value:
            raise base.full.FullCatalogError(
                "invalid_category_identity", diagnostic=diagnostic
            )
        level = int(match.group(1))
        if parent_level is not None and level <= parent_level:
            raise base.full.FullCatalogError(
                "non_increasing_category_level", diagnostic=diagnostic
            )

        raw_quantity = node.get("quantity")
        if isinstance(raw_quantity, bool) or not isinstance(raw_quantity, int):
            raise base.full.FullCatalogError(
                "invalid_category_quantity", diagnostic=diagnostic
            )
        quantity = int(raw_quantity)
        if quantity <= 0:
            return 0

        path = (*parent_path, (key, value))
        if quantity <= base.SEARCH_WINDOW_MAX_PRODUCTS:
            partitions.append(HybridPartition(path=path, quantity=quantity, strategy="category"))
            return quantity

        children = _positive_children(node)
        child_quantity_sum = sum(int(child["quantity"]) for child in children)
        if children and child_quantity_sum >= quantity:
            covered = 0
            for child in children:
                covered += walk(child, parent_path=path, parent_level=level)
            return covered

        return split_by_brand(path, quantity)

    try:
        covered = 0
        for root in roots:
            if not isinstance(root, Mapping):
                raise base.full.FullCatalogError(
                    "category_root_not_object", diagnostic=diagnostic
                )
            covered += walk(root, parent_path=(), parent_level=None)
    except base.full.FullCatalogError:
        raise
    except Exception as exc:
        diagnostic["frontier_error"] = str(exc)[:120]
        raise base.full.FullCatalogError(
            "category_frontier_not_usable", diagnostic=diagnostic
        ) from exc

    if not partitions:
        raise base.full.FullCatalogError("partition_frontier_empty", diagnostic=diagnostic)

    quantity_sum = sum(item.quantity for item in partitions)
    diagnostic["partition_quantity_sum"] = quantity_sum
    diagnostic["partitions_detected"] = len(partitions)
    if covered < root_total or quantity_sum < root_total:
        raise base.full.FullCatalogError(
            "partition_frontier_below_root_total", diagnostic=diagnostic
        )

    planned_requests = sum(math.ceil(item.quantity / page_size) for item in partitions)
    diagnostic["planned_product_requests"] = planned_requests
    if planned_requests > base.MAX_PLANNED_PRODUCT_REQUESTS:
        raise base.full.FullCatalogError(
            "partition_request_budget_exceeded", diagnostic=diagnostic
        )
    return tuple(partitions)


def _run_catalog(*, page_size: int, delay_seconds: float) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise base.full.FullCatalogError("playwright_not_installed") from exc

    diagnostic: dict[str, Any] = {
        "location_verified_same_run": False,
        "region_binding_fingerprint_verified": False,
        "binding_source_key_verified": False,
        "pages_attempted": 0,
        "pages_completed": 0,
        "catalog_products_reported": 0,
        "skus_extracted": 0,
        "skus_with_price": 0,
        "duplicate_skus_across_pages": 0,
        "blocked_http_status_observed": None,
        "partitions_detected": 0,
        "partitions_completed": 0,
        "partition_quantity_sum": 0,
        "planned_product_requests": 0,
        "planner_facet_requests": 0,
        "oversized_category_brand_splits": 0,
    }
    run_id = f"sps_operational_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    unique_products: set[str] = set()
    unique_skus: set[tuple[str, str]] = set()
    all_products: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser, _ = base.full.launch_compatible_chromium(pw)
        try:
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            home = page.goto(
                base.full.radiography.TARGET_URL,
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            if home is not None and int(home.status) in {403, 429}:
                diagnostic["blocked_http_status_observed"] = int(home.status)
                raise base.full.FullCatalogError(
                    f"http_{home.status}", diagnostic=diagnostic
                )
            if base.full.passive._blocked_surface(page):
                raise base.full.FullCatalogError(
                    "blocked_or_login_surface", diagnostic=diagnostic
                )
            page.wait_for_timeout(250)

            try:
                ensure_operational_city(page, max_dom_reresolutions=1)
            except LocationInitializationError as exc:
                raise base.full.FullCatalogError(
                    exc.reason, diagnostic=diagnostic
                ) from exc
            diagnostic["location_verified_same_run"] = True

            normalized, root_total = _fetch_normalized_facets(
                context, [dict(base.ROOT_FACET)], diagnostic
            )
            if root_total <= 0:
                raise base.full.FullCatalogError(
                    "catalog_root_total_invalid", diagnostic=diagnostic
                )
            diagnostic["catalog_products_reported"] = root_total
            partitions = _plan_hybrid_partitions(
                context,
                normalized,
                root_total=root_total,
                page_size=page_size,
                diagnostic=diagnostic,
            )

            extractor = base.LaColoniaExtractor()
            for partition_index, partition in enumerate(partitions, start=1):
                facets = base._partition_facets(partition.path)
                expected_partition_total = int(partition.quantity)
                pages = max(math.ceil(expected_partition_total / page_size), 1)

                for partition_page in range(1, pages + 1):
                    request_url = base._product_url(
                        selected_facets=facets,
                        page=partition_page,
                        page_size=page_size,
                    )
                    diagnostic["pages_attempted"] += 1
                    response = context.request.get(
                        request_url,
                        timeout=base.PRODUCT_REQUEST_TIMEOUT_MS,
                        fail_on_status_code=False,
                    )
                    payload = base._read_json_response(
                        response, diagnostic, kind="product_search"
                    )
                    observed_total, products_returned = base._read_shape(payload)
                    if observed_total != expected_partition_total:
                        diagnostic["partition_expected_total"] = expected_partition_total
                        diagnostic["partition_observed_total"] = observed_total
                        raise base.full.FullCatalogError(
                            "partition_total_mismatch", diagnostic=diagnostic
                        )
                    expected_on_page = min(
                        page_size,
                        max(
                            expected_partition_total
                            - ((partition_page - 1) * page_size),
                            0,
                        ),
                    )
                    if products_returned != expected_on_page:
                        diagnostic["expected_products_on_page"] = expected_on_page
                        diagnostic["observed_products_on_page"] = products_returned
                        raise base.full.FullCatalogError(
                            "partial_or_unexpected_product_page", diagnostic=diagnostic
                        )

                    try:
                        result = extractor.parse_payload(
                            payload,
                            scrape_run_id=run_id,
                            source_url=request_url,
                            page_size=page_size,
                        )
                    except base.StructureChangedError as exc:
                        raise base.full.FullCatalogError(
                            "product_payload_not_parseable", diagnostic=diagnostic
                        ) from exc
                    if not result.accepted:
                        raise base.full.FullCatalogError(
                            "page_validation_failed", diagnostic=diagnostic
                        )

                    page_products = [
                        base.full.passive._public_product(product)
                        for product in result.products
                    ]
                    for product in page_products:
                        product_id = str(product.get("product_id") or "")
                        if product_id:
                            unique_products.add(product_id)
                        identity = (
                            str(product.get("source_key_type") or ""),
                            str(product.get("source_key") or ""),
                        )
                        if identity in unique_skus:
                            diagnostic["duplicate_skus_across_pages"] += 1
                            continue
                        unique_skus.add(identity)
                        all_products.append(product)
                        if product.get("current_price") is not None:
                            diagnostic["skus_with_price"] += 1
                    diagnostic["pages_completed"] += 1
                    diagnostic["skus_extracted"] = len(unique_skus)

                    if delay_seconds > 0 and (
                        partition_page < pages or partition_index < len(partitions)
                    ):
                        time.sleep(delay_seconds)

                diagnostic["partitions_completed"] += 1

            if diagnostic["partitions_completed"] != diagnostic["partitions_detected"]:
                raise base.full.FullCatalogError(
                    "partition_coverage_incomplete", diagnostic=diagnostic
                )
            if len(unique_products) != root_total:
                diagnostic["unique_products_extracted"] = len(unique_products)
                raise base.full.FullCatalogError(
                    "unique_product_coverage_mismatch", diagnostic=diagnostic
                )

            artifact = {
                "schema_version": "4",
                "result": "success",
                "catalog_type": "la_colonia_sps_full_read_only",
                "supermarket_id": "la_colonia",
                "location_id": base.full.passive.MVP_LOCATION_ID,
                "city": base.full.passive.TARGET_CITY,
                "capture_strategy": CAPTURE_STRATEGY,
                "partition_strategy": PARTITION_STRATEGY,
                "location_verified_same_run": True,
                "location_verification_method": LOCATION_VERIFICATION_METHOD,
                "region_binding_fingerprint_verified": False,
                "binding_source_key_verified": False,
                "radiography_executed": False,
                "page_size": page_size,
                "catalog_products_reported": root_total,
                "unique_products_extracted": len(unique_products),
                "catalog_product_coverage": len(unique_products) / root_total,
                "partitions_detected": len(partitions),
                "partitions_completed": diagnostic["partitions_completed"],
                "partition_quantity_sum": diagnostic["partition_quantity_sum"],
                "planned_product_requests": diagnostic["planned_product_requests"],
                "product_requests_completed": diagnostic["pages_completed"],
                "planner_facet_requests": diagnostic["planner_facet_requests"],
                "oversized_category_brand_splits": diagnostic[
                    "oversized_category_brand_splits"
                ],
                "skus_extracted": len(unique_skus),
                "skus_with_price": diagnostic["skus_with_price"],
                "skus_without_price": len(unique_skus) - diagnostic["skus_with_price"],
                "duplicate_skus_across_partitions": diagnostic[
                    "duplicate_skus_across_pages"
                ],
                "catalog_complete": True,
                "validation_passed": True,
                "observed_at_utc": base.full._utc_text(),
                "products": all_products,
                "raw_context_persisted": False,
                "commercial_persistence": False,
                "production_authority": False,
                "catalog_accepted": False,
                "extraction_enabled": False,
            }
            base.full.passive._validate_artifact_shape(artifact)
            return artifact
        finally:
            browser.close()


def _failure_artifact(exc: Any) -> dict[str, Any]:
    failure = base.full._safe_failure(exc.reason, exc.diagnostic)
    failure["capture_strategy"] = CAPTURE_STRATEGY
    failure["partition_strategy"] = PARTITION_STRATEGY
    failure["radiography_executed"] = False
    failure["location_verification_method"] = LOCATION_VERIFICATION_METHOD
    failure["region_binding_fingerprint_verified"] = False
    failure["binding_source_key_verified"] = False
    for key in (
        "partitions_detected",
        "partitions_completed",
        "partition_quantity_sum",
        "planned_product_requests",
        "planner_facet_requests",
        "oversized_category_brand_splits",
        "unique_products_extracted",
        "partition_expected_total",
        "partition_observed_total",
        "expected_products_on_page",
        "observed_products_on_page",
    ):
        if key in exc.diagnostic:
            failure[key] = int(exc.diagnostic[key])
    if "frontier_error" in exc.diagnostic:
        failure["frontier_error"] = str(exc.diagnostic["frontier_error"])
    return failure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--allow-full-catalog", action="store_true")
    parser.add_argument("--page-size", type=int, choices=(50,), default=50)
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "run-artifacts" / "full-catalog.json",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=ROOT / "run-artifacts" / "full-catalog.csv",
    )
    args = parser.parse_args(argv)

    if not args.live_read_only:
        parser.error("el catálogo live requiere --live-read-only")
    if not args.allow_full_catalog:
        parser.error("el catálogo completo requiere --allow-full-catalog")
    if args.delay_seconds < 1.0:
        parser.error("--delay-seconds debe ser al menos 1.0")

    try:
        artifact = _run_catalog(
            page_size=args.page_size,
            delay_seconds=args.delay_seconds,
        )
        base.full._write_json(artifact, args.output)
        base.full._write_csv(list(artifact["products"]), args.csv_output)
    except base.full.FullCatalogError as exc:
        failure = _failure_artifact(exc)
        base.full._write_json(failure, args.output)
        print(f"sps_operational_catalog_stopped:{exc.reason}", file=sys.stderr)
        return 3

    print(
        json.dumps(
            {
                "result": "success",
                "catalog_products_reported": artifact["catalog_products_reported"],
                "unique_products_extracted": artifact["unique_products_extracted"],
                "partitions_completed": artifact["partitions_completed"],
                "product_requests_completed": artifact["product_requests_completed"],
                "skus_extracted": artifact["skus_extracted"],
                "skus_with_price": artifact["skus_with_price"],
                "catalog_complete": artifact["catalog_complete"],
                "radiography_executed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
