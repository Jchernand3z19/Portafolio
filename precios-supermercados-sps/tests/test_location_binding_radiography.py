from __future__ import annotations

import json

import pytest

from precios_supermercados.location_binding_radiography import (
    BindingConfidence,
    BindingGranularity,
    ContextStage,
    LocationBindingRadiographyError,
    analyze_location_binding,
    contains_raw_value,
    report_dict,
)


def stage(name: str, **channels) -> ContextStage:
    return ContextStage(name=name, channels=channels)


def test_city_binding_is_strong_when_region_changes_after_city_without_store() -> None:
    before = stage("before", localStorage={"regionId": "region-before"})
    after_city = stage("after_city", localStorage={"regionId": "region-sps"})

    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=before,
        after_city=after_city,
        store_selection_observed=False,
    )

    assert report.granularity_candidate is BindingGranularity.CITY
    assert report.confidence is BindingConfidence.STRONG
    assert report.technical_binding_observed is True
    assert report.decisive_stage == "after_city"
    assert report.source_location_key_candidate.startswith(
        "localStorage:regionid:sha256:"
    )
    assert contains_raw_value(report, ("region-before", "region-sps")) is False


def test_store_binding_wins_when_strong_context_changes_after_store() -> None:
    before = stage(
        "before",
        localStorage={"regionId": "region-before"},
        request_variable={"store": "none"},
    )
    after_city = stage(
        "after_city",
        localStorage={"regionId": "region-sps"},
        request_variable={"store": "none"},
    )
    after_store = stage(
        "after_store",
        localStorage={"regionId": "region-sps"},
        request_variable={"store": "store-pedregal"},
    )

    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=before,
        after_city=after_city,
        store_selection_observed=True,
        after_store=after_store,
        store_name="Plaza Pedregal",
    )

    assert report.granularity_candidate is BindingGranularity.STORE
    assert report.confidence is BindingConfidence.STRONG
    assert report.decisive_stage == "after_store"
    assert report.source_location_key_candidate.startswith(
        "request_variable:store:sha256:"
    )
    assert contains_raw_value(
        report,
        ("region-before", "region-sps", "store-pedregal"),
    ) is False


def test_city_remains_candidate_when_store_selection_does_not_change_context() -> None:
    before = stage("before", cookie={"salesChannel": "1"})
    after_city = stage("after_city", cookie={"salesChannel": "2"})
    after_store = stage("after_store", cookie={"salesChannel": "2"})

    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=before,
        after_city=after_city,
        store_selection_observed=True,
        after_store=after_store,
        store_name="Plaza Pedregal",
    )

    assert report.granularity_candidate is BindingGranularity.CITY
    assert report.confidence is BindingConfidence.STRONG
    assert report.decisive_stage == "after_city"


def test_weak_session_change_after_store_prevents_city_confirmation() -> None:
    before = stage(
        "before",
        localStorage={"regionId": "region-before"},
        cookie={"vtex_session": "session-before"},
    )
    after_city = stage(
        "after_city",
        localStorage={"regionId": "region-sps"},
        cookie={"vtex_session": "session-city"},
    )
    after_store = stage(
        "after_store",
        localStorage={"regionId": "region-sps"},
        cookie={"vtex_session": "session-store"},
    )

    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=before,
        after_city=after_city,
        store_selection_observed=True,
        after_store=after_store,
        store_name="Plaza Pedregal",
    )

    assert report.granularity_candidate is BindingGranularity.UNKNOWN
    assert report.confidence is BindingConfidence.WEAK
    assert report.technical_binding_observed is False
    assert report.source_location_key_candidate is None
    assert report.decisive_stage == "after_store"


def test_generic_vtex_session_change_is_weak_and_does_not_confirm_granularity() -> None:
    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=stage("before", cookie={"vtex_session": "session-a"}),
        after_city=stage("after_city", cookie={"vtex_session": "session-b"}),
        store_selection_observed=False,
    )

    assert report.granularity_candidate is BindingGranularity.UNKNOWN
    assert report.confidence is BindingConfidence.WEAK
    assert report.technical_binding_observed is False
    assert report.source_location_key_candidate is None
    assert report.decisive_stage == "after_city"


def test_unrelated_analytics_or_ui_keys_are_ignored() -> None:
    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=stage("before", cookie={"analytics_id": "a"}, localStorage={"theme": "light"}),
        after_city=stage("after_city", cookie={"analytics_id": "b"}, localStorage={"theme": "dark"}),
        store_selection_observed=False,
    )

    assert report.granularity_candidate is BindingGranularity.UNKNOWN
    assert report.confidence is BindingConfidence.NONE
    assert report.signals == ()


