#!/usr/bin/env python3
"""Ejecuta un plan diagnóstico cerrado de ventanas de La Colonia."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.scrapers.la_colonia_window_diagnostic_runtime import (  # noqa: E402
    DIAGNOSTIC_DELAY_SECONDS,
    DIAGNOSTIC_PLAN_NAME,
    EXIT_SECURITY_FAILURE,
    LaColoniaWindowDiagnosticRuntime,
    write_diagnostic_artifacts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--plan", choices=(DIAGNOSTIC_PLAN_NAME,), required=True)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        choices=(DIAGNOSTIC_DELAY_SECONDS,),
        default=DIAGNOSTIC_DELAY_SECONDS,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        result = LaColoniaWindowDiagnosticRuntime().run(
            request_id=args.request_id,
            plan_name=args.plan,
            delay_seconds=args.delay_seconds,
        )
        write_diagnostic_artifacts(result, args.output_dir)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Fallo de sanitización o seguridad: {exc}", file=sys.stderr)
        return EXIT_SECURITY_FAILURE

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
