"""Resolución DOM fail-closed para controles de ubicación.

Este módulo no abre red, no conoce targets live ni concede autoridad. Sólo recibe
una página Playwright ya existente y resuelve, de forma exacta y única, controles
interactivos de ciudad. Se mantiene separado de la autorización live para poder
probar el contrato completamente offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


CITY_CONTROL_ROLES: tuple[str, ...] = ("option", "radio", "menuitem", "button")
_IGNORED_CITY_LABELS = frozenset(
    {
        "selecciona tu ciudad",
        "selecciona una ciudad",
        "ciudad",
    }
)


class LocationControlResolutionError(RuntimeError):
    """Fallo determinista al resolver un control de ubicación."""


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


def _visible_role_matches(page: Any, *, role: str, exact_name: re.Pattern[str]) -> list[Any]:
    matches = page.get_by_role(role, name=exact_name)
    visible: list[Any] = []
    for index in range(matches.count()):
        candidate = matches.nth(index)
        try:
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


def resolve_exact_city_control(page: Any, city_name: str) -> ResolvedCityControl:
    """Resuelve sólo un control interactivo con nombre exacto.

    El orden de roles no es un fallback permisivo: todos los roles permitidos se
    inspeccionan y el resultado sólo se acepta si existe exactamente un elemento
    candidato en el conjunto completo. Así un DOM ambiguo falla cerrado.
    """

    normalized = _clean_label(city_name)
    if normalized is None:
        raise LocationControlResolutionError("target_city_name_invalid")
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
