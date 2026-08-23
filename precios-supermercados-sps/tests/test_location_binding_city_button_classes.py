from __future__ import annotations

import pytest

from precios_supermercados.diagnostics.location_binding_dom_controls import (
    CITY_BUTTON_CONTAINER_CSS,
    CITY_BUTTON_CSS,
    LocationControlResolutionError,
    activate_city_control,
    resolve_exact_city_control,
)


class Collection:
    def __init__(self, items):
        self.items = list(items)

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]


class EmptyLocator:
    def count(self):
        return 0


class Button:
    def __init__(self, text: str, path: list[int], *, presented: bool = True):
        self.text = text
        self.path = path
        self.presented = presented
        self.clicked = False

    def is_visible(self):
        return True

    def evaluate(self, script):
        if "parentElement.children" in script:
            return self.path
        return self.presented

    def get_attribute(self, name):
        return None

    def inner_text(self):
        return self.text

    def locator(self, selector):
        if selector == "xpath=ancestor::select[1]":
            return EmptyLocator()
        raise AssertionError(f"selector inesperado en button: {selector}")

    def click(self):
        self.clicked = True


class Container:
    def __init__(self, buttons: list[Button], path: list[int], *, presented: bool = True):
        self.buttons = buttons
        self.path = path
        self.presented = presented

    def is_visible(self):
        return True

    def evaluate(self, script):
        if "parentElement.children" in script:
            return self.path
        return self.presented

    def locator(self, selector):
        assert selector == CITY_BUTTON_CSS
        return Collection(self.buttons)


class Page:
    def __init__(self, containers: list[Container]):
        self.containers = containers

    def locator(self, selector):
        assert selector == CITY_BUTTON_CONTAINER_CSS
        return Collection(self.containers)

    def get_by_role(self, *args, **kwargs):
        raise AssertionError("la estructura confirmada debe resolverse antes que ARIA")

    def get_by_text(self, *args, **kwargs):
        raise AssertionError("la estructura confirmada debe resolverse antes que el prompt")


def test_resolves_exact_user_supplied_city_buttons_without_aria_dependency() -> None:
    tegucigalpa = Button("Tegucigalpa", [0, 0])
    san_pedro_sula = Button("San pedro sula", [0, 1])
    page = Page([Container([tegucigalpa, san_pedro_sula], [0])])

    control = resolve_exact_city_control(page, "San Pedro Sula")

    assert control.locator is san_pedro_sula
    assert control.role == "button"
    assert control.available_cities == ("San pedro sula", "Tegucigalpa")

    activate_city_control(control, "San Pedro Sula")
    assert san_pedro_sula.clicked is True
    assert tegucigalpa.clicked is False


def test_selected_or_noselected_state_does_not_change_city_identity() -> None:
    # El resolver no asume que la clase selected significa que siempre debemos
    # elegir esa ciudad. La identidad sigue siendo el texto exacto del botón.
    target = Button("San pedro sula", [0, 0])
    other = Button("Tegucigalpa", [0, 1])
    page = Page([Container([target, other], [0])])

    control = resolve_exact_city_control(page, "SAN PEDRO SULA")

    assert control.locator is target
    assert control.available_cities == ("San pedro sula", "Tegucigalpa")


def test_two_presented_structural_targets_still_fail_closed() -> None:
    page = Page(
        [
            Container([Button("San pedro sula", [0, 0])], [0]),
            Container([Button("San pedro sula", [1, 0])], [1]),
        ]
    )

    with pytest.raises(LocationControlResolutionError, match="target_city_not_unique") as exc:
        resolve_exact_city_control(page, "San Pedro Sula")

    assert exc.value.diagnostic == {
        "stage": "role",
        "role": "button",
        "candidate_count": 2,
        "effective_count": 2,
    }


def test_offviewport_structural_duplicate_does_not_compete() -> None:
    onscreen = Button("San pedro sula", [0, 0])
    offscreen = Button("San pedro sula", [1, 0])
    page = Page(
        [
            Container([onscreen], [0]),
            Container([offscreen], [1], presented=False),
        ]
    )

    control = resolve_exact_city_control(page, "San Pedro Sula")

    assert control.locator is onscreen
