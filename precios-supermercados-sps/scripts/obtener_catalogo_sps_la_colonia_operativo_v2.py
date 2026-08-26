#!/usr/bin/env python3
"""Ejecuta el catálogo operativo permitiendo recovery ante páginas VTEX cortas.

El extractor base conserva su semántica fail-closed. Este entrypoint adapta sólo el
recorrido full-catalog ya autorizado: una página rechazada exclusivamente por
cardinalidad corta puede aportar sus SKU al bucket, cuya cobertura exacta sigue
siendo validada contra recordsFiltered y, si hace falta, recuperada en orden
inverso por el runner operativo.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import obtener_catalogo_sps_la_colonia_operativo as operational


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


class RecoveryAwareLaColoniaExtractor(BaseExtractor):
    """Relaja sólo el gate por página; la cobertura del bucket sigue fail-closed."""

    def parse_payload(self, *args: Any, **kwargs: Any) -> Any:
        result = super().parse_payload(*args, **kwargs)
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
