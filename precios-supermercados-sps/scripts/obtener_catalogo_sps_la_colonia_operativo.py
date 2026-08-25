#!/usr/bin/env python3
"""Obtiene el catálogo SPS completo sin volver a ejecutar la radiografía.

El flujo operativo selecciona San Pedro Sula mediante el contrato DOM ya aprendido.
Para evitar la ventana VTEX de ~2,500 productos agrupa múltiples valores de marca
en pocas particiones disjuntas. VTEX permite repetir la misma clave selectedFacets
con valores distintos; cada partición se valida contra recordsFiltered antes de
continuar sus páginas.
"""

from __future__ import annotations

import argparse
import json
import sys
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

CAPTURE_STRATEGY = "operational_city_same_context_brand_buckets_productSearchV3"
PARTITION_STRATEGY = "brand_buckets"
LOCATION_VERIFICATION_METHOD = "structural_exact_city_control"


def _operational_verify(page: Any, context: Any, collector: Any) -> None:
    """Selecciona y verifica SPS sin ejecutar radiografía ni fingerprints."""

    del context, collector
    try:
        ensure_operational_city(page, max_dom_reresolutions=1)
    except LocationInitializationError as exc:
        raise frontier.base.full.FullCatalogError(exc.reason) from exc


def _build_brand_buckets(
    values: Sequence[Mapping[str, Any]],
    *,
    search_window: int = frontier.base.SEARCH_WINDOW_MAX_PRODUCTS,
    max_partitions: int = frontier.base.MAX_PLANNED_PRODUCT_REQUESTS,
) -> tuple[frontier.FrontierPartition, ...]:
    """Empaca marcas en bloques cuya suma nunca excede la ventana VTEX."""

    if search_window <= 0 or max_partitions <= 0:
        raise ValueError("invalid_brand_bucket_limits")

    by_value: dict[str, int] = {}
    for item in values:
        key = str(item.get("key") or "").strip().lower()
        value = str(item.get("value") or "").strip()
        quantity = item.get("quantity")
        if key != "brand" or not value:
            raise ValueError("invalid_brand_identity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("invalid_brand_quantity")
        if quantity > search_window:
            raise ValueError("brand_partition_exceeds_search_window")
        previous = by_value.get(value)
        if previous is not None and previous != quantity:
            raise ValueError("duplicate_brand_quantity_conflict")
        by_value[value] = int(quantity)

    if not by_value:
        raise ValueError("brand_partitions_missing")

    # Best-fit decreasing minimiza el número de buckets sin cambiar la cobertura.
    buckets: list[dict[str, Any]] = []
    ordered = sorted(by_value.items(), key=lambda item: (-item[1], item[0]))
    for value, quantity in ordered:
        candidates = [
            (index, int(bucket["quantity"]))
            for index, bucket in enumerate(buckets)
            if int(bucket["quantity"]) + quantity <= search_window
        ]
        if candidates:
            index = max(candidates, key=lambda item: item[1])[0]
            buckets[index]["values"].append(value)
            buckets[index]["quantity"] += quantity
        else:
            buckets.append({"values": [value], "quantity": quantity})
            if len(buckets) > max_partitions:
                raise ValueError("partition_limit_exceeded")

    return tuple(
        frontier.FrontierPartition(
            path=tuple(("brand", value) for value in bucket["values"]),
            quantity=int(bucket["quantity"]),
        )
        for bucket in buckets
    )


def _mark_operational_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact["capture_strategy"] = CAPTURE_STRATEGY
    artifact["partition_strategy"] = PARTITION_STRATEGY
    artifact["radiography_executed"] = False
    artifact["location_verification_method"] = LOCATION_VERIFICATION_METHOD
    artifact["region_binding_fingerprint_verified"] = False
    artifact["binding_source_key_verified"] = False
    artifact["brand_bucket_capacity"] = frontier.base.SEARCH_WINDOW_MAX_PRODUCTS
    return artifact


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

    old_values = frontier._category_values
    old_builder = frontier._build_frontier
    target = frontier.base.full
    old_verify = target._verify_sps_binding
    frontier._category_values = brand._brand_values
    frontier._build_frontier = _build_brand_buckets
    target._verify_sps_binding = _operational_verify

    try:
        artifact = frontier._run_partitioned_catalog(
            page_size=args.page_size,
            delay_seconds=args.delay_seconds,
        )
        _mark_operational_metadata(artifact)
        target.passive._validate_artifact_shape(artifact)
        target._write_json(artifact, args.output)
        target._write_csv(list(artifact["products"]), args.csv_output)
    except target.FullCatalogError as exc:
        failure = target._safe_failure(exc.reason, exc.diagnostic)
        _mark_operational_metadata(failure)
        for key in (
            "partitions_detected",
            "partitions_completed",
            "partition_quantity_sum",
            "planned_product_requests",
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
        target._write_json(failure, args.output)
        print(f"sps_operational_catalog_stopped:{exc.reason}", file=sys.stderr)
        return 3
    finally:
        frontier._category_values = old_values
        frontier._build_frontier = old_builder
        target._verify_sps_binding = old_verify

    print(
        json.dumps(
            {
                "result": "success",
                "catalog_products_reported": artifact["catalog_products_reported"],
                "unique_products_extracted": artifact["unique_products_extracted"],
                "partitions_completed": artifact["partitions_completed"],
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
