from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "precios-supermercados-sps-la-colonia-mvp-update.yml"


def _workflow() -> dict[str, object]:
    value = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def test_daily_workflow_uses_one_matrix_child_per_retailer_and_keeps_schedule() -> None:
    workflow = _workflow()
    assert workflow["on"] == {
        "schedule": [{"cron": "17 11 * * *"}],
        "workflow_dispatch": {
            "inputs": {
                "live_read_only_authorized": {
                    "description": "Confirma autorización humana vigente para consultas públicas read-only del MVP",
                    "required": "true",
                    "default": "false",
                    "type": "boolean",
                }
            }
        },
    }
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    assert set(jobs) == {"acquire", "persist"}
    acquire = jobs["acquire"]
    assert acquire["strategy"]["fail-fast"] == "false"
    assert acquire["strategy"]["matrix"]["retailer"] == [
        "la_colonia",
        "los_andes",
        "paiz",
        "colonial",
        "walmart",
        "pricesmart",
    ]
    assert jobs["persist"]["needs"] == "acquire"


def test_acquisition_job_is_read_only_and_publishes_attempt_scoped_handoff() -> None:
    workflow = _workflow()
    acquire = workflow["jobs"]["acquire"]
    raw_steps = "\n".join(str(step) for step in acquire["steps"])
    assert "scripts/ejecutar_adquisicion_diaria.py" in raw_steps
    assert "${{ matrix.retailer }}" in raw_steps
    assert "daily-acquisition-${{ matrix.retailer }}-${{ github.run_id }}-attempt-${{ github.run_attempt }}" in raw_steps
    assert "if': 'always()" in raw_steps or "'if': 'always()'" in raw_steps
    assert "TURSO_DATABASE_URL" not in raw_steps
    assert "TURSO_AUTH_TOKEN" not in raw_steps
    assert "actions: write" not in WORKFLOW.read_text(encoding="utf-8")


def test_persistence_downloads_all_attempts_and_assembles_latest_accepted_handoffs() -> None:
    workflow = _workflow()
    persist = workflow["jobs"]["persist"]
    steps = persist["steps"]
    download = next(step for step in steps if str(step.get("uses", "")).startswith("actions/download-artifact@"))
    assert download["with"] == {
        "pattern": "daily-acquisition-*-${{ github.run_id }}-attempt-*",
        "path": "precios-supermercados-sps/run-artifacts-handoffs",
        "merge-multiple": "false",
    }
    raw_steps = "\n".join(str(step) for step in steps)
    assert "scripts/ensamblar_adquisicion_diaria.py" in raw_steps
    assert "--run-id \"$GITHUB_RUN_ID\"" in raw_steps
    assert "scripts/preflight_mvp_turso_daily.py" in raw_steps
    assert "scripts/actualizar_mvp_turso_la_colonia.py" in raw_steps
    assert "scripts/actualizar_mvp_turso_paiz.py" in raw_steps
    assert "supermercados-mvp-${{ github.run_id }}-attempt-${{ github.run_attempt }}" in raw_steps


def test_scraper_commands_live_only_in_isolated_runner_not_persist_job() -> None:
    workflow = _workflow()
    persist_raw = "\n".join(str(step.get("run", "")) for step in workflow["jobs"]["persist"]["steps"])
    forbidden = (
        "obtener_catalogo_sps_la_colonia_operativo_v2.py",
        "obtener_catalogo_tgu_la_colonia_operativo.py",
        "obtener_catalogo_comisariato_los_andes_operativo.py",
        "obtener_catalogo_paiz_operativo.py",
        "obtener_catalogo_colonial_operativo.py",
        "obtener_catalogo_walmart_operativo.py",
        "obtener_catalogo_pricesmart_operativo.py",
    )
    assert not any(command in persist_raw for command in forbidden)
