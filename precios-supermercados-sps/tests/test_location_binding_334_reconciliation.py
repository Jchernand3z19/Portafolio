from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
REQUEST = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
SOURCE_SHA = "8cf9f0402cf24615744783ce12ff620daa3cb161"
AUTHORIZATION_ID = "LC-location-binding-334"


def test_lc334_reconciliation_targets_exact_consumed_source_without_live_execution() -> None:
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["jobs"]["radiography"]["if"] == "${{ false }}"
    reconcile = workflow["jobs"]["reconcile-consumed-authorization"]
    raw = "\n".join(str(step) for step in reconcile["steps"])
    assert f"const sourceSha = '{SOURCE_SHA}';" in raw
    assert "event: 'push'" in raw
    assert "listWorkflowRuns" in raw
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in raw
    assert "diagnosticar_binding_ubicacion_la_colonia.py" not in raw
    assert "www.lacolonia.com" not in raw

    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    assert request == {
        "schemaVersion": "precios-sps-la-colonia-location-binding-reconcile/v1",
        "authorizationId": AUTHORIZATION_ID,
        "sourceCommitSha": SOURCE_SHA,
        "requestSequence": 1,
        "authority": False,
    }
