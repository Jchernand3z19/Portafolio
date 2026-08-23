"""Resolución DOM fail-closed para controles de ubicación.

Este módulo no abre red, no conoce targets live ni concede autoridad. Sólo recibe
una página Playwright ya existente y resuelve, de forma exacta y única, el selector
visible de ubicación y los controles interactivos de ciudad. Se mantiene separado
de la autorización live para poder probar el contrato completamente offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


# La pantalla observada por el usuario presenta dos tarjetas de ciudad. El resolver
# prioriza semántica accesible real cuando existe. La evidencia LC-337 demostró que
# la superficie live puede no exponer ninguno de esos roles; por eso existe un
# fallback visual estrictamente acotado por el prompt del modal o, si el prompt no
# es localizable, por la pareja única San Pedro Sula + Tegucigalpa dentro de un
# ancestro común cercano. Nunca se promueve texto global aislado a control.
CITY_CONTROL_ROLES: tuple[str, ...] = ("radio", "option", "menuitem", "button")
CITY_CONTROL_READY_TIMEOUT_MS = 3_000
CITY_CONTROL_READY_POLL_MS = 100
CITY_MODAL_SCOPE_MAX_ANCESTORS = 8
CITY_PAIR_SCOPE_MAX_ANCESTORS = 8
CITY_PAIR_PEER = "Tegucigalpa"
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
_DOM_PATH_JS = """
(element) => {
  const path = [];
  let current = element;
  while (current && current.parentElement) {
    path.unshift(Array.prototype.indexOf.call(current.parentElement.children, current));
    current = current.parentElement;
  }
  return path;
}
"""


class LocationControlResolutionError(RuntimeError):
    """Fallo determinista con diagnóstico sanitizado opcional."""

    def __init__(
        self,
        reason: str,
        *,
        diagnostic: Mapping[str, str | int] | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.diagnostic = dict(diagnostic or {})


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
    """Exige visibilidad y cruce real con el viewport en un browser Playwright."""

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


def _dom_path(locator: Any) -> tuple[int, ...] | None:
    """Obtiene una identidad estructural efímera sin exponer HTML ni atributos."""

    evaluator = getattr(locator, "evaluate", None)
    if evaluator is None:
        return None
    try:
        raw = evaluator(_DOM_PATH_JS)
    except Exception:
        return None
    if not isinstance(raw, list):
        return None
    if any(not isinstance(index, int) or index < 0 for index in raw):
        return None
    return tuple(raw)


def _collapse_nested_presented_items(items: list[Any]) -> list[Any]:
    """Colapsa sólo coincidencias ancestro/descendiente del mismo gesto visual."""

    if len(items) < 2:
        return items
    paths = [_dom_path(item) for item in items]
    if any(path is None for path in paths):
        return items

    typed_paths = [path for path in paths if path is not None]
    kept: list[Any] = []
    seen: set[tuple[int, ...]] = set()
    for index, path in enumerate(typed_paths):
        if path in seen:
            continue
        seen.add(path)
        is_ancestor_duplicate = any(
            len(path) < len(other) and other[: len(path)] == path
            for other in typed_paths
        )
        if not is_ancestor_duplicate:
            kept.append(items[index])
    return kept


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


def _presented_text_matches(
    scope: Any,
    exact_name: re.Pattern[str],
    *,
    exclude_location_header: bool = False,
) -> tuple[list[Any], list[Any]]:
    """Devuelve matches textuales presentados antes/después del colapso anidado."""

    try:
        matches = scope.get_by_text(exact_name)
    except Exception:
        return [], []
    raw: list[Any] = []
    for index in range(matches.count()):
        candidate = matches.nth(index)
        try:
            if exclude_location_header and _has_css_class(candidate, LOCATION_SELECTOR_CLASS):
                continue
            if _is_presented_in_viewport(candidate):
                raw.append(candidate)
        except Exception:
            continue
    return raw, _collapse_nested_presented_items(raw)


def _visible_location(label: str | None) -> str | None:
    normalized = _clean_label(label)
    if normalized is None:
        return None
    if normalized.casefold() in _IGNORED_VISIBLE_LOCATION_LABELS:
        return None
    return normalized


def resolve_location_selector(page: Any) -> ResolvedLocationSelector:
    """Resuelve primero el botón estructural observado y luego el fallback legado."""

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
    """Acepta options nativos sólo cuando su ``select`` está presentado."""

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
                continue
            parent_select = candidate.locator("xpath=ancestor::select[1]")
            if role == "option":
                if _visible_native_select(parent_select) or _is_presented_in_viewport(candidate):
                    visible.append(candidate)
            elif _is_presented_in_viewport(candidate):
                visible.append(candidate)
        except Exception:
            continue
    return _collapse_nested_presented_items(visible)


def _scope_has_target_surface(parent: Any, exact_name: re.Pattern[str]) -> bool:
    for role in CITY_CONTROL_ROLES:
        try:
            if _visible_role_matches(parent, role=role, exact_name=exact_name):
                return True
        except Exception:
            continue
    _raw, text = _presented_text_matches(parent, exact_name)
    return bool(text)


def _city_modal_scope(
    page: Any,
    exact_name: re.Pattern[str],
) -> tuple[Any, bool, tuple[str, ...] | None]:
    """Acota al modal por prompt; permite texto exacto sólo dentro de ese scope."""

    try:
        raw_prompts = _presented_items(page.get_by_text(CITY_MODAL_PROMPT_PATTERN))
    except Exception:
        return page, False, None
    if not raw_prompts:
        return page, False, None
    prompts = _collapse_nested_presented_items(raw_prompts)
    if len(prompts) != 1:
        raise LocationControlResolutionError(
            "target_city_not_unique",
            diagnostic={
                "stage": "prompt",
                "candidate_count": len(raw_prompts),
                "effective_count": len(prompts),
            },
        )

    scope = prompts[0]
    peer_exact = re.compile(rf"^{re.escape(CITY_PAIR_PEER)}$", re.I)
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
        if _scope_has_target_surface(parent, exact_name):
            _peer_raw, peer_matches = _presented_text_matches(parent, peer_exact)
            labels = (CITY_PAIR_PEER,) if peer_matches else None
            return parent, True, labels
        scope = parent

    raise LocationControlResolutionError(
        "target_city_not_found",
        diagnostic={"stage": "prompt_scope", "candidate_count": len(prompts)},
    )


def _paired_city_text_scope(
    page: Any,
    exact_name: re.Pattern[str],
) -> tuple[Any, bool, tuple[str, ...] | None]:
    """Fallback sin prompt: exige las dos ciudades visibles, únicas y cercanas.

    La cabecera ``btn-modal-selector`` nunca cuenta como la opción SPS. El texto
    objetivo aislado no basta: debe coexistir con la segunda ciudad observada por el
    usuario dentro de un ancestro común alcanzable en un máximo acotado.
    """

    raw_target, target_matches = _presented_text_matches(
        page,
        exact_name,
        exclude_location_header=True,
    )
    peer_exact = re.compile(rf"^{re.escape(CITY_PAIR_PEER)}$", re.I)
    _raw_peer, peer_matches = _presented_text_matches(page, peer_exact)

    if len(target_matches) > 1:
        raise LocationControlResolutionError(
            "target_city_not_unique",
            diagnostic={
                "stage": "text",
                "candidate_count": len(raw_target),
                "effective_count": len(target_matches),
            },
        )
    if len(target_matches) != 1 or len(peer_matches) != 1:
        return page, False, None

    scope = target_matches[0]
    for _ in range(CITY_PAIR_SCOPE_MAX_ANCESTORS):
        try:
            parent = scope.locator("xpath=..")
        except Exception:
            break
        try:
            if parent.count() != 1:
                break
        except Exception:
            break
        _peer_raw, peers_in_parent = _presented_text_matches(parent, peer_exact)
        if len(peers_in_parent) == 1:
            return parent, True, (CITY_PAIR_PEER,)
        if len(peers_in_parent) > 1:
            raise LocationControlResolutionError(
                "target_city_not_unique",
                diagnostic={
                    "stage": "text",
                    "candidate_count": len(peer_matches),
                    "effective_count": len(peers_in_parent),
                },
            )
        scope = parent

    return page, False, None


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
    scope, text_allowed, text_peer_labels = _city_modal_scope(page, exact)
    if not text_allowed:
        scope, text_allowed, text_peer_labels = _paired_city_text_scope(page, exact)

    for role in CITY_CONTROL_ROLES:
        candidates = _visible_role_matches(scope, role=role, exact_name=exact)
        if not candidates:
            continue
        if len(candidates) != 1:
            raise LocationControlResolutionError(
                "target_city_not_unique",
                diagnostic={
                    "stage": "role",
                    "role": role,
                    "candidate_count": len(candidates),
                    "effective_count": len(candidates),
                },
            )

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

    if text_allowed:
        raw_text, text_matches = _presented_text_matches(
            scope,
            exact,
            exclude_location_header=True,
        )
        if len(text_matches) > 1:
            raise LocationControlResolutionError(
                "target_city_not_unique",
                diagnostic={
                    "stage": "text",
                    "candidate_count": len(raw_text),
                    "effective_count": len(text_matches),
                },
            )
        if len(text_matches) == 1:
            labels = tuple(
                sorted(
                    {normalized, *(text_peer_labels or ())},
                    key=str.casefold,
                )
            )
            return ResolvedCityControl(
                locator=text_matches[0],
                role="text",
                available_cities=labels,
            )

    raw_text, text_matches = _presented_text_matches(
        page,
        exact,
        exclude_location_header=True,
    )
    raise LocationControlResolutionError(
        "target_city_not_found",
        diagnostic={
            "stage": "text_scan" if raw_text else "role_scan",
            "candidate_count": len(raw_text),
            "effective_count": len(text_matches),
        },
    )


def _wait_for_next_city_probe(page: Any) -> None:
    """Espera un intervalo acotado sin convertir errores de DOM en autoridad."""

    try:
        page.wait_for_timeout(CITY_CONTROL_READY_POLL_MS)
    except Exception:
        return


def resolve_exact_city_control(page: Any, city_name: str) -> ResolvedCityControl:
    """Resuelve la opción visual exacta de ciudad tras abrir el modal.

    Se priorizan roles accesibles ``radio > option > menuitem > button``. Cuando el
    frontend no expone esos roles, un texto exacto sólo puede activarse si está
    acotado por el prompt visual del modal o por la pareja única y cercana
    ``San Pedro Sula`` + ``Tegucigalpa`` observada en la pantalla aportada. El texto
    aislado nunca se convierte en autoridad de selección.
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
    """Activa el control resuelto sin intentar una segunda heurística."""

    try:
        parent = control.locator.locator("xpath=ancestor::select[1]")
    except Exception:
        parent = None
    if parent is not None and parent.count() == 1:
        parent.select_option(label=city_name)
        return
    control.locator.click()
