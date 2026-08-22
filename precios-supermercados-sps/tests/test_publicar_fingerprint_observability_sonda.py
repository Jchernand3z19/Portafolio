"""Pruebas del fingerprint sanitizado publicado como commit statuses."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "publicar_fingerprint_observability_sonda.py"
)
SPEC = importlib.util.spec_from_file_location("publicar_fingerprint_observability_sonda", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _contexts(payload: dict[str, object]) -> set[str]:
    return {status.context for status in module.build_statuses(payload)}


def test_shape_collected_exposes_only_fixed_structural_fingerprint():
    payload = {
        "diagnostic_status": "shape_collected",
        "trace_candidate_count": 2,
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
        "candidate_shapes": [
            {
                "events_view": {
                    "events": {
                        "mapping_event_count": 3,
                        "source_types": {"mapping": 3},
                        "expected_custom_span_match_counts": {"$metadata.spanName": 1},
                        "standard_attribute_presence_counts": {
                            "source:http.response.status_code": 1,
                            "source:url.full": 1,
                        },
                        "precios_attribute_key_locations": ["source:precios.probe_id"],
                    }
                },
                "invocations_view": {
                    "events": {
                        "mapping_event_count": 0,
                        "source_types": {"missing": 0},
                        "expected_custom_span_match_counts": {},
                        "standard_attribute_presence_counts": {},
                        "precios_attribute_key_locations": [],
                    }
                },
            }
        ],
    }
    assert _contexts(payload) == {
        "precios-sps/obs/result/shape_collected",
        "precios-sps/obs/trace-candidates/2",
        "precios-sps/obs/mapping-events/yes",
        "precios-sps/obs/custom-span/yes",
        "precios-sps/obs/precios-attrs/yes",
        "precios-sps/obs/source/mapping",
        "precios-sps/obs/http-status/source",
        "precios-sps/obs/url-full/source",
    }


def test_shape_fingerprint_collapses_multiple_locations_and_source_types():
    payload = {
        "diagnostic_status": "shape_collected",
        "trace_candidate_count": 1,
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
        "candidate_shapes": [
            {
                "events_view": {
                    "events": {
                        "mapping_event_count": 2,
                        "source_types": {"mapping": 1, "string": 1},
                        "expected_custom_span_match_counts": {},
                        "standard_attribute_presence_counts": {
                            "top:http.response.status_code": 1,
                            "source.attributes:http.response.status_code": 1,
                        },
                        "precios_attribute_key_locations": [],
                    }
                }
            }
        ],
    }
    contexts = _contexts(payload)
    assert "precios-sps/obs/source/mixed" in contexts
    assert "precios-sps/obs/http-status/mixed" in contexts
    assert "precios-sps/obs/url-full/none" in contexts
    assert "precios-sps/obs/custom-span/no" in contexts
    assert "precios-sps/obs/precios-attrs/no" in contexts


def test_controlled_error_publishes_only_safe_internal_code():
    payload = {
        "diagnostic_status": "controlled_observability_error",
        "error_code": "probe_trace_http_status_mismatch",
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
    }
    assert _contexts(payload) == {
        "precios-sps/obs/result/controlled_observability_error",
        "precios-sps/obs/error/probe_trace_http_status_mismatch",
    }


def test_unsafe_controlled_error_code_is_not_reflected():
    payload = {
        "diagnostic_status": "controlled_observability_error",
        "error_code": "secret value\nshould-not-appear",
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
    }
    assert "precios-sps/obs/error/invalid-safe-code" in _contexts(payload)


def test_extract_payload_requires_explicit_sanitization_and_no_authority(tmp_path: Path):
    path = tmp_path / "comment.json"
    body = {
        "diagnostic_status": "shape_collected",
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
    }
    path.write_text(
        json.dumps({"body": "header\n```json\n" + json.dumps(body) + "\n```"}),
        encoding="utf-8",
    )
    assert module._extract_payload(path) == body

    body["production_authority"] = True
    path.write_text(
        json.dumps({"body": "header\n```json\n" + json.dumps(body) + "\n```"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="diagnostic_authority_invalid"):
        module._extract_payload(path)


def test_status_contexts_are_bounded_and_never_include_raw_candidate_values():
    payload = {
        "diagnostic_status": "shape_collected",
        "trace_candidate_count": 10000,
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
        "candidate_shapes": [
            {
                "events_view": {
                    "events": {
                        "mapping_event_count": 1,
                        "source_types": {"mapping": 1},
                        "expected_custom_span_match_counts": {"unexpected-path": 1},
                        "standard_attribute_presence_counts": {
                            "attacker:http.response.status_code": 1,
                            "source.resource:url.full": 1,
                        },
                        "precios_attribute_key_locations": ["event-secret-value"],
                    }
                }
            }
        ],
    }
    contexts = _contexts(payload)
    assert "precios-sps/obs/trace-candidates/999" in contexts
    assert "precios-sps/obs/http-status/none" in contexts
    assert "precios-sps/obs/url-full/resource" in contexts
    assert all("event-secret-value" not in context for context in contexts)
    assert all(len(context) <= 100 for context in contexts)
