from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import FrozenInstanceError
from urllib.parse import parse_qs, urlsplit

import pytest

import precios_supermercados.scrapers.base as base_module
import precios_supermercados.scrapers.la_colonia_window_diagnostic_runtime as runtime_module
from precios_supermercados.scrapers.base import HttpResponse, HttpStatusError, SafeHttpClient
from precios_supermercados.scrapers.la_colonia import FORBIDDEN_PATH_PREFIXES, USER_AGENT
from precios_supermercados.scrapers.la_colonia_graphql import PRODUCT_SEARCH_QUERY
from precios_supermercados.scrapers.la_colonia_window_diagnostic import (
    WindowSpec,
    build_window_url,
    diagnose_windows,
    observe_window_payload,
)
from precios_supermercados.scrapers.la_colonia_window_diagnostic_runtime import (
    EXIT_ANOMALY,
    FRONTIER_380_399_V1,
    LaColoniaWindowDiagnosticRuntime,
)

EXPECTED_PHASE_ONE = [
    ("A", 360, 379, "OrderByNameASC"),
    ("B", 370, 389, "OrderByNameASC"),
    ("C", 380, 399, "OrderByNameASC"),
    ("D", 390, 409, "OrderByNameASC"),
    ("E", 400, 419, "OrderByNameASC"),
    ("F", 380, 389, "OrderByNameASC"),
    ("G", 390, 399, "OrderByNameASC"),
    ("H", 350, 399, "OrderByNameASC"),
]


class StepClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 0.01
        return self.value


def _decode_url(url: str) -> tuple[dict[str, list[str]], dict[str, object]]:
    params = parse_qs(urlsplit(url).query)
    variables = json.loads(params["variables"][0])
    return params, variables


