from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/precios-supermercados-sps-turso-first-load.yml"


def _workflow() -> dict[str, object]:
    value = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def test_turso_first_load_is_manual_main_only_and_requires_explicit_boolean() -> None:
    workflow = _workflow()
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert set(triggers) == {"workflow_dispatch"}
    dispatch = triggers["workflow_dispatch"]
    assert isinstance(dispatch, dict)
    assert dispatch["inputs"]["apply_initial_snapshot"] == {
        "description": "Confirma la primera carga durable del snapshot inicial aprobado",
        "required": "true",
        "default": "false",
        "type": "boolean",
    }

    jobs = workflow["jobs"]
    assert set(jobs) == {"first-load"}
    job = jobs["first-load"]
    assert "github.repository == 'Jchernand3z19/Portafolio'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "inputs.apply_initial_snapshot == true" in job["if"]
    assert "permissions" not in job
    assert "environment" not in job


def test_turso_first_load_uses_exact_snapshot_sqlite_preflight_and_only_turso_secrets() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert 'SOURCE_ARTIFACT_ID: "9655225996"' in raw
    assert (
        'EXPECTED_ARTIFACT_DIGEST: "0427e88be27df89fd9fcb50ed600ef5c6aef64177bfba92b4af3d2e25756a892"'
        in raw
    )
    assert (
        'EXPECTED_JSON_SHA256: "2780eeffa5ef62f2d1c8c2c8365e88da1ca0006622d2f7b1c3529f834c9b5e50"'
        in raw
    )
    assert "sha256sum --check --strict" in raw
    assert "test_la_colonia_initial_snapshot_turso_integration.py" in raw
    assert "PRECIOS_SPS_APPROVED_SNAPSHOT_JSON" in raw
    assert "scripts/cargar_snapshot_inicial_turso.py" in raw
    assert "--apply" in raw
    assert "secrets.TURSO_DATABASE_URL" in raw
    assert "secrets.TURSO_AUTH_TOKEN" in raw
    assert "missing_required_configuration:TURSO_DATABASE_URL" in raw
    assert "missing_required_configuration:TURSO_AUTH_TOKEN" in raw
    assert "google-github-actions/auth@" not in raw
    assert "id-token" not in raw
    assert "vars." not in raw
    assert "lacolonia.com" not in raw
    assert "schedule:" not in raw
