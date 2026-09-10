from __future__ import annotations

from datetime import datetime, timezone

from scripts.recuperar_actualizacion_diaria import choose_recovery_action


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def run(**overrides: object) -> dict[str, object]:
    value = {
        "id": 123,
        "event": "schedule",
        "created_at": "2026-09-10T11:17:00Z",
        "status": "completed",
        "conclusion": "failure",
        "run_attempt": 1,
    }
    value.update(overrides)
    return value


def test_retryable_failure_requests_rerun_until_attempt_limit() -> None:
    decision = choose_recovery_action([run()], now_utc=NOW)
    assert decision == {
        "run_id": 123,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "failure",
        "action": "rerun",
        "reason": "retryable_scheduled_failure",
    }
    second = choose_recovery_action([run(run_attempt=2)], now_utc=NOW)
    assert second["action"] == "rerun"
    third = choose_recovery_action([run(run_attempt=3)], now_utc=NOW)
    assert third["action"] == "alert"
    assert third["reason"] == "recovery_attempt_limit_reached"


def test_active_run_is_not_rerun_concurrently() -> None:
    decision = choose_recovery_action(
        [run(status="in_progress", conclusion=None, run_attempt=2)], now_utc=NOW
    )
    assert decision["action"] == "wait"
    assert decision["reason"] == "scheduled_run_still_active"


def test_success_with_missing_daily_cut_alerts_instead_of_recrawling() -> None:
    decision = choose_recovery_action([run(conclusion="success")], now_utc=NOW)
    assert decision["action"] == "alert"
    assert decision["reason"] == "daily_cut_missing_after_successful_run"


def test_cancelled_or_manual_runs_are_never_automatic_recovery_targets() -> None:
    cancelled = choose_recovery_action([run(conclusion="cancelled")], now_utc=NOW)
    assert cancelled["action"] == "alert"
    assert cancelled["reason"] == "non_retryable_conclusion:cancelled"
    manual = run(event="workflow_dispatch")
    missing = choose_recovery_action([manual], now_utc=NOW)
    assert missing == {"action": "alert", "reason": "scheduled_run_missing_today"}


def test_only_latest_scheduled_run_from_current_honduras_day_is_considered() -> None:
    old = run(id=1, created_at="2026-09-09T11:17:00Z", conclusion="failure")
    current = run(id=2, created_at="2026-09-10T11:17:00Z", conclusion="timed_out", run_attempt=1)
    later = run(id=3, created_at="2026-09-10T15:00:00Z", status="in_progress", conclusion=None)
    decision = choose_recovery_action([old, current, later], now_utc=NOW)
    assert decision["run_id"] == 3
    assert decision["action"] == "wait"
