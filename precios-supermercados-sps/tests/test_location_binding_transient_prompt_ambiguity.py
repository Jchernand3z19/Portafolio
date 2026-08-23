from __future__ import annotations

import pytest

import precios_supermercados.diagnostics.location_binding_dom_controls as controls


class Page:
    def __init__(self) -> None:
        self.waits: list[int] = []

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.waits.append(milliseconds)


class Locator:
    pass


def test_duplicate_prompt_is_retryable_during_city_readiness(monkeypatch) -> None:
    page = Page()
    calls = 0
    expected = controls.ResolvedCityControl(
        locator=Locator(),
        role="button",
        available_cities=("San Pedro Sula", "Tegucigalpa"),
        state=controls.CITY_STATE_UNSELECTED,
    )

    def resolve_once(_page, _normalized):
        nonlocal calls
        calls += 1
        if calls < 4:
            raise controls.LocationControlResolutionError(
                "target_city_not_unique",
                diagnostic={
                    "stage": "prompt",
                    "candidate_count": 2,
                    "effective_count": 2,
                },
            )
        return expected

    monkeypatch.setattr(controls, "_resolve_exact_city_control_once", resolve_once)
    monkeypatch.setattr(controls, "CITY_CONTROL_READY_TIMEOUT_MS", 500)
    monkeypatch.setattr(controls, "CITY_CONTROL_READY_POLL_MS", 100)

    resolved = controls.resolve_exact_city_control(page, "San Pedro Sula")

    assert resolved is expected
    assert calls == 4
    assert page.waits == [100, 100, 100]


def test_real_role_ambiguity_remains_fail_closed_without_retry(monkeypatch) -> None:
    page = Page()
    calls = 0

    def resolve_once(_page, _normalized):
        nonlocal calls
        calls += 1
        raise controls.LocationControlResolutionError(
            "target_city_not_unique",
            diagnostic={
                "stage": "role",
                "role": "button",
                "candidate_count": 2,
                "effective_count": 2,
            },
        )

    monkeypatch.setattr(controls, "_resolve_exact_city_control_once", resolve_once)
    monkeypatch.setattr(controls, "CITY_CONTROL_READY_TIMEOUT_MS", 500)
    monkeypatch.setattr(controls, "CITY_CONTROL_READY_POLL_MS", 100)

    with pytest.raises(controls.LocationControlResolutionError, match="target_city_not_unique"):
        controls.resolve_exact_city_control(page, "San Pedro Sula")

    assert calls == 1
    assert page.waits == []


def test_persistent_duplicate_prompt_still_fails_closed_after_deadline(monkeypatch) -> None:
    page = Page()
    calls = 0

    def resolve_once(_page, _normalized):
        nonlocal calls
        calls += 1
        raise controls.LocationControlResolutionError(
            "target_city_not_unique",
            diagnostic={
                "stage": "prompt",
                "candidate_count": 2,
                "effective_count": 2,
            },
        )

    monkeypatch.setattr(controls, "_resolve_exact_city_control_once", resolve_once)
    monkeypatch.setattr(controls, "CITY_CONTROL_READY_TIMEOUT_MS", 300)
    monkeypatch.setattr(controls, "CITY_CONTROL_READY_POLL_MS", 100)

    with pytest.raises(controls.LocationControlResolutionError, match="target_city_not_unique") as exc:
        controls.resolve_exact_city_control(page, "San Pedro Sula")

    assert exc.value.diagnostic["stage"] == "prompt"
    assert calls == 4
    assert page.waits == [100, 100, 100]
