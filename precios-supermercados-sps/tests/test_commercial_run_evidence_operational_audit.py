from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = PROJECT_ROOT.parent
PROTECTED_SYMBOLS = (
    "derive_bound_run_evidence_id",
    "reconcile_bound_durable_run_row",
)


def test_durable_replay_binding_has_only_verified_operational_authority_entrypoint() -> None:
    """El binding durable sólo puede salir por la política autoritativa auditada.

    Un SHA-256 de evidencia + payload no demuestra por sí mismo que
    ``authority_evidence_id`` provenga de una autoridad productiva. El único uso
    operacional permitido es la política de La Colonia que primero verifica una
    atestación Ed25519 y la reconcilia con readiness + provenance exactas. Scripts,
    workflows y cualquier otro módulo siguen sin poder derivar el binding.
    """

    allowed = {
        PROJECT_ROOT / "src/precios_supermercados/commercial_run_evidence.py",
        PROJECT_ROOT
        / "src/precios_supermercados/scrapers/la_colonia_commercial_authority.py",
    }
    candidates = [
        *sorted((PROJECT_ROOT / "src").rglob("*.py")),
        *sorted((PROJECT_ROOT / "scripts").rglob("*.py")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yml")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yaml")),
    ]

    violations: list[str] = []
    for path in candidates:
        if path in allowed:
            continue
        raw = path.read_text(encoding="utf-8")
        if any(symbol in raw for symbol in PROTECTED_SYMBOLS):
            violations.append(str(path.relative_to(MONOREPO_ROOT)))

    assert violations == []
