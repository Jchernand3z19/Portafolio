#!/usr/bin/env python3
"""Construye una muestra de portafolio sólo con filas de publicación seguras.

No hace matching. Une ``publication.json`` con ``source-descriptors.json`` por
``source_record_id`` y conserva los nombres que cada supermercado realmente
publicó. El resultado sirve como insumo auditable para la interfaz pública.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
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


def _positive_money(value: object, *, error: str) -> str:
    if not isinstance(value, str):
        raise SampleError(error)
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise SampleError(error) from exc
    if not amount.is_finite() or amount <= 0:
        raise SampleError(error)
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
    gtin_by_product: dict[str, str] = {}
    safe_source_ids: set[str] = set()
    for offer in offer_rows:
        if not isinstance(offer, dict):
            raise SampleError("publication_offer_invalid")
        source_id = offer.get("source_record_id")
        canonical_id = offer.get("canonical_product_id")
        canonical_gtin = offer.get("canonical_gtin")
        supermarket_id = offer.get("supermarket_id")
        location_id = offer.get("location_id")
        if not all(isinstance(value, str) and value for value in (
            source_id,
            canonical_id,
            canonical_gtin,
            supermarket_id,
            location_id,
        )):
            raise SampleError("publication_offer_identity_invalid")
        if source_id in safe_source_ids:
            raise SampleError("publication_source_offer_duplicate")
        safe_source_ids.add(source_id)
        previous_gtin = gtin_by_product.setdefault(canonical_id, canonical_gtin)
        if previous_gtin != canonical_gtin:
            raise SampleError("publication_product_gtin_conflict")

        descriptor = descriptor_by_source.get(source_id)
        if descriptor is None:
            raise SampleError("descriptor_missing_for_safe_offer")
        if (
            descriptor.get("canonical_product_id") != canonical_id
            or descriptor.get("canonical_gtin") != canonical_gtin
            or descriptor.get("supermarket_id") != supermarket_id
        ):
            raise SampleError("descriptor_publication_identity_mismatch")
        if not isinstance(descriptor.get("source_name"), str) or not descriptor["source_name"].strip():
            raise SampleError("descriptor_source_name_invalid")
        current_price = _positive_money(offer.get("current_price"), error="publication_current_price_invalid")
        offers_by_product.setdefault(canonical_id, []).append({
            "supermarket_id": supermarket_id,
            "location_id": location_id,
            "source_record_id": source_id,
            "source_name": descriptor["source_name"].strip(),
            "source_brand": descriptor.get("source_brand"),
            "source_presentation": descriptor.get("source_presentation"),
            "source_category": descriptor.get("source_category"),
            "current_price": current_price,
            "is_best_price": offer.get("is_best_price") is True,
        })

    if set(descriptor_by_source) != safe_source_ids:
        raise SampleError("descriptor_set_not_exactly_safe_offers")

    rows: list[dict[str, Any]] = []
    seen_products: set[str] = set()
    for product in product_rows:
        if not isinstance(product, dict):
            raise SampleError("publication_product_invalid")
        canonical_id = product.get("canonical_product_id")
        canonical_gtin = product.get("canonical_gtin")
        if not isinstance(canonical_id, str) or not canonical_id or not isinstance(canonical_gtin, str) or not canonical_gtin:
            raise SampleError("publication_product_identity_invalid")
        if canonical_id in seen_products:
            raise SampleError("publication_product_duplicate")
        seen_products.add(canonical_id)
        if gtin_by_product.get(canonical_id) != canonical_gtin:
            raise SampleError("publication_product_gtin_conflict")
        offers = offers_by_product.get(canonical_id, [])
        expected_count = product.get("supermarket_count")
        if type(expected_count) is not int or len(offers) != expected_count or expected_count < 2:
            raise SampleError("safe_offer_count_mismatch")
        best_price = _positive_money(product.get("best_price"), error="publication_best_price_invalid")
        highest_price = _positive_money(product.get("highest_price"), error="publication_highest_price_invalid")
        savings = product.get("savings_vs_highest")
        if not isinstance(savings, str):
            raise SampleError("sample_savings_invalid")
        try:
            saving_amount = Decimal(savings)
        except InvalidOperation as exc:
            raise SampleError("sample_savings_invalid") from exc
        if not saving_amount.is_finite() or saving_amount < 0:
            raise SampleError("sample_savings_invalid")
        offers.sort(key=lambda item: (str(item["supermarket_id"]), str(item["location_id"])))
        rows.append({
            "canonical_product_id": canonical_id,
            "canonical_gtin": canonical_gtin,
            "best_supermarket_id": product.get("best_supermarket_id"),
            "best_price": best_price,
            "highest_price": highest_price,
            "savings_vs_highest": savings,
            "savings_vs_highest_pct": product.get("savings_vs_highest_pct"),
            "offers": offers,
        })

    if set(offers_by_product) != seen_products:
        raise SampleError("publication_offer_product_set_mismatch")

    # Prioriza ejemplos con ahorro real; desempate estable por GTIN/id.
    def rank(row: dict[str, Any]) -> tuple[Decimal, str, str]:
        return (-Decimal(str(row["savings_vs_highest"])), str(row["canonical_gtin"]), str(row["canonical_product_id"]))

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
