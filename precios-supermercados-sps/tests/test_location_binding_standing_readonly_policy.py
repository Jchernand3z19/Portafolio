from __future__ import annotations

import pytest

import precios_supermercados.diagnostics.la_colonia_location_binding_capture as capture


def test_standing_public_read_only_is_explicitly_disabled() -> None:
    assert capture.STANDING_PUBLIC_READ_ONLY_AUTHORIZED is False
    assert capture.STANDING_PUBLIC_READ_ONLY_AUTHORIZED_AT == "2026-08-23T21:02:02Z"
    with pytest.raises(
        capture.LocationBindingCaptureError,
        match="standing_public_read_only_not_authorized",
    ):
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


def test_standing_mode_is_live_only_and_runtime_overrides_remain_forbidden() -> None:
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


def test_standing_capture_stops_before_browser_even_for_exact_live_target(tmp_path) -> None:
    output = tmp_path / "standing-closed.json"
    result = capture.run_capture(
        authorization_id=None,
        standing_public_read_only=True,
        output_path=output,
    )

    assert result.stop_reason == "standing_public_read_only_not_authorized"
    assert result.browser_started is False
    assert result.target_navigation_started is False
    assert result.production_authority is False
    assert result.catalog_accepted is False
    assert result.extraction_enabled is False
    rendered = output.read_text(encoding="utf-8")
    assert '"browser_started": false' in rendered
    assert '"production_authority": false' in rendered
