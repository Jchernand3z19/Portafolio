"""Auditoría del diagnóstico sanitizado de Workers Observability por push confiable."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cloudflare-controlled-probe-observability-shape.yml"
MARKER = "precios-supermercados-sps/ops/cloudflare-probe-observability-diagnostic-request.json"
SCRIPT_NAME = "diagnosticar_observability_sonda_cloudflare.py"
TARGET_PR = "117"

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


def test_shape_diagnostic_runs_only_on_main_marker_push():
    raw, workflow = _load()
    assert workflow["permissions"] == {"contents": "read"}
    triggers = workflow["on"]
    assert isinstance(triggers, dict) and set(triggers) == {"push"}
    trigger = triggers["push"]
    assert trigger["branches"] == ["main"]
    assert trigger["paths"] == [MARKER]
    assert workflow["concurrency"] == {
        "group": "cloudflare-controlled-probe-observability-shape-main",
        "cancel-in-progress": "false",
    }

    assert set(workflow["jobs"]) == {
        "verify-main-marker",
        "publish-main-trigger-heartbeat",
        "inspect-observability-shape",
    }
    assert "pull_request_target" not in raw
    assert "workflow_run" not in raw
    assert "workflow_dispatch" not in raw
    assert "issue_comment" not in raw
    assert "id-token" not in raw
    assert "${{ runner.temp }}" not in raw


def test_main_marker_is_verified_before_environment_or_observability_access():
    raw, workflow = _load()
    job = workflow["jobs"]["verify-main-marker"]
    condition = job["if"]
    assert "github.repository == 'Jchernand3z19/Portafolio'" in condition
    assert "github.event_name == 'push'" in condition
    assert "github.ref == 'refs/heads/main'" in condition
    assert job["permissions"] == {"contents": "read"}
    assert "environment" not in job
    assert "env" not in job
    assert job["outputs"] == {"marker_verified": "${{ steps.verify.outputs.marker_verified }}"}

    steps = job["steps"]
    assert len(steps) == 2
    checkout = steps[0]
    assert checkout["name"] == "Checkout immutable main revision"
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }

    verify = steps[1]
    assert verify["name"] == "Verify exact one-shot marker"
    assert verify["id"] == "verify"
    script = verify["run"]
    assert '"schema": "cloudflare-controlled-probe-observability-diagnostic-request-1"' in script
    assert '"sourceRunId": "32551882793"' in script
    assert '"purpose": "sanitized-shape-observation-only"' in script
    assert '"requestSequence": 3' in script
    assert '"authority": False' in script
    assert "payload != expected" in script
    assert "controlled_observability_marker_mismatch" in script
    assert "marker_verified=true" in script
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" not in str(job)
    assert "secrets." not in str(job)
    assert "environment: cloudflare-probe" not in str(job)
    assert "github.event.pull_request" not in raw


def test_main_push_heartbeat_is_always_visible_without_cloudflare_secrets():
    _, workflow = _load()
    job = workflow["jobs"]["publish-main-trigger-heartbeat"]
    assert job["needs"] == "verify-main-marker"
    assert job["if"] == "${{ always() }}"
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    assert "environment" not in job
    assert job["env"] == {
        "TARGET_PR_NUMBER": TARGET_PR,
        "MARKER_VERIFIED": "${{ needs.verify-main-marker.outputs.marker_verified == 'true' }}",
    }
    assert len(job["steps"]) == 2

    prepare = job["steps"][0]
    assert prepare["name"] == "Prepare sanitized main-push heartbeat"
    script = prepare["run"]
    assert 'HEARTBEAT_PATH="$RUNNER_TEMP/observability-main-push-heartbeat.json"' in script
    assert '"diagnostic_status": "main_push_trigger_observed"' in script
    assert '"marker_verified"' in script
    assert '"contains_no_event_values": True' in script
    assert '"production_authority": False' in script
    assert '"catalog_accepted": False' in script

    publish = job["steps"][1]
    assert publish["name"] == "Publish sanitized main-push heartbeat"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    publish_script = publish["run"]
    assert 'issues/${TARGET_PR_NUMBER}/comments' in publish_script
    assert '--input "$HEARTBEAT_PATH"' in publish_script
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" not in str(job)
    assert "actions/checkout@" not in str(job)
    assert "actions/download-artifact@" not in str(job)


def test_diagnostic_requires_verified_marker_and_executes_only_main_code():
    raw, workflow = _load()
    job = workflow["jobs"]["inspect-observability-shape"]
    assert job["needs"] == "verify-main-marker"
    assert job["if"] == "${{ needs.verify-main-marker.outputs.marker_verified == 'true' }}"
    assert job["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }
    assert job["environment"] == "cloudflare-probe"
    assert job["env"] == {
        "PROBE_PUBLIC_KEY_SPKI_B64URL": "${{ vars.CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL }}",
        "CLOUDFLARE_ACCOUNT_ID": "${{ vars.CLOUDFLARE_ACCOUNT_ID }}",
        "TARGET_PR_NUMBER": TARGET_PR,
    }

    steps = job["steps"]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["name"] == "Checkout immutable main revision only"
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }
    assert "github.event.pull_request" not in raw
    assert "github.head_ref" not in raw
    assert "git checkout" not in raw
    assert "git fetch" not in raw
    assert f"*/scripts/{SCRIPT_NAME}" in raw
    assert 'python "$DIAGNOSTIC_SCRIPT"' in raw


def test_shape_diagnostic_has_no_gateway_oidc_or_physical_probe_capability():
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
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw


def test_shape_diagnostic_always_publishes_only_sanitized_comment_to_fixed_marker_pr():
    _, workflow = _load()
    job = workflow["jobs"]["inspect-observability-shape"]
    steps = job["steps"]
    assert steps[0]["name"] == "Prepare sanitized fallback comment"
    assert "started_without_summary" in steps[0]["run"]
    assert 'PROBE_DIAGNOSTIC_COMMENT_PATH="$RUNNER_TEMP/probe-shape-main-comment.json"' in steps[0]["run"]
    assert '"contains_no_event_values": True' in steps[0]["run"]
    assert '"production_authority": False' in steps[0]["run"]
    assert '"catalog_accepted": False' in steps[0]["run"]

    inspect = next(step for step in steps if step["name"] == "Inspect existing telemetry shape")
    assert inspect["env"] == {
        "PROBE_OBSERVABILITY_TOKEN": "${{ secrets.CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN }}"
    }
    assert 'python "$DIAGNOSTIC_SCRIPT"' in inspect["run"]

    publish = next(step for step in steps if step["name"] == "Publish sanitized diagnostic to marker PR")
    assert publish["if"] == "${{ always() }}"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    script = publish["run"]
    assert 'issues/${TARGET_PR_NUMBER}/comments' in script
    assert '--input "$PROBE_DIAGNOSTIC_COMMENT_PATH"' in script
    assert "PROBE_OBSERVABILITY_TOKEN" not in script
    assert ".probe-evidence" not in script


def test_shape_diagnostic_actions_are_pinned():
    _, workflow = _load()
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" not in step:
                continue
            action, separator, revision = step["uses"].partition("@")
            assert separator and re.fullmatch(r"[0-9a-f]{40}", revision)
            assert PINNED_ACTIONS[action] == revision
