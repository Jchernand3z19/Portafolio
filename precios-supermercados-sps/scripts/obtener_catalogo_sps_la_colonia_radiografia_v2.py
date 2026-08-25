#!/usr/bin/env python3
"""Ejecuta el catálogo SPS con snapshots tolerantes a navegación transitoria."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import obtener_catalogo_sps_la_colonia_radiografia as full  # noqa: E402

_ORIGINAL_STAGE = full.radiography._stage
_NAVIGATION_MARKERS = (
    "execution context was destroyed",
    "most likely because of a navigation",
    "cannot find context with specified id",
)


def _stable_stage(page: Any, context: Any, collector: Any, name: str) -> Any:
    """Reintenta sólo la lectura local si VTEX navega mientras se toma el snapshot."""

    last_error: BaseException | None = None
    for _ in range(6):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except Exception:
            pass
        try:
            return _ORIGINAL_STAGE(page, context, collector, name)
        except Exception as exc:
            normalized = str(exc).casefold()
            if not any(marker in normalized for marker in _NAVIGATION_MARKERS):
                raise
            last_error = exc
            page.wait_for_timeout(300)
    raise full.FullCatalogError("playwright_navigation_context_unstable") from last_error


full.radiography._stage = _stable_stage

if __name__ == "__main__":
    raise SystemExit(full.main())
