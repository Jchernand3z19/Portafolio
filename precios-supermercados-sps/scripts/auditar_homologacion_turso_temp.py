#!/usr/bin/env python3
"""Audita homologación contra Turso con SELECTs únicamente; archivo temporal."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from actualizar_mvp_turso_la_colonia import _execute_rows, _pipeline, _stmt  # noqa: E402
from precios_supermercados.product_homologation import (  # noqa: E402
    SourceProductRecord,
    homologate_products,
)

ALLOWED_SUPERMARKETS = {
    "la_colonia",
    "colonial",
    "walmart",
    "pricesmart",
    "comisariato_los_andes",
    "paiz",
}


def execute_select(sql: str, args: tuple[object, ...] = ()) -> list[list[object]]:
    if not sql.lstrip().upper().startswith("SELECT"):
        raise SystemExit("homologation_audit_non_select_blocked")
    data = _pipeline(
        os.environ["TURSO_DATABASE_URL"],
        os.environ["TURSO_AUTH_TOKEN"],
        [
            {"type": "execute", "stmt": _stmt(sql, args)},
            {"type": "close"},
        ],
    )
    results = data.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise SystemExit("homologation_audit_response_invalid")
    return _execute_rows(results[0])


def main() -> None:
    count_rows = execute_select("SELECT COUNT(*) FROM products")
    if len(count_rows) != 1 or len(count_rows[0]) != 1:
        raise SystemExit("homologation_product_count_invalid")
    expected_count = int(count_rows[0][0])
    if expected_count <= 0:
        raise SystemExit("homologation_product_count_invalid")

    records: list[SourceProductRecord] = []
    cursor = 0
    page_size = 2000
    while True:
        rows = execute_select(
            "SELECT product_id,supermarket_id,name,brand,presentation,category,ean "
            "FROM products WHERE product_id>? ORDER BY product_id LIMIT ?",
            (cursor, page_size),
        )
        if not rows:
            break
        for row in rows:
            if len(row) != 7:
                raise SystemExit("homologation_product_row_invalid")
            product_id, supermarket_id, name, brand, presentation, category, ean = row
            if not isinstance(product_id, int) or product_id <= cursor:
                raise SystemExit("homologation_product_order_invalid")
            supermarket_id = str(supermarket_id)
            if supermarket_id not in ALLOWED_SUPERMARKETS:
                raise SystemExit("homologation_supermarket_unexpected")
            records.append(
                SourceProductRecord(
                    source_record_id=f"{supermarket_id}:{product_id}",
                    supermarket_id=supermarket_id,
                    source_name=str(name),
                    source_brand=None if brand is None else str(brand),
                    source_presentation=None if presentation is None else str(presentation),
                    source_category=None if category is None else str(category),
                    barcode=None if ean is None else str(ean),
                )
            )
            cursor = product_id
        if len(rows) < page_size:
            break

    if len(records) != expected_count:
        raise SystemExit(
            f"homologation_product_count_mismatch:{expected_count}:{len(records)}"
        )

    result = homologate_products(records, candidate_threshold=Decimal("0.72"))
    by_supermarket = Counter(profile.record.supermarket_id for profile in result.profiles)
    by_type = Counter(
        profile.taxonomy.product_type or "__unclassified__"
        for profile in result.profiles
    )
    by_presentation_status = Counter(
        profile.presentation_status for profile in result.profiles
    )

    out = ROOT / "run-artifacts" / "homologation"
    out.mkdir(parents=True, exist_ok=True)
    audit = {
        "summary": result.summary,
        "by_supermarket": dict(sorted(by_supermarket.items())),
        "by_product_type": dict(sorted(by_type.items())),
        "by_presentation_status": dict(sorted(by_presentation_status.items())),
        "exact_gtin_groups": [
            {
                "canonical_gtin": group.canonical_gtin,
                "canonical_product_id": group.canonical_product_id,
                "source_record_ids": list(group.source_record_ids),
                "supermarket_ids": list(group.supermarket_ids),
            }
            for group in result.exact_gtin_groups
        ],
        "review_candidates": [
            {
                "left_source_record_id": candidate.left_source_record_id,
                "right_source_record_id": candidate.right_source_record_id,
                "left_supermarket_id": candidate.left_supermarket_id,
                "right_supermarket_id": candidate.right_supermarket_id,
                "product_type": candidate.product_type,
                "normalized_brand": candidate.normalized_brand,
                "score": str(candidate.score),
                "status": candidate.status,
                "reason": candidate.reason,
            }
            for candidate in result.candidates
        ],
    }
    (out / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out / "profiles.jsonl").open("w", encoding="utf-8") as handle:
        for profile in result.profiles:
            presentation_value = None
            if profile.presentation is not None:
                presentation_value = {
                    "dimension": profile.presentation.dimension,
                    "total_base": str(profile.presentation.total_base),
                    "pack_count": profile.presentation.pack_count,
                }
            row = {
                "source_record_id": profile.record.source_record_id,
                "supermarket_id": profile.record.supermarket_id,
                "source_name": profile.record.source_name,
                "source_brand": profile.record.source_brand,
                "source_presentation": profile.record.source_presentation,
                "source_category": profile.record.source_category,
                "barcode": profile.record.barcode,
                "normalized_name": profile.normalized_name,
                "normalized_brand": profile.normalized_brand,
                "canonical_gtin": profile.canonical_gtin,
                "canonical_product_id": profile.canonical_product_id,
                "category": profile.taxonomy.category,
                "subcategory": profile.taxonomy.subcategory,
                "product_type": profile.taxonomy.product_type,
                "taxonomy_rule_id": profile.taxonomy.rule_id,
                "presentation": presentation_value,
                "presentation_status": profile.presentation_status,
            }
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    print("HOMOLOGATION_SUMMARY=" + json.dumps(result.summary, sort_keys=True))
    print(
        "HOMOLOGATION_BY_SUPERMARKET="
        + json.dumps(dict(sorted(by_supermarket.items())), sort_keys=True)
    )
    print(
        "HOMOLOGATION_PRESENTATION_STATUS="
        + json.dumps(dict(sorted(by_presentation_status.items())), sort_keys=True)
    )


if __name__ == "__main__":
    main()
