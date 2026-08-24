#!/usr/bin/env python3
"""Ejecuta una única observación live autorizada de facets SPS.

Este wrapper existe sólo para materializar una autorización humana explícita y
acotada en un push a ``main``. Valida un marker versionado antes de solicitar
OIDC, iniciar navegador o realizar tráfico externo. Reutiliza el runner
context-bound ya auditado para la ejecución real y nunca concede autoridad de
catálogo, persistencia ni extracción productiva.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_RUNNER = PROJECT_ROOT / "scripts" / "ejecutar_facets_context_bound_la_colonia.py"
EXPECTED_REPOSITORY = "Jchernand3z19/Portafolio"
EXPECTED_REF = "refs/heads/main"
EXPECTED_EVENT = "push"
EXPECTED_WORKFLOW_REF = (
    "Jchernand3z19/Portafolio/.github/workflows/"
    "precios-supermercados-sps-la-colonia-live.yml@refs/heads/main"
)
AUTHORIZATION_ID = "SPS-context-and-root-facets-003"
AUTHORIZATION_SCHEMA = "precios-sps-context-bound-facets-authorization/v1"
AUTHORIZED_AT = "2026-08-24T20:46:11Z"
AUTHORIZED_SCOPE = "context_bound_facets_sps"
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_DIGITS = re.compile(r"[0-9]+\Z")

EXPECTED_AUTHORIZATION = {
    "schema_version": AUTHORIZATION_SCHEMA,
    "authorization_id": AUTHORIZATION_ID,
    "authorized_at": AUTHORIZED_AT,
    "scope": AUTHORIZED_SCOPE,
    "max_requests": 2,
    "concurrency": 1,
    "max_retries": 0,
    "catalog_crawl": False,
    "commercial_persistence": False,
    "production_authority": False,
    "catalog_accepted": False,
    "extraction_enabled": False,
}


def _load_runtime() -> ModuleType:
    spec = importlib.util.spec_from_file_location("context_bound_facet_runtime", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("facet_runtime_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fail(runtime: ModuleType, code: str) -> None:
    raise runtime.FacetLiveEntrypointSafetyError(code)


def _trusted_push_context(runtime: ModuleType) -> tuple[str, int, str]:
    if os.environ.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY:
        _fail(runtime, "github_repository_not_trusted")
    if os.environ.get("GITHUB_REF") != EXPECTED_REF:
        _fail(runtime, "github_ref_not_main")
    if os.environ.get("GITHUB_EVENT_NAME") != EXPECTED_EVENT:
        _fail(runtime, "github_event_not_authorized_push")
    if os.environ.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW_REF:
        _fail(runtime, "github_workflow_ref_not_trusted")

    sha = os.environ.get("GITHUB_SHA", "")
    if _SHA1.fullmatch(sha) is None:
        _fail(runtime, "github_sha_invalid")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if _DIGITS.fullmatch(run_id) is None:
        _fail(runtime, "github_run_id_invalid")
    attempt_raw = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if _DIGITS.fullmatch(attempt_raw) is None:
        _fail(runtime, "github_run_attempt_invalid")
    attempt = int(attempt_raw)
    if not 1 <= attempt <= 100:
        _fail(runtime, "github_run_attempt_invalid")
    return run_id, attempt, sha


def _validate_authorization_file(runtime: ModuleType, path: Path) -> None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise runtime.FacetLiveEntrypointSafetyError("authorization_file_unreadable") from exc
    if not raw or len(raw) > 4096:
        _fail(runtime, "authorization_file_size_invalid")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise runtime.FacetLiveEntrypointSafetyError("authorization_file_json_invalid") from exc
    if payload != EXPECTED_AUTHORIZATION:
        _fail(runtime, "authorization_file_contract_mismatch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir: Path = args.output_dir
    runtime = _load_runtime()
    try:
        run_id, run_attempt, approved_sha = _trusted_push_context(runtime)
        _validate_authorization_file(runtime, args.authorization_file)
        try:
            runtime.validate_live_authorization(
                live=True,
                authorization_id=AUTHORIZATION_ID,
                active_ids=frozenset({AUTHORIZATION_ID}),
            )
        except Exception as exc:
            raise runtime.FacetLiveEntrypointSafetyError(
                "human_live_authorization_rejected"
            ) from exc

        transport, public_key = runtime._preflight_edge_configuration()
        oidc_token = runtime._request_oidc_token()
        result = runtime._observe_sps_context_and_execute(
            transport=transport,
            public_key=public_key,
            oidc_token=oidc_token,
            run_id=run_id,
            run_attempt=run_attempt,
            approved_sha=approved_sha,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "facet-entrypoint-evidence.json").write_bytes(result.artifact_bytes())
        (output_dir / "facet-discovery-summary.json").write_bytes(
            runtime.serialize_facet_discovery_summary(result.discovery_summary)
        )
        runtime._write_json(
            output_dir / "facet-entrypoint-status.json",
            {
                "schema_version": "context-bound-facet-live-status-1",
                "status": "completed",
                "requests_attempted": result.discovery_summary.get("requests_attempted"),
                "requests_completed": result.discovery_summary.get("requests_completed"),
                "discovery_outcome": result.discovery_summary.get("discovery_outcome"),
                "raw_values_exposed": False,
                "production_authority": False,
                "catalog_accepted": False,
                "extraction_enabled": False,
            },
        )
        return 0 if result.discovery_summary.get("discovery_completed") is True else 2
    except BaseException as exc:
        try:
            runtime._write_json(output_dir / "facet-entrypoint-status.json", runtime._failure_status(exc))
        except Exception:
            pass
        print(
            f"FACET_ENTRYPOINT_DENIED: {getattr(exc, 'code', 'unexpected_failure')}",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
