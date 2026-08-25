#!/usr/bin/env python3
"""Entrypoint MVP bound con una única recuperación del control DOM de ciudad.

El run 32807247386 mostró un re-render real del botón de San Pedro Sula mientras
Playwright intentaba hacer click. Este wrapper no amplía el tráfico comercial: sólo
re-resuelve una vez el mismo control de ciudad cuando el primer click termina en un
TimeoutError. Si el primer click ya dejó SPS seleccionado, no vuelve a hacer click.
La consulta explícita sigue limitada por el runner bound original a un máximo de una.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import probar_muestra_sps_la_colonia_bound as bound  # noqa: E402


def _is_playwright_timeout(exc: BaseException) -> bool:
    return exc.__class__.__name__ == "TimeoutError"


def activate_city_control_resilient(
    control: Any,
    city_name: str,
    *,
    activate_fn: Callable[[Any, str], bool],
    resolve_fn: Callable[[Any, str], Any],
    wait_for_city_fn: Callable[[Any], str],
) -> bool:
    """Activa la misma ciudad con como máximo una re-resolución por detach/timeout."""

    try:
        return activate_fn(control, city_name)
    except Exception as exc:
        if not _is_playwright_timeout(exc):
            raise

        try:
            page = control.locator.page
        except Exception as page_exc:
            raise bound.passive.MvpSampleError(
                "sps_city_control_activation_timeout"
            ) from page_exc

        # El click puede haber disparado el cambio antes de que el nodo se desmontara.
        # Verificar primero evita duplicar una selección que ya ocurrió.
        try:
            wait_for_city_fn(page)
            return True
        except bound.passive.MvpSampleError:
            pass

        refreshed = resolve_fn(page, city_name)
        try:
            return activate_fn(refreshed, city_name)
        except Exception as retry_exc:
            if _is_playwright_timeout(retry_exc):
                raise bound.passive.MvpSampleError(
                    "sps_city_control_activation_timeout"
                ) from retry_exc
            raise


def main(argv: list[str] | None = None) -> int:
    original_activate = bound.activate_city_control

    def _resilient(control: Any, city_name: str) -> bool:
        return activate_city_control_resilient(
            control,
            city_name,
            activate_fn=original_activate,
            resolve_fn=bound.resolve_exact_city_control,
            wait_for_city_fn=bound.passive._wait_for_city,
        )

    bound.activate_city_control = _resilient
    try:
        return bound.main(argv)
    finally:
        bound.activate_city_control = original_activate


if __name__ == "__main__":
    raise SystemExit(main())
