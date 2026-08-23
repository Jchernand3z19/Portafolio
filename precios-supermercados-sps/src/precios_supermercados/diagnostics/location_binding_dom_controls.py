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


# La pantalla observada por el usuario presenta tarjetas de ciudad con indicador
# tipo radio. Cuando un mismo gesto visual expone simultáneamente un radio y una
# superficie button con el mismo nombre accesible, el radio es el control semántico
# específico y la superficie genérica no debe convertir esa única opción visual en
# una ambigüedad artificial. La unicidad sigue siendo obligatoria dentro del rol
# elegido: dos radios realmente presentados para la misma ciudad continúan fallando
# cerrado. Un duplicado DOM fuera del viewport no representa una segunda opción que
# el usuario tenga delante.
CITY_CONTROL_ROLES: tuple[str, ...] = ("radio", "option", "menuitem", "button")
CITY_CONTROL_READY_TIMEOUT_MS = 3_000
CITY_CONTROL_READY_POLL_MS = 100
CITY_MODAL_SCOPE_MAX_ANCESTORS = 8
LOCATION_SELECTOR_CLASS = "btn-modal-selector"
LOCATION_SELECTOR_CSS = f"button.{LOCATION_SELECTOR_CLASS}"
CITY_MODAL_PROMPT_PATTERN = re.compile(
    r"^\s*¿?\s*desde\s+qu[eé]\s+ciudad\s+nos\s+visita\??\s*$",
    re.I,
)
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
_VIEWPORT_INTERSECTION_JS = """
(element) => {
  const rect = element.getBoundingClientRect();
  const width = window.innerWidth || document.documentElement.clientWidth || 0;
  const height = window.innerHeight || document.documentElement.clientHeight || 0;
  return (
    rect.width > 0 &&
    rect.height > 0 &&
    rect.right > 0 &&
    rect.bottom > 0 &&
    rect.left < width &&
    rect.top < height
  );
}
"""


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


def _is_presented_in_viewport(locator: Any) -> bool:
    """Exige visibilidad y cruce real con el viewport en un browser Playwright.

    ``Locator.is_visible()`` considera visibles elementos con caja fuera de la
    pantalla. Eso es útil para Playwright pero no para decidir qué control está
    realmente presentado al usuario en un modal responsive. Los dobles offline que
    no implementan ``evaluate`` conservan la semántica histórica basada en
    ``is_visible``; un locator real que no pueda evaluarse falla cerrado.
    """

    try:
        if not locator.is_visible():
            return False
    except Exception:
        return False

    evaluator = getattr(locator, "evaluate", None)
    if evaluator is None:
        return True
    try:
        return bool(evaluator(_VIEWPORT_INTERSECTION_JS))
    except Exception:
        return False


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


def _presented_items(collection: Any) -> list[Any]:
    presented: list[Any] = []
    for index in range(collection.count()):
        candidate = collection.nth(index)
        if _is_presented_in_viewport(candidate):
            presented.append(candidate)
    return presented


def _visible_location(label: str | None) -> str | None:
    normalized = _clean_label(label)
    if normalized is None:
        return None
    if normalized.casefold() in _IGNORED_VISIBLE_LOCATION_LABELS:
        return None
    return normalized