def _request_fingerprint(url: str) -> str:
    _, variables = _decode_url(url)
    safe = {
        key: variables[key]
        for key in (
            "from",
            "to",
            "orderBy",
            "hideUnavailableItems",
            "skusFilter",
        )
    }
    return hashlib.sha256(
        json.dumps(safe, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _product(key: str) -> dict[str, object]:
    return {
        "productId": key,
        "productName": f"Synthetic {key}",
        "items": [{"itemId": f"SKU-{key}"}],
    }


def _payload(keys: list[str], *, total: int = 9291) -> dict[str, object]:
    return {
        "data": {
            "productSearch": {
                "recordsFiltered": total,
                "products": [_product(key) for key in keys],
            }
        }
    }


class RecordingTransport:
    def __init__(self, planner) -> None:
        self.planner = planner
        self.calls: list[dict[str, object]] = []

    def __call__(self, url, headers, timeout):
        params, variables = _decode_url(url)
        call = {
            "url": url,
            "params": params,
            "variables": variables,
            "headers": dict(headers),
            "timeout": timeout,
        }
        self.calls.append(call)
        status, body = self.planner(variables, len(self.calls))
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        return HttpResponse(status, url, {}, encoded)


def _complete_planner(variables, call_number):
    start = int(variables["from"])
    end = int(variables["to"])
    return 200, _payload([f"P{index}" for index in range(start, end + 1)])


def _runtime(planner=_complete_planner, *, sleeper=None):
    transport = RecordingTransport(planner)
    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=FORBIDDEN_PATH_PREFIXES,
        user_agent=USER_AGENT,
        max_retries=0,
        retry_delay_seconds=0,
        transport=transport,
        sleeper=lambda _: None,
    )
    sleeps = [] if sleeper is None else sleeper
    runtime = LaColoniaWindowDiagnosticRuntime(
        client,
        sleeper=sleeps.append,
        monotonic=StepClock(),
    )
    return runtime, transport, sleeps


def _synthetic_live_keys() -> dict[str, list[str]]:
    h = [f"H{index:02d}" for index in range(50)]
    outside = [f"X{index:02d}" for index in range(20)]
    return {
        "A": h[30:50],
        "B": h[0:20],
        "C": h[0:20],
        "D": outside,
        "E": outside,
        "F": h[0:10],
        "G": h[10:20],
        "H": h,
    }


def _name_for_variables(variables: dict[str, object]) -> str:
    by_range = {
        (start, end): name
        for name, start, end, order_by in EXPECTED_PHASE_ONE
        if order_by == variables["orderBy"]
    }
    return by_range[(int(variables["from"]), int(variables["to"]))]


def test_phase_one_builds_exact_distinct_urls_and_variables_offline():
    runtime, transport, sleeps = _runtime()
    result = runtime.run(request_id="request-audit-001")

    assert result.summary["phase_two_started"] is False
    assert len(transport.calls) == 8
    assert sleeps == [1.5] * 7

    expected_urls = [build_window_url(window) for window in FRONTIER_380_399_V1.phase_one]
    actual_urls = [str(call["url"]) for call in transport.calls]
    assert actual_urls == expected_urls
    assert len(set(actual_urls)) == 8

    for call, expected in zip(transport.calls, EXPECTED_PHASE_ONE, strict=True):
        name, start, end, order_by = expected
        params = call["params"]
        variables = call["variables"]
        assert variables == {
            "query": "supermercado",
            "fullText": "",
            "selectedFacets": [{"key": "category-1", "value": "supermercado"}],
            "orderBy": order_by,
            "from": start,
            "to": end,
            "hideUnavailableItems": False,
            "skusFilter": "ALL",
        }, name
        assert params["workspace"] == ["master"]
        assert params["locale"] == ["es-HN"]
        assert params["operationName"] == ["productSearchV3"]
        assert params["query"] == [PRODUCT_SEARCH_QUERY]


def test_b_c_and_d_e_have_different_urls_variables_and_safe_fingerprints():
    urls = {window.name: build_window_url(window) for window in FRONTIER_380_399_V1.phase_one}
    decoded = {name: _decode_url(url)[1] for name, url in urls.items()}
    fingerprints = {name: _request_fingerprint(url) for name, url in urls.items()}

    assert urls["B"] != urls["C"]
    assert decoded["B"] != decoded["C"]
    assert urls["D"] != urls["E"]
    assert decoded["D"] != decoded["E"]
    assert fingerprints["B"] != fingerprints["C"]
    assert fingerprints["D"] != fingerprints["E"]
    assert len(set(fingerprints.values())) == 8


def test_window_specs_are_immutable_and_url_building_does_not_mutate_plan():
    before = tuple(
        (item.name, item.from_index, item.to_index, item.order_by)
        for item in FRONTIER_380_399_V1.phase_one
    )
    for window in FRONTIER_380_399_V1.phase_one:
        build_window_url(window)
    after = tuple(
        (item.name, item.from_index, item.to_index, item.order_by)
        for item in FRONTIER_380_399_V1.phase_one
    )
    assert before == after == tuple(EXPECTED_PHASE_ONE)
    with pytest.raises(FrozenInstanceError):
        FRONTIER_380_399_V1.phase_one[0].from_index = 0


def test_transport_receives_each_constructed_url_once_in_a_to_h_order():
    runtime, transport, _ = _runtime()
    runtime.run(request_id="request-audit-002")
    expected_urls = [build_window_url(window) for window in FRONTIER_380_399_V1.phase_one]
    actual_urls = [str(call["url"]) for call in transport.calls]
    assert actual_urls == expected_urls
    assert Counter(actual_urls) == Counter({url: 1 for url in expected_urls})
    assert [
        _name_for_variables(call["variables"]) for call in transport.calls
    ] == list("ABCDEFGH")


def test_safe_http_client_has_no_response_cache_and_does_not_reuse_previous_body():
    url = build_window_url(FRONTIER_380_399_V1.phase_one[0])
    bodies = [b'{"sequence":1}', b'{"sequence":2}']
    calls = []

    def transport(request_url, headers, timeout):
        calls.append(request_url)
        return HttpResponse(200, request_url, {}, bodies[len(calls) - 1])

    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=FORBIDDEN_PATH_PREFIXES,
        user_agent=USER_AGENT,
        max_retries=0,
        transport=transport,
        sleeper=lambda _: None,
    )
    first = client.get(url)
    second = client.get(url)
    assert calls == [url, url]
    assert first.body == bodies[0]
    assert second.body == bodies[1]
    assert first.body != second.body
    assert not hasattr(client, "cache")


def test_max_retries_zero_prevents_hidden_transport_calls():
    url = build_window_url(FRONTIER_380_399_V1.phase_one[0])
    calls = []

    def transport(request_url, headers, timeout):
        calls.append(request_url)
        return HttpResponse(503, request_url, {}, b"error")

    client = SafeHttpClient(
        allowed_hosts={"www.lacolonia.com"},
        forbidden_path_prefixes=FORBIDDEN_PATH_PREFIXES,
        user_agent=USER_AGENT,
        max_retries=0,
        transport=transport,
        sleeper=lambda _: None,
    )
    with pytest.raises(HttpStatusError, match="503"):
        client.get(url)
    assert calls == [url]


def test_urllib_transport_sends_the_exact_url_without_local_rewrite(monkeypatch):
    expected_url = build_window_url(FRONTIER_380_399_V1.phase_one[2])
    captured = {}

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def geturl(self):
            return expected_url

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(base_module, "urlopen", fake_urlopen)
    response = SafeHttpClient._urllib_transport(
        expected_url,
        {"User-Agent": USER_AGENT},
        20.0,
    )
    assert captured == {"url": expected_url, "timeout": 20.0}
    assert response.url == expected_url


def test_runtime_uses_each_response_body_for_its_own_window():
    expected_signatures = {}

    def planner(variables, call_number):
        name = _name_for_variables(variables)
        width = int(variables["to"]) - int(variables["from"]) + 1
        keys = [f"CALL-{call_number}-{offset}" for offset in range(width)]
        spec = next(item for item in FRONTIER_380_399_V1.phase_one if item.name == name)
        expected_signatures[name] = observe_window_payload(spec, _payload(keys)).signature
        return 200, _payload(keys)

    runtime, _, _ = _runtime(planner)
    result = runtime.run(request_id="request-audit-003")
    actual = {window["window"]: window["signature"] for window in result.summary["windows"]}
    assert actual == expected_signatures
    assert len(set(actual.values())) == 8


