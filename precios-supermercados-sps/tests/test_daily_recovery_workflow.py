from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "precios-supermercados-sps-la-colonia-dispatch-recovery.yml"
RECOVERY = ROOT / "precios-supermercados-sps" / "scripts" / "recuperar_actualizacion_diaria.py"
CHECKER = ROOT / "precios-supermercados-sps" / "scripts" / "comprobar_corte_diario_turso.py"


def test_daily_recovery_is_scheduled_main_only_and_bounded() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    recovery = RECOVERY.read_text(encoding="utf-8")
    checker = CHECKER.read_text(encoding="utf-8")

    assert "name: Precios SPS - Recuperación diaria controlada" in workflow
    assert 'cron: "17 14 * * *"' in workflow
    assert 'cron: "17 18 * * *"' in workflow
    assert "pull_request:" not in workflow
    assert "issue_comment:" not in workflow
    assert "actions: write" in workflow
    assert "contents: read" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "persist-credentials: false" in workflow
    assert "comprobar_corte_diario_turso.py" in workflow
    assert "recuperar_actualizacion_diaria.py" in workflow
    assert "steps.daily_cut.outputs.complete == 'false'" in workflow
    assert "MAX_RUN_ATTEMPTS = 3" in recovery
    assert 'RETRYABLE_CONCLUSIONS = {"failure", "timed_out"}' in recovery
    assert "rerun-failed-jobs" in recovery
    assert 'run.get("event") != "schedule"' in recovery
    assert "scheduled_run_missing_today" in recovery
    assert "daily_cut_missing_after_successful_run" in recovery
    assert "EXPECTED_SCOPE" in checker
    assert '"complete_today": not missing' in checker


def test_daily_recovery_does_not_create_or_dispatch_a_new_live_run() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    recovery = RECOVERY.read_text(encoding="utf-8")
    combined = workflow + recovery

    assert "/dispatches" not in combined
    assert "repository_dispatch" not in combined
    assert "workflow_dispatch" in workflow  # operator may run the recovery check itself
    assert "live_read_only_authorized" not in workflow
    assert "rerun-failed-jobs" in recovery
    assert "event=schedule" in recovery
