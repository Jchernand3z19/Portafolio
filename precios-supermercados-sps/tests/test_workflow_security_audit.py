"""Auditoría fail-closed del YAML ejecutable de los workflows SPS."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ALL_WORKFLOW_FILES = tuple(sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml"))))


def is_sps_workflow(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8").casefold()
    return any(
        marker in path.name.casefold() or marker in raw
        for marker in (
            "precios-supermercados-sps",
            "la-colonia",
            "la_colonia",
            "la colonia",
            "lacolonia",
        )
    )


WORKFLOWS = tuple(path for path in ALL_WORKFLOW_FILES if is_sps_workflow(path))

PINNED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/github-script": "3a2844b7e9c422d3c10d287c895573f7108da1b3",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
}

PROBE_WORKFLOW = "precios-supermercados-sps-cloudflare-probe.yml"
TEST_WORKFLOW = "precios-supermercados-sps-tests.yml"
COMMAND_WORKFLOW = "precios-supermercados-sps-la-colonia-command.yml"
RECOVERY_WORKFLOW = "precios-supermercados-sps-la-colonia-dispatch-recovery.yml"
LA_DIAGNOSTIC_WORKFLOW = "precios-supermercados-sps-la-colonia-diagnostic.yml"
FACET_WORKFLOW = "precios-supermercados-sps-la-colonia-facet-discovery.yml"
LIVE_WORKFLOW = "precios-supermercados-sps-la-colonia-live.yml"
LOCATION_BINDING_WORKFLOW = "precios-supermercados-sps-la-colonia-location-binding.yml"
LOCATION_BINDING_REQUEST = ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
FULL_RADIOGRAPHY_SCRIPT = "scripts/radiografiar_selector_ubicacion_la_colonia.py"
GOOGLE_SHEETS_STORAGE_WORKFLOW = "precios-supermercados-sps-google-sheets-storage.yml"
GOOGLE_SHEETS_STORAGE_REQUEST = "precios-supermercados-sps/.automation/google-sheets-storage-request.json"
PROBE_GATEWAY_SECRET = "CLOUDFLARE_PROBE_GATEWAY_URL"
PROBE_OBSERVABILITY_SECRET = "CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN"
PROBE_PUBLIC_KEY_VAR = "CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL"
CLOUDFLARE_ACCOUNT_VAR = "CLOUDFLARE_ACCOUNT_ID"
GOOGLE_SHEETS_SERVICE_ACCOUNT_SECRET = "PRECIOS_SPS_GOOGLE_SERVICE_ACCOUNT_JSON"
GOOGLE_SHEETS_SPREADSHEET_VAR = "PRECIOS_SPS_GOOGLE_SPREADSHEET_ID"

EXPECTED_PERMISSIONS = {
    PROBE_WORKFLOW: {"contents": "read"},
    COMMAND_WORKFLOW: {"contents": "read", "pull-requests": "read"},
    RECOVERY_WORKFLOW: {"actions": "read", "contents": "read"},
    LA_DIAGNOSTIC_WORKFLOW: {"contents": "read"},
    FACET_WORKFLOW: {"contents": "read"},
    LIVE_WORKFLOW: {"contents": "read"},
    LOCATION_BINDING_WORKFLOW: {"contents": "read"},
    GOOGLE_SHEETS_STORAGE_WORKFLOW: {"contents": "read"},
    TEST_WORKFLOW: {"contents": "read"},
}

ALLOWED_JOB_PERMISSIONS = {
    PROBE_WORKFLOW: {"controlled-probe": {"contents": "read", "id-token": "write"}},
    GOOGLE_SHEETS_STORAGE_WORKFLOW: {"publish-status": {"statuses": "write"}},
}

EXPECTED_TRIGGERS = {
    PROBE_WORKFLOW: {"workflow_dispatch"},
    COMMAND_WORKFLOW: {"pull_request_target"},
    LA_DIAGNOSTIC_WORKFLOW: {"workflow_dispatch"},
    RECOVERY_WORKFLOW: {"workflow_run"},
    FACET_WORKFLOW: {"workflow_dispatch"},
    LIVE_WORKFLOW: {"workflow_dispatch"},
    LOCATION_BINDING_WORKFLOW: {"push"},
    GOOGLE_SHEETS_STORAGE_WORKFLOW: {"workflow_dispatch", "push"},
    TEST_WORKFLOW: {"workflow_dispatch", "pull_request", "push"},
}

BLOCKED_ENTRYPOINTS = {
    COMMAND_WORKFLOW,
    LA_DIAGNOSTIC_WORKFLOW,
    RECOVERY_WORKFLOW,
    FACET_WORKFLOW,
    LIVE_WORKFLOW,
}

ALLOWED_SECRET_REFERENCES = {
    PROBE_WORKFLOW: {PROBE_GATEWAY_SECRET, PROBE_OBSERVABILITY_SECRET},
    GOOGLE_SHEETS_STORAGE_WORKFLOW: {GOOGLE_SHEETS_SERVICE_ACCOUNT_SECRET},
}
ALLOWED_VAR_REFERENCES = {
    PROBE_WORKFLOW: {PROBE_PUBLIC_KEY_VAR, CLOUDFLARE_ACCOUNT_VAR},
    GOOGLE_SHEETS_STORAGE_WORKFLOW: {GOOGLE_SHEETS_SPREADSHEET_VAR},
}


def load_workflow(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict), f"{path.name}: raíz YAML inválida"
    assert set(value).issuperset({"name", "on", "permissions", "jobs"}), path.name
    return value


def workflows() -> tuple[tuple[Path, dict[str, Any]], ...]:
    assert {path.name for path in WORKFLOWS} == set(EXPECTED_PERMISSIONS)
    return tuple((path, load_workflow(path)) for path in WORKFLOWS)


def jobs(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = value["jobs"]
    assert isinstance(result, dict) and result
    assert all(isinstance(job, dict) for job in result.values())
    return result


def job_steps(job: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    current = job.get("steps", [])
    assert isinstance(current, list)
    assert all(isinstance(step, dict) for step in current)
    return tuple(current)


def steps(value: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for job in jobs(value).values():
        result.extend(job_steps(job))
    return tuple(result)


def action_references(value: dict[str, Any]) -> tuple[str, ...]:
    refs = [str(step["uses"]) for step in steps(value) if step.get("uses") is not None]
    refs.extend(str(job["uses"]) for job in jobs(value).values() if job.get("uses") is not None)
    return tuple(refs)


def secret_references(path: Path) -> set[str]:
    raw = path.read_text(encoding="utf-8")
    return set(re.findall(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)\s*\}\}", raw))


def variable_references(path: Path) -> set[str]:
    raw = path.read_text(encoding="utf-8")
    return set(re.findall(r"\$\{\{\s*vars\.([A-Za-z0-9_]+)\s*\}\}", raw))


def all_jobs_blocked(value: dict[str, Any]) -> bool:
    return all(job.get("if") == "${{ false }}" for job in jobs(value).values())


def test_all_external_actions_are_pinned_to_verified_full_shas():
    for path, workflow in workflows():
        for reference in action_references(workflow):
            action, separator, revision = reference.partition("@")
            assert separator and re.fullmatch(r"[0-9a-f]{40}", revision), (path.name, reference)
            assert PINNED_ACTIONS.get(action) == revision, (path.name, reference)


def test_permissions_secret_and_variable_references_are_exact():
    for path, workflow in workflows():
        assert workflow["permissions"] == EXPECTED_PERMISSIONS[path.name]
        overrides = {
            name: job["permissions"]
            for name, job in jobs(workflow).items()
            if "permissions" in job
        }
        assert overrides == ALLOWED_JOB_PERMISSIONS.get(path.name, {})
        assert secret_references(path) == ALLOWED_SECRET_REFERENCES.get(path.name, set())
        assert variable_references(path) == ALLOWED_VAR_REFERENCES.get(path.name, set())


def test_checkout_identity_is_immutable_and_credentials_are_not_persisted():
    for path, workflow in workflows():
        if path.name == PROBE_WORKFLOW:
            probe_jobs = jobs(workflow)
            privileged_checkout = [
                step for step in job_steps(probe_jobs["controlled-probe"])
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ]
            assert privileged_checkout == []
            verifier_checkout = [
                step for step in job_steps(probe_jobs["verify-evidence"])
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ]
            assert len(verifier_checkout) == 1
            assert verifier_checkout[0]["with"] == {
                "ref": "${{ github.sha }}",
                "persist-credentials": "false",
            }
            continue

        checkout_steps = [
            step for step in steps(workflow)
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        expected_ref = (
            "${{ github.workflow_sha }}"
            if path.name in {COMMAND_WORKFLOW, RECOVERY_WORKFLOW}
            else "${{ github.sha }}"
        )
        assert checkout_steps, path.name
        for step in checkout_steps:
            assert step.get("with") == {"ref": expected_ref, "persist-credentials": "false"}


def test_unrelated_live_entrypoints_remain_globally_blocked():
    by_name = {path.name: workflow for path, workflow in workflows()}
    for name in BLOCKED_ENTRYPOINTS:
        assert all_jobs_blocked(by_name[name]), name
    command = by_name[COMMAND_WORKFLOW]
    assert "actions" not in command["permissions"]
    controller = (
        REPO_ROOT / "precios-supermercados-sps" / "scripts" / "controlar_solicitud_archivo_la_colonia.js"
    ).read_text(encoding="utf-8")
    assert "GLOBAL LIVE BLOCKED" in controller
    assert "/actions/workflows/{workflow_id}/dispatches" not in controller
    assert "github.request(" not in controller


def test_controlled_probe_remains_manual_isolated_and_verified_outside_oidc_job():
    workflow = load_workflow(WORKFLOW_DIR / PROBE_WORKFLOW)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"] in ("", None)
    probe_jobs = jobs(workflow)
    assert set(probe_jobs) == {"controlled-probe", "verify-evidence"}
    privileged = probe_jobs["controlled-probe"]
    verifier = probe_jobs["verify-evidence"]
    assert privileged.get("environment") == "cloudflare-probe"
    assert verifier.get("environment") == "cloudflare-probe"
    assert privileged["permissions"] == {"contents": "read", "id-token": "write"}
    assert verifier.get("needs") == "controlled-probe"
    privileged_raw = "\n".join(str(step) for step in job_steps(privileged))
    verifier_raw = "\n".join(str(step) for step in job_steps(verifier))
    assert "actions/checkout@" not in privileged_raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in verifier_raw
    assert "cloudflare_controlled_probe_verifier" in verifier_raw
    assert "cloudflare_controlled_probe_observability" in verifier_raw


def test_only_controlled_probe_job_can_request_oidc_write_permission():
    for path, workflow in workflows():
        assert "id-token" not in workflow["permissions"]
        for name, job in jobs(workflow).items():
            permissions = job.get("permissions", {})
            if path.name == PROBE_WORKFLOW and name == "controlled-probe":
                assert permissions.get("id-token") == "write"
            else:
                assert "id-token" not in permissions


def test_trigger_sets_are_closed_without_issue_comment_authority():
    for path, workflow in workflows():
        triggers = workflow["on"]
        assert isinstance(triggers, dict)
        assert set(triggers) == EXPECTED_TRIGGERS[path.name]
        assert "issue_comment" not in triggers


def test_pull_request_target_never_checks_out_untrusted_pr_code():
    for path, workflow in workflows():
        if "pull_request_target" not in workflow["on"]:
            continue
        raw = path.read_text(encoding="utf-8")
        assert path.name in BLOCKED_ENTRYPOINTS
        assert all_jobs_blocked(workflow)
        assert "actions: write" not in raw
        assert "github.head_ref" not in raw
        assert "github.event.pull_request.head" not in raw
        checkout = [
            step for step in steps(workflow)
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        assert all(step["with"]["ref"] == "${{ github.workflow_sha }}" for step in checkout)


def test_full_location_radiography_is_exact_single_use_public_page_diagnostic():
    path = WORKFLOW_DIR / LOCATION_BINDING_WORKFLOW
    workflow = load_workflow(path)
    assert workflow["on"] == {
        "push": {"branches": ["main"], "paths": [LOCATION_BINDING_REQUEST]}
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "la-colonia-full-location-radiography",
        "cancel-in-progress": "false",
    }
    binding_jobs = jobs(workflow)
    assert set(binding_jobs) == {"preflight", "full-radiography"}
    preflight = binding_jobs["preflight"]
    live = binding_jobs["full-radiography"]
    assert preflight.get("if") == (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' }}"
    )
    assert live.get("needs") == "preflight"
    assert live.get("if") == "${{ needs.preflight.outputs.allowed == 'true' }}"
    assert "permissions" not in preflight and "permissions" not in live
    assert "environment" not in preflight and "environment" not in live

    preflight_raw = "\n".join(str(step) for step in job_steps(preflight))
    live_raw = "\n".join(str(step) for step in job_steps(live))
    raw = path.read_text(encoding="utf-8")
    assert LOCATION_BINDING_REQUEST in preflight_raw
    assert "precios-sps-la-colonia-full-location-radiography-request/v1" in preflight_raw
    assert "2026-08-23T18:54:18Z" in preflight_raw
    assert "explicit-user-instruction" in preflight_raw
    assert "https://www.lacolonia.com/" in preflight_raw
    assert "targetCity: 'San Pedro Sula'" in preflight_raw
    assert "singleUse: true" in preflight_raw
    assert "authority: false" in preflight_raw
    assert "getCommit" in preflight_raw and "getContent" in preflight_raw
    assert FULL_RADIOGRAPHY_SCRIPT in live_raw
    assert "diagnosticar_binding_ubicacion_la_colonia.py" not in live_raw
    assert "scripts/probar_la_colonia.py" not in live_raw
    assert "scripts/descubrir_facets_la_colonia.py" not in live_raw
    assert "secrets." not in raw
    assert "vars." not in raw
    assert "workflow_dispatch" not in raw
    assert "pull_request:" not in raw
    assert "pull_request_target:" not in raw
    assert "schedule:" not in raw
    assert "issue_comment:" not in raw
    assert "id-token" not in raw
    assert "actions: write" not in raw
    assert "--target" not in raw
    assert "--authorization" not in raw


def test_network_capable_scripts_are_blocked_or_exactly_authorized():
    sensitive_commands = {
        "scripts/probar_la_colonia.py",
        "scripts/diagnosticar_ventanas_la_colonia.py",
        "scripts/descubrir_facets_la_colonia.py",
        "scripts/diagnosticar_binding_ubicacion_la_colonia.py",
        FULL_RADIOGRAPHY_SCRIPT,
    }
    for path, workflow in workflows():
        commands = "\n".join(str(step.get("run", "")) for step in steps(workflow))
        if not any(command in commands for command in sensitive_commands):
            continue
        if path.name == LOCATION_BINDING_WORKFLOW:
            assert FULL_RADIOGRAPHY_SCRIPT in commands
            assert "scripts/probar_la_colonia.py" not in commands
            assert "scripts/diagnosticar_ventanas_la_colonia.py" not in commands
            assert "scripts/descubrir_facets_la_colonia.py" not in commands
            assert "scripts/diagnosticar_binding_ubicacion_la_colonia.py" not in commands
            continue
        assert path.name in BLOCKED_ENTRYPOINTS
        assert all_jobs_blocked(workflow)


def test_google_sheets_storage_remains_controlled_and_least_privilege():
    path = WORKFLOW_DIR / GOOGLE_SHEETS_STORAGE_WORKFLOW
    workflow = load_workflow(path)
    assert set(workflow["on"]) == {"workflow_dispatch", "push"}
    assert workflow["on"]["push"] == {
        "branches": ["main"],
        "paths": [GOOGLE_SHEETS_STORAGE_REQUEST],
    }
    assert workflow["permissions"] == {"contents": "read"}
    storage_jobs = jobs(workflow)
    assert set(storage_jobs) == {"preflight", "storage", "publish-status"}
    assert storage_jobs["storage"].get("environment") == "precios-sps-storage"
    assert storage_jobs["publish-status"].get("permissions") == {"statuses": "write"}
    raw = path.read_text(encoding="utf-8")
    assert GOOGLE_SHEETS_SERVICE_ACCOUNT_SECRET in raw
    assert GOOGLE_SHEETS_SPREADSHEET_VAR in raw
    assert "pull_request_target:" not in raw
    assert "issue_comment:" not in raw
    assert "id-token" not in raw


def test_ci_paths_cover_project_policy_and_every_sps_workflow():
    workflow = load_workflow(WORKFLOW_DIR / TEST_WORKFLOW)
    expected_paths = {"precios-supermercados-sps/**", ".github/workflows/**"}
    assert set(workflow["on"]["pull_request"]["paths"]) == expected_paths
    assert set(workflow["on"]["push"]["paths"]) == expected_paths
    assert workflow["on"]["push"]["branches"] == ["main"]


@pytest.mark.parametrize("suffix", [".yml", ".yaml"])
def test_renamed_sps_workflow_is_still_classified(tmp_path: Path, suffix: str):
    fake = tmp_path / f"backdoor{suffix}"
    fake.write_text(
        "name: alternate\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
        "jobs:\n  bypass:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: python precios-supermercados-sps/scripts/probar_la_colonia.py\n",
        encoding="utf-8",
    )
    assert is_sps_workflow(fake)


def test_job_level_reusable_workflow_reference_cannot_evade_pin_audit():
    workflow = {"jobs": {"bypass": {"uses": "attacker/example/.github/workflows/live.yml@main"}}}
    reference = action_references(workflow)[0]
    action, separator, revision = reference.partition("@")
    assert separator
    assert not re.fullmatch(r"[0-9a-f]{40}", revision)
    assert action not in PINNED_ACTIONS


def test_yaml_comments_cannot_satisfy_a_security_field(tmp_path: Path):
    fake = tmp_path / "fake.yml"
    fake.write_text(
        "name: fake\non:\n  workflow_dispatch:\n# permissions:\n#   contents: read\n"
        "jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      # - uses: actions/checkout@{PINNED_ACTIONS['actions/checkout']}\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        load_workflow(fake)
