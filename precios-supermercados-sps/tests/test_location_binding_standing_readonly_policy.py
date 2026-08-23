from __future__ import annotations

import pytest

import precios_supermercados.diagnostics.la_colonia_location_binding_capture as capture


def test_standing_public_read_only_is_versioned_and_does_not_need_run_id() -> None:
    assert capture.STANDING_PUBLIC_READ_ONLY_AUTHORIZED is True
    assert capture.STANDING_PUBLIC_READ_ONLY_AUTHORIZED_AT == "2026-08-23T21:02:02Z"
    capture.validate_capture_authorization(
        authorization_id=None,
        network_policy="live",
        standing_public_read_only=True,
    )


def test_standing_mode_cannot_be_mixed_with_legacy_authorization_id() -> None:
    with pytest.raises(capture.LocationBindingCaptureError, match="authorization_mode_conflict"):
        capture.validate_capture_authorization(
            authorization_id="LC-location-binding-777",
            network_policy="live",
            standing_public_read_only=True,
        )


def test_standing_mode_is_live_only_and_runtime_gates_remain_closed() -> None:
    with pytest.raises(
        capture.LocationBindingCaptureError,
        match="standing_public_read_only_live_only",
    ):
        capture.validate_capture_authorization(
            authorization_id=None,
            network_policy="local_only",
            standing_public_read_only=True,
        )

    with pytest.raises(
        capture.LocationBindingCaptureError,
        match="live_runtime_overrides_forbidden",
    ):
        capture.validate_capture_authorization(
            authorization_id=None,
            network_policy="live",
            active_ids=set(),
            standing_public_read_only=True,
        )


def test_invalid_live_target_is_rejected_before_standing_mode_can_start_browser() -> None:
    result = capture.run_capture(
        authorization_id=None,
        standing_public_read_only=True,
        target_url="https://example.com/",
    )
    assert result.stop_reason == "live_target_not_exact_la_colonia_home"
    assert result.browser_started is False
    assert result.target_navigation_started is False
    assert result.production_authority is False
    assert result.catalog_accepted is False
    assert result.extraction_enabled is False
