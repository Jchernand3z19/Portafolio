#!/usr/bin/env python3
"""Obtiene el catálogo SPS completo sin volver a ejecutar la radiografía.

Las cantidades de facets se usan sólo para empacar marcas en buckets conservadores.
El total raíz y el total real de cada bucket se toman de productSearchV3, que es la
fuente autoritativa para paginación. Así una diferencia pequeña entre facets y
Search no aborta una descarga válida.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_particionado_v2 as frontier  # noqa: E402
import obtener_catalogo_sps_la_colonia_particionado_v3 as brand  # noqa: E402
from precios_supermercados.scrapers.la_colonia_location import (  # noqa: E402
    LocationInitializationError,
    ensure_operational_city,
)

core = frontier.base
full = core.full
CAPTURE_STRATEGY = "operational_city_authoritative_brand_buckets_productSearchV3"
PARTITION_STRATEGY = "brand_buckets_productSearch_authoritative_totals"
LOCATION_VERIFICATION_METHOD = "structural_exact_city_control"
BUCKET_ESTIMATE_CAPACITY = 2300


def _build_brand_buckets(
    values: Sequence[Mapping[str, Any]],
    *,
    estimate_capacity: int = BUCKET_ESTIMATE_CAPACITY,
) -> tuple[frontier.FrontierPartition, ...]:
    if estimate_capacity <= 0 or estimate_capacity > core.SEARCH_WINDOW_MAX_PRODUCTS:
        raise ValueError("invalid_brand_bucket_capacity")

    by_value: dict[str, int] = {}
    for item in values:
        key = str(item.get("key") or "").strip().lower()
        value = str(item.get("value") or "").strip()
        quantity = item.get("quantity")
        if key != "brand" or not value:
            raise ValueError("invalid_brand_identity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("invalid_brand_quantity")
        if quantity > core.SEARCH_WINDOW_MAX_PRODUCTS:
            raise ValueError("brand_partition_exceeds_search_window")
        previous = by_value.get(value)
        if previous is not None and previous != quantity:
            raise ValueError("duplicate_brand_quantity_conflict")
        by_value[value] = int(quantity)

    if not by_value:
        raise ValueError("brand_partitions_missing")

    buckets: list[dict[str, Any]] = []
    for value, quantity in sorted(by_value.items(), key=lambda item: (-item[1], item[0])):
        candidates = [
            (index, int(bucket["quantity"]))
            for index, bucket in enumerate(buckets)
            if int(bucket["quantity"]) + quantity <= estimate_capacity
        ]
        if candidates:
            index = max(candidates, key=lambda item: item[1])[0]
            buckets[index]["values"].append(value)
            buckets[index]["quantity"] += quantity
        else:
            buckets.append({"values": [value], "quantity": quantity})

    if len(buckets) > core.MAX_PLANNED_PRODUCT_REQUESTS:
        raise ValueError("partition_limit_exceeded")

    return tuple(
        frontier.FrontierPartition(
            path=tuple(("brand", value) for value in bucket["values"]),
            quantity=int(bucket["quantity"]),
        )
        for bucket in buckets
    )


def _process_page(
    *,
    payload: Mapping[str, Any],
    request_url: str,
    extractor: Any,
    run_id: str,
    page_size: int,
    unique_products: set[str],
    unique_skus: set[tuple[str, str]],
    all_products: list[dict[str, Any]],
    diagnostic: dict[str, Any],
) -> None:
    try:
        result = extractor.parse_payload(
            payload,
            scrape_run_id=run_id,
            source_url=request_url,
            page_size=page_size,
        )
    except core.StructureChangedError as exc:
        raise full.FullCatalogError(
            "product_payload_not_parseable", diagnostic=diagnostic
        ) from exc
    if not result.accepted:
        raise full.FullCatalogError("page_validation_failed", diagnostic=diagnostic)

    for parsed in result.products:
        product = full.passive._public_product(parsed)
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


def _run_catalog(*, page_size: int, delay_seconds: float) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise full.FullCatalogError("playwright_not_installed") from exc

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
        "partition_quantity_estimate_sum": 0,
        "partition_observed_total_sum": 0,
        "planned_product_requests": 0,
        "product_requests_completed": 0,
        "partition_total_adjustments": 0,
    }
    run_id = f"sps_operational_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    unique_products: set[str] = set()
    unique_skus: set[tuple[str, str]] = set()
    all_products: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser, _ = full.launch_compatible_chromium(pw)
        try:
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            home = page.goto(
                full.radiography.TARGET_URL,
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            if home is not None and int(home.status) in {403, 429}:
                diagnostic["blocked_http_status_observed"] = int(home.status)
                raise full.FullCatalogError(f"http_{home.status}", diagnostic=diagnostic)
            if full.passive._blocked_surface(page):
                raise full.FullCatalogError("blocked_or_login_surface", diagnostic=diagnostic)
            page.wait_for_timeout(250)

            try:
                ensure_operational_city(page, max_dom_reresolutions=1)
            except LocationInitializationError as exc:
                raise full.FullCatalogError(exc.reason, diagnostic=diagnostic) from exc
            diagnostic["location_verified_same_run"] = True

            # productSearchV3, no facets.recordsFiltered, define el total autoritativo.
            root_url = core._product_url(
                selected_facets=[dict(core.ROOT_FACET)], page=1, page_size=page_size
            )
            root_response = context.request.get(
                root_url,
                timeout=core.PRODUCT_REQUEST_TIMEOUT_MS,
                fail_on_status_code=False,
            )
            root_payload = core._read_json_response(
                root_response, diagnostic, kind="root_product_search"
            )
            root_total, _ = core._read_shape(root_payload)
            if root_total <= 0:
                raise full.FullCatalogError("catalog_root_total_invalid", diagnostic=diagnostic)
            diagnostic["catalog_products_reported"] = root_total
            diagnostic["product_requests_completed"] += 1

            tree_response = context.request.get(
                core._category_tree_url(),
                timeout=core.FACET_REQUEST_TIMEOUT_MS,
                fail_on_status_code=False,
            )
            tree_payload = core._read_json_response(
                tree_response, diagnostic, kind="brand_facets"
            )
            data = tree_payload.get("data")
            if not isinstance(data, Mapping):
                raise full.FullCatalogError("brand_facets_data_missing", diagnostic=diagnostic)
            try:
                normalized = core.LaColoniaFacetDiscoveryAdapter._normalize_tree(data)
                if normalized.get("sampling") is not False:
                    raise ValueError("brand_facets_sampling_detected")
                brand_values = brand._brand_values(normalized)
                partitions = _build_brand_buckets(brand_values)
            except Exception as exc:
                diagnostic["frontier_error"] = str(exc)[:120]
                raise full.FullCatalogError("brand_buckets_not_usable", diagnostic=diagnostic) from exc

            diagnostic["partitions_detected"] = len(partitions)
            diagnostic["partition_quantity_estimate_sum"] = sum(
                partition.quantity for partition in partitions
            )
            diagnostic["planned_product_requests"] = sum(
                math.ceil(partition.quantity / page_size) for partition in partitions
            ) + 1
            if diagnostic["planned_product_requests"] > core.MAX_PLANNED_PRODUCT_REQUESTS:
                raise full.FullCatalogError(
                    "partition_request_budget_exceeded", diagnostic=diagnostic
                )

            extractor = core.LaColoniaExtractor()
            for partition_index, partition in enumerate(partitions, start=1):
                facets = core._partition_facets(partition.path)

                first_url = core._product_url(
                    selected_facets=facets, page=1, page_size=page_size
                )
                diagnostic["pages_attempted"] += 1
                first_response = context.request.get(
                    first_url,
                    timeout=core.PRODUCT_REQUEST_TIMEOUT_MS,
                    fail_on_status_code=False,
                )
                first_payload = core._read_json_response(
                    first_response, diagnostic, kind="product_search"
                )
                actual_total, products_returned = core._read_shape(first_payload)
                diagnostic["product_requests_completed"] += 1
                if actual_total <= 0 or actual_total > core.SEARCH_WINDOW_MAX_PRODUCTS:
                    diagnostic["partition_observed_total"] = actual_total
                    raise full.FullCatalogError(
                        "brand_bucket_outside_search_window", diagnostic=diagnostic
                    )
                if actual_total != partition.quantity:
                    diagnostic["partition_total_adjustments"] += 1
                diagnostic["partition_observed_total_sum"] += actual_total

                expected_first = min(page_size, actual_total)
                if products_returned != expected_first:
                    diagnostic["expected_products_on_page"] = expected_first
                    diagnostic["observed_products_on_page"] = products_returned
                    raise full.FullCatalogError(
                        "partial_or_unexpected_product_page", diagnostic=diagnostic
                    )
                _process_page(
                    payload=first_payload,
                    request_url=first_url,
                    extractor=extractor,
                    run_id=run_id,
                    page_size=page_size,
                    unique_products=unique_products,
                    unique_skus=unique_skus,
                    all_products=all_products,
                    diagnostic=diagnostic,
                )

                pages = max(math.ceil(actual_total / page_size), 1)
                for partition_page in range(2, pages + 1):
                    if diagnostic["product_requests_completed"] >= core.MAX_PLANNED_PRODUCT_REQUESTS:
                        raise full.FullCatalogError(
                            "partition_request_budget_exceeded", diagnostic=diagnostic
                        )
                    if delay_seconds > 0:
                        time.sleep(delay_seconds)
                    request_url = core._product_url(
                        selected_facets=facets,
                        page=partition_page,
                        page_size=page_size,
                    )
                    diagnostic["pages_attempted"] += 1
                    response = context.request.get(
                        request_url,
                        timeout=core.PRODUCT_REQUEST_TIMEOUT_MS,
                        fail_on_status_code=False,
                    )
                    payload = core._read_json_response(
                        response, diagnostic, kind="product_search"
                    )
                    observed_total, products_returned = core._read_shape(payload)
                    diagnostic["product_requests_completed"] += 1
                    if observed_total != actual_total:
                        diagnostic["partition_expected_total"] = actual_total
                        diagnostic["partition_observed_total"] = observed_total
                        raise full.FullCatalogError(
                            "partition_total_changed_mid_run", diagnostic=diagnostic
                        )
                    expected_on_page = min(
                        page_size,
                        max(actual_total - ((partition_page - 1) * page_size), 0),
                    )
                    if products_returned != expected_on_page:
                        diagnostic["expected_products_on_page"] = expected_on_page
                        diagnostic["observed_products_on_page"] = products_returned
                        raise full.FullCatalogError(
                            "partial_or_unexpected_product_page", diagnostic=diagnostic
                        )
                    _process_page(
                        payload=payload,
                        request_url=request_url,
                        extractor=extractor,
                        run_id=run_id,
                        page_size=page_size,
                        unique_products=unique_products,
                        unique_skus=unique_skus,
                        all_products=all_products,
                        diagnostic=diagnostic,
                    )

                diagnostic["partitions_completed"] += 1
                if delay_seconds > 0 and partition_index < len(partitions):
                    time.sleep(delay_seconds)

            diagnostic["unique_products_extracted"] = len(unique_products)
            if diagnostic["partitions_completed"] != diagnostic["partitions_detected"]:
                raise full.FullCatalogError(
                    "partition_coverage_incomplete", diagnostic=diagnostic
                )
            if len(unique_products) != root_total:
                raise full.FullCatalogError(
                    "unique_product_coverage_mismatch", diagnostic=diagnostic
                )

            artifact = {
                "schema_version": "5",
                "result": "success",
                "catalog_type": "la_colonia_sps_full_read_only",
                "supermarket_id": "la_colonia",
                "location_id": full.passive.MVP_LOCATION_ID,
                "city": full.passive.TARGET_CITY,
                "capture_strategy": CAPTURE_STRATEGY,
                "partition_strategy": PARTITION_STRATEGY,
                "location_verified_same_run": True,
                "location_verification_method": LOCATION_VERIFICATION_METHOD,
                "region_binding_fingerprint_verified": False,
                "binding_source_key_verified": False,
                "radiography_executed": False,
                "page_size": page_size,
                "brand_bucket_estimate_capacity": BUCKET_ESTIMATE_CAPACITY,
                "catalog_products_reported": root_total,
                "unique_products_extracted": len(unique_products),
                "catalog_product_coverage": len(unique_products) / root_total,
                "partitions_detected": diagnostic["partitions_detected"],
                "partitions_completed": diagnostic["partitions_completed"],
                "partition_quantity_estimate_sum": diagnostic[
                    "partition_quantity_estimate_sum"
                ],
                "partition_observed_total_sum": diagnostic[
                    "partition_observed_total_sum"
                ],
                "partition_total_adjustments": diagnostic[
                    "partition_total_adjustments"
                ],
                "planned_product_requests": diagnostic["planned_product_requests"],
                "product_requests_completed": diagnostic[
                    "product_requests_completed"
                ],
                "skus_extracted": len(unique_skus),
                "skus_with_price": diagnostic["skus_with_price"],
                "skus_without_price": len(unique_skus) - diagnostic["skus_with_price"],
                "duplicate_skus_across_partitions": diagnostic[
                    "duplicate_skus_across_pages"
                ],
                "catalog_complete": True,
                "validation_passed": True,
                "observed_at_utc": full._utc_text(),
                "products": all_products,
                "raw_context_persisted": False,
                "commercial_persistence": False,
                "production_authority": False,
                "catalog_accepted": False,
                "extraction_enabled": False,
            }
            full.passive._validate_artifact_shape(artifact)
            return artifact
        finally:
            browser.close()


def _failure_artifact(exc: Any) -> dict[str, Any]:
    failure = full._safe_failure(exc.reason, exc.diagnostic)
    failure["capture_strategy"] = CAPTURE_STRATEGY
    failure["partition_strategy"] = PARTITION_STRATEGY
    failure["radiography_executed"] = False
    failure["location_verification_method"] = LOCATION_VERIFICATION_METHOD
    failure["region_binding_fingerprint_verified"] = False
    failure["binding_source_key_verified"] = False
    failure["brand_bucket_estimate_capacity"] = BUCKET_ESTIMATE_CAPACITY
    for key in (
        "partitions_detected",
        "partitions_completed",
        "partition_quantity_estimate_sum",
        "partition_observed_total_sum",
        "partition_total_adjustments",
        "planned_product_requests",
        "product_requests_completed",
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
        full._write_json(artifact, args.output)
        full._write_csv(list(artifact["products"]), args.csv_output)
    except full.FullCatalogError as exc:
        full._write_json(_failure_artifact(exc), args.output)
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
