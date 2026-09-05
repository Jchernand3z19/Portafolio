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

# La implementación previa se conserva byte-for-byte en el módulo base. Esta
# capa sólo registra el nuevo operador productivo y mantiene cerrados los
# conjuntos de workflows/permisos/triggers que la auditoría exige.
base.PRODUCTION_OPERATOR_WORKFLOW = "precios-supermercados-sps-production-operator.yml"
base.PRODUCTION_UPDATE_REQUEST = (
    "precios-supermercados-sps/.automation/production-update-request.json"
)
base.EXPECTED_PERMISSIONS[base.PRODUCTION_OPERATOR_WORKFLOW] = {
    "actions": "write",
    "contents": "read",
}
base.EXPECTED_TRIGGERS[base.PRODUCTION_OPERATOR_WORKFLOW] = {"push"}

# Reexporta íntegramente los tests existentes; sus globals siguen apuntando al
# módulo base ya extendido, de modo que no se pierde ninguna comprobación.
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
