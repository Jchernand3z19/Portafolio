from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/precios-supermercados-sps-la-colonia-location-binding.yml"
MARKER = REPO_ROOT / ".github/workflows/requests/la-colonia-location-binding-reconcile-request.json"
SOURCE_SHA = "dcc3894185517cb778db2d3b30e8edfa4822726f"
AUTHORIZATION_ID = "LC-location-binding-337"


def test_reconciliation_targets_only_lc337_activation_merge_without_live_execution() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = MARKER.read_text(encoding="utf-8")

    assert f"const sourceSha = '{SOURCE_SHA}';" in workflow
    assert SOURCE_SHA in marker
    assert AUTHORIZATION_ID in marker
    assert '"requestSequence": 1' in marker
    assert '"authority": false' in marker
    assert "event: 'push'" in workflow
    assert "head_sha: sourceSha" in workflow
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
    assert "city_control_diagnostic" in workflow
    assert "radiography:\n" in workflow
    assert "if: ${{ false }}" in workflow
    assert "www.lacolonia.com" not in workflow
    assert "page.goto" not in workflow
