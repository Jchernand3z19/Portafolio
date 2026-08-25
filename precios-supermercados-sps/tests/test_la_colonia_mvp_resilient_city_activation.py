from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "probar_muestra_sps_la_colonia_resilient.py"
SPEC = importlib.util.spec_from_file_location("probar_muestra_sps_la_colonia_resilient", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _control(page: object) -> SimpleNamespace:
    return SimpleNamespace(locator=SimpleNamespace(page=page))


def test_timeout_does_not_repeat_click_when_city_was_already_selected() -> None:
    page = object()
    control = _control(page)
    calls = {"activate": 0, "resolve": 0, "wait": 0}

    def activate(_control, _city):
        calls["activate"] += 1
        raise TimeoutError("detached")

    def wait_for_city(observed_page):
        assert observed_page is page
        calls["wait"] += 1
        return "San Pedro Sula"

    def resolve(_page, _city):
        calls["resolve"] += 1
        raise AssertionError("must not re-resolve after verified selection")

    assert module.activate_city_control_resilient(
        control,
        "San Pedro Sula",
        activate_fn=activate,
        resolve_fn=resolve,
        wait_for_city_fn=wait_for_city,
    ) is True
    assert calls == {"activate": 1, "resolve": 0, "wait": 1}


def test_timeout_reresolves_same_city_once_when_selection_did_not_land() -> None:
    page = object()
    first = _control(page)
    refreshed = _control(page)
    calls = {"activate": 0, "resolve": 0}

    def activate(control, city):
        assert city == "San Pedro Sula"
        calls["activate"] += 1
        if control is first:
            raise TimeoutError("detached")
        assert control is refreshed
        return True

    def wait_for_city(_page):
        raise module.bound.passive.MvpSampleError("sps_city_selection_unverified")

    def resolve(observed_page, city):
        assert observed_page is page
        assert city == "San Pedro Sula"
        calls["resolve"] += 1
        return refreshed

    assert module.activate_city_control_resilient(
        first,
        "San Pedro Sula",
        activate_fn=activate,
        resolve_fn=resolve,
        wait_for_city_fn=wait_for_city,
    ) is True
    assert calls == {"activate": 2, "resolve": 1}


def test_second_timeout_stops_fail_closed_without_more_refreshes() -> None:
    page = object()
    first = _control(page)
    refreshed = _control(page)
    calls = {"activate": 0, "resolve": 0}

    def activate(_control, _city):
        calls["activate"] += 1
        raise TimeoutError("detached")

    def wait_for_city(_page):
        raise module.bound.passive.MvpSampleError("sps_city_selection_unverified")

    def resolve(_page, _city):
        calls["resolve"] += 1
        return refreshed

    with pytest.raises(
        module.bound.passive.MvpSampleError,
        match="sps_city_control_activation_timeout",
    ):
        module.activate_city_control_resilient(
            first,
            "San Pedro Sula",
            activate_fn=activate,
            resolve_fn=resolve,
            wait_for_city_fn=wait_for_city,
        )

    assert calls == {"activate": 2, "resolve": 1}


def test_non_timeout_activation_error_is_not_retried() -> None:
    page = object()
    first = _control(page)

    def activate(_control, _city):
        raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError, match="unexpected"):
        module.activate_city_control_resilient(
            first,
            "San Pedro Sula",
            activate_fn=activate,
            resolve_fn=lambda *_: pytest.fail("must not resolve"),
            wait_for_city_fn=lambda *_: pytest.fail("must not wait"),
        )
