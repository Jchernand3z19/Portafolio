from __future__ import annotations

import re

import pytest

from precios_supermercados.diagnostics.location_binding_dom_controls import (
    LocationControlResolutionError,
    ResolvedCityControl,
    activate_city_control,
    resolve_exact_city_control,
)


class FakeCollection:
    def __init__(self, items):
        self.items = list(items)

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]


class FakeSelect:
    def __init__(self, options):
        self.options = list(options)
        self.selected = None

    def count(self):
        return 1

    def locator(self, selector):
        assert selector == "option"
        return FakeCollection(self.options)

    def select_option(self, *, label):
        self.selected = label


class FakeListbox:
    def __init__(self, options):
        self.options = list(options)

    def count(self):
        return 1

    def get_by_role(self, role):
        assert role == "option"
        return FakeCollection(self.options)


class MissingContainer:
    def count(self):
        return 0


class FakeControl:
    def __init__(
        self,
        *,
        label,
        role,
        visible=True,
        parent_select=None,
        parent_listbox=None,
    ):
        self.label = label
        self.role = role
        self.visible = visible
        self.parent_select = parent_select
        self.parent_listbox = parent_listbox
        self.clicked = False

    def is_visible(self):
        return self.visible

    def locator(self, selector):
        if selector == "xpath=ancestor::select[1]":
            return self.parent_select or MissingContainer()
        if selector == "xpath=ancestor::*[@role='listbox'][1]":
            return self.parent_listbox or MissingContainer()
        raise AssertionError(selector)

    def get_attribute(self, name):
        assert name == "aria-label"
        return self.label

    def inner_text(self):
        return self.label

    def click(self):
        self.clicked = True


class FakePage:
    def __init__(self, controls):
        self.controls = list(controls)

    def get_by_role(self, role, *, name):
        assert isinstance(name, re.Pattern)
        return FakeCollection(
            control
            for control in self.controls
            if control.role == role and name.fullmatch(control.label)
        )


def test_native_select_preserves_real_city_labels_and_activates_exact_target() -> None:
    sps = FakeControl(label="San Pedro Sula", role="option", visible=False)
    tgu = FakeControl(label="Tegucigalpa", role="option", visible=False)
    placeholder = FakeControl(label="Selecciona tu ciudad", role="option", visible=False)
    parent = FakeSelect([placeholder, sps, tgu])
    sps.parent_select = parent
    tgu.parent_select = parent
    placeholder.parent_select = parent
    page = FakePage([sps, tgu, placeholder])

    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved.role == "option"
    assert resolved.available_cities == ("San Pedro Sula", "Tegucigalpa")
    activate_city_control(resolved, "San Pedro Sula")
    assert parent.selected == "San Pedro Sula"
    assert sps.clicked is False


def test_custom_listbox_preserves_visible_city_siblings() -> None:
    sps = FakeControl(label="San Pedro Sula", role="option")
    tgu = FakeControl(label="Tegucigalpa", role="option")
    hidden = FakeControl(label="La Ceiba", role="option", visible=False)
    listbox = FakeListbox([sps, tgu, hidden])
    sps.parent_listbox = listbox
    tgu.parent_listbox = listbox
    hidden.parent_listbox = listbox
    page = FakePage([sps, tgu, hidden])

    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved.role == "option"
    assert resolved.available_cities == ("San Pedro Sula", "Tegucigalpa")


def test_custom_button_city_is_accepted_only_when_exact_and_unique() -> None:
    sps = FakeControl(label="San Pedro Sula", role="button")
    page = FakePage([sps, FakeControl(label="Tegucigalpa", role="button")])

    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved == ResolvedCityControl(
        locator=sps,
        role="button",
        available_cities=("San Pedro Sula",),
    )
    activate_city_control(resolved, "San Pedro Sula")
    assert sps.clicked is True


def test_duplicate_exact_city_controls_fail_closed_even_across_roles() -> None:
    page = FakePage(
        [
            FakeControl(label="San Pedro Sula", role="button"),
            FakeControl(label="San Pedro Sula", role="radio"),
        ]
    )

    with pytest.raises(LocationControlResolutionError, match="target_city_not_unique"):
        resolve_exact_city_control(page, "San Pedro Sula")


def test_noninteractive_text_is_not_promoted_to_city_control() -> None:
    page = FakePage([])

    with pytest.raises(LocationControlResolutionError, match="target_city_not_found"):
        resolve_exact_city_control(page, "San Pedro Sula")


def test_hidden_custom_control_is_not_accepted() -> None:
    page = FakePage([FakeControl(label="San Pedro Sula", role="button", visible=False)])

    with pytest.raises(LocationControlResolutionError, match="target_city_not_found"):
        resolve_exact_city_control(page, "San Pedro Sula")


def test_blank_city_name_is_rejected_before_dom_lookup() -> None:
    with pytest.raises(LocationControlResolutionError, match="target_city_name_invalid"):
        resolve_exact_city_control(FakePage([]), "   ")
