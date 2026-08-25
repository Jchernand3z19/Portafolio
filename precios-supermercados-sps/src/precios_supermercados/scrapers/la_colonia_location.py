"""Inicialización operativa de ubicación para el scraper de La Colonia.

Este módulo NO ejecuta la radiografía de descubrimiento. Usa únicamente el contrato
DOM ya aprendido y probado para abrir el selector, elegir exactamente San Pedro
Sula y comprobar el estado estructural seleccionado. La radiografía histórica se
mantiene como evidencia para diagnosticar cambios estructurales, no como requisito
de cada scraping.
"""

from __future__ import annotations

from typing import Any

from precios_supermercados.diagnostics.location_binding_dom_controls import (
    CITY_STATE_SELECTED,
    LocationControlResolutionError,
    open_location_selector,
    resolve_exact_city_control,
    verify_structural_city_selection,
)

TARGET_URL = "https://www.lacolonia.com/"
TARGET_CITY = "San Pedro Sula"
INITIAL_CLICK_TIMEOUT_MS = 3_000
FORCED_CLICK_TIMEOUT_MS = 5_000
RELOAD_TIMEOUT_MS = 20_000


class LocationInitializationError(RuntimeError):
    """Fallo fail-closed al inicializar la ciudad operativa del scraper."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _is_timeout(exc: BaseException) -> bool:
    return exc.__class__.__name__ == "TimeoutError"


def _activate_exact_city(control: Any, city_name: str) -> None:
    """Activa el control exacto; sólo fuerza click tras un timeout de overlay."""

    if control.state == CITY_STATE_SELECTED:
        return
    try:
        page = control.locator.page
    except Exception as exc:
        raise LocationInitializationError("city_control_context_unavailable") from exc

    try:
        parent = control.locator.locator("xpath=ancestor::select[1]")
    except Exception:
        parent = None

    try:
        if parent is not None and parent.count() == 1:
            parent.select_option(label=city_name)
        else:
            control.locator.click(timeout=INITIAL_CLICK_TIMEOUT_MS)
        return
    except Exception as exc:
        if not _is_timeout(exc):
            raise LocationInitializationError("city_activation_failed") from exc

    # VTEX ha mostrado un overlay que intercepta el click normal. Re-resolvemos el
    # mismo control exacto una sola vez y sólo entonces usamos force=True.
    try:
        refreshed = resolve_exact_city_control(page, city_name)
    except LocationControlResolutionError as exc:
        raise LocationInitializationError(str(exc)) from exc
    if refreshed.state == CITY_STATE_SELECTED:
        return

    try:
        parent = refreshed.locator.locator("xpath=ancestor::select[1]")
    except Exception:
        parent = None
    try:
        if parent is not None and parent.count() == 1:
            parent.select_option(label=city_name)
        else:
            refreshed.locator.click(force=True, timeout=FORCED_CLICK_TIMEOUT_MS)
    except Exception as exc:
        reason = "city_activation_timeout" if _is_timeout(exc) else "city_activation_failed"
        raise LocationInitializationError(reason) from exc


def _select_and_verify(page: Any, city_name: str) -> str | None:
    try:
        open_location_selector(page)
        page.wait_for_timeout(150)
        control = resolve_exact_city_control(page, city_name)
    except LocationControlResolutionError as exc:
        raise LocationInitializationError(str(exc)) from exc

    _activate_exact_city(control, city_name)
    page.wait_for_timeout(500 if control.state != CITY_STATE_SELECTED else 100)
    try:
        return verify_structural_city_selection(page, city_name)
    except LocationControlResolutionError as exc:
        raise LocationInitializationError(str(exc)) from exc


def ensure_operational_city(
    page: Any,
    city_name: str = TARGET_CITY,
    *,
    max_dom_reresolutions: int = 1,
) -> str | None:
    """Selecciona y verifica la ciudad sin ejecutar radiografía ni fingerprints.

    Se permite como máximo una recarga DOM para absorber una carga transitoria en la
    que el modal todavía no está disponible. No reintenta consultas comerciales.
    """

    if max_dom_reresolutions not in {0, 1}:
        raise ValueError("max_dom_reresolutions_must_be_zero_or_one")

    last_error: LocationInitializationError | None = None
    for attempt in range(max_dom_reresolutions + 1):
        try:
            return _select_and_verify(page, city_name)
        except LocationInitializationError as exc:
            last_error = exc
            if attempt >= max_dom_reresolutions:
                break
            try:
                page.reload(wait_until="domcontentloaded", timeout=RELOAD_TIMEOUT_MS)
            except Exception as reload_exc:
                raise LocationInitializationError("city_dom_reload_failed") from reload_exc
            page.wait_for_timeout(350)

    assert last_error is not None
    raise LocationInitializationError(
        f"{last_error.reason}_after_single_dom_reresolution"
        if max_dom_reresolutions == 1
        else last_error.reason
    ) from last_error
