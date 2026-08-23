from __future__ import annotations

import pytest

from precios_supermercados.diagnostics.location_binding_dom_controls import (
    CITY_BUTTON_CONTAINER_CSS,
    CITY_BUTTON_CSS,
    CITY_BUTTON_SELECTED_CLASS,
    CITY_BUTTON_UNSELECTED_CLASS,
    CITY_STATE_SELECTED,
    CITY_STATE_UNSELECTED,
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
    def __init__(
        self,
        text: str,
        path: list[int],
        *,
        state: str = CITY_STATE_UNSELECTED,
        presented: bool = True,
        classes: str | None = None,
    ):
        self.text = text
        self.path = path
        self.presented = presented
        self.clicked = False
        if classes is not None:
            self.classes = classes
        elif state == CITY_STATE_SELECTED:
            self.classes = CITY_BUTTON_SELECTED_CLASS
        else:
            self.classes = CITY_BUTTON_UNSELECTED_CLASS

    def is_visible(self):
        return True

    def evaluate(self, script):
        if "parentElement.children" in script:
            return self.path
        return self.presented

    def get_attribute(self, name):
        if name == "class":
            return self.classes
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


def test_resolves_and_clicks_exact_unselected_user_supplied_city_button() -> None:
    tegucigalpa = Button("Tegucigalpa", [0, 0], state=CITY_STATE_SELECTED)
    san_pedro_sula = Button("San pedro sula", [0, 1], state=CITY_STATE_UNSELECTED)
    page = Page([Container([tegucigalpa, san_pedro_sula], [0])])

    control = resolve_exact_city_control(page, "San Pedro Sula")

    assert control.locator is san_pedro_sula
    assert control.role == "button"
    assert control.state == CITY_STATE_UNSELECTED
    assert control.available_cities == ("San pedro sula", "Tegucigalpa")

    assert activate_city_control(control, "San Pedro Sula") is True
    assert san_pedro_sula.clicked is True
    assert tegucigalpa.clicked is False


def test_selected_target_is_a_safe_noop() -> None:
    target = Button("San pedro sula", [0, 0], state=CITY_STATE_SELECTED)
    other = Button("Tegucigalpa", [0, 1], state=CITY_STATE_UNSELECTED)
    page = Page([Container([target, other], [0])])

    control = resolve_exact_city_control(page, "SAN PEDRO SULA")

    assert control.locator is target
    assert control.state == CITY_STATE_SELECTED
    assert control.available_cities == ("San pedro sula", "Tegucigalpa")
    assert activate_city_control(control, "San Pedro Sula") is False
    assert target.clicked is False
    assert other.clicked is False


def test_structural_target_with_both_state_classes_fails_closed() -> None:
    target = Button(
        "San pedro sula",
        [0, 0],
        classes=f"{CITY_BUTTON_SELECTED_CLASS} {CITY_BUTTON_UNSELECTED_CLASS}",
    )
    page = Page([Container([target], [0])])

    with pytest.raises(LocationControlResolutionError, match="target_city_state_invalid"):
        resolve_exact_city_control(page, "San Pedro Sula")


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
    assert control.state == CITY_STATE_UNSELECTED