def resolve_location_selector(page: Any) -> ResolvedLocationSelector:
    """Resuelve primero el botón estructural observado y luego el fallback legado.

    La evidencia HTML aportada por el usuario expone la ubicación seleccionada como
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


def _visible_native_select(parent_select: Any) -> bool:
    """Acepta options nativos sólo cuando su ``select`` está presentado.

    Playwright puede considerar invisibles los elementos ``option`` de un select
    nativo aun cuando el propio ``select`` sí sea interactivo. Por eso la
    visibilidad se decide en el contenedor. Un select duplicado oculto o fuera del
    viewport no debe competir con el control realmente presentado al usuario.
    """

    try:
        return parent_select.count() == 1 and _is_presented_in_viewport(parent_select)
    except Exception:
        return False


def _visible_role_matches(scope: Any, *, role: str, exact_name: re.Pattern[str]) -> list[Any]:
    matches = scope.get_by_role(role, name=exact_name)
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
            if role == "option":
                if _visible_native_select(parent_select) or _is_presented_in_viewport(candidate):
                    visible.append(candidate)
            elif _is_presented_in_viewport(candidate):
                visible.append(candidate)
        except Exception:
            continue
    return visible


def _city_modal_scope(page: Any, exact_name: re.Pattern[str]) -> Any:
    """Acota la búsqueda al modal visual realmente presentado.

    La captura aportada por el usuario muestra el prompt exacto
    ``¿Desde qué ciudad nos visita?``. Si ese prompt cruza el viewport, se toma el
    menor ancestro que además contiene una opción exacta presentada para la ciudad
    objetivo. Un duplicado responsive que Playwright considera visible pero que está
    fuera de pantalla no compite con el modal que el usuario tiene delante. Si el
    prompt no existe se conserva el resolver histórico para selects/listboxes.
    """

    try:
        prompts = _presented_items(page.get_by_text(CITY_MODAL_PROMPT_PATTERN))
    except Exception:
        return page
    if not prompts:
        return page
    if len(prompts) != 1:
        raise LocationControlResolutionError("target_city_not_unique")

    scope = prompts[0]
    for _ in range(CITY_MODAL_SCOPE_MAX_ANCESTORS):
        try:
            parent = scope.locator("xpath=..")
        except Exception:
            break
        try:
            if parent.count() != 1:
                break
        except Exception:
            break
        for role in CITY_CONTROL_ROLES:
            try:
                if _visible_role_matches(parent, role=role, exact_name=exact_name):
                    return parent
            except Exception:
                continue
        scope = parent

    # El modal ya está identificado físicamente pero todavía no presenta una opción
    # interactiva; el bucle exterior puede volver a sondear durante la ventana
    # acotada de readiness.
    raise LocationControlResolutionError("target_city_not_found")


def _usable_labels(options: Any, *, require_visible: bool) -> tuple[str, ...]:
    labels: list[str] = []
    for index in range(options.count()):
        option = options.nth(index)
        if require_visible and not _is_presented_in_viewport(option):
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


def _radio_scope_labels(scope: Any) -> tuple[str, ...] | None:
    """Conserva sólo ciudades hermanas presentadas cuando el modal usa radios."""

    try:
        radios = scope.get_by_role("radio")
    except Exception:
        return None
    labels: list[str] = []
    for index in range(radios.count()):
        radio = radios.nth(index)
        if not _is_presented_in_viewport(radio):
            continue
        label = _label(radio)
        if label and label.casefold() not in _IGNORED_CITY_LABELS:
            labels.append(label)
    return tuple(sorted(set(labels), key=str.casefold)) or None


def _resolve_exact_city_control_once(page: Any, normalized: str) -> ResolvedCityControl:
    exact = re.compile(rf"^{re.escape(normalized)}$", re.I)
    scope = _city_modal_scope(page, exact)

    for role in CITY_CONTROL_ROLES:
        candidates = _visible_role_matches(scope, role=role, exact_name=exact)
        if not candidates:
            continue
        if len(candidates) != 1:
            raise LocationControlResolutionError("target_city_not_unique")

        locator = candidates[0]
        if role == "option":
            labels = _option_container_labels(locator)
        elif role == "radio":
            labels = _radio_scope_labels(scope)
        else:
            labels = None
        if not labels:
            labels = (normalized,)
        return ResolvedCityControl(locator=locator, role=role, available_cities=labels)

    raise LocationControlResolutionError("target_city_not_found")


def _wait_for_next_city_probe(page: Any) -> None:
    """Espera un intervalo acotado sin convertir errores de DOM en autoridad."""

    try:
        page.wait_for_timeout(CITY_CONTROL_READY_POLL_MS)
    except Exception:
        # Dobles de prueba sin reloj Playwright siguen pudiendo ejercitar el
        # contrato de resolución; en browser real la espera sí consume el intervalo.
        return


def resolve_exact_city_control(page: Any, city_name: str) -> ResolvedCityControl:
    """Resuelve la opción visual exacta de ciudad tras abrir el modal.

    Si está presentado el prompt ``¿Desde qué ciudad nos visita?`` la búsqueda se
    acota al menor ancestro que contiene la opción objetivo. Dentro de ese scope se
    usan roles por especificidad semántica: ``radio`` > ``option`` > ``menuitem`` >
    ``button``. Un radio único puede coexistir con una superficie button decorativa
    del mismo gesto visual sin generar un falso ``target_city_not_unique``; dos
    candidatos del mismo rol realmente presentados siguen fallando cerrado.

    El botón de encabezado ``btn-modal-selector`` se excluye siempre. En selects
    nativos sólo compiten options cuyo ``select`` ancestro está presentado en el
    viewport. La ausencia temporal puede reintentarse durante tres segundos; una
    ambigüedad real falla de inmediato.
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
