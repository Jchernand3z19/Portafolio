#!/usr/bin/env python3
"""Ejecuta el catálogo operativo permitiendo recovery ante huecos de VTEX.

El extractor base conserva su semántica fail-closed. Este entrypoint adapta sólo el
recorrido full-catalog ya autorizado: una página rechazada exclusivamente por
cardinalidad corta puede aportar sus SKU al bucket y una página vacía válida puede
continuar sin aportar datos. En ambos casos la cobertura exacta del bucket sigue
siendo obligatoria contra recordsFiltered y, si hace falta, se recupera en orden
inverso por el runner operativo.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import obtener_catalogo_sps_la_colonia_operativo as operational
from precios_supermercados.scrapers.base import (
    EmptyResponseError,
    ExtractionMetrics,
    ExtractionResult,
)


BaseExtractor = operational.core.LaColoniaExtractor


def _partial_page_is_safe_for_bucket_recovery(result: Any) -> bool:
    """Aísla exactamente el rechazo causado por una página corta parseable."""

    metrics = result.metrics
    return (
        not result.accepted
        and "quality:partial_product_page" in result.quality_events
        and metrics.structural_events == 0
        and metrics.errors == 0
        and metrics.skus_extracted > 0
        and metrics.skus_with_price > 0
    )


def _empty_page_for_bucket_recovery(
    payload: Any,
    *,
    source_url: str,
    page_size: int,
) -> ExtractionResult:
    """Representa un hueco vacío sin aceptar cobertura incompleta del bucket."""

    total_products, products_returned = operational.core._read_shape(payload)
    if total_products <= 0 or products_returned != 0:
        raise EmptyResponseError("La página controlada no devolvió productos")
    metrics = ExtractionMetrics(
        products_discovered=total_products,
        products_requested=page_size,
        products_returned=0,
        pages_discovered=max(math.ceil(total_products / page_size), 1),
        pages_processed=1,
    )
    metrics.page_coverage = metrics.pages_processed / metrics.pages_discovered
    return ExtractionResult(
        products=(),
        metrics=metrics,
        quality_events=("quality:empty_product_page_recovery",),
        accepted=True,
        source_url=source_url,
    )


class RecoveryAwareLaColoniaExtractor(BaseExtractor):
    """Relaja sólo gates de página; la cobertura del bucket sigue fail-closed."""

    def parse_payload(self, *args: Any, **kwargs: Any) -> Any:
        try:
            result = super().parse_payload(*args, **kwargs)
        except EmptyResponseError:
            payload = args[0] if args else kwargs.get("payload")
            return _empty_page_for_bucket_recovery(
                payload,
                source_url=str(kwargs.get("source_url") or ""),
                page_size=int(kwargs.get("page_size") or 5),
            )
        if _partial_page_is_safe_for_bucket_recovery(result):
            return replace(result, accepted=True)
        return result


def main(argv: list[str] | None = None) -> int:
    # El runner operativo resuelve la clase desde ``core`` al iniciar el catálogo.
    # No se altera el extractor base usado por otros entrypoints.
    original = operational.core.LaColoniaExtractor
    operational.core.LaColoniaExtractor = RecoveryAwareLaColoniaExtractor
    try:
        return operational.main(argv)
    finally:
        operational.core.LaColoniaExtractor = original


if __name__ == "__main__":
    raise SystemExit(main())
