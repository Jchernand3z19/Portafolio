from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from precios_supermercados.automation.la_colonia_file_dispatcher import (
    ALLOWED_WORKFLOWS,
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
FACET_WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml"
RECOVERY_WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-dispatch-recovery.yml"
OBSERVER = REPO_ROOT / "precios-supermercados-sps/scripts/validar_resultado_controlador_la_colonia.js"
OPERATIONAL = REPO_ROOT / "precios-supermercados-sps/.automation/la-colonia-live-command.json"
SOURCE_RUN_ID = "31070000001"


def valid_context(**overrides):
    value = {
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
    value.update(overrides)
    return value


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


def normal_command(**overrides):
    value = {
        "request_id": "la-colonia-smoke-10-001",
        "supermarket": "la_colonia",
        "mode": "smoke",
        "page_size": 10,
        "max_pages": 2,
        "max_products": 0,
        "delay_seconds": 1.5,
        "profile": "baseline",
        "thresholds": None,
        "allow_full": False,
    }
    value.update(overrides)
    return value


def diagnostic_command(**overrides):
    value = {
        "request_id": "la-colonia-window-diagnostic-380-399-001",
        "supermarket": "la_colonia",
        "mode": "diagnostic_overlap",
        "diagnostic_plan": "frontier_380_399_v1",
        "delay_seconds": 1.5,
        "allow_full": False,
    }
    value.update(overrides)
    return value


def decide(command, comments=()):
    return evaluate_file_request(valid_context(), json.dumps(command), comments)


def run_observer(tmp_path: Path, artifact: dict):
    node = shutil.which("node")
    assert node is not None
    result_path = tmp_path / "dispatcher-result.json"
    summary_path = tmp_path / "summary.md"
    result_path.write_text(json.dumps(artifact), encoding="utf-8")
    env = {
        **os.environ,
        "RESULT_PATH": str(result_path),
        "SOURCE_RUN_ID": SOURCE_RUN_ID,
        "GITHUB_STEP_SUMMARY": str(summary_path),
    }
    completed = subprocess.run(
        [node, str(OBSERVER)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    return completed, summary


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


def test_facet_contract_exact_is_accepted():
    decision = decide(facet_command())
    assert decision.accepted
    assert decision.mode == "facet_discovery"


def test_facet_workflow_is_selected_by_trusted_code():
    assert decide(facet_command()).workflow == FACET_DISCOVERY_WORKFLOW


def test_facet_inputs_are_exactly_normalized():
    assert decide(facet_command()).inputs == {
        "request_id": FACET_DISCOVERY_REQUEST_ID,
        "discovery_plan": FACET_DISCOVERY_PLAN,
        "delay_seconds": "1.5",
    }


def test_controller_effective_allow_list_contains_exactly_three_workflows():
    assert TRUSTED_WORKFLOWS == frozenset(
        {LIVE_WORKFLOW, DIAGNOSTIC_WORKFLOW, FACET_DISCOVERY_WORKFLOW}
    )
    assert ALLOWED_WORKFLOWS == frozenset({LIVE_WORKFLOW, DIAGNOSTIC_WORKFLOW})


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"discovery_plan": "unknown"}, "plan"),
        ({"delay_seconds": 1.0}, "1.5"),
        ({"allow_full": True}, "allow_full"),
        ({"request_id": "other"}, "request_id"),
    ],
)
def test_facet_closed_values_are_rejected(override, fragment):
    result = decide(facet_command(**override))
    assert not result.accepted
    assert fragment.lower() in result.reason.lower()


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
    command = facet_command()
    command[field] = "forbidden"
    result = decide(command)
    assert not result.accepted
    assert result.inputs is None


@pytest.mark.parametrize(
    "field",
    ["request_id", "supermarket", "mode", "discovery_plan", "delay_seconds", "allow_full"],
)
def test_missing_facet_fields_are_rejected(field):
    command = facet_command()
    command.pop(field)
    assert not decide(command).accepted


def test_smoke_compatibility_is_preserved():
    result = decide(normal_command())
    assert result.accepted and result.workflow == LIVE_WORKFLOW


def test_staged_compatibility_is_preserved():
    result = decide(
        normal_command(
            request_id="staged-products-001",
            mode="staged",
            page_size=20,
            max_pages=0,
            max_products=100,
        )
    )
    assert result.accepted and result.workflow == LIVE_WORKFLOW


def test_diagnostic_compatibility_is_preserved():
    result = decide(diagnostic_command())
    assert result.accepted and result.workflow == DIAGNOSTIC_WORKFLOW


def test_facet_request_is_idempotent():
    result = decide(facet_command(), [request_marker(FACET_DISCOVERY_REQUEST_ID)])
    assert not result.accepted
    assert not result.should_comment


def test_facet_workflow_only_exposes_workflow_dispatch():
    text = FACET_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    for trigger in (
        "schedule:", "push:", "pull_request:", "pull_request_target:",
        "issue_comment:", "workflow_run:",
    ):
        assert trigger not in text


def test_facet_workflow_has_minimum_permissions():
    text = FACET_WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in text
    for forbidden in ("actions: write", "issues: write", "pull-requests: write"):
        assert forbidden not in text


