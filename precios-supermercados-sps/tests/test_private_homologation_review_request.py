from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "precios-supermercados-sps-homologation-review.yml"
PUBLICATION = ROOT / ".github" / "workflows" / "precios-supermercados-sps-safe-analytics-publication.yml"
REQUEST = ROOT / "precios-supermercados-sps" / ".automation" / "homologation-review-request.json"


def load_workflow() -> dict[str, object]:
    text = WORKFLOW.read_text(encoding="utf-8")
    # PyYAML 1.1 interpreta `on` como booleano; se valida además por texto.
    document = yaml.safe_load(text)
    assert isinstance(document, dict)
    return document


def test_private_review_request_is_read_only_and_closed_set() -> None:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    assert set(request) == {"schema", "action", "read_only", "reason", "sequence"}
    assert request == {
        "schema": "precios-sps-homologation-review-request/v1",
        "action": "export_private_homologation_review",
        "read_only": True,
        "reason": "initial_production_review",
        "sequence": 1,
    }


def test_private_review_workflow_has_no_write_authority_or_scraping() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    parsed = load_workflow()
    assert parsed["permissions"] == {"contents": "read"}
    assert 'paths:\n      - "precios-supermercados-sps/.automation/homologation-review-request.json"' in workflow
    assert "persist-credentials: false" in workflow
    assert "exportar_revision_homologacion.py" in workflow
    assert "private-homologation-review-${{ github.run_id }}" in workflow
    assert "TURSO_DATABASE_URL" in workflow and "TURSO_AUTH_TOKEN" in workflow
    assert "obtener_catalogo_" not in workflow
    assert "actualizar_mvp_turso_" not in workflow
    assert "git push" not in workflow
    assert "contents: write" not in workflow


def test_private_review_cannot_trigger_safe_publication_by_workflow_name() -> None:
    publication = PUBLICATION.read_text(encoding="utf-8")
    assert "Precios SPS - Generar revisión privada de homologación" not in publication
    assert "review-queue.json" not in publication
