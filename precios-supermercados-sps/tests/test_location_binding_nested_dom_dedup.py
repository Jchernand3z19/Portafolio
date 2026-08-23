from __future__ import annotations

import pytest

import precios_supermercados.diagnostics.la_colonia_location_binding_capture as capture
from precios_supermercados.diagnostics.location_binding_dom_controls import (
    LocationControlResolutionError,
    _collapse_nested_presented_items,
)


class PathLocator:
    def __init__(self, path: tuple[int, ...]):
        self.path = list(path)

    def is_visible(self):
        return True

    def evaluate(self, script):
        assert "parentElement.children" in script
        return list(self.path)


def test_nested_dom_matches_collapse_to_deepest_specific_node() -> None:
    outer = PathLocator((0, 1))
    middle = PathLocator((0, 1, 2))
    inner = PathLocator((0, 1, 2, 0))

    assert _collapse_nested_presented_items([outer, middle, inner]) == [inner]


def test_distinct_sibling_controls_remain_ambiguous_candidates() -> None:
    first = PathLocator((0, 1, 0))
    second = PathLocator((0, 1, 1))

    assert _collapse_nested_presented_items([first, second]) == [first, second]


def test_duplicate_locator_for_same_dom_node_is_deduplicated() -> None:
    first = PathLocator((0, 1, 0))
    duplicate = PathLocator((0, 1, 0))

    assert _collapse_nested_presented_items([first, duplicate]) == [first]


def test_city_resolution_diagnostic_propagates_without_raw_dom(monkeypatch) -> None:
    diagnostic = {
        "stage": "role",
        "role": "radio",
        "candidate_count": 2,
        "effective_count": 2,
    }

    def fail_resolution(page, city_name):
        raise LocationControlResolutionError(
            "target_city_not_unique",
            diagnostic=diagnostic,
        )

    monkeypatch.setattr(capture, "resolve_exact_city_control", fail_resolution)

    with pytest.raises(capture.LocationBindingCaptureError) as exc_info:
        capture._city_select_and_options(object(), "San Pedro Sula")

    assert str(exc_info.value) == "target_city_not_unique"
    assert exc_info.value.diagnostic == diagnostic
    assert set(exc_info.value.diagnostic) == {
        "stage",
        "role",
        "candidate_count",
        "effective_count",
    }
