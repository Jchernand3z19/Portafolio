"""Construye comentarios sanitizados para ejecuciones live de La Colonia."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MAX_COMMENT_LENGTH = 60_000
MAX_COLLECTION_ITEMS = 30
MAX_SCALAR_LENGTH = 2_000

METRIC_FIELDS = (
    "accepted",
    "pages_expected",
    "pages_attempted",
    "pages_completed",
    "page_coverage",
    "products_reported_initial",
    "products_reported_final",
    "products_returned",
    "products_processed",
    "skus_returned",
    "skus_extracted",
    "skus_with_price",
    "skus_without_price",
    "promotional_skus",
    "weighted_skus",
    "duplicate_skus",
    "duplicate_products",
    "http_403",
    "http_429",
    "persistent_http_429",
    "http_5xx",
    "retries",
    "errors",
    "structural_events",
    "duration_seconds",
    "average_response_seconds",
    "average_response_bytes",
    "warnings",
    "rejection_reasons",
    "proposed_thresholds",
)

METADATA_FIELDS = (
    ("Workflow", "workflow"),
    ("Run number", "run_number"),
    ("Run ID interno", "run_id"),
    ("URL completa de la ejecución", "run_url"),
    ("Rama", "branch"),
    ("Commit SHA", "sha"),
    ("Modo", "mode"),
    ("Page size", "page_size"),
    ("Max pages", "max_pages"),
    ("Max products", "max_products"),
    ("Delay seconds", "delay_seconds"),
    ("Profile", "profile"),
    ("Código de salida", "exit_code"),
    ("Nombre del artefacto", "artifact_name"),
    ("URL de artefactos", "artifacts_url"),
)


def load_summary(path: str | Path) -> dict[str, Any] | None:
    """Carga un resumen JSON si existe y tiene una raíz de objeto."""

    summary_path = Path(path)
    if not summary_path.is_file():
        return None
    try:
        value = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _limited(value: Any) -> Any:
    if isinstance(value, Mapping):
        items = list(value.items())[:MAX_COLLECTION_ITEMS]
        return {str(key): _limited(item) for key, item in items}
    if isinstance(value, (list, tuple, set)):
        return [_limited(item) for item in list(value)[:MAX_COLLECTION_ITEMS]]
    if isinstance(value, str) and len(value) > MAX_SCALAR_LENGTH:
        return value[: MAX_SCALAR_LENGTH - 1] + "…"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)[:MAX_SCALAR_LENGTH]


def _display(value: Any) -> str:
    value = _limited(value)
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    elif value is None:
        text = "no disponible"
    else:
        text = str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def build_live_result_comment(
    summary: Mapping[str, Any] | None,
    metadata: Mapping[str, Any],
    *,
    max_length: int = MAX_COMMENT_LENGTH,
) -> str:
    """Devuelve Markdown con una lista cerrada de métricas no comerciales."""

    metrics_value = summary.get("metrics", {}) if isinstance(summary, Mapping) else {}
    metrics = metrics_value if isinstance(metrics_value, Mapping) else {}
    run_id = _display(metadata.get("run_id", "unknown"))

    lines = [
        "## La Colonia — resultado live",
        "",
        "| Campo | Valor |",
        "|---|---|",
    ]
    for label, key in METADATA_FIELDS:
        lines.append(f"| {label} | `{_display(metadata.get(key))}` |")

    lines.extend(["", "### Métricas sanitizadas", "", "| Métrica | Valor |", "|---|---|"])
    for key in METRIC_FIELDS:
        lines.append(f"| `{key}` | `{_display(metrics.get(key))}` |")

    if summary is None:
        lines.extend(
            [
                "",
                "> `run-summary.json` no estaba disponible; la ejecución y su código de salida se reportan sin inventar métricas.",
            ]
        )

    lines.extend(
        [
            "",
            "Este comentario contiene únicamente métricas agregadas y no publica productos, precios ni el catálogo.",
            "",
            f"<!-- la-colonia-live-result:{run_id} -->",
        ]
    )
    text = "\n".join(lines)
    if len(text) <= max_length:
        return text

    marker = f"\n\n<!-- la-colonia-live-result:{run_id} -->"
    notice = "\n\n> Comentario truncado de forma segura por límite de longitud."
    keep = max(max_length - len(marker) - len(notice), 0)
    return text[:keep].rstrip() + notice + marker
