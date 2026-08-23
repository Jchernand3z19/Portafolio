from __future__ import annotations

from pathlib import Path

import yaml

import precios_supermercados.diagnostics.la_colonia_location_binding_capture as capture


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
AGENTS = REPO_ROOT / ".github/workflows/AGENTS.md"
RECONCILE = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
AUTHORIZATION_IDS = frozenset(
    {
        "LC-location-binding-336",
        "LC-location-binding-331",
        "LC-location-binding-332",
    }
)


def test_consumed_location_binding_authorizations_are_fail_closed_during_reconciliation() -> None:
    assert capture.LIVE_EXECUTION_ENABLED is False
    assert capture.ACTIVE_AUTHORIZATION_IDS == frozenset()
    assert capture.CONSUMED_AUTHORIZATION_IDS == AUTHORIZATION_IDS

    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch", "push"}
    assert workflow["jobs"]["radiography"]["if"] == "${{ false }}"
    assert RECONCILE.exists()

    rules = AGENTS.read_text(encoding="utf-8")
    for authorization_id in AUTHORIZATION_IDS:
        assert authorization_id in rules
    assert "no hay autorizaciones live activas" in rules