def test_facet_workflow_checks_out_main_not_pr_code():
    text = FACET_WORKFLOW.read_text(encoding="utf-8")
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "pull_request.head" not in text


def test_facet_workflow_has_fixed_concurrency_timeout_and_delay():
    text = FACET_WORKFLOW.read_text(encoding="utf-8")
    assert "group: la-colonia-facet-discovery" in text
    assert "cancel-in-progress: false" in text
    assert "timeout-minutes: 10" in text
    assert '"DELAY_SECONDS": "1.5"' in text


def test_facet_workflow_only_accepts_three_inputs():
    text = FACET_WORKFLOW.read_text(encoding="utf-8")
    inputs = text.split("inputs:", 1)[1].split("permissions:", 1)[0]
    for expected in ("request_id:", "discovery_plan:", "delay_seconds:"):
        assert expected in inputs
    for forbidden in ("query:", "url:", "selectedFacets:", "from:", "to:", "workflow:"):
        assert forbidden not in inputs


def test_facet_workflow_maps_exit_zero_and_two_to_technical_success():
    text = FACET_WORKFLOW.read_text(encoding="utf-8")
    assert '"$exit_code" -eq 0' in text
    assert '"$exit_code" -eq 2' in text


def test_controller_delegates_only_to_trusted_main_script():
    text = CONTROLLER.read_text(encoding="utf-8")
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "controlar_solicitud_archivo_la_colonia.js" in text
    assert "pull_request.head" not in text


def test_controller_has_required_security_contract_markers():
    text = CONTROLLER.read_text(encoding="utf-8")
    for marker in (
        "const allowedWorkflows = new Map([",
        "workflow_id: selectedWorkflowFile",
        "return_run_details: true",
        "const apiVersion = '2026-03-10';",
        "mode: decision.mode || null",
        "workflow: decision.workflow || null",
        "ref: decision.ref",
    ):
        assert marker in text
    assert "workflow_id: decision.workflow" not in text


def test_controller_runtime_has_exact_three_workflow_choices_and_fixed_facet_ref():
    runtime = (REPO_ROOT / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia.js").read_text(encoding="utf-8")
    assert runtime.count("precios-supermercados-sps-la-colonia-facet-discovery.yml") >= 2
    assert '[FACET_WORKFLOW, new Set(["facet_discovery"])]' in runtime
    assert 'decision.mode === "facet_discovery" ? "main"' in runtime
    assert "workflow_id: selectedWorkflowFile" in runtime
    assert "workflow_id: decision.workflow" not in runtime


def test_controller_runtime_validates_exact_facet_inputs():
    runtime = (REPO_ROOT / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia.js").read_text(encoding="utf-8")
    assert "normalizedInputsAreTrusted" in runtime
    assert 'decision.inputs.request_id === "la-colonia-facet-discovery-001"' in runtime
    assert 'decision.inputs.discovery_plan === "catalog_categories_v1"' in runtime
    assert 'decision.inputs.delay_seconds === "1.5"' in runtime


def test_controller_uses_one_dispatch_and_does_not_retry_after_comment_failure():
    runtime = (REPO_ROOT / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia.js").read_text(encoding="utf-8")
    endpoint = '"POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"'
    assert runtime.count(endpoint) == 1
    assert "comentario pendiente de recuperación por el conector" in runtime


def test_observer_accepts_valid_facet_relation(tmp_path):
    completed, summary = run_observer(tmp_path, observer_artifact())
    assert completed.returncode == 0
    assert "mode: `facet_discovery`" in summary
    assert f"workflow: `{FACET_DISCOVERY_WORKFLOW}`" in summary


def test_observer_rejects_unknown_mode(tmp_path):
    completed, _ = run_observer(tmp_path, observer_artifact(mode="unknown"))
    assert completed.returncode == 1


def test_observer_rejects_unknown_workflow(tmp_path):
    completed, _ = run_observer(tmp_path, observer_artifact(workflow=".github/workflows/arbitrary.yml"))
    assert completed.returncode == 1


def test_observer_rejects_invalid_relation(tmp_path):
    completed, _ = run_observer(tmp_path, observer_artifact(workflow=LIVE_WORKFLOW))
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


def test_observer_summary_is_sanitized(tmp_path):
    completed, summary = run_observer(tmp_path, observer_artifact())
    assert completed.returncode == 0
    for forbidden in ("example.invalid", "productId", "category_value", "price"):
        assert forbidden not in summary


def test_recovery_workflow_still_checks_out_main_and_never_dispatches():
    text = RECOVERY_WORKFLOW.read_text(encoding="utf-8")
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "/dispatches" not in text


def test_operational_file_remains_previous_diagnostic_contract():
    value = json.loads(OPERATIONAL.read_text(encoding="utf-8"))
    assert value == {
        "request_id": "la-colonia-window-diagnostic-380-399-001",
        "supermarket": "la_colonia",
        "mode": "diagnostic_overlap",
        "diagnostic_plan": "frontier_380_399_v1",
        "delay_seconds": 1.5,
        "allow_full": False,
    }
