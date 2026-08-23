from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
MARKER = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
SOURCE_SHA = "52d305e97f98840f1b3786b3d7358cbaa5e87e46"


def test_full_radiography_reconciliation_targets_only_activation_merge() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = MARKER.read_text(encoding="utf-8")

    assert f"const sourceSha = '{SOURCE_SHA}';" in workflow
    assert SOURCE_SHA in marker
    assert "precios-sps-la-colonia-full-location-radiography-reconcile/v1" in marker
    assert '"authority": false' in marker
    assert "head_sha: sourceSha" in workflow
    assert "event: 'push'" in workflow
    assert "la-colonia-full-location-radiography-${{ steps.source.outputs.run_id }}" in workflow
    assert "reconciliation/radiography.json" in workflow
    assert "full_radiography_authority_contract_invalid" in workflow
    assert "full_radiography_target_contract_invalid" in workflow
    assert "precios-sps/full-radiography-reconcile" in workflow
    assert "precios-sps/full-radiography-selection" in workflow


def test_reconciliation_cannot_execute_live_capture() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    reconcile = workflow.split("reconcile-consumed-authorization:", 1)[1]

    assert "radiography:\n" in workflow
    assert "if: ${{ false }}" in workflow
    assert "radiografiar_selector_ubicacion_la_colonia.py" not in reconcile
    assert "diagnosticar_binding_ubicacion_la_colonia.py" not in reconcile
    assert "page.goto" not in reconcile
    assert "requests.get" not in reconcile
    assert "secrets." not in reconcile
    assert "id-token" not in reconcile