def test_pauses_do_not_modify_urls_or_variables():
    sleeps = []
    runtime, transport, _ = _runtime(sleeper=sleeps)
    before = [build_window_url(window) for window in FRONTIER_380_399_V1.phase_one]
    runtime.run(request_id="request-audit-004")
    after = [str(call["url"]) for call in transport.calls]
    assert after == before
    assert sleeps == [1.5] * 7


def test_synthetic_live_pattern_reproduces_overlap_union_and_runtime_outcome():
    keys_by_name = _synthetic_live_keys()

    def planner(variables, call_number):
        return 200, _payload(keys_by_name[_name_for_variables(variables)])

    runtime, transport, _ = _runtime(planner)
    result = runtime.run(request_id="request-audit-synthetic-001")
    summary = result.summary

    assert result.exit_code == EXIT_ANOMALY
    assert summary["diagnostic_outcome"] == "unexpected_overlap"
    assert summary["phase_two_started"] is False
    assert summary["requests_attempted"] == 8
    assert len(transport.calls) == 8
    assert summary["expected_unique_positions"] == 70
    assert summary["products_unique_in_union"] == 70
    assert summary["union_delta"] == 0
    assert summary["repeated_occurrences"] == 100
    assert summary["duplicates_within_windows"] == 0

    windows = {item["window"]: item for item in summary["windows"]}
    assert windows["B"]["signature"] == windows["C"]["signature"]
    assert windows["D"]["signature"] == windows["E"]["signature"]

    overlaps = {
        (item["left"].split(":")[-1], item["right"].split(":")[-1]): (
            item["expected"], item["observed"]
        )
        for item in summary["overlaps"]
    }
    assert overlaps[("A", "B")] == (10, 0)
    assert overlaps[("B", "C")] == (10, 20)
    assert overlaps[("C", "D")] == (10, 0)
    assert overlaps[("D", "E")] == (10, 20)
    assert ("F", "G") not in overlaps


def test_equal_signatures_follow_equal_private_sequences_not_response_bytes():
    keys = _synthetic_live_keys()
    specs = {item.name: item for item in FRONTIER_380_399_V1.phase_one}
    b = observe_window_payload(specs["B"], _payload(keys["B"]), response_bytes=5000)
    c = observe_window_payload(specs["C"], _payload(keys["C"]), response_bytes=5000)
    changed_c = observe_window_payload(
        specs["C"],
        _payload(keys["C"][:-1] + ["DIFFERENT"]),
        response_bytes=5000,
    )
    d = observe_window_payload(specs["D"], _payload(keys["D"]), response_bytes=4000)
    e = observe_window_payload(specs["E"], _payload(keys["E"]), response_bytes=4000)
    changed_e = observe_window_payload(
        specs["E"],
        _payload(keys["E"][:-1] + ["OTHER"]),
        response_bytes=4000,
    )
    assert b.signature == c.signature
    assert b.signature != changed_c.signature
    assert d.signature == e.signature
    assert d.signature != changed_e.signature
    assert c.response_bytes == changed_c.response_bytes
    assert e.response_bytes == changed_e.response_bytes


def test_equal_response_bytes_do_not_create_overlap_or_identity():
    left = WindowSpec("L", 0, 19)
    right = WindowSpec("R", 20, 39)
    left_observation = observe_window_payload(
        left,
        _payload([f"LEFT-{index}" for index in range(20)]),
        response_bytes=12345,
    )
    right_observation = observe_window_payload(
        right,
        _payload([f"RIGHT-{index}" for index in range(20)]),
        response_bytes=12345,
    )
    report = diagnose_windows([left_observation, right_observation])
    assert left_observation.response_bytes == right_observation.response_bytes
    assert left_observation.signature != right_observation.signature
    assert report.overlaps == ()
    assert report.products_unique_in_union == 40


def test_unexpected_overlap_is_decisive_and_phase_two_is_skipped_by_design():
    keys = _synthetic_live_keys()
    observations = [
        observe_window_payload(window, _payload(keys[window.name]))
        for window in FRONTIER_380_399_V1.phase_one
    ]
    report = diagnose_windows(observations)
    findings = runtime_module._derive_phase_one_findings(report)
    assert "unexpected_overlap" in findings
    assert runtime_module._phase_two_required(report, findings) is False
    assert runtime_module._derive_outcome(report, None, findings) == "unexpected_overlap"


def test_request_fingerprint_contains_only_sanitized_request_controls():
    url = build_window_url(FRONTIER_380_399_V1.phase_one[2])
    fingerprint = _request_fingerprint(url)
    assert len(fingerprint) == 64
    assert "https://" not in fingerprint
    assert "supermercado" not in fingerprint
    assert "product" not in fingerprint.casefold()
