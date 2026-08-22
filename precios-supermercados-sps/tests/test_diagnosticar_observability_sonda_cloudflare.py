"""Pruebas offline del diagnóstico sanitizado de Observability."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "diagnosticar_observability_sonda_cloudflare.py"
)
SPEC = importlib.util.spec_from_file_location("diagnosticar_observability_sonda_cloudflare", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_direct_custom_span_query_uses_only_known_span_and_optional_fixed_service():
    start = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 21, 12, 1, tzinfo=timezone.utc)

    scoped = module._direct_custom_span_query(
        from_utc=start,
        to_utc=end,
        service_scoped=True,
    )
    any_service = module._direct_custom_span_query(
        from_utc=start,
        to_utc=end,
        service_scoped=False,
    )

    assert scoped["view"] == "events"
    assert scoped["parameters"]["datasets"] == [module.OBSERVABILITY_DATASET]
    scoped_filters = scoped["parameters"]["filters"]
    assert scoped_filters == [
        module._filter("$metadata.service", module.CONTROLLED_PROBE_SERVICE),
        module._filter("$metadata.spanName", module.CONTROLLED_PROBE_SPAN_NAME),
    ]
    assert any_service["parameters"]["filters"] == [
        module._filter("$metadata.spanName", module.CONTROLLED_PROBE_SPAN_NAME)
    ]
    assert scoped["timeframe"] == any_service["timeframe"]


def test_event_summary_reports_presence_without_copying_metadata_values():
    secret_url = "https://secret.invalid/path"
    summary = module._summarize_events(
        [
            {
                "dataset": module.OBSERVABILITY_DATASET,
                "$metadata": {
                    "traceId": "trace-secret",
                    "spanId": "span-secret",
                    "parentSpanId": "parent-secret",
                    "spanName": module.CONTROLLED_PROBE_SPAN_NAME,
                    "service": module.CONTROLLED_PROBE_SERVICE,
                    "statusCode": 200,
                    "url": secret_url,
                    "origin": "fetch",
                    "type": "cf-worker-event",
                },
                "source": {"precios.probe_id": "probe-secret"},
            }
        ]
    )

    assert summary["mapping_event_count"] == 1
    assert summary["metadata_presence_counts"]["statusCode"] == 1
    assert summary["metadata_presence_counts"]["url"] == 1
    assert summary["metadata_presence_counts"]["parentSpanId"] == 1
    assert summary["expected_custom_span_match_counts"] == {"$metadata.spanName": 1}
    assert summary["precios_attribute_key_locations"] == ["source:precios.probe_id"]
    rendered = repr(summary)
    assert "trace-secret" not in rendered
    assert "span-secret" not in rendered
    assert "parent-secret" not in rendered
    assert secret_url not in rendered
    assert "probe-secret" not in rendered


def test_direct_trace_relation_never_exposes_trace_ids():
    response = {
        "result": {
            "events": {
                "events": [
                    {"$metadata": {"traceId": "candidate-secret"}},
                    {"$metadata": {"traceId": "other-secret"}},
                ]
            }
        }
    }
    assert module._direct_trace_relation(response, ["candidate-secret"]) == "mixed"
    assert module._direct_trace_relation(response, ["other-secret"]) == "mixed"

    candidate_only = {
        "result": {"events": {"events": [{"$metadata": {"traceId": "candidate-secret"}}]}}
    }
    assert module._direct_trace_relation(candidate_only, ["candidate-secret"]) == "candidate"
    assert module._direct_trace_relation(candidate_only, ["different-secret"]) == "outside"
