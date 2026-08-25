from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "probar_muestra_sps_la_colonia_intelligent_v1.py"
SPEC = importlib.util.spec_from_file_location("probar_muestra_sps_la_colonia_intelligent_v1_context", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class RawPostRequest:
    def __init__(self, raw: str):
        self.url = "https://www.lacolonia.com/_v/segment/graphql/v1"
        self.headers = {}
        self.post_data = raw

    @property
    def post_data_json(self):
        raise ValueError("playwright did not expose parsed body")


def test_raw_post_data_json_fallback_captures_canonical_region_and_channel() -> None:
    region = "opaque-sps-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )
    tracker.reset_and_enable()
    tracker.observe_request(
        RawPostRequest(
            json.dumps(
                {
                    "variables": json.dumps(
                        {"regionId": region, "segment": {"channel": "1"}}
                    )
                }
            )
        )
    )

    assert tracker.explicit_context() == (region, "1")
    assert tracker.region_observed_after_activation is True


def test_form_encoded_variables_string_is_decoded_without_persisting_context() -> None:
    region = "opaque-sps-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )
    tracker.reset_and_enable()
    raw = "variables=" + json.dumps({"regionId": region, "salesChannel": "2"})
    tracker.observe_request(RawPostRequest(raw))

    assert tracker.explicit_context() == (region, "2")
    assert region not in repr(tracker)


def test_canonical_region_seen_before_activation_survives_same_browser_context_reset() -> None:
    region = "opaque-sps-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )
    request = SimpleNamespace(
        url=f"https://www.lacolonia.com/?regionId={region}&sc=1",
        headers={},
        post_data_json=None,
        post_data=None,
    )
    tracker.observe_request(request)
    assert tracker.fingerprint_verified is True
    assert tracker.region_observed_after_activation is False

    tracker.reset_and_enable()

    assert tracker.explicit_context() == (region, "1")
    assert tracker.region_observed_after_activation is False


def test_passive_json_response_can_supply_context_without_extra_request() -> None:
    region = "opaque-sps-region"
    tracker = module.ExplicitV1ContextTracker(
        expected_fingerprint=module.bound._stable_fingerprint(region)
    )
    tracker.reset_and_enable()
    response = SimpleNamespace(
        url="https://www.lacolonia.com/_v/segment/graphql/v1",
        headers={"content-type": "application/json"},
        json=lambda: {"data": {"segment": {"regionId": region, "channel": "3"}}},
    )

    tracker.observe_response(response)

    assert tracker.explicit_context() == (region, "3")
