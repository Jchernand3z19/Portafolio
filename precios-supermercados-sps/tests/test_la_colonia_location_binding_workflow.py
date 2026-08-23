from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
SCRIPT = REPO_ROOT / "precios-supermercados-sps/scripts/diagnosticar_binding_ubicacion_la_colonia.py"
REQUEST = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-request.json"
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


def test_workflow_is_manual_least_privilege_and_globally_blocked() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["on"]) == {"workflow_dispatch"}
    dispatch = workflow["on"]["workflow_dispatch"]
    assert set(dispatch) == {"inputs"}
    assert set(dispatch["inputs"]) == {"authorization_id"}
    authorization = dispatch["inputs"]["authorization_id"]
    assert authorization["required"] == "true"
    assert authorization["type"] == "string"

    assert set(workflow["jobs"]) == {"radiography"}
    job = workflow["jobs"]["radiography"]
    assert job["if"] == "${{ false }}"
    assert "environment" not in job
    assert "permissions" not in job
    assert job["timeout-minutes"] == "10"
    assert not REQUEST.exists()


def test_workflow_does_not_expose_secrets_or_live_overrides() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
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
    assert "www.lacolonia.com" not in raw
    for authorization_id in CONSUMED_IDS:
        assert authorization_id in raw


def test_dispatch_input_is_passed_only_through_environment_not_shell_interpolation() -> None:
    workflow = load_workflow()
    job = workflow["jobs"]["radiography"]
    assert job["env"]["AUTHORIZATION_ID"] == "${{ inputs.authorization_id }}"
    run_steps = [
        step
        for step in job["steps"]
        if "diagnosticar_binding_ubicacion_la_colonia.py" in str(step.get("run", ""))
    ]
    assert len(run_steps) == 1
    command = run_steps[0]["run"]
    assert '"$AUTHORIZATION_ID"' in command
    assert "${{ inputs." not in command


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


def test_consumed_authorizations_and_unrelated_ids_stay_blocked(tmp_path: Path) -> None:
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
