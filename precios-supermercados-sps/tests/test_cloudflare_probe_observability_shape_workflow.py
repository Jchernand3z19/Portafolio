"""Auditoría del diagnóstico automático y sanitizado de Workers Observability."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cloudflare-controlled-probe-observability-shape.yml"

PINNED_ACTIONS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
}


def _load() -> tuple[str, dict[str, object]]:
    raw = WORKFLOW.read_text(encoding="utf-8")
    value = yaml.load(raw, Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return raw, value


def test_shape_diagnostic_is_push_main_self_scoped_and_comment_only_write():
    raw, workflow = _load()
    assert workflow["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }
    triggers = workflow["on"]
    assert isinstance(triggers, dict) and set(triggers) == {"push"}
    push = triggers["push"]
    assert push["branches"] == ["main"]
    assert push["paths"] == [".github/workflows/cloudflare-controlled-probe-observability-shape.yml"]
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict) and set(jobs) == {"inspect-observability-shape"}
    job = jobs["inspect-observability-shape"]
    assert job["environment"] == "cloudflare-probe"
    assert "id-token" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw
    assert "pull-requests: write" not in raw
    assert "contents: write" not in raw


def test_shape_diagnostic_has_no_gateway_or_physical_fetch_capability():
    raw, _ = _load()
    assert "CLOUDFLARE_PROBE_GATEWAY_URL" not in raw
    assert "PROBE_GATEWAY_URL" not in raw
    assert ".workers.dev" not in raw
    assert "/v1/probe" not in raw
    assert "curl " not in raw
    assert "scripts/probar_la_colonia.py" not in raw
    assert "scripts/diagnosticar_ventanas_la_colonia.py" not in raw
    assert "scripts/descubrir_facets_la_colonia.py" not in raw
    assert "lacolonia" not in raw.lower()
    assert "CloudflareObservabilityHttpTransport" in raw
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" in raw


def test_shape_diagnostic_reads_raw_shapes_without_reusing_strict_normalizers():
    raw, _ = _load()
    assert 'SOURCE_RUN_ID: "32551882793"' in raw
    assert 'SOURCE_RUN_ATTEMPT: "1"' in raw
    assert 'SOURCE_COMMIT_SHA: "cc15edef22709911beb1d1b027ae4c9992da1944"' in raw
    assert "verify_controlled_probe_artifact" in raw
    assert "build_trace_summary_query" in raw
    assert "build_trace_events_query" in raw
    assert "build_trace_invocations_query" in raw
    assert "normalize_events_response" not in raw
    assert "normalize_invocations_response" not in raw
    assert "raw_events_shape" in raw
    assert "raw_invocations_shape" in raw
    assert '"contains_no_event_values": True' in raw
    assert '"production_authority": False' in raw
    assert '"catalog_accepted": False' in raw
    assert "expected_custom_span_match_counts" in raw
    assert "metadata_presence_counts" in raw
    assert "standard_attribute_presence_counts" in raw
    assert "safe_keys" in raw
    assert "print(event" not in raw
    assert "json.dumps(artifact" not in raw
    assert "trace_id" not in raw.split('"candidate_shapes"', 1)[-1] if '"candidate_shapes"' in raw else True


def test_shape_diagnostic_always_prepares_and_publishes_only_sanitized_comment():
    raw, workflow = _load()
    steps = workflow["jobs"]["inspect-observability-shape"]["steps"]
    assert steps[0]["name"] == "Prepare sanitized fallback comment"
    assert "started_without_summary" in steps[0]["run"]
    assert 'Path(os.environ["RUNNER_TEMP"], "probe-shape-comment.json")' in steps[0]["run"]

    inspect = next(step for step in steps if step["name"] == "Inspect raw telemetry shape without trusting event schema")
    assert "ControlledProbeObservabilityError" in inspect["run"]
    assert '"error_code": exc.code' in inspect["run"]
    assert '"error_type": type(exc).__name__[:64]' in inspect["run"]
    assert "str(exc)" not in inspect["run"]
    assert "traceback" not in inspect["run"]

    publish = next(step for step in steps if step["name"] == "Publish sanitized diagnostic to technical PR")
    assert publish["if"] == "${{ always() }}"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    script = publish["run"]
    assert 'repos/${GITHUB_REPOSITORY}/issues/103/comments' in script
    assert '--input "$RUNNER_TEMP/probe-shape-comment.json"' in script
    assert "--method POST" in script
    assert "curl " not in script
    assert ".probe-evidence" not in script
    assert "PROBE_OBSERVABILITY_TOKEN" not in script


def test_shape_diagnostic_actions_are_pinned_and_checkout_is_immutable():
    _, workflow = _load()
    steps = workflow["jobs"]["inspect-observability-shape"]["steps"]
    uses_steps = [step for step in steps if "uses" in step]
    for step in uses_steps:
        action, separator, revision = step["uses"].partition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision)
        assert PINNED_ACTIONS[action] == revision

    checkout = next(step for step in uses_steps if step["uses"].startswith("actions/checkout@"))
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }
