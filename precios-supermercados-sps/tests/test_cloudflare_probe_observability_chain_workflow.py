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

TARGET_BRANCH = "diag/precios-sps-observability-request-007"
TARGET_PR = "117"


def _load() -> tuple[str, dict[str, object]]:
    raw = WORKFLOW.read_text(encoding="utf-8")
    value = yaml.load(raw, Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return raw, value


def _assert_common_chain_gate(condition: str) -> None:
    assert "github.repository == 'Jchernand3z19/Portafolio'" in condition
    assert "github.event.workflow_run.event == 'pull_request'" in condition
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in condition
    assert f"github.event.workflow_run.head_branch == '{TARGET_BRANCH}'" in condition
    assert "github.event.workflow_run.actor.login" not in condition
    assert "github.event.workflow_run.pull_requests" not in condition


def test_chain_targets_fresh_marker_and_separates_heartbeat_from_environment():
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
    assert workflow["concurrency"]["group"] == "cloudflare-controlled-probe-observability-chain-117"

    jobs = workflow["jobs"]
    assert set(jobs) == {"publish-chain-heartbeat", "inspect-existing-evidence"}
    heartbeat = jobs["publish-chain-heartbeat"]
    diagnostic = jobs["inspect-existing-evidence"]

    _assert_common_chain_gate(heartbeat["if"])
    _assert_common_chain_gate(diagnostic["if"])
    assert "github.event.workflow_run.conclusion == 'success'" not in heartbeat["if"]
    assert "github.event.workflow_run.conclusion == 'success'" in diagnostic["if"]
    assert "environment" not in heartbeat
    assert diagnostic["environment"] == "cloudflare-probe"
    assert heartbeat["env"]["TARGET_PR_NUMBER"] == TARGET_PR
    assert diagnostic["env"]["TARGET_PR_NUMBER"] == TARGET_PR

    assert "id-token" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in raw


def test_runner_temp_is_resolved_only_after_chain_runner_exists():
    raw, workflow = _load()
    assert "${{ runner.temp }}" not in raw

    heartbeat = workflow["jobs"]["publish-chain-heartbeat"]
    diagnostic = workflow["jobs"]["inspect-existing-evidence"]
    assert heartbeat["env"] == {
        "TARGET_PR_NUMBER": TARGET_PR,
        "SOURCE_CI_SUCCESS": "${{ github.event.workflow_run.conclusion == 'success' }}",
    }
    assert diagnostic["env"] == {
        "PROBE_PUBLIC_KEY_SPKI_B64URL": "${{ vars.CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL }}",
        "CLOUDFLARE_ACCOUNT_ID": "${{ vars.CLOUDFLARE_ACCOUNT_ID }}",
        "TARGET_PR_NUMBER": TARGET_PR,
    }

    heartbeat_prepare = heartbeat["steps"][0]["run"]
    assert 'CHAIN_HEARTBEAT_PATH="$RUNNER_TEMP/probe-shape-chain-heartbeat.json"' in heartbeat_prepare
    assert "export CHAIN_HEARTBEAT_PATH" in heartbeat_prepare
    assert "GITHUB_ENV" in heartbeat_prepare

    diagnostic_prepare = diagnostic["steps"][0]["run"]
    assert 'PROBE_DIAGNOSTIC_COMMENT_PATH="$RUNNER_TEMP/probe-shape-chain-comment.json"' in diagnostic_prepare
    assert "export PROBE_DIAGNOSTIC_COMMENT_PATH" in diagnostic_prepare
    assert "GITHUB_ENV" in diagnostic_prepare


def test_chain_heartbeat_is_sanitized_and_has_no_environment_secret_or_checkout():
    _, workflow = _load()
    job = workflow["jobs"]["publish-chain-heartbeat"]
    assert "environment" not in job
    assert job["timeout-minutes"] == "2"
    assert job["env"] == {
        "TARGET_PR_NUMBER": TARGET_PR,
        "SOURCE_CI_SUCCESS": "${{ github.event.workflow_run.conclusion == 'success' }}",
    }
    assert len(job["steps"]) == 2

    prepare = job["steps"][0]
    assert prepare["name"] == "Prepare sanitized chain heartbeat"
    assert "env" not in prepare
    prepare_script = prepare["run"]
    assert '"diagnostic_status": "chain_trigger_observed"' in prepare_script
    assert '"source_ci_success"' in prepare_script
    assert '"contains_no_event_values": True' in prepare_script
    assert '"production_authority": False' in prepare_script
    assert '"catalog_accepted": False' in prepare_script
    assert "PROBE_OBSERVABILITY_TOKEN" not in prepare_script

    publish = job["steps"][1]
    assert publish["name"] == "Publish sanitized chain heartbeat"
    assert publish["env"] == {"GH_TOKEN": "${{ github.token }}"}
    publish_script = publish["run"]
    assert 'issues/${TARGET_PR_NUMBER}/comments' in publish_script
    assert '--input "$CHAIN_HEARTBEAT_PATH"' in publish_script
    assert '[[ "$TARGET_PR_NUMBER" =~ ^[1-9][0-9]{0,9}$ ]]' in publish_script
    assert "PROBE_OBSERVABILITY_TOKEN" not in publish_script
    assert ".probe-evidence" not in publish_script

    assert "actions/checkout@" not in str(job)
    assert "actions/download-artifact@" not in str(job)
    assert "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN" not in str(job)
    assert ".probe-evidence" not in str(job)


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


def test_chain_always_publishes_only_sanitized_output_to_fresh_marker_pr():
    _, workflow = _load()
    job = workflow["jobs"]["inspect-existing-evidence"]
    assert job["env"]["TARGET_PR_NUMBER"] == TARGET_PR
    assert "PROBE_DIAGNOSTIC_COMMENT_PATH" not in job["env"]
    steps = job["steps"]
    assert steps[0]["name"] == "Prepare sanitized fallback comment"
    assert "started_without_summary" in steps[0]["run"]
    assert '"contains_no_event_values": True' in steps[0]["run"]
    assert '"production_authority": False' in steps[0]["run"]
    assert '"catalog_accepted": False' in steps[0]["run"]
    assert "GITHUB_ENV" in steps[0]["run"]

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
    heartbeat = workflow["jobs"]["publish-chain-heartbeat"]
    assert all("uses" not in step for step in heartbeat["steps"])

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
