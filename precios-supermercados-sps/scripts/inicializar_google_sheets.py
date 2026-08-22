#!/usr/bin/env python3
"""Verifica o inicializa el storage Google Sheets sin ejecutar scrapers."""

from __future__ import annotations

import argparse
import json
import os
import sys

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
    if isinstance(code, str) and code and len(code) <= 128:
        return code
    return "storage_bootstrap_unexpected_error"


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
        print(
            json.dumps(
                {"status": "error", "error_code": _safe_error_code(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except Exception:
        # Evita que una excepción de librería imprima request/body/credenciales.
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_code": "storage_bootstrap_unexpected_error",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 3

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
