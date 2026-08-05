#!/usr/bin/env python3
"""Genera el comentario sanitizado de una ejecución live de La Colonia."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.automation.la_colonia_live_reporting import (  # noqa: E402
    build_live_result_comment,
    load_summary,
)


def _metadata() -> dict[str, str]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}" if repository and run_id else ""
    return {
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", ""),
        "run_id": run_id,
        "run_url": run_url,
        "branch": os.environ.get("GITHUB_REF_NAME", ""),
        "sha": os.environ.get("GITHUB_SHA", ""),
        "mode": os.environ.get("INPUT_MODE", ""),
        "page_size": os.environ.get("INPUT_PAGE_SIZE", ""),
        "max_pages": os.environ.get("INPUT_MAX_PAGES", ""),
        "max_products": os.environ.get("INPUT_MAX_PRODUCTS", ""),
        "delay_seconds": os.environ.get("INPUT_DELAY_SECONDS", ""),
        "profile": os.environ.get("INPUT_PROFILE", ""),
        "exit_code": os.environ.get("RUNNER_EXIT_CODE", ""),
        "artifact_name": os.environ.get("ARTIFACT_NAME", ""),
        "artifacts_url": f"{run_url}#artifacts" if run_url else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    comment = build_live_result_comment(load_summary(args.summary), _metadata())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(comment, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
