from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from precios_supermercados.scrapers.la_colonia_window_diagnostic import (
    WindowSpec,
    build_window_url,
    diagnose_windows,
    observe_window_payload,
    serialize_sanitized_report,
    validate_sanitized_summary,
)


def product(index: int, *, key: str | None = None, items: int = 1):
    return {
        "productId": key or f"P{index:04d}",
        "productName": f"Synthetic {index}",
        "items": [{"itemId": f"S{index}-{item}"} for item in range(items)],
    }


def payload(start: int, count: int, total: int, *, keys=None):
    values = (
        [product(start + offset, key=key) for offset, key in enumerate(keys)]
        if keys is not None
        else [product(index) for index in range(start, start + count)]
    )
    return {"data": {"productSearch": {"recordsFiltered": total, "products": values}}}


def observation(name: str, start: int, end: int, keys, *, total: int = 9291):
    spec = WindowSpec(name, start, end)
    return observe_window_payload(spec, payload(start, len(keys), total, keys=keys))


def test_inclusive_window_is_valid_and_width_is_twenty():
    spec = WindowSpec("C", 380, 399)
    assert spec.width == 20
    variables = json.loads(parse_qs(urlsplit(build_window_url(spec)).query)["variables"][0])
    assert variables["from"] == 380
    assert variables["to"] == 399


def test_negative_from_is_rejected():
    with pytest.raises(ValueError, match="negativo"):
        WindowSpec("bad", -1, 10)


def test_to_lower_than_from_is_rejected():
    with pytest.raises(ValueError, match="mayor o igual"):
        WindowSpec("bad", 10, 9)


def test_window_above_fifty_is_rejected():
    with pytest.raises(ValueError, match="50"):
        WindowSpec("bad", 0, 50)


def test_disallowed_order_is_rejected():
    with pytest.raises(ValueError, match="no permitido"):
        WindowSpec("bad", 0, 19, "OrderByUnknown")


def test_complete_overlapping_windows_match_expected_overlap():
    a = observation("A", 360, 379, [f"P{i}" for i in range(360, 380)])
    b = observation("B", 370, 389, [f"P{i}" for i in range(370, 390)])
    report = diagnose_windows([a, b])
    assert report.overlaps[0].expected == 10
    assert report.overlaps[0].observed == 10
    assert report.products_unique_in_union == 30
    assert "quality:unexpected_overlap" not in report.quality_events


def test_window_with_nineteen_elements_is_reported_partial():
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 399)])
    assert c.products_returned == 19
    assert "quality:partial_window" in c.quality_events


def test_counted_but_not_materialized_scenario_is_distinguishable():
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 399)], total=9291)
    summary = diagnose_windows([c]).sanitized_summary()
    assert summary["windows"][0]["records_filtered"] == 9291
    assert summary["windows"][0]["products_returned"] == 19


def test_post_window_filtering_scenario_creates_union_deficit():
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 399)])
    d_keys = [f"P{i}" for i in range(390, 399)] + [f"P{i}" for i in range(400, 410)]
    d = observation("D", 390, 409, d_keys)
    report = diagnose_windows([c, d])
    assert report.expected_unique_positions == 30
    assert report.products_unique_in_union == 29
    assert report.union_delta == -1
    assert "quality:union_unique_below_expected" in report.quality_events


def test_non_unique_order_movement_changes_observed_overlap():
    a = observation("A", 360, 379, [f"P{i}" for i in range(360, 380)])
    b_keys = [f"P{i}" for i in range(371, 391)]
    b = observation("B", 370, 389, b_keys)
    report = diagnose_windows([a, b])
    assert report.overlaps[0].expected == 10
    assert report.overlaps[0].observed == 9
    assert "quality:unexpected_overlap" in report.quality_events


def test_unexpected_overlap_between_non_overlapping_windows_is_recorded():
    a = observation("A", 360, 379, [f"P{i}" for i in range(360, 380)])
    e_keys = ["P379"] + [f"P{i}" for i in range(401, 420)]
    e = observation("E", 400, 419, e_keys)
    report = diagnose_windows([a, e])
    assert report.overlaps[0].expected == 0
    assert report.overlaps[0].observed == 1


def test_missing_element_in_union_is_detected():
    f = observation("F", 380, 389, [f"P{i}" for i in range(380, 390)])
    g = observation("G", 390, 399, [f"P{i}" for i in range(390, 399)])
    report = diagnose_windows([f, g])
    assert report.expected_unique_positions == 20
    assert report.products_unique_in_union == 19


def test_duplicate_inside_window_is_detected():
    keys = [f"P{i}" for i in range(380, 399)] + ["P398"]
    c = observation("C", 380, 399, keys)
    report = diagnose_windows([c])
    assert report.duplicates_within_windows == 1
    assert "quality:duplicate_product_within_window" in report.quality_events


def test_stable_total_has_no_total_change_event():
    a = observation("A", 360, 379, [f"P{i}" for i in range(360, 380)], total=9291)
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 400)], total=9291)
    report = diagnose_windows([a, c])
    assert report.total_initial == report.total_final == 9291
    assert "quality:catalog_total_changed" not in report.quality_events


def test_changing_total_is_recorded():
    a = observation("A", 360, 379, [f"P{i}" for i in range(360, 380)], total=9291)
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 400)], total=9292)
    report = diagnose_windows([a, c])
    assert report.total_initial == 9291
    assert report.total_final == 9292
    assert "quality:catalog_total_changed" in report.quality_events


def test_summary_contains_only_sanitized_aggregate_fields():
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 400)])
    summary = diagnose_windows([c]).sanitized_summary()
    rendered = json.dumps(summary)
    for forbidden in ("productId", "itemId", "productName", "source_key"):
        assert forbidden not in rendered


def test_direct_identifier_field_is_rejected_by_sanitizer():
    with pytest.raises(ValueError, match="no permitido"):
        validate_sanitized_summary({"productId": "P1"})


def test_individual_hash_field_is_rejected_by_sanitizer():
    with pytest.raises(ValueError, match="no permitido"):
        validate_sanitized_summary({"source_key_hash": "abc"})


def test_artifact_size_is_limited():
    windows = [
        observation(
            chr(65 + offset),
            offset * 10,
            offset * 10 + 19,
            [f"P{i}" for i in range(offset * 10, offset * 10 + 20)],
        )
        for offset in range(8)
    ]
    report = diagnose_windows(windows)
    encoded = serialize_sanitized_report(report, max_bytes=64 * 1024)
    assert len(encoded) < 64 * 1024
    with pytest.raises(ValueError, match="supera"):
        serialize_sanitized_report(report, max_bytes=10)


def test_normal_runner_module_is_not_imported_or_modified():
    import precios_supermercados.scrapers.la_colonia_window_diagnostic as module

    assert not hasattr(module, "LaColoniaCatalogRunner")


def test_partial_page_policy_is_not_reinterpreted_as_accepted():
    c = observation("C", 380, 399, [f"P{i}" for i in range(380, 399)])
    summary = diagnose_windows([c]).sanitized_summary()
    assert "accepted" not in summary
    assert "quality:partial_window" in summary["windows"][0]["quality_events"]


def test_synthetic_baseline_of_two_hundred_is_complete():
    windows = []
    for page in range(10):
        start = page * 20
        windows.append(
            observation(
                f"P{page + 1}",
                start,
                start + 19,
                [f"P{i}" for i in range(start, start + 20)],
                total=9291,
            )
        )
    report = diagnose_windows(windows)
    assert all(item.products_returned == 20 for item in report.observations)
    assert report.products_unique_in_union == 200
    assert report.union_delta == 0
