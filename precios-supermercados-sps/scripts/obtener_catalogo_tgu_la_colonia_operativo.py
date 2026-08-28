#!/usr/bin/env python3
"""Ejecuta el catálogo operativo existente de La Colonia para Tegucigalpa.

No duplica el scraper: adapta únicamente la ciudad/ubicación del runner SPS ya
probado y conserva sus mismas validaciones, pausas y recuperación fail-closed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo as operational  # noqa: E402
import obtener_catalogo_sps_la_colonia_operativo_v2 as recovery  # noqa: E402

TARGET_CITY = "Tegucigalpa"
LOCATION_ID = "la_colonia_tgu"
CATALOG_TYPE = "la_colonia_tgu_full_read_only"


def main(argv: list[str] | None = None) -> int:
    original_ensure_city = operational.ensure_operational_city
    original_run_catalog = operational._run_catalog

    def ensure_tgu(page: Any, *, max_dom_reresolutions: int = 1) -> str | None:
        return original_ensure_city(
            page,
            TARGET_CITY,
            max_dom_reresolutions=max_dom_reresolutions,
        )

    def run_tgu_catalog(*, page_size: int, delay_seconds: float) -> dict[str, Any]:
        artifact = dict(
            original_run_catalog(
                page_size=page_size,
                delay_seconds=delay_seconds,
            )
        )
        artifact["catalog_type"] = CATALOG_TYPE
        artifact["location_id"] = LOCATION_ID
        artifact["city"] = TARGET_CITY
        return artifact

    operational.ensure_operational_city = ensure_tgu
    operational._run_catalog = run_tgu_catalog
    try:
        return recovery.main(argv)
    finally:
        operational.ensure_operational_city = original_ensure_city
        operational._run_catalog = original_run_catalog


if __name__ == "__main__":
    raise SystemExit(main())
