#!/usr/bin/env python3
"""Reintenta de forma acotada la actualización diaria programada fallida.

Sólo opera sobre ejecuciones `schedule` del workflow productivo, del día local de
Honduras. Nunca crea una ejecución live nueva: solicita `rerun-failed-jobs` sobre
el mismo run programado y conserva su SHA/ref/actor originales.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

HN_ZONE = ZoneInfo("America/Tegucigalpa")
MAX_RUN_ATTEMPTS = 3
RETRYABLE_CONCLUSIONS = {"failure", "timed_out"}
ACTIVE_STATUSES = {"queued", "in_progress", "waiting", "pending", "requested"}


class RecoveryError(RuntimeError):
    pass


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryError("recovery_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def local_day_window(now_utc: datetime) -> tuple[datetime, datetime]:
    local = now_utc.astimezone(HN_ZONE)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc), (start_local + timedelta(days=1)).astimezone(timezone.utc)


def choose_recovery_action(runs: list[dict[str, Any]], *, now_utc: datetime) -> dict[str, object]:
    start, end = local_day_window(now_utc)
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for run in runs:
        if run.get("event") != "schedule":
            continue
        created_raw = run.get("created_at")
        if not isinstance(created_raw, str):
            continue
        created = parse_utc(created_raw)
        if start <= created < end:
            candidates.append((created, run))
    if not candidates:
        return {"action": "alert", "reason": "scheduled_run_missing_today"}
    _, latest = max(candidates, key=lambda item: item[0])
    status = latest.get("status")
    conclusion = latest.get("conclusion")
    run_id = latest.get("id")
    attempt = latest.get("run_attempt", 1)
    if type(run_id) is not int or type(attempt) is not int or attempt < 1:
        raise RecoveryError("recovery_run_metadata_invalid")
    base = {"run_id": run_id, "run_attempt": attempt, "status": status, "conclusion": conclusion}
    if status in ACTIVE_STATUSES:
        return {**base, "action": "wait", "reason": "scheduled_run_still_active"}
    if status != "completed":
        return {**base, "action": "alert", "reason": "scheduled_run_status_unexpected"}
    if conclusion == "success":
        return {**base, "action": "alert", "reason": "daily_cut_missing_after_successful_run"}
    if conclusion not in RETRYABLE_CONCLUSIONS:
        return {**base, "action": "alert", "reason": f"non_retryable_conclusion:{conclusion}"}
    if attempt >= MAX_RUN_ATTEMPTS:
        return {**base, "action": "alert", "reason": "recovery_attempt_limit_reached"}
    return {**base, "action": "rerun", "reason": "retryable_scheduled_failure"}


def request_json(url: str, token: str, *, method: str = "GET") -> tuple[int, dict[str, Any] | None]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "precios-sps-daily-recovery",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RecoveryError(f"github_api_http_{exc.code}:{raw[:300]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RecoveryError(f"github_api_transport:{exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--now-utc")
    args = parser.parse_args()
    if "/" not in args.repository or "/" in args.workflow or not args.workflow.endswith(".yml"):
        raise SystemExit("recovery_target_invalid")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("github_token_missing")
    now_utc = parse_utc(args.now_utc) if args.now_utc else datetime.now(timezone.utc)
    encoded_workflow = urllib.parse.quote(args.workflow, safe="")
    base = f"https://api.github.com/repos/{args.repository}"
    list_url = f"{base}/actions/workflows/{encoded_workflow}/runs?event=schedule&per_page=10"
    status, payload = request_json(list_url, token)
    if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise RecoveryError("workflow_runs_response_invalid")
    decision = choose_recovery_action(payload["workflow_runs"], now_utc=now_utc)
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    action = decision["action"]
    if action == "wait":
        return 0
    if action == "alert":
        return 4
    if action != "rerun" or type(decision.get("run_id")) is not int:
        raise RecoveryError("recovery_decision_invalid")
    rerun_url = f"{base}/actions/runs/{decision['run_id']}/rerun-failed-jobs"
    rerun_status, _ = request_json(rerun_url, token, method="POST")
    if rerun_status != 201:
        raise RecoveryError(f"rerun_response_invalid:{rerun_status}")
    print(json.dumps({"action": "rerun_requested", "run_id": decision["run_id"], "previous_attempt": decision["run_attempt"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RecoveryError as exc:
        raise SystemExit(str(exc)) from exc
