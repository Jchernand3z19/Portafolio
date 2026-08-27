from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/precios-supermercados-sps-preserve-initial-snapshot.yml"


def test_preservation_workflow_is_github_only_and_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'SOURCE_ARTIFACT_ID: "9590684834"' in text
    assert (
        'EXPECTED_JSON_SHA256: "2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50"'
        in text
    )
    assert "actions: read" in text
    assert "contents: read" in text
    assert "id-token: write" not in text
    assert "secrets." not in text
    assert "lacolonia.com" not in text
    assert "api.github.com/repos/${GITHUB_REPOSITORY}/actions/artifacts/${SOURCE_ARTIFACT_ID}/zip" in text
    assert "sha256sum --check --strict" in text
    assert '"skus_extracted": 9439' in text
    assert '"catalog_product_coverage": 1.0' in text
    assert "retention-days: 90" in text
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1"
        in text
    )


def test_preservation_runs_on_merge_of_its_own_workflow_file() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in text
    assert "- main" in text
    assert (
        '- ".github/workflows/precios-supermercados-sps-preserve-initial-snapshot.yml"'
        in text
    )
    assert "workflow_dispatch:" in text
