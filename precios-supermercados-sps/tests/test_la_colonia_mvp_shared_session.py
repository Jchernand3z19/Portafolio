from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "probar_muestra_sps_la_colonia_session.py"
SPEC = importlib.util.spec_from_file_location("probar_muestra_sps_la_colonia_session", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CookieContext:
    def __init__(self, cookies=None):
        self._cookies = list(cookies or [])

    def cookies(self):
        return list(self._cookies)

    def set_cookie(self, name: str, value: str, domain: str = ".lacolonia.com") -> None:
        self._cookies = [cookie for cookie in self._cookies if cookie["name"] != name]
        self._cookies.append({"name": name, "value": value, "domain": domain})


def request(context: CookieContext, *, region=None, headers=None):
    payload = {"variables": {"regionId": region}} if region is not None else None
    page = SimpleNamespace(context=context)
    frame = SimpleNamespace(page=page)
    return SimpleNamespace(
        frame=frame,
        headers=dict(headers or {}),
        url="https://www.lacolonia.com/_v/segment/graphql/v1",
        post_data_json=payload,
    )


def tracker_for(region: str):
    return module.SharedBrowserSessionTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )


def test_body_only_region_accepts_exact_vtexsession_transition() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    context.set_cookie("vtexsession", "session-before")
    tracker = tracker_for(region)

    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    context.set_cookie("vtexsession", "session-after")
    tracker.snapshot_context(context)
    tracker.observe_request(request(context, region=region))

    assert tracker.segment_cookie_transition_observed is False
    assert tracker.session_cookie_transition_observed is True
    assert tracker.fingerprint_verified is True
    assert tracker.replay_context() == ({}, ())
    assert module.SharedBrowserSessionTracker.shared_fallback_used is True
    private_repr = repr(tracker.__dict__)
    assert "session-before" not in private_repr
    assert "session-after" not in private_repr
    assert region not in private_repr


def test_unchanged_vtexsession_does_not_authorize_body_only_region() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    context.set_cookie("vtexsession", "same-session")
    tracker = tracker_for(region)

    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    tracker.snapshot_context(context)
    tracker.observe_request(request(context, region=region))

    with pytest.raises(
        module.bound.passive.MvpSampleError,
        match="sps_region_binding_body_only_without_shared_session_transition",
    ):
        tracker.replay_context()
    assert tracker.session_cookie_transition_observed is False


def test_missing_vtexsession_baseline_stays_fail_closed() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    tracker = tracker_for(region)

    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    context.set_cookie("vtexsession", "session-after")
    tracker.snapshot_context(context)
    tracker.observe_request(request(context, region=region))

    with pytest.raises(module.bound.passive.MvpSampleError):
        tracker.replay_context()
    assert tracker.session_cookie_baseline_observed is False
    assert tracker.session_cookie_active_observed is True


def test_segment_transition_remains_valid_without_vtexsession() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    context.set_cookie("vtexsegment", "segment-before")
    tracker = tracker_for(region)

    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    context.set_cookie("vtexsegment", "segment-after")
    tracker.snapshot_context(context)
    tracker.observe_request(request(context, region=region))

    assert tracker.segment_cookie_transition_observed is True
    assert tracker.session_cookie_transition_observed is False
    assert tracker.replay_context() == ({}, ())


def test_explicit_region_header_keeps_priority_without_cookie_transition() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    tracker = tracker_for(region)
    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    tracker.observe_request(
        request(context, headers={"x-vtex-region": region})
    )

    assert tracker.replay_context() == ({"x-vtex-region": region}, ())
    assert module.SharedBrowserSessionTracker.shared_fallback_used is False


def test_vtexsession_snapshot_ignores_other_domains_and_returns_only_hash() -> None:
    context = CookieContext()
    context.set_cookie("vtexsession", "secret-session", domain="example.com")
    assert module._cookie_fingerprint_from_context(
        context, module.SESSION_COOKIE_NAME
    ) is None

    context.set_cookie("vtexsession", "secret-session", domain=".lacolonia.com")
    fingerprint = module._cookie_fingerprint_from_context(
        context, module.SESSION_COOKIE_NAME
    )
    assert fingerprint == module.bound._stable_fingerprint("secret-session")
    assert fingerprint != "secret-session"


def test_diagnostics_are_boolean_only() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    context.set_cookie("vtexsession", "session-before")
    tracker = tracker_for(region)
    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    context.set_cookie("vtexsession", "session-after")
    tracker.snapshot_context(context)

    diagnostics = module._shared_diagnostics()
    assert diagnostics["session_cookie_baseline_observed"] is True
    assert diagnostics["session_cookie_active_observed"] is True
    assert diagnostics["session_cookie_transition_verified"] is True
    assert all(isinstance(value, bool) for value in diagnostics.values())
    assert "session-before" not in repr(diagnostics)
    assert "session-after" not in repr(diagnostics)


def test_replay_uses_original_region_tracker_after_live_monkeypatch() -> None:
    region = "opaque-sps-region"
    context = CookieContext()
    context.set_cookie("vtexsession", "session-before")
    tracker = tracker_for(region)
    tracker.reset_and_enable()
    tracker.begin_city_activation(context)
    context.set_cookie("vtexsession", "session-after")
    tracker.snapshot_context(context)
    tracker.observe_request(request(context, region=region))

    original = module.bound.RegionContextTracker
    module.bound.RegionContextTracker = module.SharedBrowserSessionTracker
    try:
        assert tracker.replay_context() == ({}, ())
    finally:
        module.bound.RegionContextTracker = original
