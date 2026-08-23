"""Resolución DOM fail-closed para controles de ubicación.

Este módulo no abre red, no conoce targets live ni concede autoridad. Sólo recibe
una página Playwright ya existente y resuelve, de forma exacta y única, el selector
visible de ubicación y los controles interactivos de ciudad. Se mantiene separado
de la autorización live para poder probar el contrato completamente offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


CITY_CONTROL_ROLES: tuple[str, ...] = ("option", "radio", "menuitem", "button")
CITY_CONTROL_READY_TIMEOUT_MS = 3_000
CITY_CONTROL_READY_POLL_MS = 100
LOCATION_SELECTOR_CLASS = "btn-modal-selector"
LOCATION_SELECTOR_CSS = f"button.{LOCATION_SELECTOR_CLASS}"
_LOCATION_SELECTOR_ACCESSIBLE_PATTERN = re.compile(
    r"selecciona\s+tu\s+tienda|selecciona\s+una\s+tienda|ubicaci[oó]n",
    re.I,
)
_IGNORED_CITY_LABELS = frozenset(
    {
        "selecciona tu ciudad",
        "selecciona una ciudad",
        "ciudad",
    }
)
_IGNORED_VISIBLE_LOCATION_LABELS = frozenset(
    {
        "selecciona tu tienda",
        "selecciona una tienda",
        "selecciona tu ciudad",
        "selecciona una ciudad",
        "ubicacion",
        "ubicación",
        "ciudad",
        "tienda",
    }
)


class LocationControlResolutionError(RuntimeError):
    """Fallo determinista al resolver un control de ubicación."""


@dataclass(frozen=True, slots=True)
class ResolvedLocationSelector:
    """Botón único que abre el selector y ubicación visible, si la expone."""

    locator: Any
    source: str
    visible_location: str | None


@dataclass(frozen=True, slots=True)
class ResolvedCityControl:
    """Control exacto y único junto con etiquetas públicas observables."""

    locator: Any
    role: str
    available_cities: tuple[str, ...]


def _clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def _label(locator: Any) -> str | None:
    try:
        aria = _clean_label(locator.get_attribute("aria-label"))
    except Exception:
        aria = None
    if aria:
        return aria
    try:
        return _clean_label(locator.inner_text())
    except Exception:
        return None


def _has_css_class(locator: Any, class_name: str) -> bool:
    try:
        raw = locator.get_attribute("class") or ""
    except Exception:
        return False
    return class_name in str(raw).split()


def _visible_items(collection: Any) -> list[Any]:
    visible: list[Any] = []
    for index in range(collection.count()):
        candidate = collection.nth(index)
        try:
            if candidate.is_visible():
                visible.append(candidate)
        except Exception:
            continue
    return visible


def _visible_location(label: str | None) -> str | None:
    normalized = _clean_label(label)
    if normalized is None:
        return None
    if normalized.casefold() in _IGNORED_VISIBLE_LOCATION_LABELS:
        return None
    return normalized


def resolve_location_selector(page: Any) -> ResolvedLocationSelector:
    """Resuelve primero el botón estructural observado y luego el fallback legado.

    La evidencia HTML actual de La Colonia expone la ubicación seleccionada como
    ``<button class="btn-modal-selector">San pedro sula</button>``. Ese selector
    estructural se usa sólo si existe exactamente un botón visible. Si no existe,
    se conserva el fallback accesible histórico. Cualquier ambigüedad falla cerrado.
    """

    try:
        structural = _visible_items(page.locator(LOCATION_SELECTOR_CSS))
    except Exception:
        structural = []
    if len(structural) > 1:
        raise LocationControlResolutionError("location_selector_not_unique")
    if len(structural) == 1:
        label = _label(structural[0])
        if label is None:
            raise LocationControlResolutionError("location_selector_label_missing")
        return ResolvedLocationSelector(
            locator=structural[0],
            source="btn-modal-selector",
            visible_location=_visible_location(label),
        )

    try:
        accessible = _visible_items(
            page.get_by_role("button", name=_LOCATION_SELECTOR_ACCESSIBLE_PATTERN)
        )
    except Exception:
        accessible = []
    if not accessible:
        raise LocationControlResolutionError("location_selector_not_found")
    if len(accessible) != 1:
        raise LocationControlResolutionError("location_selector_not_unique")
    return ResolvedLocationSelector(
        locator=accessible[0],
        source="accessible-fallback",
        visible_location=_visible_location(_label(accessible[0])),
    )


def open_location_selector(page: Any) -> ResolvedLocationSelector:
    """Abre exactamente el selector resuelto y devuelve la ubicación visible previa."""

    resolved = resolve_location_selector(page)
    resolved.locator.click()
    return resolved


def _visible_role_matches(page: Any, *, role: str, exact_name: re.Pattern[str]) -> list[Any]:
    matches = page.get_by_role(role, name=exact_name)
    visible: list[Any] = []
    for index in range(matches.count()):
        candidate = matches.nth(index)
        try:
            if role == "button" and _has_css_class(candidate, LOCATION_SELECTOR_CLASS):
                # El botón del encabezado muestra la ciudad actual pero no es una
                # opción del modal. Nunca debe competir con el control que cambia
                # realmente la ciudad.
                continue
            parent_select = candidate.locator("xpath=ancestor::select[1]")
            if candidate.is_visible() or (role == "option" and parent_select.count() == 1):
                visible.append(candidate)
        except Exception:
            continue
    return visible


def _usable_labels(options: Any, *, require_visible: bool) -> tuple[str, ...]:
    labels: list[str] = []
    for index in range(options.count()):
        option = options.nth(index)
        if require_visible:
            try:
                if not option.is_visible():
                    continue
            except Exception:
                continue
        label = _label(option)
        if label and label.casefold() not in _IGNORED_CITY_LABELS:
            labels.append(label)
    return tuple(sorted(set(labels), key=str.casefold))


def _option_container_labels(option: Any) -> tuple[str, ...] | None:
    """Conserva ciudades hermanas sólo en contenedores inequívocos de options."""

    try:
        parent = option.locator("xpath=ancestor::select[1]")
    except Exception:
        parent = None
    if parent is not None and parent.count() == 1:
        return _usable_labels(parent.locator("option"), require_visible=False)

    try:
        listbox = option.locator("xpath=ancestor::*[@role='listbox'][1]")
    except Exception:
        return None
    if listbox.count() != 1:
        return None
    return _usable_labels(listbox.get_by_role("option"), require_visible=True)


def _resolve_exact_city_control_once(page: Any, normalized: str) -> ResolvedCityControl:
    exact = re.compile(rf"^{re.escape(normalized)}$", re.I)
    candidates: list[tuple[str, Any]] = []
    for role in CITY_CONTROL_ROLES:
        candidates.extend(
            (role, candidate)
            for candidate in _visible_role_matches(page, role=role, exact_name=exact)
        )

    if not candidates:
        raise LocationControlResolutionError("target_city_not_found")
    if len(candidates) != 1:
        raise LocationControlResolutionError("target_city_not_unique")

    role, locator = candidates[0]
    labels = _option_container_labels(locator) if role == "option" else None
    if not labels:
        labels = (normalized,)
    return ResolvedCityControl(locator=locator, role=role, available_cities=labels)


def _wait_for_next_city_probe(page: Any) -> None:
    """Espera un intervalo acotado sin convertir errores de DOM en autoridad."""

    try:
        page.wait_for_timeout(CITY_CONTROL_READY_POLL_MS)
    except Exception:
        # Dobles de prueba sin reloj Playwright siguen pudiendo ejercitar el
        # contrato de resolución; en browser real la espera sí consume el intervalo.
        return


def resolve_exact_city_control(page: Any, city_name: str) -> ResolvedCityControl:
    """Resuelve un control exacto, esperando de forma acotada al render del modal.

    El orden de roles no es un fallback permisivo: todos los roles permitidos se
    inspeccionan y el resultado sólo se acepta si existe exactamente un elemento
    candidato en el conjunto completo. El botón de encabezado
    ``btn-modal-selector`` se excluye explícitamente porque sólo refleja la ciudad
    actual y no representa una opción de cambio. La ausencia temporal puede
    reintentarse durante tres segundos; una ambigüedad falla de inmediato.
    """

    normalized = _clean_label(city_name)
    if normalized is None:
        raise LocationControlResolutionError("target_city_name_invalid")

    wait_count = CITY_CONTROL_READY_TIMEOUT_MS // CITY_CONTROL_READY_POLL_MS
    for attempt in range(wait_count + 1):
        try:
            return _resolve_exact_city_control_once(page, normalized)
        except LocationControlResolutionError as exc:
            if str(exc) != "target_city_not_found" or attempt == wait_count:
                raise
            _wait_for_next_city_probe(page)

    raise AssertionError("unreachable")


def activate_city_control(control: ResolvedCityControl, city_name: str) -> None:
    """Activa el control resuelto sin intentar heurísticas adicionales."""

    try:
        parent = control.locator.locator("xpath=ancestor::select[1]")
    except Exception:
        parent = None
    if parent is not None and parent.count() == 1:
        parent.select_option(label=city_name)
        return
    control.locator.click()
