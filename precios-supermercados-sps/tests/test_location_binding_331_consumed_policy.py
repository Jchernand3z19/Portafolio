from __future__ import annotations

import json
from pathlib import Path

import precios_supermercados.diagnostics.la_colonia_location_binding_capture as capture


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
RECONCILE = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
AGENTS = REPO_ROOT / ".github/workflows/AGENTS.md"
SOURCE_SHA = "b5b8aeb707ad66d570ed21aa5843b2943d7c2dbf"
AUTHORIZATION_ID = "LC-location-binding-331"


def test_lc331_is_operationally_consumed_before_offline_reconciliation() -> None:
    assert capture.LIVE_EXECUTION_ENABLED is False
    assert capture.ACTIVE_AUTHORIZATION_IDS == frozenset()
    marker = json.loads(RECONCILE.read_text(encoding="utf-8"))
    assert marker == {
        "schemaVersion": "precios-sps-la-colonia-location-binding-reconcile/v1",
        "authorizationId": AUTHORIZATION_ID,
        "sourceCommitSha": SOURCE_SHA,
        "requestSequence": 1,
        "authority": False,
    }
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert f"const sourceSha = '{SOURCE_SHA}';" in workflow
    assert "if: ${{ false }}" in workflow
    rules = AGENTS.read_text(encoding="utf-8")
    assert AUTHORIZATION_ID in rules
    assert "no hay autorizaciones live activas" in rules
