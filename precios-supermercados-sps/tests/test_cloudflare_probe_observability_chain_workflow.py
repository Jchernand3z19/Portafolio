"""Auditoría del encadenamiento automático y seguro del diagnóstico Cloudflare."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cloudflare-controlled-probe-observability-chain.yml"
SCRIPT = (
    REPO_ROOT
    / "precios-supermercados-sps"
    / "scripts"
    / "diagnosticar_observability_sonda_cloudflare.py"
)

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


def test_chain_runs_only_after_successful_marker_pr_ci():
    raw, workflow = _load()
    assert workflow["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }
    assert set(workflow["on"]) == {"workflow_run"}
    trigger = workflow["on"]["workflow_run"]
    assert trigger["workflows"] == ["Precios Supermercados SPS - Pruebas base"]
    assert trigger["types"] == ["completed"]

    job = workflow["jobs"]["inspect-existing-evidence"]
    condition = job["if"]
    assert "github.event.workflow_run.event == 'pull_request'" in condition
    assert "github.event.workflow_run.conclusion == 'success'" in condition
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in condition
    assert "github.event.workflow_run.head_branch == 'diag/precios-sps-observability-request-001'" in condition
    assert "github.event.workflow_run.actor.login == 'Jchernand3z19'" in condition
    assert "github.event.workflow_run.pull_requests[0].number == 107" in condition
    assert job["environment"] == "cloudflare-probe"
    assert "id-token" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw


def test_chain_executes_only_trusted_default_branch_code():
    raw, workflow = _load()
    job = workflow["jobs"]["inspect-existing-evidence"]
    steps = job["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["name"] == "Checkout trusted default-branch revision only"
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }
    assert "github.event.workflow_run.head_sha" not in raw
    assert "git checkout" not in raw
    assert "git fetch" not in raw
    assert "*/scripts/diagnosticar_observability_sonda_cloudflare.py" in raw
    assert 'python "$DIAGNOSTIC_SCRIPT"' in raw


def test_chain_has_no_gateway_oidc_or_physical_probe_capability():
    raw, _ = _load()
    lowered = raw.lower()
    assert "cloudflare_probe_gateway_url" not in lowered
    assert "probe_gateway_url" not in lowered
    assert ".workers.dev" not in lowered
    assert "/v1/probe" not in lowered
    assert "curl " not in lowered
    assert "la-colonia" not in lowered
    assert "la_colonia" not in lowered
    assert "la colonia" not in lowered
    assert "lacolonia" not in lowered
    assert "scripts/probar_" not in lowered
    assert "run-id: 32551882793" in raw
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" in raw
    assert "CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL" in raw
    assert "CLOUDFLARE_ACCOUNT_ID" in raw


def test_chain_always_publishes_only_sanitized_output_to_fixed_marker_pr():
    raw, workflow = _load()
    job = workflow["jobs"]["inspect-existing-evidence"]
    assert job["env"]["TARGET_PR_NUMBER"] == "107"
    assert job["env"]["PROBE_DIAGNOSTIC_COMMENT_PATH"] == "${{ runner.temp }}/probe-shape-chain-comment.json"
    steps = job["steps"]
    assert steps[0]["name"] == "Prepare sanitized fallback comment"
    assert "started_without_summary" in steps[0]["run"]
    publish = next(step for step in steps if step["name"] == "Publish sanitized diagnostic to marker PR")
    assert publish["if"] == "${{ always() }}"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    script = publish["run"]
    assert 'issues/${TARGET_PR_NUMBER}/comments' in script
    assert '--input "$PROBE_DIAGNOSTIC_COMMENT_PATH"' in script
    assert "PROBE_OBSERVABILITY_TOKEN" not in script
    assert ".probe-evidence" not in script


def test_chain_actions_are_pinned():
    _, workflow = _load()
    steps = workflow["jobs"]["inspect-existing-evidence"]["steps"]
    for step in (step for step in steps if "uses" in step):
        action, separator, revision = step["uses"].partition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision)
        assert PINNED_ACTIONS[action] == revision


def test_diagnostic_script_reports_structure_not_event_values():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert '"contains_no_event_values": True' in raw
    assert '"production_authority": False' in raw
    assert '"catalog_accepted": False' in raw
    assert "verify_controlled_probe_artifact" in raw
    assert "build_trace_summary_query" in raw
    assert "build_trace_events_query" in raw
    assert "build_trace_invocations_query" in raw
    assert "expected_custom_span_match_counts" in raw
    assert "standard_attribute_presence_counts" in raw
    assert "metadata_presence_counts" in raw
    assert "print(raw_event" not in raw
    assert "json.dumps(artifact" not in raw
    assert "str(exc)" not in raw
