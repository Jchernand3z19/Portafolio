#!/usr/bin/env python3
"""Ejecuta recorridos live manuales, progresivos y sin persistencia comercial."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from precios_supermercados.scrapers.la_colonia_runner import (  # noqa: E402
    AcceptanceProfile,
    AcceptanceThresholds,
    CatalogRunResult,
    CrawlConfig,
    LaColoniaCatalogRunner,
)

SAFE_PAGE_SIZES = (10, 20, 30, 50)


def _optional_positive(value: str) -> int | None:
    parsed = int(value)
    return parsed if parsed > 0 else None


def _thresholds(args: argparse.Namespace) -> AcceptanceThresholds:
    return AcceptanceThresholds(
        max_missing_price_ratio=args.max_missing_price_ratio,
        max_duplicate_sku_ratio=args.max_duplicate_sku_ratio,
        max_duplicate_product_ratio=args.max_duplicate_product_ratio,
        max_total_change_ratio=args.max_total_change_ratio,
    )


def _resolve_limits(args: argparse.Namespace) -> tuple[int | None, int | None]:
    if args.mode == "smoke":
        return args.max_pages or 2, None
    if args.mode == "staged":
        if args.max_pages is None and args.max_products is None:
            return 10, None
        return args.max_pages, args.max_products
    return None, None


def _markdown(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    rows = [
        ("run_id", metrics["run_id"]),
        ("accepted", metrics["accepted"]),
        ("page_size", metrics["page_size"]),
        ("order_by", metrics["order_by"]),
        ("products_reported_initial", metrics["products_reported_initial"]),
        ("products_reported_final", metrics["products_reported_final"]),
        ("pages_expected", metrics["pages_expected"]),
        ("pages_attempted", metrics["pages_attempted"]),
        ("pages_completed", metrics["pages_completed"]),
        ("page_coverage", metrics["page_coverage"]),
        ("products_returned", metrics["products_returned"]),
        ("products_processed", metrics["products_processed"]),
        ("skus_returned", metrics["skus_returned"]),
        ("skus_extracted", metrics["skus_extracted"]),
        ("skus_with_price", metrics["skus_with_price"]),
        ("skus_without_price", metrics["skus_without_price"]),
        ("promotional_skus", metrics["promotional_skus"]),
        ("weighted_skus", metrics["weighted_skus"]),
        ("duplicate_skus", metrics["duplicate_skus"]),
        ("duplicate_products", metrics["duplicate_products"]),
        ("errors", metrics["errors"]),
        ("structural_events", metrics["structural_events"]),
        ("http_403", metrics["http_403"]),
        ("http_429", metrics["http_429"]),
        ("http_5xx", metrics["http_5xx"]),
        ("retries", metrics["retries"]),
        ("duration_seconds", metrics["duration_seconds"]),
        ("average_response_seconds", metrics["average_response_seconds"]),
        ("average_response_bytes", metrics["average_response_bytes"]),
        ("delay_seconds_applied", metrics["delay_seconds_applied"]),
    ]
    lines = [
        "# La Colonia — resumen de recorrido",
        "",
        f"Modo: `{summary['mode']}`",
        f"Perfil: `{summary['profile']}`",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
    ]
    lines.extend(f"| `{name}` | `{value}` |" for name, value in rows)
    lines.extend(
        [
            "",
            "## Rechazos",
            "",
            *(
                [f"- {reason}" for reason in metrics["rejection_reasons"]]
                or ["- Ninguno"]
            ),
            "",
            "## Advertencias",
            "",
            *([f"- {warning}" for warning in metrics["warnings"]] or ["- Ninguna"]),
            "",
            "## Umbrales propuestos",
            "",
            "```json",
            json.dumps(metrics["proposed_thresholds"], ensure_ascii=False, indent=2),
            "```",
            "",
            "El informe no contiene el catálogo completo ni datos comerciales versionados.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_summary(
    result: CatalogRunResult,
    *,
    output_dir: Path,
    mode: str,
    profile: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = result.sanitized_summary()
    summary["mode"] = mode
    summary["profile"] = profile
    if extra:
        summary.update(extra)
    (output_dir / "run-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "run-summary.md").write_text(
        _markdown(summary),
        encoding="utf-8",
    )
    return summary


def _run_once(
    *,
    args: argparse.Namespace,
    max_pages: int | None,
    max_products: int | None,
    suffix: str = "",
) -> CatalogRunResult:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"live_la_colonia_{args.mode}_{timestamp}{suffix}"
    config = CrawlConfig(
        page_size=args.page_size,
        max_pages=max_pages,
        max_products=max_products,
        delay_seconds=args.delay_seconds,
        max_retries=args.max_retries,
        stop_on_error=True,
        order_by=args.order_by,
        max_duration_seconds=args.max_duration_seconds,
    )
    runner = LaColoniaCatalogRunner()
    return runner.run(
        config,
        run_id=run_id,
        profile=AcceptanceProfile(args.profile),
        thresholds=_thresholds(args),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "staged", "full"), default="smoke")
    parser.add_argument("--page-size", type=int, choices=SAFE_PAGE_SIZES, default=10)
    parser.add_argument("--max-pages", type=_optional_positive)
    parser.add_argument("--max-products", type=_optional_positive)
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    parser.add_argument("--max-retries", type=int, choices=range(0, 4), default=2)
    parser.add_argument(
        "--order-by",
        choices=("OrderByNameASC", "OrderByReleaseDateDESC"),
        default="OrderByNameASC",
    )
    parser.add_argument(
        "--profile",
        choices=("baseline", "validation"),
        default="baseline",
    )
    parser.add_argument("--max-missing-price-ratio", type=float)
    parser.add_argument("--max-duplicate-sku-ratio", type=float)
    parser.add_argument("--max-duplicate-product-ratio", type=float)
    parser.add_argument("--max-total-change-ratio", type=float)
    parser.add_argument("--max-duration-seconds", type=float, default=1_800.0)
    parser.add_argument("--max-full-pages", type=int, default=300)
    parser.add_argument("--allow-full", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "run-artifacts")
    args = parser.parse_args()

    if args.delay_seconds < 0:
        parser.error("--delay-seconds no puede ser negativo")
    if args.mode == "full":
        if not args.allow_full:
            parser.error("full requiere --allow-full")
        if args.profile != "validation" or not _thresholds(args).complete:
            parser.error("full requiere perfil validation y los cuatro umbrales")
        preflight = _run_once(args=args, max_pages=1, max_products=None, suffix="_preflight")
        catalog_pages = preflight.metrics.catalog_pages_reported
        if not preflight.metrics.accepted or catalog_pages > args.max_full_pages:
            summary = _write_summary(
                preflight,
                output_dir=args.output_dir,
                mode=args.mode,
                profile=args.profile,
                extra={
                    "full_started": False,
                    "full_stop_reason": (
                        "preflight_rejected"
                        if not preflight.metrics.accepted
                        else "catalog_request_count_exceeds_safety_limit"
                    ),
                    "max_full_pages": args.max_full_pages,
                    "recommendation": (
                        "Evaluar recorrido por categorías o sesiones separadas; "
                        "no se forzó el catálogo completo."
                    ),
                },
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 2
        if args.delay_seconds:
            import time

            time.sleep(args.delay_seconds)
        result = _run_once(args=args, max_pages=None, max_products=None, suffix="_full")
    else:
        max_pages, max_products = _resolve_limits(args)
        result = _run_once(
            args=args,
            max_pages=max_pages,
            max_products=max_products,
        )

    summary = _write_summary(
        result,
        output_dir=args.output_dir,
        mode=args.mode,
        profile=args.profile,
        extra={"full_started": args.mode == "full"},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.metrics.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