def test_request_header_can_be_decisive_binding_mechanism() -> None:
    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=stage("before", request_header={"binding": "binding-a"}),
        after_city=stage("after_city", request_header={"binding": "binding-b"}),
        store_selection_observed=False,
    )

    assert report.granularity_candidate is BindingGranularity.CITY
    assert report.source_location_key_candidate.startswith(
        "request_header:binding:sha256:"
    )


def test_context_keys_are_case_insensitive_between_stages() -> None:
    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=stage("before", localStorage={"RegionID": "a"}),
        after_city=stage("after_city", localStorage={"regionId": "b"}),
        store_selection_observed=False,
    )

    assert report.granularity_candidate is BindingGranularity.CITY
    assert len(report.signals) == 1
    assert report.signals[0].key == "regionid"


def test_report_envelope_contains_only_fingerprints_not_raw_context_values() -> None:
    secrets = (
        "opaque-region-sps-123",
        "opaque-store-456",
        "opaque-session-789",
    )
    report = analyze_location_binding(
        city_name="San Pedro Sula",
        before=stage(
            "before",
            localStorage={"regionId": "before"},
            cookie={"vtex_session": "before-session"},
        ),
        after_city=stage(
            "after_city",
            localStorage={"regionId": secrets[0]},
            cookie={"vtex_session": secrets[2]},
        ),
        store_selection_observed=True,
        after_store=stage(
            "after_store",
            localStorage={"regionId": secrets[0]},
            request_variable={"storeId": secrets[1]},
            cookie={"vtex_session": secrets[2]},
        ),
        store_name="Plaza Pedregal",
    )

    rendered = json.dumps(report_dict(report), ensure_ascii=False, sort_keys=True)
    assert all(secret not in rendered for secret in secrets)
    assert report_dict(report)["raw_values_exposed"] is False
    assert "sha256:" in rendered


def test_same_evidence_produces_deterministic_source_location_key_candidate() -> None:
    arguments = dict(
        city_name="San Pedro Sula",
        before=stage("before", localStorage={"regionId": "a"}),
        after_city=stage("after_city", localStorage={"regionId": "b"}),
        store_selection_observed=False,
    )
    first = analyze_location_binding(**arguments)
    second = analyze_location_binding(**arguments)
    assert first.source_location_key_candidate == second.source_location_key_candidate


def test_store_selector_requires_after_store_snapshot_and_store_name() -> None:
    before = stage("before", localStorage={})
    city = stage("after_city", localStorage={})

    with pytest.raises(LocationBindingRadiographyError, match="after_store_required"):
        analyze_location_binding(
            city_name="San Pedro Sula",
            before=before,
            after_city=city,
            store_selection_observed=True,
            store_name="Plaza Pedregal",
        )
    with pytest.raises(LocationBindingRadiographyError, match="store_name_invalid"):
        analyze_location_binding(
            city_name="San Pedro Sula",
            before=before,
            after_city=city,
            store_selection_observed=True,
            after_store=stage("after_store", localStorage={}),
            store_name=None,
        )


def test_store_evidence_is_rejected_when_store_selector_was_not_observed() -> None:
    with pytest.raises(
        LocationBindingRadiographyError,
        match="store_evidence_without_selector",
    ):
        analyze_location_binding(
            city_name="San Pedro Sula",
            before=stage("before", localStorage={}),
            after_city=stage("after_city", localStorage={}),
            store_selection_observed=False,
            after_store=stage("after_store", localStorage={}),
            store_name="Plaza Pedregal",
        )


def test_context_stage_rejects_invalid_channel_shape() -> None:
    with pytest.raises(LocationBindingRadiographyError, match="channel_values_invalid"):
        ContextStage(name="before", channels={"cookie": ["not", "mapping"]})


def test_context_stage_rejects_non_json_context_values() -> None:
    report_before = ContextStage(name="before", channels={"cookie": {"regionId": object()}})
    report_after = ContextStage(name="after", channels={"cookie": {"regionId": "b"}})
    with pytest.raises(
        LocationBindingRadiographyError,
        match="context_value_not_serializable",
    ):
        analyze_location_binding(
            city_name="San Pedro Sula",
            before=report_before,
            after_city=report_after,
            store_selection_observed=False,
        )
