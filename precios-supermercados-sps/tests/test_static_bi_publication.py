from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "precios-supermercados-sps-portfolio-data-sync.yml"
BI_URL = (
    "https://raw.githubusercontent.com/Jchernand3z19/Portafolio/portfolio-data/"
    "precios-supermercados-sps/published/bi/la-colonia-walmart-sps/dataset.json"
)


def test_static_bi_dataset_reuses_the_safe_artifact_without_turso_reads() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "safe-analytics-la-colonia-walmart-sps-${{ github.event.workflow_run.id }}" in raw
    assert "precios-sps-static-bi-dataset/v1" in raw
    assert "precios-sps-publication/v1" in raw
    assert "precios-sps-publication-manifest/v1" in raw
    assert "precios-sps-safe-source-descriptors/v1" in raw
    assert "precios-sps-safe-portfolio-sample/v1" in raw
    assert "fail_closed_strong_identity_and_commercial_consistency" in raw
    assert "portfolio_sync_offer_count_mismatch" in raw
    assert "portfolio_sync_product_count_mismatch" in raw
    assert "portfolio_sync_descriptor_offer_identity_mismatch" in raw
    assert "portfolio_sync_secret_material_detected" in raw
    assert "source_workflow_run_id" in raw
    assert "source_head_sha" in raw
    assert "source_descriptors" in raw
    assert "precios-supermercados-sps/published/bi/la-colonia-walmart-sps/dataset.json" in raw
    assert "precios-supermercados-sps/portfolio/sample-data.json" in raw
    assert "const dataBranch = 'portfolio-data';" in raw
    assert "createOrUpdateFileContents" in raw

    assert "TURSO_DATABASE_URL: ${{ secrets." not in raw
    assert "TURSO_AUTH_TOKEN: ${{ secrets." not in raw
    assert "scripts/exportar_modelo_analitico.py" not in raw
    assert "scripts/generar_descriptores_publicacion_segura.py" not in raw
    assert "actions/checkout@" not in raw


def test_power_bi_refresh_points_to_static_publication_not_turso() -> None:
    readme = (PROJECT_ROOT / "powerbi" / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs" / "BI-IMPLEMENTATION-GUIDE.md").read_text(encoding="utf-8")

    for document in (readme, guide):
        assert BI_URL in document
        assert "precios-sps-static-bi-dataset/v1" in document
        assert "no" in document.casefold() and "turso" in document.casefold()

    assert "publication.offers" in guide
    assert "publication.products" in guide
    assert "publication.common_basket" in guide
    assert "source_descriptors" in guide
