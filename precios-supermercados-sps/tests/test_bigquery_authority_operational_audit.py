from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = PROJECT_ROOT.parent
GENERIC_BUILDER = "build_bigquery_write_plan"


def test_operational_bigquery_projection_must_cross_source_authority_policy() -> None:
    """Código operativo no puede proyectar un run comercial saltando la política.

    El builder genérico queda disponible para su propio módulo y para tests de
    mecánica BigQuery. La única ruta operacional positiva autorizada es la policy
    de La Colonia, que deriva crev1 y adjunta auditoría pública de la atestación.
    """

    allowed = {
        PROJECT_ROOT / "src/precios_supermercados/bigquery_persistence.py",
        PROJECT_ROOT
        / "src/precios_supermercados/scrapers/la_colonia_commercial_authority.py",
    }
    candidates = [
        *sorted((PROJECT_ROOT / "src").rglob("*.py")),
        *sorted((PROJECT_ROOT / "scripts").rglob("*.py")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yml")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yaml")),
    ]
    violations = []
    for path in candidates:
        if path in allowed:
            continue
        if GENERIC_BUILDER in path.read_text(encoding="utf-8"):
            violations.append(str(path.relative_to(MONOREPO_ROOT)))
    assert violations == []
