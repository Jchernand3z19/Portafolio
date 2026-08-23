#!/usr/bin/env python3
"""Verifica o inicializa el storage Google Sheets sin ejecutar scrapers."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from precios_supermercados.google_sheets_adapter import (
    GoogleSheetsAdapterError,
    GoogleSheetsWorkbookAdapter,
)
from precios_supermercados.google_sheets_bootstrap import (
    ALLOWED_BOOTSTRAP_MODES,
    MODE_CHECK,
    GoogleSheetsBootstrapError,
    run_google_sheets_bootstrap,
)
from precios_supermercados.google_sheets_transport import (
    GoogleSheetsHttpTransport,
    GoogleSheetsTransportError,
)


SPREADSHEET_ID_ENV = "PRECIOS_SPS_GOOGLE_SPREADSHEET_ID"
SERVICE_ACCOUNT_JSON_ENV = "PRECIOS_SPS_GOOGLE_SERVICE_ACCOUNT_JSON"
_SAFE_OUTPUT = re.compile(r"^[a-z0-9_.-]{1,128}$")


class StorageCliError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise StorageCliError(f"missing_{name.casefold()}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verifica el Spreadsheet o materializa únicamente configuración; "
            "no ejecuta scraping."
        )
    )
    parser.add_argument(
        "--mode",
        choices=sorted(ALLOWED_BOOTSTRAP_MODES),
        default=MODE_CHECK,
    )
    return parser


def run(mode: str) -> dict[str, object]:
    spreadsheet_id = _required_env(SPREADSHEET_ID_ENV)
    service_account_json = _required_env(SERVICE_ACCOUNT_JSON_ENV)
    transport = GoogleSheetsHttpTransport.from_service_account_json(
        spreadsheet_id,
        service_account_json,
    )
    adapter = GoogleSheetsWorkbookAdapter(transport)
    result = run_google_sheets_bootstrap(adapter, mode=mode)
    return {
        "status": "ok",
        **result.as_dict(),
    }


def _safe_error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and _SAFE_OUTPUT.fullmatch(code):
        return code
    return "storage_bootstrap_unexpected_error"


def _write_github_outputs(
    *,
    result: str,
    error_code: str,
    wrote: bool | None,
) -> None:
    """Publica sólo señales allowlisted; nunca IDs, bodies ni credenciales."""

    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    if result not in {"ok", "error"}:
        raise StorageCliError("github_output_result_invalid")
    if not _SAFE_OUTPUT.fullmatch(error_code):
        raise StorageCliError("github_output_error_code_invalid")
    wrote_text = "unknown" if wrote is None else str(wrote).casefold()
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"result={result}\n")
        handle.write(f"error_code={error_code}\n")
        handle.write(f"wrote={wrote_text}\n")


def _report_error(code: str, *, exit_code: int) -> int:
    _write_github_outputs(result="error", error_code=code, wrote=None)
    print(
        json.dumps({"status": "error", "error_code": code}, sort_keys=True),
        file=sys.stderr,
    )
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args.mode)
    except (
        StorageCliError,
        GoogleSheetsTransportError,
        GoogleSheetsAdapterError,
        GoogleSheetsBootstrapError,
    ) as exc:
        return _report_error(_safe_error_code(exc), exit_code=2)
    except Exception:
        # Evita que una excepción de librería imprima request/body/credenciales.
        return _report_error("storage_bootstrap_unexpected_error", exit_code=3)

    wrote = result.get("wrote")
    wrote_value = wrote if isinstance(wrote, bool) else None
    _write_github_outputs(result="ok", error_code="none", wrote=wrote_value)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
