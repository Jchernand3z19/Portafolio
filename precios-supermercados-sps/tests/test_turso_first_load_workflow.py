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
    assert set(jobs) == {"prepare-sqlite", "first-load"}

    prepare = jobs["prepare-sqlite"]
    assert "github.repository == 'Jchernand3z19/Portafolio'" in prepare["if"]
    assert "github.ref == 'refs/heads/main'" in prepare["if"]
    assert "inputs.apply_initial_snapshot != true" in prepare["if"]
    assert "permissions" not in prepare
    assert "environment" not in prepare

    first_load = jobs["first-load"]
    assert "github.repository == 'Jchernand3z19/Portafolio'" in first_load["if"]
    assert "github.ref == 'refs/heads/main'" in first_load["if"]
    assert "inputs.apply_initial_snapshot == true" in first_load["if"]
    assert "permissions" not in first_load
    assert "environment" not in first_load


def test_turso_prepare_sqlite_uses_exact_snapshot_and_publishes_verified_database() -> None:
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
    assert "--sqlite-output" in raw
    assert "precios-sps-la-colonia-initial.db" in raw
    assert "PRAGMA integrity_check" in raw
    assert '"offers_current": 9439' in raw
    assert '"offer_history": 9439' in raw
    assert '"source_products": 9439' in raw
    assert "(7081, 2358)" in raw
    assert "(8965, 474, 1003)" in raw
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in raw
    assert "precios-sps-la-colonia-initial-sqlite-32922877781" in raw


def test_turso_direct_first_load_remains_explicit_and_uses_only_turso_secrets() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

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
