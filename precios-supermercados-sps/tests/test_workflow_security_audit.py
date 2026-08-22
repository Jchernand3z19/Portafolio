"""Auditoría fail-closed del YAML ejecutable de los workflows SPS."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ALL_WORKFLOW_FILES = tuple(
    sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")))
)


def is_sps_workflow(path: Path) -> bool:
    """Clasifica por nombre o contenido para que renombrar no evada la auditoría."""

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
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/github-script": "f28e40c7f34bde8b3046d885e986cb6290c5673b",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
}

PROBE_WORKFLOW = "precios-supermercados-sps-cloudflare-probe.yml"
PROBE_GATEWAY_SECRET = "CLOUDFLARE_PROBE_GATEWAY_URL"
PROBE_PUBLIC_KEY_VAR = "CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL"

EXPECTED_PERMISSIONS = {
    PROBE_WORKFLOW: {"contents": "read"},
    "precios-supermercados-sps-la-colonia-command.yml": {
        "contents": "read",
        "pull-requests": "read",
    },
    "precios-supermercados-sps-la-colonia-dispatch-recovery.yml": {
        "actions": "read",
        "contents": "read",
    },
    "precios-supermercados-sps-la-colonia-diagnostic.yml": {"contents": "read"},
    "precios-supermercados-sps-la-colonia-facet-discovery.yml": {"contents": "read"},
    "precios-supermercados-sps-la-colonia-live.yml": {"contents": "read"},
    "precios-supermercados-sps-tests.yml": {"contents": "read"},
}

ALLOWED_JOB_PERMISSIONS = {
    PROBE_WORKFLOW: {
        "controlled-probe": {
            "contents": "read",
            "id-token": "write",
        }
    }
}

EXPECTED_TRIGGERS = {
    PROBE_WORKFLOW: {"workflow_dispatch"},
    "precios-supermercados-sps-la-colonia-command.yml": {"pull_request_target"},
    "precios-supermercados-sps-la-colonia-diagnostic.yml": {"workflow_dispatch"},
    "precios-supermercados-sps-la-colonia-dispatch-recovery.yml": {"workflow_run"},
    "precios-supermercados-sps-la-colonia-facet-discovery.yml": {"workflow_dispatch"},
    "precios-supermercados-sps-la-colonia-live.yml": {"workflow_dispatch"},
    "precios-supermercados-sps-tests.yml": {
        "workflow_dispatch",
        "pull_request",
        "push",
    },
}

BLOCKED_ENTRYPOINTS = {
    "precios-supermercados-sps-la-colonia-command.yml",
    "precios-supermercados-sps-la-colonia-diagnostic.yml",
    "precios-supermercados-sps-la-colonia-dispatch-recovery.yml",
    "precios-supermercados-sps-la-colonia-facet-discovery.yml",
    "precios-supermercados-sps-la-colonia-live.yml",
}

ALLOWED_SECRET_REFERENCES = {
    PROBE_WORKFLOW: {PROBE_GATEWAY_SECRET},
}
ALLOWED_VAR_REFERENCES = {
    PROBE_WORKFLOW: {PROBE_PUBLIC_KEY_VAR},
}


def load_workflow(path: Path) -> dict[str, Any]:
    """Parsea sin constructores de objetos y conserva `on` como string YAML."""

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
    all_steps: list[dict[str, Any]] = []
    for job in jobs(value).values():
        all_steps.extend(job_steps(job))
    return tuple(all_steps)


def action_references(value: dict[str, Any]) -> tuple[str, ...]:
    references = [
        str(step["uses"])
        for step in steps(value)
        if step.get("uses") is not None
    ]
    references.extend(
        str(job["uses"])
        for job in jobs(value).values()
        if job.get("uses") is not None
    )
    return tuple(references)


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


def test_permissions_are_exact_with_only_explicit_job_overrides_and_references():
    for path, workflow in workflows():
        assert workflow["permissions"] == EXPECTED_PERMISSIONS[path.name]
        actual_overrides = {
            name: job["permissions"]
            for name, job in jobs(workflow).items()
            if "permissions" in job
        }
        assert actual_overrides == ALLOWED_JOB_PERMISSIONS.get(path.name, {})
        assert secret_references(path) == ALLOWED_SECRET_REFERENCES.get(path.name, set())
        assert variable_references(path) == ALLOWED_VAR_REFERENCES.get(path.name, set())


def test_checkout_identity_is_immutable_and_credentials_are_not_persisted():
    for path, workflow in workflows():
        if path.name == PROBE_WORKFLOW:
            probe_jobs = jobs(workflow)
            privileged_checkout = [
                step
                for step in job_steps(probe_jobs["controlled-probe"])
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ]
            assert privileged_checkout == [], "El job con OIDC no debe ejecutar código del repositorio"

            verifier_checkout = [
                step
                for step in job_steps(probe_jobs["verify-evidence"])
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ]
            assert len(verifier_checkout) == 1
            assert verifier_checkout[0]["with"] == {
                "ref": "${{ github.sha }}",
                "persist-credentials": "false",
            }
            continue

        checkout_steps = [
            step for step in steps(workflow) if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        expected_ref = (
            "${{ github.workflow_sha }}"
            if path.name
            in {
                "precios-supermercados-sps-la-colonia-command.yml",
                "precios-supermercados-sps-la-colonia-dispatch-recovery.yml",
            }
            else "${{ github.sha }}"
        )
        assert checkout_steps, path.name
        for step in checkout_steps:
            inputs = step.get("with")
            assert isinstance(inputs, dict)
            assert inputs == {"ref": expected_ref, "persist-credentials": "false"}


def test_privileged_and_live_entrypoints_are_globally_blocked():
    by_name = dict(workflows())
    for name in BLOCKED_ENTRYPOINTS:
        path = WORKFLOW_DIR / name
        assert all_jobs_blocked(by_name[path]), name

    command = by_name[WORKFLOW_DIR / "precios-supermercados-sps-la-colonia-command.yml"]
    assert "actions" not in command["permissions"]
    controller = (
        REPO_ROOT
        / "precios-supermercados-sps"
        / "scripts"
        / "controlar_solicitud_archivo_la_colonia.js"
    ).read_text(encoding="utf-8")
    assert "GLOBAL LIVE BLOCKED" in controller
    assert "/actions/workflows/{workflow_id}/dispatches" not in controller
    assert "github.request(" not in controller


def test_controlled_probe_is_manual_isolated_and_verified_outside_oidc_job():
    path = WORKFLOW_DIR / PROBE_WORKFLOW
    workflow = load_workflow(path)
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert set(triggers) == {"workflow_dispatch"}
    assert triggers["workflow_dispatch"] in ("", None)

    probe_jobs = jobs(workflow)
    assert set(probe_jobs) == {"controlled-probe", "verify-evidence"}
    privileged = probe_jobs["controlled-probe"]
    verifier = probe_jobs["verify-evidence"]
    assert privileged.get("environment") == "cloudflare-probe"
    assert verifier.get("environment") == "cloudflare-probe"
    assert privileged.get("if") != "${{ false }}"
    assert verifier.get("needs") == "controlled-probe"
    assert privileged["permissions"] == {"contents": "read", "id-token": "write"}
    assert "permissions" not in verifier
    assert workflow["permissions"] == {"contents": "read"}

    privileged_raw = "\n".join(str(step) for step in job_steps(privileged))
    verifier_raw = "\n".join(str(step) for step in job_steps(verifier))
    raw = path.read_text(encoding="utf-8")
    assert secret_references(path) == {PROBE_GATEWAY_SECRET}
    assert variable_references(path) == {PROBE_PUBLIC_KEY_VAR}
    assert "actions/checkout@" not in privileged_raw
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in verifier_raw
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" not in verifier_raw
    assert "cloudflare_controlled_probe_verifier" in verifier_raw
    assert "actions/download-artifact@" in verifier_raw
    assert "${{ inputs." not in raw
    assert "github.event.inputs" not in raw
    assert "originUrl" not in raw
    assert "scripts/probar_la_colonia.py" not in raw
    assert "scripts/diagnosticar_ventanas_la_colonia.py" not in raw
    assert "scripts/descubrir_facets_la_colonia.py" not in raw
    assert "urn:precios-sps:cloudflare:probe:v1" in raw
    assert "environment: cloudflare-probe" in raw
    assert ".workers.dev" in raw
    assert "--retry 0" in raw
    assert "${PROBE_GATEWAY_URL%/}/v1/probe" in raw


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
        triggers = workflow["on"]
        if "pull_request_target" not in triggers:
            continue
        assert all_jobs_blocked(workflow)
        raw = path.read_text(encoding="utf-8")
        assert "github.event.pull_request.head" not in raw
        assert "github.head_ref" not in raw
        assert "actions: write" not in raw
        checkout = [
            step for step in steps(workflow) if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        assert all(step["with"]["ref"] == "${{ github.workflow_sha }}" for step in checkout)


def test_network_capable_scripts_exist_only_inside_blocked_jobs():
    sensitive_commands = {
        "scripts/probar_la_colonia.py",
        "scripts/diagnosticar_ventanas_la_colonia.py",
        "scripts/descubrir_facets_la_colonia.py",
    }
    for path, workflow in workflows():
        commands = "\n".join(str(step.get("run", "")) for step in steps(workflow))
        if any(command in commands for command in sensitive_commands):
            assert path.name in BLOCKED_ENTRYPOINTS
            assert all_jobs_blocked(workflow)


def test_ci_paths_cover_project_policy_and_every_sps_workflow():
    workflow = load_workflow(WORKFLOW_DIR / "precios-supermercados-sps-tests.yml")
    expected_paths = {
        "precios-supermercados-sps/**",
        ".github/workflows/**",
    }
    pull_request = workflow["on"]["pull_request"]
    push = workflow["on"]["push"]
    assert set(pull_request["paths"]) == expected_paths
    assert set(push["paths"]) == expected_paths
    assert push["branches"] == ["main"]


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
    workflow = {
        "jobs": {"bypass": {"uses": "attacker/example/.github/workflows/live.yml@main"}}
    }
    assert action_references(workflow) == (
        "attacker/example/.github/workflows/live.yml@main",
    )
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
