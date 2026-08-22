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


def _assert_owner_gate(condition: str) -> None:
    assert "github.repository == 'Jchernand3z19/Portafolio'" in condition
    assert "github.event.pull_request.head.repo.full_name == github.repository" in condition
    assert "github.event.pull_request.user.login == 'Jchernand3z19'" in condition
    assert "github.event.pull_request.base.ref == 'main'" in condition
    assert "github.event.pull_request.changed_files" not in condition


def test_shape_diagnostic_uses_controlled_pull_request_target_only():
    raw, workflow = _load()
    assert workflow["permissions"] == {"contents": "read"}
    triggers = workflow["on"]
    assert isinstance(triggers, dict) and set(triggers) == {"pull_request_target"}
    trigger = triggers["pull_request_target"]
    assert trigger["types"] == ["opened", "synchronize", "reopened"]
    assert trigger["branches"] == ["main"]
    assert trigger["paths"] == [MARKER]

    jobs = workflow["jobs"]
    assert set(jobs) == {
        "verify-marker-change",
        "publish-trigger-heartbeat",
        "inspect-observability-shape",
    }
    preflight = jobs["verify-marker-change"]
    heartbeat = jobs["publish-trigger-heartbeat"]
    diagnostic = jobs["inspect-observability-shape"]
    _assert_owner_gate(preflight["if"])
    assert heartbeat["needs"] == "verify-marker-change"
    assert diagnostic["needs"] == "verify-marker-change"
    expected_gate = "${{ needs.verify-marker-change.outputs.marker_only == 'true' }}"
    assert heartbeat["if"] == expected_gate
    assert diagnostic["if"] == expected_gate
    assert "environment" not in preflight
    assert "environment" not in heartbeat
    assert diagnostic["environment"] == "cloudflare-probe"
    assert "id-token" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw
    assert "statuses: write" not in raw
    assert "contents: write" not in raw
    assert "workflow_run" not in raw
    assert "workflow_dispatch" not in raw
    assert "github.event.pull_request.changed_files" not in raw


def test_marker_change_is_verified_from_github_api_before_privileged_jobs():
    raw, workflow = _load()
    job = workflow["jobs"]["verify-marker-change"]
    assert job["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
    }
    assert job["timeout-minutes"] == "2"
    assert job["outputs"] == {"marker_only": "${{ steps.verify.outputs.marker_only }}"}
    assert job["env"] == {
        "TARGET_PR_NUMBER": "${{ github.event.pull_request.number }}",
        "EXPECTED_MARKER": MARKER,
    }
    assert len(job["steps"]) == 1
    step = job["steps"][0]
    assert step["name"] == "Verify exact marker-only change from GitHub API"
    assert step["id"] == "verify"
    assert step["env"] == {"GH_TOKEN": "${{ github.token }}"}
    script = step["run"]
    assert '[[ "$TARGET_PR_NUMBER" =~ ^[1-9][0-9]{0,9}$ ]]' in script
    assert 'FILES_PATH="$RUNNER_TEMP/observability-marker-files.jsonl"' in script
    assert 'pulls/${TARGET_PR_NUMBER}/files?per_page=100' in script
    assert "--paginate" in script
    assert "@json" in script
    assert 'files == [os.environ["EXPECTED_MARKER"]]' in script
    assert "GITHUB_OUTPUT" in script
    assert "marker_only={'true' if marker_only else 'false'}" in script
    assert "actions/checkout@" not in str(job)
    assert "actions/download-artifact@" not in str(job)
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" not in str(job)
    assert "secrets." not in str(job)
    assert "environment" not in job
    assert "github.event.pull_request.changed_files" not in raw


