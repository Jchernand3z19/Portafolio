from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
LEGACY_SCRIPT = REPO_ROOT / "precios-supermercados-sps/scripts/diagnosticar_binding_ubicacion_la_colonia.py"
FULL_SCRIPT = REPO_ROOT / "precios-supermercados-sps/scripts/radiografiar_selector_ubicacion_la_colonia.py"
REQUEST = ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
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


def load_legacy_script_module():
    spec = importlib.util.spec_from_file_location("location_binding_cli", LEGACY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_radiography_is_single_use_push_only_and_least_privilege() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["on"]) == {"push"}
    assert workflow["on"]["push"] == {"branches": ["main"], "paths": [REQUEST]}
    assert workflow["concurrency"] == {
        "group": "la-colonia-full-location-radiography",
        "cancel-in-progress": "false",
    }
    assert set(workflow["jobs"]) == {"preflight", "full-radiography"}
    preflight = workflow["jobs"]["preflight"]
    live = workflow["jobs"]["full-radiography"]
    assert preflight["if"] == (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' }}"
    )
    assert live["needs"] == "preflight"
    assert live["if"] == "${{ needs.preflight.outputs.allowed == 'true' }}"
    assert "permissions" not in preflight
    assert "permissions" not in live
    assert "environment" not in preflight
    assert "environment" not in live


def test_preflight_binds_current_human_instruction_and_exact_merge_shape() -> None:
    workflow = load_workflow()
    raw = "\n".join(str(step) for step in workflow["jobs"]["preflight"]["steps"])
    assert "precios-sps-la-colonia-full-location-radiography-request/v1" in raw
    assert "2026-08-23T18:54:18Z" in raw
    assert "explicit-user-instruction" in raw
    assert "https://www.lacolonia.com/" in raw
    assert "San Pedro Sula" in raw
    assert "singleUse: true" in raw
    assert "authority: false" in raw
    assert "getCommit" in raw
    assert "getContent" in raw
    assert "full_radiography_trigger_not_exact_commit" in raw
    assert "full_radiography_marker_contract_mismatch" in raw


def test_runtime_is_fixed_and_publishes_only_diagnostic_artifact_directory() -> None:
    workflow = load_workflow()
    steps = workflow["jobs"]["full-radiography"]["steps"]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }
    runtime = next(
        step for step in steps
        if "radiografiar_selector_ubicacion_la_colonia.py" in str(step.get("run", ""))
    )
    assert "--output-dir precios-supermercados-sps/diagnostic-artifacts/full-location-radiography" in runtime["run"]
    assert "--target" not in runtime["run"]
    assert "--authorization" not in runtime["run"]
    upload = next(step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    assert upload["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert upload["with"]["path"] == (
        "precios-supermercados-sps/diagnostic-artifacts/full-location-radiography/"
    )


def test_workflow_has_no_secret_oidc_dispatch_or_untrusted_entrypoint() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "secrets.",
        "vars.",
        "id-token",
        "pull_request_target",
        "issue_comment",
        "schedule:",
        "workflow_dispatch",
        "actions: write",
        "--target",
        "--network-policy",
        "--live-execution",
        "--active-id",
    ):
        assert forbidden not in raw


def test_full_script_is_fixed_to_home_and_does_not_crawl_catalog() -> None:
    raw = FULL_SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_URL = "https://www.lacolonia.com/"' in raw
    assert 'TARGET_CITY = "San Pedro Sula"' in raw
    assert "page.goto(TARGET_URL" in raw
    assert "MAX_CLICK_ATTEMPTS = 8" in raw
    for forbidden in (
        "graphql",
        "facets",
        "search-graphql",
        "productSearch",
        "--target-url",
        "--authorization-id",
    ):
        assert forbidden.casefold() not in raw.casefold()
    assert "catalog_accepted" in raw
    assert "extraction_enabled" in raw
    assert '"authority": False' in raw


def test_consumed_authorizations_remain_blocked_in_legacy_entrypoint(tmp_path: Path) -> None:
    module = load_legacy_script_module()
    for authorization_id in CONSUMED_IDS:
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
        assert '"stop_reason": "authorization_id_consumed"' in rendered
        assert '"browser_started": false' in rendered
        assert '"production_authority": false' in rendered
        assert '"catalog_accepted": false' in rendered
        assert '"extraction_enabled": false' in rendered
