from __future__ import annotations

import json
import socket
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from precios_supermercados.scrapers.la_colonia_facet_discovery import (
    CATALOG_CATEGORIES_V1,
    FACET_DISCOVERY_MAX_ARTIFACT_BYTES,
    analyze_category_facets,
    estimate_facet_discovery_budget,
)
from precios_supermercados.scrapers.la_colonia_facet_discovery_adapter import (
    CATEGORY_TREE_OPERATION,
    CATEGORY_TREE_QUERY,
    FACET_DISCOVERY_ENDPOINT,
    FACET_DISCOVERY_HOST,
    FACET_DISCOVERY_MAX_REQUESTS,
    FACET_DISCOVERY_MAX_RETRIES,
    FACET_DISCOVERY_TIMEOUT_SECONDS,
    ROOT_TOTAL_OPERATION,
    ROOT_TOTAL_QUERY,
    FacetDiscoveryTransportError,
    LaColoniaFacetDiscoveryAdapter,
)
from precios_supermercados.scrapers.la_colonia_facet_discovery_runtime import (
    OUTCOME_OVER_BUDGET,
    OUTCOME_SAMPLING,
    OUTCOME_WITHIN_BUDGET,
    FacetDiscoveryRuntime,
    render_facet_discovery_markdown,
    serialize_facet_discovery_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "precios-supermercados-sps/scripts/descubrir_facets_la_colonia.py"
ADAPTER_SOURCE = REPO_ROOT / "precios-supermercados-sps/src/precios_supermercados/scrapers/la_colonia_facet_discovery_adapter.py"


def facet_command():
    return {
        "request_id": "la-colonia-facet-discovery-001",
        "supermarket": "la_colonia",
        "mode": "facet_discovery",
        "discovery_plan": "catalog_categories_v1",
        "delay_seconds": 1.5,
        "allow_full": False,
    }


def category_tree(quantities=(55, 45), *, sampling=False, missing_children=False):
    values = []
    for index, quantity in enumerate(quantities, start=1):
        node = {
            "key": "category-1",
            "value": f"private-{index}",
            "quantity": quantity,
        }
        if not missing_children:
            node["children"] = []
        values.append(node)
    return {
        "recordsFiltered": sum(quantities),
        "sampling": sampling,
        "facets": [{"type": "CATEGORYTREE", "values": values}],
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class CaptureOpener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        params = parse_qs(urlparse(request.full_url).query)
        operation = params["operationName"][0]
        if operation == ROOT_TOTAL_OPERATION:
            return FakeResponse({"data": {"productSearch": {"recordsFiltered": 100}}})
        return FakeResponse(
            {
                "data": {
                    "productSearch": {"recordsFiltered": 100},
                    "facets": {
                        "sampling": False,
                        "facets": category_tree()["facets"],
                    },
                }
            }
        )


def test_adapter_uses_fixed_https_host_and_endpoint():
    parsed = urlparse(FACET_DISCOVERY_ENDPOINT)
    assert parsed.scheme == "https"
    assert parsed.hostname == FACET_DISCOVERY_HOST == "www.lacolonia.com"
    assert parsed.path == "/_v/segment/graphql/v1"


def test_adapter_exposes_only_two_fixed_operations():
    assert ROOT_TOTAL_OPERATION in ROOT_TOTAL_QUERY
    assert CATEGORY_TREE_OPERATION in CATEGORY_TREE_QUERY
    assert FACET_DISCOVERY_MAX_REQUESTS == 2


def test_root_query_only_requests_total():
    assert "recordsFiltered" in ROOT_TOTAL_QUERY
    for forbidden in ("products {", "productId", "items {", "Price", "brand"):
        assert forbidden not in ROOT_TOTAL_QUERY


def test_category_tree_query_requests_only_facets_and_control_total():
    for required in ("recordsFiltered", "sampling", "facets", "children", "quantity"):
        assert required in CATEGORY_TREE_QUERY
    for forbidden in ("products {", "productId", "itemId", "Price", "brand"):
        assert forbidden not in CATEGORY_TREE_QUERY


def test_adapter_has_zero_retries_fixed_timeout_and_no_cookies_or_tokens():
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    assert FACET_DISCOVERY_MAX_RETRIES == 0
    assert FACET_DISCOVERY_TIMEOUT_SECONDS == 20
    for forbidden in ("Cookie", "Authorization", "X-VTEX-API-AppKey", "X-VTEX-API-AppToken", "secret"):
        assert forbidden not in source


def test_adapter_builds_only_fixed_variables_and_headers():
    opener = CaptureOpener()
    adapter = LaColoniaFacetDiscoveryAdapter(opener=opener)
    adapter(CATALOG_CATEGORIES_V1.requests[0])
    request, timeout = opener.requests[0]
    params = parse_qs(urlparse(request.full_url).query)
    variables = json.loads(params["variables"][0])
    assert params["operationName"] == [ROOT_TOTAL_OPERATION]
    assert variables == {
        "query": "",
        "fullText": "",
        "selectedFacets": [],
        "from": 0,
        "to": 0,
    }
    assert timeout == FACET_DISCOVERY_TIMEOUT_SECONDS
    assert request.get_header("User-agent")
    assert request.get_header("Cookie") is None
    assert request.get_header("Authorization") is None


def test_adapter_rejects_unknown_logical_operation():
    adapter = LaColoniaFacetDiscoveryAdapter(opener=CaptureOpener())
    fake = type(CATALOG_CATEGORIES_V1.requests[0])("unknown", 1, "unknown")
    with pytest.raises(FacetDiscoveryTransportError):
        adapter(fake)


def test_adapter_enforces_maximum_two_requests():
    opener = CaptureOpener()
    adapter = LaColoniaFacetDiscoveryAdapter(opener=opener)
    adapter(CATALOG_CATEGORIES_V1.requests[0])
    adapter(CATALOG_CATEGORIES_V1.requests[1])
    with pytest.raises(FacetDiscoveryTransportError):
        adapter(CATALOG_CATEGORIES_V1.requests[0])
    assert len(opener.requests) == 2


def test_adapter_rejects_nonpositive_root_total():
    def opener(request, timeout):
        return FakeResponse({"data": {"productSearch": {"recordsFiltered": 0}}})

    with pytest.raises(FacetDiscoveryTransportError):
        LaColoniaFacetDiscoveryAdapter(opener=opener)(CATALOG_CATEGORIES_V1.requests[0])


def test_runtime_completes_within_budget_using_fake_transport_only():
    responses = iter(({"recordsFiltered": 100}, category_tree()))
    sleeps = []
    runtime = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=sleeps.append)
    result = runtime.run(facet_command())
    assert result.summary["discovery_outcome"] == OUTCOME_WITHIN_BUDGET
    assert result.summary["requests_completed"] == 2
    assert sleeps == [1.5]


def test_runtime_stops_sampling_without_budget():
    responses = iter(({"recordsFiltered": 100}, category_tree(sampling=True)))
    result = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command())
    assert result.summary["discovery_outcome"] == OUTCOME_SAMPLING
    assert result.summary["discovery_completed"] is False
    assert result.summary["estimated_total_requests"] == 0


