from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
SCRIPT = REPO_ROOT / "precios-supermercados-sps/scripts/diagnosticar_binding_ubicacion_la_colonia.py"
REQUEST = ".github/workflows/requests/la-colonia-location-binding-request.json"
AUTHORIZED_ID = "LC-location-binding-337"
CONSUMED_IDS = (
    "LC-location-binding-336",
    "LC-location-binding-331",
    "LC-location-binding-332",
    "LC-location-binding-333",
    "LC-location-binding-334",
    "LC-location-binding-335",
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


def test_workflow_has_only_controlled_main_marker_trigger() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["on"]) == {"push"}
    assert workflow["on"]["push"] == {
        "branches": ["main"],
        "paths": [REQUEST],
    }
    assert workflow["concurrency"] == {
        "group": "la-colonia-location-binding-radiography",
        "cancel-in-progress": "false",
    }


def test_preflight_is_unprivileged_and_requires_exact_versioned_request() -> None:
    workflow = load_workflow()
    assert set(workflow["jobs"]) == {"preflight", "radiography"}
    preflight = workflow["jobs"]["preflight"]
    assert "environment" not in preflight
    assert "permissions" not in preflight
    assert preflight["if"] == (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' }}"
    )
    assert preflight["outputs"] == {
        "allowed": "${{ steps.request.outputs.allowed }}",
        "authorization_id": "${{ steps.request.outputs.authorization_id }}",
        "request_sequence": "${{ steps.request.outputs.request_sequence }}",
    }

    raw = "\n".join(str(step) for step in preflight["steps"])
    assert REQUEST in raw
    assert f"expectedAuthorizationId = '{AUTHORIZED_ID}'" in raw
    for consumed_id in CONSUMED_IDS:
        assert consumed_id in raw
    assert "location_binding_authorization_id_consumed" in raw
    assert "precios-sps-la-colonia-location-binding-request/v1" in raw
    assert "requestSequence" in raw
    assert "maxLogicalActions" in raw
    assert "location_binding_trigger_not_exact_authorized_commit" in raw
    assert "location_binding_request_authority_must_be_false" in raw
    assert "getCommit" in raw
    assert "getContent" in raw
    assert "allowed', 'true" in raw


def test_radiography_runs_only_after_preflight_and_has_no_secret_authority() -> None:
    workflow = load_workflow()
    job = workflow["jobs"]["radiography"]
    assert job["needs"] == "preflight"
    assert job["if"] == "${{ needs.preflight.outputs.allowed == 'true' }}"
    assert "environment" not in job
    assert "permissions" not in job
    assert job["timeout-minutes"] == "10"
    assert job["env"] == {
        "PYTHONPATH": "${{ github.workspace }}/precios-supermercados-sps/src",
        "AUTHORIZATION_ID": "${{ needs.preflight.outputs.authorization_id }}",
    }

    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in raw
    assert "vars." not in raw
    assert "id-token" not in raw
    assert "actions: write" not in raw
    assert "pull_request_target" not in raw
    assert "issue_comment" not in raw
    assert "schedule:" not in raw
    assert "workflow_dispatch" not in raw
    assert "--target" not in raw
    assert "--network-policy" not in raw
    assert "--live-execution" not in raw
    assert "--active-id" not in raw


def test_authorization_is_passed_only_through_preflight_output_and_environment() -> None:
    workflow = load_workflow()
    job = workflow["jobs"]["radiography"]
    run_steps = [
        step
        for step in job["steps"]
        if "diagnosticar_binding_ubicacion_la_colonia.py" in str(step.get("run", ""))
    ]
    assert len(run_steps) == 1
    command = run_steps[0]["run"]
    assert '"$AUTHORIZATION_ID"' in command
    assert "${{ needs.preflight.outputs.authorization_id }}" not in command
    assert "${{ github.event" not in command


def test_checkout_and_artifact_actions_are_pinned_and_output_is_only_sanitized_json() -> None:
    workflow = load_workflow()
    steps = workflow["jobs"]["radiography"]["steps"]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }
    upload = next(step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    assert upload["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert upload["with"]["path"] == (
        "precios-supermercados-sps/diagnostic-artifacts/location-binding-radiography.json"
    )


def test_cli_has_no_live_override_flags_and_prior_authorizations_stay_consumed(tmp_path: Path) -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
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

    module = load_script_module()
    for consumed_id in CONSUMED_IDS:
        output = tmp_path / f"{consumed_id}.json"
        exit_code = module.main(
            [
                "--authorization-id",
                consumed_id,
                "--output-path",
                str(output),
            ]
        )
        assert exit_code == 3
        assert output.exists()
        rendered = output.read_text(encoding="utf-8")
        assert '"stop_reason": "authorization_id_consumed"' in rendered
        assert '"browser_started": false' in rendered
        assert '"target_navigation_started": false' in rendered
        assert '"production_authority": false' in rendered
        assert '"catalog_accepted": false' in rendered
        assert '"extraction_enabled": false' in rendered
