from __future__ import annotations

import re

import pytest

from precios_supermercados.diagnostics.location_binding_dom_controls import (
    LOCATION_SELECTOR_CLASS,
    LOCATION_SELECTOR_CSS,
    LocationControlResolutionError,
    ResolvedCityControl,
    ResolvedLocationSelector,
    activate_city_control,
    open_location_selector,
    resolve_exact_city_control,
    resolve_location_selector,
)


class FakeCollection:
    def __init__(self, items):
        self.items = list(items)

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]


class FakeSelect:
    def __init__(self, options, *, visible=True):
        self.options = list(options)
        self.visible = visible
        self.selected = None

    def count(self):
        return 1

    def is_visible(self):
        return self.visible

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
        classes="",
    ):
        self.label = label
        self.role = role
        self.visible = visible
        self.parent_select = parent_select
        self.parent_listbox = parent_listbox
        self.classes = classes
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
        if name == "aria-label":
            return self.label
        if name == "class":
            return self.classes
        raise AssertionError(name)

    def inner_text(self):
        return self.label

    def click(self):
        self.clicked = True


class FakePage:
    def __init__(self, controls, *, structural=()):
        self.controls = list(controls)
        self.structural = list(structural)

    def locator(self, selector):
        assert selector == LOCATION_SELECTOR_CSS
        return FakeCollection(self.structural)

    def get_by_role(self, role, *, name=None):
        if name is not None:
            assert isinstance(name, re.Pattern)
        return FakeCollection(
            control
            for control in self.controls
            if control.role == role
            and control.label is not None
            and (name is None or name.fullmatch(control.label))
        )


class FakeScope(FakePage):
    def __init__(self, controls):
        super().__init__(controls)

    def count(self):
        return 1

    def locator(self, selector):
        if selector == "xpath=..":
            return MissingContainer()
        return super().locator(selector)


class FakePrompt:
    def __init__(self, parent):
        self.parent = parent

    def is_visible(self):
        return True

    def locator(self, selector):
        assert selector == "xpath=.."
        return self.parent


class FakePageWithPrompt(FakePage):
    def __init__(self, controls, *, prompt, structural=()):
        super().__init__(controls, structural=structural)
        self.prompt = prompt

    def get_by_text(self, pattern):
        assert isinstance(pattern, re.Pattern)
        assert pattern.fullmatch("¿Desde qué ciudad nos visita?")
        return FakeCollection([self.prompt])


def test_structural_location_button_matches_user_supplied_html_and_exposes_city() -> None:
    button = FakeControl(
        label="San pedro sula",
        role="button",
        classes=LOCATION_SELECTOR_CLASS,
    )
    legacy = FakeControl(label="Ubicación", role="button")
    page = FakePage([button, legacy], structural=[button])

    resolved = resolve_location_selector(page)

    assert resolved == ResolvedLocationSelector(
        locator=button,
        source="btn-modal-selector",
        visible_location="San pedro sula",
    )
    opened = open_location_selector(page)
    assert opened == resolved
    assert button.clicked is True
    assert legacy.clicked is False


def test_structural_location_button_ambiguity_fails_closed() -> None:
    page = FakePage(
        [],
        structural=[
            FakeControl(
                label="San Pedro Sula",
                role="button",
                classes=LOCATION_SELECTOR_CLASS,
            ),
            FakeControl(
                label="Tegucigalpa",
                role="button",
                classes=LOCATION_SELECTOR_CLASS,
            ),
        ],
    )

    with pytest.raises(LocationControlResolutionError, match="location_selector_not_unique"):
        resolve_location_selector(page)


def test_structural_location_button_requires_readable_label() -> None:
    page = FakePage(
        [],
        structural=[
            FakeControl(label=None, role="button", classes=LOCATION_SELECTOR_CLASS)
        ],
    )

    with pytest.raises(LocationControlResolutionError, match="location_selector_label_missing"):
        resolve_location_selector(page)


def test_legacy_location_selector_remains_supported_without_false_city() -> None:
    legacy = FakeControl(label="Selecciona tu tienda", role="button")
    resolved = resolve_location_selector(FakePage([legacy]))

    assert resolved.source == "accessible-fallback"
    assert resolved.visible_location is None
    assert resolved.locator is legacy


