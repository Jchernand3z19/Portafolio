"""Extiende la auditoría histórica de workflows sin degradar sus invariantes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


BASE_PATH = Path(__file__).with_name("_workflow_security_audit_base.py")
SPEC = importlib.util.spec_from_file_location("_workflow_security_audit_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

base.PRODUCTION_OPERATOR_WORKFLOW = "precios-supermercados-sps-production-operator.yml"
base.PRODUCTION_UPDATE_REQUEST = (
    "precios-supermercados-sps/.automation/production-update-request.json"
)
base.SAFE_ANALYTICS_WORKFLOW = "precios-supermercados-sps-safe-analytics-publication.yml"
base.EXPECTED_PERMISSIONS[base.PRODUCTION_OPERATOR_WORKFLOW] = {
    "actions": "write",
    "contents": "read",
}
base.EXPECTED_TRIGGERS[base.PRODUCTION_OPERATOR_WORKFLOW] = {"push"}
base.EXPECTED_PERMISSIONS[base.SAFE_ANALYTICS_WORKFLOW] = {"contents": "read"}
base.EXPECTED_TRIGGERS[base.SAFE_ANALYTICS_WORKFLOW] = {"workflow_run", "workflow_dispatch"}
base.ALLOWED_SECRET_REFERENCES[base.SAFE_ANALYTICS_WORKFLOW] = {
    base.TURSO_DATABASE_URL_SECRET,
    base.TURSO_AUTH_TOKEN_SECRET,
}

for name, value in vars(base).items():
    if name.startswith("test_"):
        globals()[name] = value


def test_production_operator_is_main_only_closed_and_least_privilege() -> None:
    path = base.WORKFLOW_DIR / base.PRODUCTION_OPERATOR_WORKFLOW
    workflow = base.load_workflow(path)
    assert workflow["permissions"] == {"actions": "write", "contents": "read"}
    assert workflow["concurrency"] == {
        "group": "precios-sps-production-operator",
        "cancel-in-progress": "false",
    }
    assert workflow["on"] == {
        "push": {
            "branches": ["main"],
            "paths": [base.PRODUCTION_UPDATE_REQUEST],
        }
    }
    operator_jobs = base.jobs(workflow)
    assert set(operator_jobs) == {"dispatch"}
    dispatch = operator_jobs["dispatch"]
    assert dispatch["if"] == (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' && github.event_name == 'push' }}"
    )
    assert dispatch["timeout-minutes"] == "5"
    assert "environment" not in dispatch
    assert "permissions" not in dispatch

    raw = path.read_text(encoding="utf-8")
    assert base.PRODUCTION_UPDATE_REQUEST in raw
    assert "precios-sps-production-update-request/v1" in raw
    assert "daily_all_productive_retailers" in raw
    assert "production_request_schema_closed_set_mismatch" in raw
    assert "production_request_authorization_window_too_long" in raw
    assert "production_request_authorization_not_current" in raw
    assert "production_request_live_authority_missing" in raw
    assert "production_request_persistence_authority_missing" in raw
    assert "createWorkflowDispatch" in raw
    assert "precios-supermercados-sps-la-colonia-mvp-update.yml" in raw
    assert "ref: 'main'" in raw
    assert "live_read_only_authorized: 'true'" in raw
    assert "secrets." not in raw
    assert "vars." not in raw
    assert "pull_request:" not in raw
    assert "pull_request_target:" not in raw
    assert "issue_comment:" not in raw
    assert "schedule:" not in raw
    assert "id-token" not in raw

    parsed = yaml.load(raw, Loader=yaml.BaseLoader)
    checkout = next(
        step
        for step in parsed["jobs"]["dispatch"]["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": "false",
    }


def test_safe_analytics_publication_is_trusted_read_only_and_fail_closed() -> None:
    path = base.WORKFLOW_DIR / base.SAFE_ANALYTICS_WORKFLOW
    workflow = base.load_workflow(path)
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "precios-sps-safe-analytics-publication",
        "cancel-in-progress": "false",
    }
    assert workflow["on"] == {
        "workflow_run": {
            "workflows": ["Precios SPS - Refrescar homologación derivada"],
            "types": ["completed"],
        },
        "workflow_dispatch": "",
    }
    workflow_jobs = base.jobs(workflow)
    assert set(workflow_jobs) == {"publish"}
    publish = workflow_jobs["publish"]
    assert publish["timeout-minutes"] == "20"
    assert "permissions" not in publish
    assert "environment" not in publish
    expected_if = (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "(github.event_name == 'workflow_dispatch' || "
        "(github.event_name == 'workflow_run' && "
        "github.event.workflow_run.conclusion == 'success' && "
        "github.event.workflow_run.head_branch == 'main')) }}"
    )
    assert " ".join(str(publish["if"]).split()) == " ".join(expected_if.split())

    raw = path.read_text(encoding="utf-8")
    assert "scripts/exportar_modelo_analitico.py" in raw
    assert "scripts/generar_descriptores_publicacion_segura.py" in raw
    assert "scripts/generar_muestra_portafolio_segura.py" in raw
    assert "portfolio-sample.json" in raw
    assert "--scope la_colonia=la_colonia_sps" in raw
    assert "--scope walmart=walmart_sps" in raw
    assert "--scope colonial=colonial_sps" not in raw
    assert "precios-sps-publication/v1" in raw
    assert "precios-sps-safe-source-descriptors/v1" in raw
    assert "precios-sps-safe-portfolio-sample/v1" in raw
    assert "fail_closed_strong_identity_and_commercial_consistency" in raw
    assert "TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}" in raw
    assert "TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}" in raw
    assert "pull_request:" not in raw
    assert "pull_request_target:" not in raw
    assert "issue_comment:" not in raw
    assert "schedule:" not in raw
    assert "id-token" not in raw
    assert "contents: write" not in raw

    parsed = yaml.load(raw, Loader=yaml.BaseLoader)
    checkout = next(
        step
        for step in parsed["jobs"]["publish"]["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert checkout["with"] == {
        "ref": "${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}",
        "persist-credentials": "false",
    }
