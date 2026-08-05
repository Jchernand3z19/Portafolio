#!/usr/bin/env python3
"""Valida un issue_comment y genera una decisión JSON para GitHub Actions."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.automation.la_colonia_dispatcher import (  # noqa: E402
    build_response_comment,
    evaluate_event,
)


def _read_object(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--pr", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    event = _read_object(args.event) or {}
    pr = _read_object(args.pr)
    decision = evaluate_event(event, pr)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    dispatcher_url = f"{server}/{repository}/actions/runs/{run_id}"
    comment_id = event.get("comment", {}).get("id", "unknown")
    payload = decision.as_dict(
        comment=build_response_comment(
            decision,
            comment_id=comment_id,
            dispatcher_run_id=run_id,
            dispatcher_url=dispatcher_url,
        )
    )
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
