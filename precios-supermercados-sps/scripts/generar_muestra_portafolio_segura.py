#!/usr/bin/env python3
"""Construye una muestra de portafolio sólo con filas de publicación seguras.

No hace matching. Une ``publication.json`` con ``source-descriptors.json`` por
``source_record_id`` y conserva los nombres que cada supermercado realmente
publicó. El resultado sirve como insumo auditable para la interfaz pública.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

PUBLICATION_SCHEMA = "precios-sps-publication/v1"
DESCRIPTOR_SCHEMA = "precios-sps-safe-source-descriptors/v1"
OUTPUT_SCHEMA = "precios-sps-safe-portfolio-sample/v1"
POLICY = "fail_closed_strong_identity_and_commercial_consistency"


class SampleError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleError("sample_input_invalid") from exc
    if not isinstance(value, dict):
        raise SampleError("sample_input_not_object")
    return value


def build_sample(publication: dict[str, Any], descriptors: dict[str, Any], *, limit: int) -> dict[str, Any]:
    if publication.get("schema") != PUBLICATION_SCHEMA:
        raise SampleError("publication_schema_invalid")
    if descriptors.get("schema") != DESCRIPTOR_SCHEMA:
        raise SampleError("descriptor_schema_invalid")
    if publication.get("comparison_policy") != POLICY or descriptors.get("comparison_policy") != POLICY:
        raise SampleError("comparison_policy_invalid")
    if type(limit) is not int or limit < 1 or limit > 50:
        raise SampleError("sample_limit_invalid")

    offer_rows = publication.get("offers")
    product_rows = publication.get("products")
    descriptor_rows = descriptors.get("rows")
    if not isinstance(offer_rows, list) or not isinstance(product_rows, list) or not isinstance(descriptor_rows, list):
        raise SampleError("sample_rows_invalid")

    descriptor_by_source: dict[str, dict[str, Any]] = {}
    for row in descriptor_rows:
        if not isinstance(row, dict) or not isinstance(row.get("source_record_id"), str):
            raise SampleError("descriptor_row_invalid")
        source_id = row["source_record_id"]
        if source_id in descriptor_by_source:
            raise SampleError("descriptor_source_duplicate")
        descriptor_by_source[source_id] = row

    offers_by_product: dict[str, list[dict[str, Any]]] = {}
    for offer in offer_rows:
        if not isinstance(offer, dict):
            raise SampleError("publication_offer_invalid")
        source_id = offer.get("source_record_id")
        canonical_id = offer.get("canonical_product_id")
        canonical_gtin = offer.get("canonical_gtin")
        if not all(isinstance(value, str) and value for value in (source_id, canonical_id, canonical_gtin)):
            raise SampleError("publication_offer_identity_invalid")
        descriptor = descriptor_by_source.get(source_id)
        if descriptor is None:
            raise SampleError("descriptor_missing_for_safe_offer")
        if descriptor.get("canonical_product_id") != canonical_id or descriptor.get("canonical_gtin") != canonical_gtin:
            raise SampleError("descriptor_publication_identity_mismatch")
        offers_by_product.setdefault(canonical_id, []).append({
            "supermarket_id": offer.get("supermarket_id"),
            "location_id": offer.get("location_id"),
            "source_record_id": source_id,
            "source_name": descriptor.get("source_name"),
            "source_brand": descriptor.get("source_brand"),
            "source_presentation": descriptor.get("source_presentation"),
            "current_price": offer.get("current_price"),
            "is_best_price": offer.get("is_best_price") is True,
        })

    rows: list[dict[str, Any]] = []
    for product in product_rows:
        if not isinstance(product, dict):
            raise SampleError("publication_product_invalid")
        canonical_id = product.get("canonical_product_id")
        canonical_gtin = product.get("canonical_gtin")
        if not isinstance(canonical_id, str) or not isinstance(canonical_gtin, str):
            raise SampleError("publication_product_identity_invalid")
        offers = offers_by_product.get(canonical_id, [])
        expected_count = product.get("supermarket_count")
        if type(expected_count) is not int or len(offers) != expected_count or expected_count < 2:
            raise SampleError("safe_offer_count_mismatch")
        offers.sort(key=lambda item: (str(item["supermarket_id"]), str(item["location_id"])))
        rows.append({
            "canonical_product_id": canonical_id,
            "canonical_gtin": canonical_gtin,
            "best_supermarket_id": product.get("best_supermarket_id"),
            "best_price": product.get("best_price"),
            "highest_price": product.get("highest_price"),
            "savings_vs_highest": product.get("savings_vs_highest"),
            "savings_vs_highest_pct": product.get("savings_vs_highest_pct"),
            "offers": offers,
        })

    # Prioriza ejemplos con ahorro real; desempate estable por GTIN/id.
    def rank(row: dict[str, Any]) -> tuple[float, str, str]:
        try:
            saving = float(row["savings_vs_highest"])
        except (TypeError, ValueError) as exc:
            raise SampleError("sample_savings_invalid") from exc
        return (-saving, str(row["canonical_gtin"]), str(row["canonical_product_id"]))

    rows.sort(key=rank)
    selected = rows[:limit]
    return {
        "schema": OUTPUT_SCHEMA,
        "comparison_policy": POLICY,
        "currency": publication.get("currency"),
        "scope": publication.get("scope"),
        "row_count": len(selected),
        "selection_rule": "highest_absolute_savings_within_safe_common_comparable_universe",
        "rows": selected,
    }


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--publication", type=Path, required=True)
    result.add_argument("--descriptors", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--limit", type=int, default=10)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    document = build_sample(_read(args.publication), _read(args.descriptors), limit=args.limit)
    _write(args.output, document)
    print(json.dumps({"schema": document["schema"], "row_count": document["row_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