def test_runner_temp_is_resolved_only_after_runner_exists():
    raw, workflow = _load()
    assert "${{ runner.temp }}" not in raw

    preflight = workflow["jobs"]["verify-marker-change"]
    heartbeat = workflow["jobs"]["publish-trigger-heartbeat"]
    diagnostic = workflow["jobs"]["inspect-observability-shape"]
    preflight_script = preflight["steps"][0]["run"]
    assert 'FILES_PATH="$RUNNER_TEMP/observability-marker-files.jsonl"' in preflight_script

    heartbeat_prepare = heartbeat["steps"][0]["run"]
    assert 'TRIGGER_COMMENT_PATH="$RUNNER_TEMP/observability-trigger-heartbeat.json"' in heartbeat_prepare
    assert "export TRIGGER_COMMENT_PATH" in heartbeat_prepare
    assert "GITHUB_ENV" in heartbeat_prepare

    diagnostic_prepare = diagnostic["steps"][0]["run"]
    assert 'PROBE_DIAGNOSTIC_COMMENT_PATH="$RUNNER_TEMP/probe-shape-comment.json"' in diagnostic_prepare
    assert "export PROBE_DIAGNOSTIC_COMMENT_PATH" in diagnostic_prepare
    assert "GITHUB_ENV" in diagnostic_prepare


def test_trigger_heartbeat_is_sanitized_and_has_no_environment_or_repository_code():
    _, workflow = _load()
    job = workflow["jobs"]["publish-trigger-heartbeat"]
    assert job["needs"] == "verify-marker-change"
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    assert "environment" not in job
    assert job["timeout-minutes"] == "2"
    assert job["env"] == {
        "TARGET_PR_NUMBER": "${{ github.event.pull_request.number }}",
    }
    assert len(job["steps"]) == 2

    prepare = job["steps"][0]
    assert prepare["name"] == "Prepare sanitized trigger heartbeat"
    assert "env" not in prepare
    prepare_script = prepare["run"]
    assert '"diagnostic_status": "trigger_observed"' in prepare_script
    assert '"marker_change_verified": True' in prepare_script
    assert '"contains_no_event_values": True' in prepare_script
    assert '"production_authority": False' in prepare_script
    assert '"catalog_accepted": False' in prepare_script
    assert 'Path(os.environ["TRIGGER_COMMENT_PATH"])' in prepare_script
    assert "PROBE_OBSERVABILITY_TOKEN" not in prepare_script

    publish = job["steps"][1]
    assert publish["name"] == "Publish sanitized trigger heartbeat"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    publish_script = publish["run"]
    assert '[[ "$TARGET_PR_NUMBER" =~ ^[1-9][0-9]{0,9}$ ]]' in publish_script
    assert 'issues/${TARGET_PR_NUMBER}/comments' in publish_script
    assert '--input "$TRIGGER_COMMENT_PATH"' in publish_script
    assert "curl " not in publish_script

    assert "actions/checkout@" not in str(job)
    assert "PROBE_OBSERVABILITY_TOKEN" not in str(job)
    assert ".probe-evidence" not in str(job)
    assert "run-id: 32551882793" not in str(job)
    assert "la-colonia" not in str(job).lower()
    assert "lacolonia" not in str(job).lower()


def test_pull_request_target_executes_only_trusted_base_revision_and_modern_script():
    raw, workflow = _load()
    job = workflow["jobs"]["inspect-observability-shape"]
    assert job["needs"] == "verify-marker-change"
    assert job["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }
    steps = job["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["name"] == "Checkout trusted base revision only"
    assert checkout["with"] == {
        "ref": "${{ github.event.pull_request.base.sha }}",
        "persist-credentials": "false",
    }
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
    _, workflow = _load()
    job = workflow["jobs"]["inspect-observability-shape"]
    assert job["env"]["TARGET_PR_NUMBER"] == "${{ github.event.pull_request.number }}"
    assert "PROBE_DIAGNOSTIC_COMMENT_PATH" not in job["env"]
    steps = job["steps"]
    assert steps[0]["name"] == "Prepare sanitized fallback comment"
    assert "started_without_summary" in steps[0]["run"]
    assert '"contains_no_event_values": True' in steps[0]["run"]
    assert '"production_authority": False' in steps[0]["run"]
    assert '"catalog_accepted": False' in steps[0]["run"]
    assert "GITHUB_ENV" in steps[0]["run"]

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
    preflight = workflow["jobs"]["verify-marker-change"]
    heartbeat = workflow["jobs"]["publish-trigger-heartbeat"]
    assert all("uses" not in step for step in preflight["steps"])
    assert all("uses" not in step for step in heartbeat["steps"])

    steps = workflow["jobs"]["inspect-observability-shape"]["steps"]
    uses_steps = [step for step in steps if "uses" in step]
    for step in uses_steps:
        action, separator, revision = step["uses"].partition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision)
        assert PINNED_ACTIONS[action] == revision
