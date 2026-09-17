#!/usr/bin/env python3
"""Exporta una cola privada y explicable de revisión de identidad desde Turso.

No modifica perfiles, precios ni ejecuciones y no consulta supermercados. Lee
``products`` una vez, ejecuta identidad v2 y materializa candidatos/conflictos.
El artefacto nunca forma parte del serving B2C público.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from backfill_homologacion_turso import (  # noqa: E402
    _fetch_products,
    _query,
    _scalar,
    _source_preflight,
)
from precios_supermercados.product_homologation import (  # noqa: E402
    HomologationResult,
    ProductProfile,
    SourceProductRecord,
    homologate_products,
)
from precios_supermercados.product_identity_v2 import (  # noqa: E402
    IDENTITY_NORMALIZATION_VERSION,
    audit_identity_quality,
    canonicalize_brand_key,
    canonical_presentation_fields,
    canonical_egg_size,
    explain_candidate,
    homologate_products_v2,
    source_brand_role,
)
from precios_supermercados.product_identity_decisions import (  # noqa: E402
    IDENTITY_POLICY_VERSION,
    ReviewedIdentityDecision,
    assess_product_relation,
    build_reviewed_identity_groups,
    candidate_id,
    index_reviewed_decisions,
    load_reviewed_decisions,
    profile_evidence_fingerprint,
)

SCHEMA = "precios-sps-homologation-review/v3"
DEFAULT_CANDIDATE_LIMIT = 5000
DEFAULT_GAP_LIMIT = 5000


def _brand_evidence(profile: ProductProfile) -> str:
    source = canonicalize_brand_key(profile.record.source_brand)
    if source is not None and source == profile.normalized_brand:
        return "source"
    if source is None and profile.normalized_brand is not None:
        return "name_known_brand"
    if source is not None and profile.normalized_brand != source:
        return "source_conflict"
    return "missing"


def _product_payload(
    profile: ProductProfile,
    image_evidence_by_source: Mapping[str, tuple[dict[str, object], ...]] | None = None,
) -> dict[str, object]:
    record = profile.record
    presentation = canonical_presentation_fields(record, profile.taxonomy)
    payload = {
        "source_record_id": record.source_record_id,
        "supermarket_id": record.supermarket_id,
        "source_name": record.source_name,
        "source_brand": record.source_brand,
        "source_presentation": record.source_presentation,
        "source_category": record.source_category,
        "barcode": record.barcode,
        "raw_brand": record.source_brand,
        "normalized_brand": profile.normalized_brand,
        "canonical_brand": profile.normalized_brand,
        "brand_evidence": _brand_evidence(profile),
        "source_brand_role": source_brand_role(record.source_brand),
        "normalized_brand_role": (
            "commercial_brand_candidate"
            if profile.normalized_brand is not None
            else "unknown"
        ),
        "manufacturer_brand": None,
        "owner_brand": None,
        "manufacturer_owner_status": "not_exposed_by_source",
        "canonical_gtin": profile.canonical_gtin,
        "category": profile.taxonomy.category,
        "subcategory": profile.taxonomy.subcategory,
        "product_type": profile.taxonomy.product_type,
        "taxonomy_rule_id": profile.taxonomy.rule_id,
        "egg_size": canonical_egg_size(record, profile.taxonomy),
        "raw_presentation": presentation.raw_presentation,
        "normalized_quantity": None if presentation.normalized_quantity is None else format(presentation.normalized_quantity.normalize(), "f"),
        "normalized_unit": presentation.normalized_unit,
        "normalized_pack_count": presentation.normalized_pack_count,
        "canonical_total": None if presentation.canonical_total is None else format(presentation.canonical_total.normalize(), "f"),
        "display_presentation": presentation.display_presentation,
        "presentation_status": presentation.status,
        "presentation_dimension": None if profile.presentation is None else profile.presentation.dimension,
        "presentation_total_base": None if profile.presentation is None else format(profile.presentation.total_base.normalize(), "f"),
        "presentation_pack_count": None if profile.presentation is None else profile.presentation.pack_count,
        "matching_tokens": list(profile.matching_tokens),
        "evidence_fingerprint": profile_evidence_fingerprint(profile),
    }
    if image_evidence_by_source is not None:
        payload["image_evidence"] = list(
            image_evidence_by_source.get(record.source_record_id, ())
        )
    return payload


def build_review_queue(
    result: HomologationResult,
    *,
    generated_at_utc: str,
    baseline_result: HomologationResult | None = None,
    runtime_seconds: dict[str, float] | None = None,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    taxonomy_gap_limit: int = DEFAULT_GAP_LIMIT,
    reviewed_decisions: Iterable[ReviewedIdentityDecision] = (),
    image_evidence_by_source: Mapping[str, tuple[dict[str, object], ...]] | None = None,
) -> dict[str, object]:
    if candidate_limit < 0 or taxonomy_gap_limit < 0:
        raise ValueError("review_limit_invalid")
    profiles = {profile.record.source_record_id: profile for profile in result.profiles}
    decisions = tuple(reviewed_decisions)
    decisions_by_candidate = index_reviewed_decisions(decisions)
    reviewed_groups = build_reviewed_identity_groups(result.profiles, decisions)

    candidates = []
    for candidate in result.candidates[:candidate_limit]:
        left = profiles[candidate.left_source_record_id]
        right = profiles[candidate.right_source_record_id]
        evidence = explain_candidate(left, right)
        pair_id = candidate_id(
            candidate.left_source_record_id,
            candidate.right_source_record_id,
        )
        relation = assess_product_relation(
            left,
            right,
            decisions_by_candidate.get(pair_id),
        )
        candidates.append(
            {
                "candidate_id": pair_id,
                "left": _product_payload(left, image_evidence_by_source),
                "right": _product_payload(right, image_evidence_by_source),
                "candidate_ranking_score": format(candidate.score, "f"),
                "score_semantics": "review_queue_ranking_only_not_probability",
                "decision_state": evidence.decision_state,
                "confidence_level": evidence.confidence_level,
                "matching_signals": list(evidence.matching_signals),
                "conflict_signals": list(evidence.conflict_signals),
                "reason": candidate.reason,
                "reviewed_relation": relation.relation,
                "reviewed_decision_state": relation.decision_state,
                "reviewed_master_product_id": relation.master_product_id,
                "reviewed_evidence_codes": list(relation.evidence_codes),
                "reviewed_reasons": list(relation.reasons),
                "recommended_action": "human_review",
                "allowed_decisions": ["same_product", "different_products", "pending"],
                "allowed_relations": [
                    "VERIFIED_EQUIVALENT",
                    "PRODUCT_VARIANT",
                    "COMPARABLE_ALTERNATIVE",
                    "CONFLICT",
                    "UNRESOLVED",
                ],
                "decision_contract": {
                    "policy_version": IDENTITY_POLICY_VERSION,
                    "left_evidence_fingerprint": profile_evidence_fingerprint(left),
                    "right_evidence_fingerprint": profile_evidence_fingerprint(right),
                    "public_serving_allowed": False,
                },
            }
        )

    exact_conflicts = []
    for group in result.exact_gtin_groups:
        if group.comparison_status != "review_required":
            continue
        exact_conflicts.append(
            {
                "canonical_gtin": group.canonical_gtin,
                "canonical_product_id": group.canonical_product_id,
                "conflict_reasons": list(group.conflict_reasons),
                "products": [
                    _product_payload(profiles[source_id], image_evidence_by_source)
                    for source_id in group.source_record_ids
                ],
                "recommended_action": "verify_same_gtin_commercial_consistency",
            }
        )

    gaps = [profile for profile in result.profiles if profile.taxonomy.product_type is None]
    gap_sample = [
        _product_payload(profile, image_evidence_by_source)
        for profile in gaps[:taxonomy_gap_limit]
    ]

    without_gtin = sum(profile.canonical_gtin is None for profile in result.profiles)
    with_gtin = len(result.profiles) - without_gtin
    ready_groups = sum(group.comparison_status == "ready" for group in result.exact_gtin_groups)
    review_groups = len(result.exact_gtin_groups) - ready_groups
    quality = audit_identity_quality(result)
    baseline_summary = None
    if baseline_result is not None:
        baseline_summary = {
            **baseline_result.summary,
            **audit_identity_quality(baseline_result),
        }
    before_after = None
    if baseline_summary is not None:
        after_summary = {**result.summary, **quality}
        comparable_keys = sorted(
            key
            for key in set(baseline_summary) & set(after_summary)
            if isinstance(baseline_summary[key], int)
            and not isinstance(baseline_summary[key], bool)
            and isinstance(after_summary[key], int)
            and not isinstance(after_summary[key], bool)
        )
        before_after = {
            "before_engine": "product-homologation-v1",
            "after_engine": IDENTITY_NORMALIZATION_VERSION,
            "before": baseline_summary,
            "after": after_summary,
            "delta": {
                key: int(after_summary[key]) - int(baseline_summary[key])
                for key in comparable_keys
            },
            "runtime_seconds": runtime_seconds or {},
        }
    image_profiles = (
        0
        if image_evidence_by_source is None
        else sum(
            bool(image_evidence_by_source.get(profile.record.source_record_id))
            for profile in result.profiles
        )
    )
    summary = {
        **result.summary,
        **quality,
        "normalization_version": IDENTITY_NORMALIZATION_VERSION,
        "identity_policy_version": IDENTITY_POLICY_VERSION,
        "with_valid_gtin": with_gtin,
        "without_valid_gtin": without_gtin,
        "exact_gtin_groups_ready": ready_groups,
        "exact_gtin_groups_needing_review": review_groups,
        "review_candidates_total": len(result.candidates),
        "fuzzy_review_candidates_total": len(result.candidates),
        "taxonomy_gaps_total": len(gaps),
        "image_reference_available": image_profiles,
        "image_signal_status": (
            "not_loaded"
            if image_evidence_by_source is None
            else "current_product_images_available"
            if image_profiles
            else "product_images_table_empty"
        ),
        "reviewed_decisions_total": len(decisions),
        "reviewed_identity_groups_total": len(reviewed_groups),
    }
    candidate_section = {
        "total": len(result.candidates),
        "included": len(candidates),
        "truncated": len(candidates) < len(result.candidates),
        "rows": candidates,
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc,
        "normalization_version": IDENTITY_NORMALIZATION_VERSION,
        "private_review_artifact": True,
        "public_serving_allowed": False,
        "decision_policy": "candidate_generation_is_broad_but_identity_confirmation_remains_fail_closed",
        "summary": summary,
        "before_after": before_after,
        "review_candidates": candidate_section,
        # Compatibilidad aditiva con consumidores privados v1.
        "fuzzy_candidates": candidate_section,
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
        "reviewed_identity_groups": {
            "total": len(reviewed_groups),
            "rows": [
                {
                    "master_product_id": group.master_product_id,
                    "source_record_ids": list(group.source_record_ids),
                    "supermarket_ids": list(group.supermarket_ids),
                    "relation": group.relation,
                    "public_serving_allowed": False,
                }
                for group in reviewed_groups
            ],
        },
    }


def export_review(
    products: Iterable[tuple[int, SourceProductRecord]],
    output: Path,
    *,
    generated_at_utc: str,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    taxonomy_gap_limit: int = DEFAULT_GAP_LIMIT,
    reviewed_decisions: Iterable[ReviewedIdentityDecision] = (),
    image_evidence_by_source: Mapping[str, tuple[dict[str, object], ...]] | None = None,
) -> dict[str, object]:
    records = tuple(record for _, record in products)
    baseline_started = time.monotonic()
    baseline_result = homologate_products(records, candidate_threshold=Decimal("0.72"))
    baseline_seconds = time.monotonic() - baseline_started
    candidate_started = time.monotonic()
    result = homologate_products_v2(records, candidate_threshold=Decimal("0.72"))
    candidate_seconds = time.monotonic() - candidate_started
    document = build_review_queue(
        result,
        generated_at_utc=generated_at_utc,
        baseline_result=baseline_result,
        runtime_seconds={
            "before": round(baseline_seconds, 3),
            "after": round(candidate_seconds, 3),
        },
        candidate_limit=candidate_limit,
        taxonomy_gap_limit=taxonomy_gap_limit,
        reviewed_decisions=reviewed_decisions,
        image_evidence_by_source=image_evidence_by_source,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return document


def _fetch_current_image_evidence(
    url: str, token: str
) -> dict[str, tuple[dict[str, object], ...]] | None:
    """Lee una vez la evidencia vigente; ``None`` indica esquema aún no migrado."""

    exists = _query(
        url,
        token,
        "SELECT name FROM sqlite_master WHERE type='table' AND name='product_images'",
    )
    if not exists:
        return None
    if exists != [["product_images"]]:
        raise SystemExit("homologation_review_product_images_schema_invalid")

    expected = _scalar(
        url,
        token,
        "SELECT COUNT(*) FROM product_images WHERE valid_to_utc IS NULL",
    )
    grouped: dict[str, list[dict[str, object]]] = {}
    cursor = 0
    loaded = 0
    while True:
        rows = _query(
            url,
            token,
            """SELECT product_image_id,product_id,supermarket_id,location_id,
                image_url,source_position,is_primary,source_image_id,
                valid_from_utc,first_seen_run_id,last_seen_run_id
            FROM product_images
            WHERE valid_to_utc IS NULL AND product_image_id>?
            ORDER BY product_image_id LIMIT 2000""",
            (cursor,),
        )
        if not rows:
            break
        for raw in rows:
            if len(raw) != 11:
                raise SystemExit("homologation_review_product_image_row_invalid")
            (
                image_id,
                product_id,
                supermarket_id,
                location_id,
                image_url,
                position,
                is_primary,
                source_image_id,
                valid_from_utc,
                first_seen_run_id,
                last_seen_run_id,
            ) = raw
            if (
                type(image_id) is not int
                or type(product_id) is not int
                or type(position) is not int
                or is_primary not in {0, 1}
                or not all(
                    isinstance(value, str) and value
                    for value in (
                        supermarket_id,
                        location_id,
                        image_url,
                        valid_from_utc,
                        first_seen_run_id,
                        last_seen_run_id,
                    )
                )
                or not str(image_url).startswith("https://")
                or (source_image_id is not None and not isinstance(source_image_id, str))
            ):
                raise SystemExit("homologation_review_product_image_row_invalid")
            source_record_id = f"{supermarket_id}:{product_id}"
            grouped.setdefault(source_record_id, []).append(
                {
                    "location_id": location_id,
                    "image_url": image_url,
                    "source_position": position,
                    "is_primary": bool(is_primary),
                    "source_image_id": source_image_id,
                    "valid_from_utc": valid_from_utc,
                    "first_seen_run_id": first_seen_run_id,
                    "last_seen_run_id": last_seen_run_id,
                    "identity_authority": False,
                }
            )
            cursor = image_id
            loaded += 1
        if len(rows) < 2000:
            break
    confirmed = _scalar(
        url,
        token,
        "SELECT COUNT(*) FROM product_images WHERE valid_to_utc IS NULL",
    )
    if loaded != expected or confirmed != expected:
        raise SystemExit("homologation_review_product_images_changed_during_read")
    return {
        source_id: tuple(
            sorted(
                evidence,
                key=lambda item: (
                    str(item["location_id"]),
                    int(item["source_position"]),
                    str(item["image_url"]),
                ),
            )
        )
        for source_id, evidence in grouped.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-limit", type=int, default=DEFAULT_CANDIDATE_LIMIT)
    parser.add_argument("--taxonomy-gap-limit", type=int, default=DEFAULT_GAP_LIMIT)
    parser.add_argument(
        "--decision-registry",
        type=Path,
        default=ROOT / "config" / "homologation" / "reviewed-decisions-v1.json",
    )
    args = parser.parse_args()
    url = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not url.strip() or not token.strip():
        raise SystemExit("turso_credentials_missing")
    before = _source_preflight(url, token)
    products = _fetch_products(url, token)
    image_evidence = _fetch_current_image_evidence(url, token)
    if len(products) != before["products"]:
        raise SystemExit("homologation_review_source_changed_during_read")
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    document = export_review(
        products,
        args.output,
        generated_at_utc=generated,
        candidate_limit=args.candidate_limit,
        taxonomy_gap_limit=args.taxonomy_gap_limit,
        reviewed_decisions=load_reviewed_decisions(args.decision_registry),
        image_evidence_by_source=image_evidence,
    )
    print(
        json.dumps(
            {
                "schema": document["schema"],
                "output": str(args.output),
                "summary": document["summary"],
                "review_candidates_included": document["review_candidates"]["included"],
                "taxonomy_gaps_included": document["taxonomy_gaps"]["included"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
