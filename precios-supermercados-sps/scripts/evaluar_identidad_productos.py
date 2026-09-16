#!/usr/bin/env python3
"""Evalúa el motor shadow contra casos de verdad base versionados."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.product_homologation import SourceProductRecord  # noqa: E402
from precios_supermercados.product_identity_decisions import (  # noqa: E402
    IDENTITY_POLICY_VERSION,
    IDENTITY_RELATIONS,
    assess_product_relation,
)
from precios_supermercados.product_identity_v2 import (  # noqa: E402
    IDENTITY_NORMALIZATION_VERSION,
    homologate_products_v2,
)

SCHEMA = "precios-sps-product-identity-evaluation/v1"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "homologation" / "golden-pairs-v1.jsonl"


class IdentityEvaluationError(ValueError):
    """El conjunto de evaluación o su resultado no es válido."""


def _record(value: object) -> SourceProductRecord:
    if not isinstance(value, dict):
        raise IdentityEvaluationError("golden_record_invalid")
    required = {
        "source_record_id",
        "supermarket_id",
        "source_name",
        "source_brand",
        "source_presentation",
        "barcode",
    }
    if set(value) != required:
        raise IdentityEvaluationError("golden_record_fields_invalid")
    return SourceProductRecord(
        source_record_id=str(value["source_record_id"]),
        supermarket_id=str(value["supermarket_id"]),
        source_name=str(value["source_name"]),
        source_brand=value["source_brand"],
        source_presentation=value["source_presentation"],
        barcode=value["barcode"],
    )


def evaluate_golden_pairs(path: Path) -> dict[str, object]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = [json.loads(line) for line in lines]
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityEvaluationError("golden_fixture_unreadable") from exc
    if not rows:
        raise IdentityEvaluationError("golden_fixture_empty")

    results: list[dict[str, object]] = []
    true_positive = false_positive = false_negative = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise IdentityEvaluationError("golden_case_invalid")
        expected = row.get("expected_relation")
        if not isinstance(expected, str):
            raise IdentityEvaluationError("golden_expected_relation_invalid")
        left_record = _record(row.get("left"))
        right_record = _record(row.get("right"))
        homologation = homologate_products_v2((left_record, right_record), candidate_threshold=0)
        profiles = {profile.record.source_record_id: profile for profile in homologation.profiles}
        assessment = assess_product_relation(
            profiles[left_record.source_record_id],
            profiles[right_record.source_record_id],
        )
        actual = assessment.relation
        expected_identity = expected in IDENTITY_RELATIONS
        actual_identity = actual in IDENTITY_RELATIONS
        if expected_identity and actual_identity:
            true_positive += 1
        elif not expected_identity and actual_identity:
            false_positive += 1
        elif expected_identity and not actual_identity:
            false_negative += 1
        results.append(
            {
                "case_id": row["case_id"],
                "expected_relation": expected,
                "actual_relation": actual,
                "passed": actual == expected,
                "decision_state": assessment.decision_state,
                "reasons": list(assessment.reasons),
            }
        )

    precision = (
        1.0
        if true_positive + false_positive == 0
        else true_positive / (true_positive + false_positive)
    )
    recall = (
        1.0
        if true_positive + false_negative == 0
        else true_positive / (true_positive + false_negative)
    )
    passed = sum(bool(row["passed"]) for row in results)
    return {
        "schema": SCHEMA,
        "policy_version": IDENTITY_POLICY_VERSION,
        "engine_version": IDENTITY_NORMALIZATION_VERSION,
        "summary": {
            "cases": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "identity_true_positive": true_positive,
            "identity_false_positive": false_positive,
            "identity_false_negative": false_negative,
            "identity_precision": precision,
            "identity_recall": recall,
        },
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_golden_pairs(args.fixture)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(args.output)
    print(rendered, end="")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
