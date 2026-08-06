from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from precios_supermercados.automation.la_colonia_file_dispatcher import (
    DIAGNOSTIC_WORKFLOW,
    FACET_DISCOVERY_PLAN,
    FACET_DISCOVERY_REQUEST_ID,
    FACET_DISCOVERY_WORKFLOW,
    LIVE_WORKFLOW,
    TRUSTED_WORKFLOWS,
    evaluate_file_request,
    request_marker,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-command.yml"
CONTROLLER_RUNTIME = REPO_ROOT / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia.js"
FACET_WORKFLOW_FILE = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml"
RECOVERY_WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-dispatch-recovery.yml"
OBSERVER = REPO_ROOT / "precios-supermercados-sps/scripts/validar_resultado_controlador_la_colonia.js"
OPERATIONAL = REPO_ROOT / "precios-supermercados-sps/.automation/la-colonia-live-command.json"
SOURCE_RUN_ID = "31070000001"


def context():
    return {
        "repository_owner": "Jchernand3z19",
        "repository_full_name": "Jchernand3z19/Portafolio",
        "pr_number": 7,
        "state": "open",
        "base_repo_full_name": "Jchernand3z19/Portafolio",
        "head_repo_full_name": "Jchernand3z19/Portafolio",
        "head_repo_fork": False,
        "head_ref": "feature/la-colonia-full-crawl-validation",
        "head_sha": "a" * 40,
        "command_file_changed": True,
        "command_file_status": "ok",
    }


def facet_command(**overrides):
    value = {
        "request_id": FACET_DISCOVERY_REQUEST_ID,
        "supermarket": "la_colonia",
        "mode": "facet_discovery",
        "discovery_plan": FACET_DISCOVERY_PLAN,
        "delay_seconds": 1.5,
        "allow_full": False,
    }
    value.update(overrides)
    return value


def decide(command, comments=()):
    return evaluate_file_request(context(), json.dumps(command), comments)


def observer_artifact(**overrides):
    value = {
        "accepted": True,
        "request_id": FACET_DISCOVERY_REQUEST_ID,
        "mode": "facet_discovery",
        "workflow": FACET_DISCOVERY_WORKFLOW,
        "pr_number": 7,
        "head_sha": "a" * 40,
        "ref": "feature/la-colonia-full-crawl-validation",
        "dispatch_sent": True,
        "live_run_id": "31070000002",
        "live_run_url": "https://example.invalid/run",
        "comment_published": True,
        "comment_method": "rest",
        "controller_run_id": SOURCE_RUN_ID,
        "controller_url": "https://example.invalid/controller",
        "reason": "",
        "warnings": [],
    }
    value.update(overrides)
    return value


def run_observer(tmp_path: Path, artifact: dict):
    node = shutil.which("node")
    assert node is not None
    result_path = tmp_path / "dispatcher-result.json"
    summary_path = tmp_path / "summary.md"
    result_path.write_text(json.dumps(artifact), encoding="utf-8")
    completed = subprocess.run(
        [node, str(OBSERVER)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "RESULT_PATH": str(result_path),
            "SOURCE_RUN_ID": SOURCE_RUN_ID,
            "GITHUB_STEP_SUMMARY": str(summary_path),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    return completed, summary


def test_exact_facet_contract_selects_fixed_workflow_and_inputs():
    decision = decide(facet_command())
    assert decision.accepted is True
    assert decision.mode == "facet_discovery"
    assert decision.workflow == FACET_DISCOVERY_WORKFLOW
    assert decision.inputs == {
        "request_id": FACET_DISCOVERY_REQUEST_ID,
        "discovery_plan": FACET_DISCOVERY_PLAN,
        "delay_seconds": "1.5",
    }


def test_effective_allow_list_contains_exactly_three_workflows():
    assert TRUSTED_WORKFLOWS == frozenset(
        {LIVE_WORKFLOW, DIAGNOSTIC_WORKFLOW, FACET_DISCOVERY_WORKFLOW}
    )


@pytest.mark.parametrize(
    "override",
    [
        {"discovery_plan": "unknown"},
        {"delay_seconds": 1.0},
        {"allow_full": True},
        {"request_id": "other"},
    ],
)
def test_closed_facet_values_are_rejected(override):
    assert decide(facet_command(**override)).accepted is False


@pytest.mark.parametrize(
    "field",
    [
        "URL", "url", "query", "operationName", "selectedFacets", "facet",
        "facet_level", "levels", "category", "from", "to", "orderBy",
        "order_by", "page_size", "max_pages", "max_products", "max_requests",
        "profile", "thresholds", "workflow", "full",
    ],
)
def test_arbitrary_facet_fields_are_rejected(field):
    value = facet_command()
    value[field] = "forbidden"
    decision = decide(value)
    assert decision.accepted is False
    assert decision.inputs is None


@pytest.mark.parametrize(
    "field",
    ["request_id", "supermarket", "mode", "discovery_plan", "delay_seconds", "allow_full"],
)
def test_missing_facet_fields_are_rejected(field):
    value = facet_command()
    value.pop(field)
    assert decide(value).accepted is False


def test_facet_request_is_idempotent():
    decision = decide(facet_command(), [request_marker(FACET_DISCOVERY_REQUEST_ID)])
    assert decision.accepted is False
    assert decision.should_comment is False


def test_facet_workflow_is_manual_with_minimum_permissions_and_main_checkout():
    text = FACET_WORKFLOW_FILE.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "timeout-minutes: 10" in text
    assert "cancel-in-progress: false" in text
    for forbidden in (
        "schedule:", "push:", "pull_request:", "pull_request_target:",
        "issue_comment:", "workflow_run:", "actions: write", "issues: write",
        "pull-requests: write",
    ):
        assert forbidden not in text


def test_facet_workflow_exposes_only_three_inputs_and_maps_exit_two_to_success():
    text = FACET_WORKFLOW_FILE.read_text(encoding="utf-8")
    inputs = text.split("inputs:", 1)[1].split("permissions:", 1)[0]
    for expected in ("request_id:", "discovery_plan:", "delay_seconds:"):
        assert expected in inputs
    for forbidden in ("query:", "url:", "selectedFacets:", "from:", "to:", "workflow:"):
        assert forbidden not in inputs
    assert '"$exit_code" -eq 0' in text
    assert '"$exit_code" -eq 2' in text


def test_controller_workflow_runs_only_trusted_main_module():
    text = CONTROLLER.read_text(encoding="utf-8")
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "controlar_solicitud_archivo_la_colonia.js" in text
    assert "pull_request.head" not in text
    assert "workflow_id: decision.workflow" not in text


def test_controller_runtime_validates_relation_exact_inputs_and_fixed_main_ref():
    text = CONTROLLER_RUNTIME.read_text(encoding="utf-8")
    assert '[FACET_WORKFLOW, new Set(["facet_discovery"])]' in text
    assert 'decision.mode === "facet_discovery" ? "main"' in text
    assert "workflow_id: selectedWorkflowFile" in text
    assert "workflow_id: decision.workflow" not in text
    assert 'decision.inputs.request_id === "la-colonia-facet-discovery-001"' in text
    assert 'decision.inputs.discovery_plan === "catalog_categories_v1"' in text
    assert 'decision.inputs.delay_seconds === "1.5"' in text


def test_controller_runtime_dispatches_once_and_does_not_repeat_after_comment_failure():
    text = CONTROLLER_RUNTIME.read_text(encoding="utf-8")
    endpoint = '"POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"'
    assert text.count(endpoint) == 1
    assert "comentario pendiente de recuperación por el conector" in text


def test_observer_accepts_facet_and_keeps_sanitized_summary(tmp_path):
    completed, summary = run_observer(tmp_path, observer_artifact())
    assert completed.returncode == 0
    assert "mode: `facet_discovery`" in summary
    assert f"workflow: `{FACET_DISCOVERY_WORKFLOW}`" in summary
    for forbidden in ("example.invalid", "productId", "category_value", "price"):
        assert forbidden not in summary


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "unknown"},
        {"workflow": ".github/workflows/arbitrary.yml"},
        {"workflow": LIVE_WORKFLOW},
    ],
)
def test_observer_rejects_unknown_or_invalid_relationships(tmp_path, overrides):
    completed, _ = run_observer(tmp_path, observer_artifact(**overrides))
    assert completed.returncode == 1


def test_observer_keeps_recovery_required(tmp_path):
    completed, _ = run_observer(tmp_path, observer_artifact(comment_published=False))
    assert completed.returncode == 1
    assert "RECOVERY_REQUIRED" in completed.stderr


def test_observer_keeps_legacy_compatibility(tmp_path):
    artifact = observer_artifact()
    artifact.pop("mode")
    artifact.pop("workflow")
    completed, summary = run_observer(tmp_path, artifact)
    assert completed.returncode == 0
    assert "legacy_artifact: `true`" in summary


def test_recovery_workflow_still_checks_out_main_and_never_dispatches():
    text = RECOVERY_WORKFLOW.read_text(encoding="utf-8")
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "/dispatches" not in text


def test_operational_contract_is_unchanged_when_present_on_functional_branch():
    if not OPERATIONAL.exists():
        assert OPERATIONAL.name == "la-colonia-live-command.json"
        return
    assert json.loads(OPERATIONAL.read_text(encoding="utf-8")) == {
        "request_id": "la-colonia-window-diagnostic-380-399-001",
        "supermarket": "la_colonia",
        "mode": "diagnostic_overlap",
        "diagnostic_plan": "frontier_380_399_v1",
        "delay_seconds": 1.5,
        "allow_full": False,
    }