def test_runtime_rejects_changing_total():
    responses = iter(({"recordsFiltered": 100}, {**category_tree(), "recordsFiltered": 99}))
    result = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command())
    assert result.summary["stop_reason"] == "catalog_total_changed"
    assert result.summary["discovery_completed"] is False


def test_runtime_rejects_incomplete_tree():
    responses = iter(({"recordsFiltered": 100}, category_tree(missing_children=True)))
    result = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command())
    assert result.summary["discovery_outcome"] == "incomplete_facet_tree"


@pytest.mark.parametrize("quantity", [-1, "invalid"])
def test_runtime_rejects_invalid_quantities(quantity):
    tree = category_tree()
    tree["facets"][0]["values"][0]["quantity"] = quantity
    responses = iter(({"recordsFiltered": 100}, tree))
    result = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command())
    assert result.summary["discovery_completed"] is False


def test_runtime_rejects_more_than_250_leaves():
    tree = category_tree(tuple(1 for _ in range(251)))
    responses = iter(({"recordsFiltered": 251}, tree))
    result = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command())
    assert result.summary["stop_reason"] == "partition_limit_exceeded"


def test_budget_exactly_500_is_allowed():
    tree = category_tree((4100, 4050, 1))
    analysis = analyze_category_facets(tree, root_total=8151)
    budget = estimate_facet_discovery_budget(analysis)
    assert budget.total_estimated_requests == 500
    assert budget.within_request_limit is True


def test_budget_above_500_is_rejected_as_over_budget():
    tree = category_tree((4100, 4050, 100))
    analysis = analyze_category_facets(tree, root_total=8250)
    budget = estimate_facet_discovery_budget(analysis)
    assert budget.total_estimated_requests > 500
    assert budget.within_request_limit is False
    responses = iter(({"recordsFiltered": 8250}, tree))
    result = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command())
    assert result.summary["discovery_outcome"] == OUTCOME_OVER_BUDGET
    assert result.summary["discovery_completed"] is True


def test_runtime_has_concurrency_one_and_zero_retries():
    runtime = FacetDiscoveryRuntime(lambda request: {}, max_retries=0, max_requests=2)
    assert runtime.concurrency == 1
    assert runtime.max_retries == 0
    with pytest.raises(ValueError):
        FacetDiscoveryRuntime(lambda request: {}, max_retries=1)


def test_sanitized_artifacts_are_below_64_kib_and_hide_private_values():
    responses = iter(({"recordsFiltered": 100}, category_tree()))
    summary = FacetDiscoveryRuntime(lambda request: next(responses), sleeper=lambda value: None).run(facet_command()).summary
    json_bytes = serialize_facet_discovery_summary(summary)
    markdown = render_facet_discovery_markdown(summary).encode("utf-8")
    assert len(json_bytes) < FACET_DISCOVERY_MAX_ARTIFACT_BYTES
    assert len(markdown) < FACET_DISCOVERY_MAX_ARTIFACT_BYTES
    assert len(json_bytes) + len(markdown) < FACET_DISCOVERY_MAX_ARTIFACT_BYTES
    combined = json_bytes + markdown
    for forbidden in (b"private-1", b"private-2", b"productId", b"SKU", b"price"):
        assert forbidden not in combined


def test_cli_declares_two_artifacts_and_explicit_exit_codes():
    text = CLI.read_text(encoding="utf-8")
    assert 'Path("facet-discovery-summary.json")' in text
    assert 'Path("facet-discovery-summary.md")' in text
    for code in (
        "EXIT_WITHIN_BUDGET = 0",
        "EXIT_OVER_BUDGET = 2",
        "EXIT_SAMPLING = 3",
        "EXIT_INCOMPLETE = 4",
        "EXIT_INVALID = 5",
        "EXIT_SECURITY = 6",
    ):
        assert code in text


def test_no_real_internet_is_needed_by_tests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("internet real prohibido")

    monkeypatch.setattr(socket, "create_connection", blocked)
    opener = CaptureOpener()
    adapter = LaColoniaFacetDiscoveryAdapter(opener=opener)
    assert adapter(CATALOG_CATEGORIES_V1.requests[0]) == {"recordsFiltered": 100}
    assert adapter(CATALOG_CATEGORIES_V1.requests[1])["sampling"] is False