def test_location_selector_missing_fails_closed() -> None:
    with pytest.raises(LocationControlResolutionError, match="location_selector_not_found"):
        resolve_location_selector(FakePage([]))


def test_header_current_city_button_is_not_a_modal_city_option() -> None:
    header = FakeControl(
        label="San Pedro Sula",
        role="button",
        classes=LOCATION_SELECTOR_CLASS,
    )
    city = FakeControl(label="San Pedro Sula", role="option", visible=False)
    tgu = FakeControl(label="Tegucigalpa", role="option", visible=False)
    parent = FakeSelect([city, tgu])
    city.parent_select = parent
    tgu.parent_select = parent
    page = FakePage([header, city, tgu], structural=[header])

    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved.locator is city
    assert resolved.role == "option"
    assert resolved.available_cities == ("San Pedro Sula", "Tegucigalpa")


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


def test_hidden_native_select_duplicate_does_not_compete_with_visible_select() -> None:
    visible_sps = FakeControl(label="San Pedro Sula", role="option", visible=False)
    visible_tgu = FakeControl(label="Tegucigalpa", role="option", visible=False)
    visible_parent = FakeSelect([visible_sps, visible_tgu], visible=True)
    visible_sps.parent_select = visible_parent
    visible_tgu.parent_select = visible_parent

    hidden_sps = FakeControl(label="San Pedro Sula", role="option", visible=False)
    hidden_tgu = FakeControl(label="Tegucigalpa", role="option", visible=False)
    hidden_parent = FakeSelect([hidden_sps, hidden_tgu], visible=False)
    hidden_sps.parent_select = hidden_parent
    hidden_tgu.parent_select = hidden_parent

    page = FakePage([hidden_sps, hidden_tgu, visible_sps, visible_tgu])
    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved.locator is visible_sps
    assert resolved.available_cities == ("San Pedro Sula", "Tegucigalpa")


def test_two_visible_native_selects_with_same_city_still_fail_closed() -> None:
    first_sps = FakeControl(label="San Pedro Sula", role="option", visible=False)
    second_sps = FakeControl(label="San Pedro Sula", role="option", visible=False)
    first_parent = FakeSelect([first_sps], visible=True)
    second_parent = FakeSelect([second_sps], visible=True)
    first_sps.parent_select = first_parent
    second_sps.parent_select = second_parent

    with pytest.raises(LocationControlResolutionError, match="target_city_not_unique"):
        resolve_exact_city_control(FakePage([first_sps, second_sps]), "San Pedro Sula")


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


def test_radio_is_preferred_over_duplicate_button_surface_for_same_city() -> None:
    button = FakeControl(label="San Pedro Sula", role="button")
    sps_radio = FakeControl(label="San Pedro Sula", role="radio")
    tgu_radio = FakeControl(label="Tegucigalpa", role="radio")
    page = FakePage([button, sps_radio, tgu_radio])

    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved.locator is sps_radio
    assert resolved.role == "radio"
    assert resolved.available_cities == ("San Pedro Sula", "Tegucigalpa")
    activate_city_control(resolved, "San Pedro Sula")
    assert sps_radio.clicked is True
    assert button.clicked is False


def test_visual_prompt_scopes_choice_and_ignores_same_city_control_outside_modal() -> None:
    outside_radio = FakeControl(label="San Pedro Sula", role="radio")
    modal_sps = FakeControl(label="San Pedro Sula", role="radio")
    modal_tgu = FakeControl(label="Tegucigalpa", role="radio")
    modal_button = FakeControl(label="San Pedro Sula", role="button")
    modal = FakeScope([modal_sps, modal_tgu, modal_button])
    prompt = FakePrompt(modal)
    page = FakePageWithPrompt(
        [outside_radio, modal_sps, modal_tgu, modal_button],
        prompt=prompt,
    )

    resolved = resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved.locator is modal_sps
    assert resolved.role == "radio"
    assert resolved.available_cities == ("San Pedro Sula", "Tegucigalpa")


def test_two_visible_radios_with_same_city_still_fail_closed() -> None:
    page = FakePage(
        [
            FakeControl(label="San Pedro Sula", role="radio"),
            FakeControl(label="San Pedro Sula", role="radio"),
            FakeControl(label="San Pedro Sula", role="button"),
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
