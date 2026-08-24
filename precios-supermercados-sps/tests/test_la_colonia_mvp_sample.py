from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from precios_supermercados.scrapers.la_colonia import LaColoniaExtractor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "la_colonia"
SCRIPT = PROJECT_ROOT / "scripts" / "probar_muestra_sps_la_colonia.py"
SPEC = importlib.util.spec_from_file_location("probar_muestra_sps_la_colonia", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

FIXED_TIME = datetime(2026, 8, 24, 23, 0, tzinfo=timezone.utc)


def _result():
    payload = json.loads((FIXTURES / "product_search_page.json").read_text(encoding="utf-8"))
    extractor = LaColoniaExtractor(clock=lambda: FIXED_TIME)
    return extractor.parse_payload(
        payload,
        scrape_run_id="mvp_sample_test",
        source_url=extractor.build_page_url(page_size=5),
        page_size=5,
    )


def _walk_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key).casefold()
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def test_builds_small_sps_sample_from_existing_extractor_contract() -> None:
    artifact = module.build_sample_artifact(
        extraction_result=_result(),
        sample_size=5,
        observed_at_utc=FIXED_TIME,
        location_verified_same_run=True,
    )

    assert artifact["sample_type"] == "la_colonia_sps_mvp_read_only"
    assert artifact["sample_only"] is True
    assert artifact["location_id"] == "la_colonia_sps"
    assert artifact["city"] == "San Pedro Sula"
    assert artifact["location_verified_same_run"] is True
    assert artifact["sample_skus_returned"] == 5
    assert artifact["sample_skus_with_price"] == 3
    assert artifact["validation_passed"] is True
    assert artifact["production_authority"] is False
    assert artifact["catalog_accepted"] is False
    assert artifact["commercial_persistence"] is False
    assert artifact["extraction_enabled"] is False
    assert artifact["raw_context_persisted"] is False

    first = artifact["products"][0]
    assert first["source_name"] == "Malteada Sula Chocosula 473 Ml"
    assert first["brand"] == "Sula"
    assert first["presentation"] == "473 Ml"
    assert first["current_price"] == "19.9"
    assert first["product_id"] == "1001"
    assert first["item_id"] == "2001"


def test_sample_never_relabels_unverified_context_as_sps() -> None:
    with pytest.raises(module.MvpSampleError, match="sps_location_not_verified_same_run"):
        module.build_sample_artifact(
            extraction_result=_result(),
            sample_size=5,
            observed_at_utc=FIXED_TIME,
            location_verified_same_run=False,
        )


def test_sample_artifact_does_not_persist_request_or_session_context() -> None:
    artifact = module.build_sample_artifact(
        extraction_result=_result(),
        sample_size=5,
        observed_at_utc=FIXED_TIME,
        location_verified_same_run=True,
    )
    keys = set(_walk_keys(artifact))

    assert "source_url" not in keys
    assert "request_url" not in keys
    assert "regionid" not in keys
    assert "headers" not in keys
    assert "cookies" not in keys
    assert "token" not in keys
    assert "vtex_session" not in keys
    assert "raw_values" not in keys


def test_live_fuse_is_required_before_browser_path(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "_run_live_sample",
        lambda **_: (_ for _ in ()).throw(AssertionError("browser path must not run")),
    )

    with pytest.raises(SystemExit) as captured:
        module.main(["--sample-size", "5"])
    assert captured.value.code == 2
