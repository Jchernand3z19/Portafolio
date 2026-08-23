from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
SCRIPT = REPO_ROOT / "precios-supermercados-sps/scripts/diagnosticar_binding_ubicacion_la_colonia.py"
REQUEST = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-standing-request.json"
RECONCILE_REQUEST = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
CONSUMED_IDS = (
    "LC-location-binding-336",
    "LC-location-binding-331",
    "LC-location-binding-332",
    "LC-location-binding-333",
    "LC-location-binding-334",
    "LC-location-binding-335",
    "LC-location-binding-337",
)


def load_workflow() -> dict:
    value = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def load_script_module():
    spec = importlib.util.spec_from_file_location("location_binding_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_is_bounded_read_only_and_can_run_from_main_marker() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["on"]) == {"workflow_dispatch", "push"}
    assert workflow["on"]["workflow_dispatch"] in ("", None)
    assert workflow["on"]["push"] == {
        "branches": ["main"],
        "paths": [
            ".github/workflows/requests/la-colonia-location-binding-standing-request.json"
        ],
    }

    assert set(workflow["jobs"]) == {"binding", "publish-status"}
    job = workflow["jobs"]["binding"]
    assert job["if"] == (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' }}"
    )
    assert "environment" not in job
    assert "permissions" not in job
    assert job["timeout-minutes"] == "10"
    assert workflow["concurrency"] == {
        "group": "la-colonia-location-binding-read-only",
        "cancel-in-progress": "false",
    }
    assert job["outputs"] == {
        "run_state": "${{ steps.report.outputs.run_state }}",
        "stop_reason": "${{ steps.report.outputs.stop_reason }}",
        "technical_binding_observed": "${{ steps.report.outputs.technical_binding_observed }}",
        "granularity_candidate": "${{ steps.report.outputs.granularity_candidate }}",
        "confidence": "${{ steps.report.outputs.confidence }}",
        "visible_location": "${{ steps.report.outputs.visible_location }}",
        "logical_actions": "${{ steps.report.outputs.logical_actions }}",
    }
    assert not RECONCILE_REQUEST.exists()


def test_workflow_has_versioned_standing_authorization_contract() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "precios-sps-standing-public-readonly-location-binding/v1" in raw
    assert "2026-08-23T21:02:02Z" in raw
    assert "verify-location-binding" in raw
    assert "requestSequence" in raw
    assert "authority" in raw
    assert "--standing-public-read-only" in raw
    assert "--authorization-id" not in raw
    assert "secrets." not in raw
    assert "vars." not in raw
    assert "id-token" not in raw
    assert "actions: write" not in raw
    assert "pull_request_target" not in raw
    assert "issue_comment" not in raw
    assert "schedule:" not in raw
    assert "--target" not in raw
    assert "--network-policy" not in raw
    assert "--live-execution" not in raw
    assert "--active-id" not in raw


def test_checkout_and_artifact_actions_are_pinned_and_output_is_only_sanitized_json() -> None:
    workflow = load_workflow()
    steps = workflow["jobs"]["binding"]["steps"]
    checkout = next(
        step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }
    upload = next(
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    )
    assert upload["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert upload["with"]["path"] == (
        "precios-supermercados-sps/diagnostic-artifacts/location-binding-radiography.json"
    )


def test_status_publisher_is_isolated_and_only_receives_sanitized_outputs() -> None:
    workflow = load_workflow()
    publisher = workflow["jobs"]["publish-status"]
    assert publisher["needs"] == ["binding"]
    assert publisher["if"] == (
        "${{ always() && github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' }}"
    )
    assert publisher["permissions"] == {"contents": "read", "statuses": "write"}
    assert "environment" not in publisher
    assert publisher["env"] == {
        "RUN_STATE": "${{ needs.binding.outputs.run_state }}",
        "STOP_REASON": "${{ needs.binding.outputs.stop_reason }}",
        "TECHNICAL_BINDING": "${{ needs.binding.outputs.technical_binding_observed }}",
        "GRANULARITY": "${{ needs.binding.outputs.granularity_candidate }}",
        "CONFIDENCE": "${{ needs.binding.outputs.confidence }}",
        "VISIBLE_LOCATION": "${{ needs.binding.outputs.visible_location }}",
        "LOGICAL_ACTIONS": "${{ needs.binding.outputs.logical_actions }}",
    }
    raw = "\n".join(str(step) for step in publisher["steps"])
    assert "actions/checkout@" not in raw
    assert "actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3" in raw
    assert "createCommitStatus" in raw
    assert "precios-sps/location-binding-run" in raw
    assert "precios-sps/location-binding-location" in raw
    assert "precios-sps/location-binding-readonly" in raw
    assert "secrets." not in raw


def test_cli_exposes_standing_mode_but_no_runtime_target_or_network_overrides() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "--standing-public-read-only" in raw
    for forbidden in (
        "--target-url",
        "--network-policy",
        "--live-execution-enabled",
        "--active-id",
        "active_ids=",
        "live_execution_enabled=",
        "network_policy=",
        "target_url=",
    ):
        assert forbidden not in raw


def test_legacy_consumed_authorizations_remain_blocked(tmp_path: Path) -> None:
    module = load_script_module()
    for authorization_id, expected_reason in (
        *((authorization_id, "authorization_id_consumed") for authorization_id in CONSUMED_IDS),
        ("LC-location-binding-777", "authorization_id_not_active"),
    ):
        output = tmp_path / f"{authorization_id}.json"
        exit_code = module.main(
            [
                "--authorization-id",
                authorization_id,
                "--output-path",
                str(output),
            ]
        )
        assert exit_code == 3
        rendered = output.read_text(encoding="utf-8")
        assert f'"stop_reason": "{expected_reason}"' in rendered
        assert '"browser_started": false' in rendered
        assert '"target_navigation_started": false' in rendered
        assert '"production_authority": false' in rendered
        assert '"catalog_accepted": false' in rendered
        assert '"extraction_enabled": false' in rendered


def test_marker_is_optional_for_manual_dispatch_and_safe_when_present() -> None:
    if REQUEST.exists():
        value = REQUEST.read_text(encoding="utf-8")
        assert "precios-sps-standing-public-readonly-location-binding/v1" in value
        assert '"authority": false' in value
