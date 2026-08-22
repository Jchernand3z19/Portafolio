"""Auditoría de seguridad del workflow que re-verifica evidencia física existente."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cloudflare-controlled-probe-evidence-verify.yml"

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


def test_existing_probe_verifier_is_read_only_manual_and_main_only():
    raw, workflow = _load()
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    triggers = workflow["on"]
    assert isinstance(triggers, dict) and set(triggers) == {"workflow_dispatch"}
    dispatch = triggers["workflow_dispatch"]
    assert isinstance(dispatch, dict) and set(dispatch) == {"inputs"}
    inputs = dispatch["inputs"]
    assert isinstance(inputs, dict)
    assert set(inputs) == {"source_run_id", "source_run_attempt", "source_commit_sha"}
    assert inputs["source_run_id"]["required"] == "true"
    assert inputs["source_run_id"]["type"] == "string"
    assert inputs["source_run_attempt"]["required"] == "true"
    assert inputs["source_run_attempt"]["type"] == "string"
    assert inputs["source_run_attempt"]["default"] == "1"
    assert inputs["source_commit_sha"]["required"] == "true"
    assert inputs["source_commit_sha"]["type"] == "string"

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict) and set(jobs) == {"verify-existing-evidence"}
    job = jobs["verify-existing-evidence"]
    assert job["if"] == "${{ github.ref == 'refs/heads/main' }}"
    assert job["environment"] == "cloudflare-probe"
    assert "permissions" not in job
    assert "id-token" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw


def test_existing_probe_verifier_has_no_gateway_or_live_fetch_capability():
    raw, _ = _load()
    assert "CLOUDFLARE_PROBE_GATEWAY_URL" not in raw
    assert "PROBE_GATEWAY_URL" not in raw
    assert ".workers.dev" not in raw
    assert "/v1/probe" not in raw
    assert "curl " not in raw
    assert "scripts/probar_la_colonia.py" not in raw
    assert "scripts/diagnosticar_ventanas_la_colonia.py" not in raw
    assert "scripts/descubrir_facets_la_colonia.py" not in raw
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" in raw
    assert "CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL" in raw
    assert "CLOUDFLARE_ACCOUNT_ID" in raw


def test_existing_probe_verifier_actions_are_pinned_and_checkout_is_immutable():
    _, workflow = _load()
    job = workflow["jobs"]["verify-existing-evidence"]
    steps = job["steps"]
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

    download = next(step for step in uses_steps if step["uses"].startswith("actions/download-artifact@"))
    assert download["with"] == {
        "name": "precios-sps-cloudflare-controlled-probe",
        "path": ".probe-evidence",
        "github-token": "${{ github.token }}",
        "repository": "${{ github.repository }}",
        "run-id": "${{ inputs.source_run_id }}",
    }


def test_existing_probe_verifier_binds_signed_source_identity_and_only_polls_telemetry():
    raw, _ = _load()
    assert 'expected_commit_sha=os.environ["SOURCE_COMMIT_SHA"]' in raw
    assert 'expected_run_id=os.environ["SOURCE_RUN_ID"]' in raw
    assert 'expected_run_attempt=int(os.environ["SOURCE_RUN_ATTEMPT"])' in raw
    assert "verify_controlled_probe_artifact" in raw
    assert "ControlledProbeObservabilityVerifierClient" in raw
    assert "CloudflareObservabilityHttpTransport" in raw
    assert 'exc.code != "probe_discovery_trace_missing"' in raw
    assert "for query_attempt in range(1, 13):" in raw
    assert "time.sleep(15)" in raw
    assert "production_authority is not False" in raw
    assert "catalog_accepted is not False" in raw
