#!/usr/bin/env python3
"""Exporta catálogo B2C con normalización pública de marca y presentación.

El núcleo v3 se conserva en ``exportar_consumer_catalog_core.py``. Esta fachada
mantiene su API (incluidos los hooks usados por TGU) y aplica únicamente una
normalización de lectura antes de escribir archivos públicos.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import exportar_consumer_catalog_core as _core  # noqa: E402
from precios_supermercados.consumer_catalog_display import (  # noqa: E402
    canonical_brand,
    canonical_egg_size,
    canonical_presentation,
)

# Conserva la API histórica del script, incluidos helpers privados consumidos por
# el exportador TGU y por las pruebas del contrato v3.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_ORIGINAL_BUILD_ROWS = _core.build_rows
_ORIGINAL_EXPORT = _core.export_consumer_catalog
_ORIGINAL_MAIN = _core.main


def _derived_presentation(offer: VisibleOffer) -> str | None:
    return canonical_presentation(
        source_presentation=offer.presentation,
        product_name=offer.product_name,
        product_type=offer.product_type,
        presentation_dimension=offer.presentation_dimension,
        presentation_total_base=offer.presentation_total_base,
        presentation_status=offer.presentation_status,
    )


def build_rows(
    offers: Iterable[VisibleOffer],
    freshness_by_scope: dict[tuple[str, str], str],
    history_by_offer: dict[tuple[str, str], tuple[HistoricalPoint, ...]] | None = None,
    *,
    as_of_utc=None,
) -> list[dict[str, object]]:
    """Construye filas v3 y limpia sólo atributos descriptivos públicos."""
    _core._derived_presentation = _derived_presentation
    rows = _ORIGINAL_BUILD_ROWS(
        offers,
        freshness_by_scope,
        history_by_offer,
        as_of_utc=as_of_utc,
    )
    for row in rows:
        row["brand"] = canonical_brand(row.get("brand"), row.get("product_name"))
        size = canonical_egg_size(row.get("product_name"), row.get("product_type"))
        if size is not None:
            # Campo aditivo: la presentación sigue siendo el conteo; el tamaño de
            # huevo no vuelve a fragmentar el selector de presentación.
            row["variant"] = size
    return rows


def _sync_core() -> None:
    """Sincroniza hooks mutables para preservar el contrato del exportador TGU."""
    for name in (
        "EXPECTED_SCOPE",
        "RETAILER_NAMES",
        "MAX_PARTITION_ROWS",
        "PUBLIC_COMPARABILITY",
        "fetch_visible_offers",
        "fetch_historical_points",
        "_identity_groups",
    ):
        setattr(_core, name, globals()[name])
    _core._derived_presentation = _derived_presentation
    _core.build_rows = build_rows


def export_consumer_catalog(
    backend: QueryBackend,
    scope: ComparisonScope,
    output_directory: Path,
    *,
    as_of_utc,
    freshness_window,
    require_products: bool = False,
) -> dict[str, object]:
    _sync_core()
    return _ORIGINAL_EXPORT(
        backend,
        scope,
        output_directory,
        as_of_utc=as_of_utc,
        freshness_window=freshness_window,
        require_products=require_products,
    )


def main(argv: Sequence[str] | None = None) -> int:
    _sync_core()
    previous_export = _core.export_consumer_catalog
    _core.export_consumer_catalog = export_consumer_catalog
    try:
        return _ORIGINAL_MAIN(argv)
    finally:
        _core.export_consumer_catalog = previous_export


if __name__ == "__main__":
    raise SystemExit(main())
