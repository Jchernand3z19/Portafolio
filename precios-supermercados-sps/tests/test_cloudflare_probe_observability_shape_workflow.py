"""Auditoría del diagnóstico sanitizado de Workers Observability por PR controlado."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cloudflare-controlled-probe-observability-shape.yml"
MARKER = "precios-supermercados-sps/ops/cloudflare-probe-observability-diagnostic-request.json"
SCRIPT_NAME = "diagnosticar_observability_sonda_cloudflare.py"

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


def test_shape_diagnostic_uses_controlled_pull_request_target_only():
    raw, workflow = _load()
    assert workflow["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }
    triggers = workflow["on"]
    assert isinstance(triggers, dict) and set(triggers) == {"pull_request_target"}
    trigger = triggers["pull_request_target"]
    assert trigger["types"] == ["opened", "synchronize", "reopened"]
    assert trigger["branches"] == ["main"]
    assert trigger["paths"] == [MARKER]

    job = workflow["jobs"]["inspect-observability-shape"]
    condition = job["if"]
    assert "github.repository == 'Jchernand3z19/Portafolio'" in condition
    assert "github.event.pull_request.head.repo.full_name == github.repository" in condition
    assert "github.event.pull_request.user.login == 'Jchernand3z19'" in condition
    assert "github.event.pull_request.base.ref == 'main'" in condition
    assert "github.event.pull_request.changed_files == 1" in condition
    assert job["environment"] == "cloudflare-probe"
    assert "id-token" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw
    assert "statuses: write" not in raw
    assert "contents: write" not in raw
    assert "workflow_run" not in raw
    assert "workflow_dispatch" not in raw


def test_pull_request_target_executes_only_trusted_base_revision_and_modern_script():
    raw, workflow = _load()
    steps = workflow["jobs"]["inspect-observability-shape"]["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["name"] == "Checkout trusted base revision only"
    assert checkout["with"] == {
        "ref": "${{ github.event.pull_request.base.sha }}",
        "persist-credentials": "false",
    }
    assert raw.count("github.event.pull_request.head") == 1
    assert "github.event.pull_request.head.sha" not in raw
    assert "github.event.pull_request.head.ref" not in raw
    assert "github.head_ref" not in raw
    assert "git checkout" not in raw
    assert "git fetch" not in raw
    assert f"*/scripts/{SCRIPT_NAME}" in raw
    assert 'python "$DIAGNOSTIC_SCRIPT"' in raw
    assert "Inspect raw telemetry shape without trusting event schema" not in raw


def test_shape_diagnostic_has_no_gateway_or_physical_fetch_capability():
    raw, _ = _load()
    lowered = raw.lower()
    assert "cloudflare_probe_gateway_url" not in lowered
    assert "probe_gateway_url" not in lowered
    assert ".workers.dev" not in lowered
    assert "/v1/probe" not in lowered
    assert "curl " not in lowered
    assert "scripts/probar_" not in lowered
    assert "la-colonia" not in lowered
    assert "la_colonia" not in lowered
    assert "la colonia" not in lowered
    assert "lacolonia" not in lowered
    assert "run-id: 32551882793" in raw
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" in raw
    assert "CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL" in raw
    assert "CLOUDFLARE_ACCOUNT_ID" in raw


def test_shape_diagnostic_always_publishes_only_sanitized_comment_to_triggering_pr():
    raw, workflow = _load()
    job = workflow["jobs"]["inspect-observability-shape"]
    assert job["env"]["TARGET_PR_NUMBER"] == "${{ github.event.pull_request.number }}"
    assert job["env"]["PROBE_DIAGNOSTIC_COMMENT_PATH"] == "${{ runner.temp }}/probe-shape-comment.json"
    steps = job["steps"]
    assert steps[0]["name"] == "Prepare sanitized fallback comment"
    assert "started_without_summary" in steps[0]["run"]
    assert '"contains_no_event_values": True' in steps[0]["run"]
    assert '"production_authority": False' in steps[0]["run"]
    assert '"catalog_accepted": False' in steps[0]["run"]

    inspect = next(step for step in steps if step["name"] == "Inspect existing telemetry shape")
    assert inspect["env"] == {
        "PROBE_OBSERVABILITY_TOKEN": "${{ secrets.CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN }}"
    }
    assert 'python "$DIAGNOSTIC_SCRIPT"' in inspect["run"]

    publish = next(step for step in steps if step["name"] == "Publish sanitized diagnostic to triggering PR")
    assert publish["if"] == "${{ always() }}"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    script = publish["run"]
    assert 'issues/${TARGET_PR_NUMBER}/comments' in script
    assert '[[ "$TARGET_PR_NUMBER" =~ ^[1-9][0-9]{0,9}$ ]]' in script
    assert '--input "$PROBE_DIAGNOSTIC_COMMENT_PATH"' in script
    assert "--method POST" in script
    assert "curl " not in script
    assert ".probe-evidence" not in script
    assert "PROBE_OBSERVABILITY_TOKEN" not in script


def test_shape_diagnostic_actions_are_pinned():
    _, workflow = _load()
    steps = workflow["jobs"]["inspect-observability-shape"]["steps"]
    uses_steps = [step for step in steps if "uses" in step]
    for step in uses_steps:
        action, separator, revision = step["uses"].partition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision)
        assert PINNED_ACTIONS[action] == revision
