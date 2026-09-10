#!/usr/bin/env python3
"""Exporta una cola privada de revisión de homologación desde Turso.

No modifica perfiles, precios ni ejecuciones y no consulta supermercados. Está
pensado para ejecución manual: lee `products` una sola vez, ejecuta el mismo motor
de homologación y materializa los casos que requieren trabajo humano o nuevas
reglas. El artefacto nunca forma parte del serving B2C público.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from backfill_homologacion_turso import _fetch_products, _source_preflight  # noqa: E402
from precios_supermercados.product_homologation import (  # noqa: E402
    HomologationResult,
    ProductProfile,
    SourceProductRecord,
    homologate_products,
)

SCHEMA = "precios-sps-homologation-review/v1"
DEFAULT_CANDIDATE_LIMIT = 5000
DEFAULT_GAP_LIMIT = 5000


def _product_payload(profile: ProductProfile) -> dict[str, object]:
    record = profile.record
    presentation = profile.presentation
    return {
        "source_record_id": record.source_record_id,
        "supermarket_id": record.supermarket_id,
        "source_name": record.source_name,
        "source_brand": record.source_brand,
        "source_presentation": record.source_presentation,
        "source_category": record.source_category,
        "barcode": record.barcode,
        "normalized_brand": profile.normalized_brand,
        "canonical_gtin": profile.canonical_gtin,
        "category": profile.taxonomy.category,
        "subcategory": profile.taxonomy.subcategory,
        "product_type": profile.taxonomy.product_type,
        "presentation_status": profile.presentation_status,
        "presentation_dimension": None if presentation is None else presentation.dimension,
        "presentation_total_base": None if presentation is None else format(presentation.total_base.normalize(), "f"),
        "presentation_pack_count": None if presentation is None else presentation.pack_count,
    }


def build_review_queue(
    result: HomologationResult,
    *,
    generated_at_utc: str,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    taxonomy_gap_limit: int = DEFAULT_GAP_LIMIT,
) -> dict[str, object]:
    if candidate_limit < 0 or taxonomy_gap_limit < 0:
        raise ValueError("review_limit_invalid")
    profiles = {profile.record.source_record_id: profile for profile in result.profiles}

    candidates = []
    for candidate in result.candidates[:candidate_limit]:
        left = profiles[candidate.left_source_record_id]
        right = profiles[candidate.right_source_record_id]
        candidates.append({
            "left": _product_payload(left),
            "right": _product_payload(right),
            "score": format(candidate.score, "f"),
            "reason": candidate.reason,
            "recommended_action": "human_review",
            "allowed_decisions": ["same_product", "different_products", "pending"],
        })

    exact_conflicts = []
    for group in result.exact_gtin_groups:
        if group.comparison_status != "review_required":
            continue
        exact_conflicts.append({
            "canonical_gtin": group.canonical_gtin,
            "canonical_product_id": group.canonical_product_id,
            "conflict_reasons": list(group.conflict_reasons),
            "products": [_product_payload(profiles[source_id]) for source_id in group.source_record_ids],
            "recommended_action": "verify_same_gtin_commercial_consistency",
        })

    gaps = [
        profile
        for profile in result.profiles
        if profile.taxonomy.product_type is None
    ]
    gap_sample = [_product_payload(profile) for profile in gaps[:taxonomy_gap_limit]]

    without_gtin = sum(profile.canonical_gtin is None for profile in result.profiles)
    with_gtin = len(result.profiles) - without_gtin
    ready_groups = sum(group.comparison_status == "ready" for group in result.exact_gtin_groups)
    review_groups = len(result.exact_gtin_groups) - ready_groups
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc,
        "private_review_artifact": True,
        "public_serving_allowed": False,
        "decision_policy": "candidates_never_become_comparable_without_strong_identity_or_explicit_accepted_evidence",
        "summary": {
            **result.summary,
            "with_valid_gtin": with_gtin,
            "without_valid_gtin": without_gtin,
            "exact_gtin_groups_ready": ready_groups,
            "exact_gtin_groups_needing_review": review_groups,
            "fuzzy_review_candidates_total": len(result.candidates),
            "taxonomy_gaps_total": len(gaps),
        },
        "fuzzy_candidates": {
            "total": len(result.candidates),
            "included": len(candidates),
            "truncated": len(candidates) < len(result.candidates),
            "rows": candidates,
        },
        "exact_gtin_conflicts": {
            "total": len(exact_conflicts),
            "rows": exact_conflicts,
        },
        "taxonomy_gaps": {
            "total": len(gaps),
            "included": len(gap_sample),
            "truncated": len(gap_sample) < len(gaps),
            "rows": gap_sample,
        },
    }


def export_review(
    products: Iterable[tuple[int, SourceProductRecord]],
    output: Path,
    *,
    generated_at_utc: str,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    taxonomy_gap_limit: int = DEFAULT_GAP_LIMIT,
) -> dict[str, object]:
    records = tuple(record for _, record in products)
    result = homologate_products(records, candidate_threshold=Decimal("0.72"))
    document = build_review_queue(
        result,
        generated_at_utc=generated_at_utc,
        candidate_limit=candidate_limit,
        taxonomy_gap_limit=taxonomy_gap_limit,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(output)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-limit", type=int, default=DEFAULT_CANDIDATE_LIMIT)
    parser.add_argument("--taxonomy-gap-limit", type=int, default=DEFAULT_GAP_LIMIT)
    args = parser.parse_args()
    url = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not url.strip() or not token.strip():
        raise SystemExit("turso_credentials_missing")
    before = _source_preflight(url, token)
    products = _fetch_products(url, token)
    if len(products) != before["products"]:
        raise SystemExit("homologation_review_source_changed_during_read")
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    document = export_review(
        products,
        args.output,
        generated_at_utc=generated,
        candidate_limit=args.candidate_limit,
        taxonomy_gap_limit=args.taxonomy_gap_limit,
    )
    print(json.dumps({
        "schema": document["schema"],
        "output": str(args.output),
        "summary": document["summary"],
        "fuzzy_candidates_included": document["fuzzy_candidates"]["included"],
        "taxonomy_gaps_included": document["taxonomy_gaps"]["included"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
