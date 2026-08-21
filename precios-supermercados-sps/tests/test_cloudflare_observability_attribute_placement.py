from __future__ import annotations

from copy import deepcopy

import pytest

from precios_supermercados.cloudflare_observability_adapter import (
    CloudflareObservabilityAdapterError,
    parse_cloudflare_trace_detail_response,
    parse_cloudflare_trace_discovery_response,
)
from precios_supermercados.cloudflare_trace_evidence import ORIGIN_EXECUTION_SPAN_NAME

SERVICE = "precios-sps-provenance"
TRACE = "trace-placement-001"
CUSTOM = "span-custom-placement-001"
INVOCATION = "invocation-placement-001"
VERSION = "version-placement-001"
AUTH = "authorization-placement-001"
RUN = "32518905738:1"
START = 1_787_340_500_000


def _standard() -> dict[str, object]:
    return {
        "cloud.provider": "cloudflare",
        "cloud.platform": "cloudflare.workers",
        "faas.invocation_id": INVOCATION,
        "service.name": SERVICE,
        "cloudflare.script_version.id": VERSION,
    }


def _custom_attributes() -> dict[str, object]:
    return {
        "precios.trace_contract_version": "1",
        "precios.collector_provider": "cloudflare_workers",
        "precios.authorization_id": AUTH,
        "precios.run_id": RUN,
        "precios.approved_commit_sha": "a" * 40,
        "precios.reservation_id": "reservation-placement-001",
        "precios.request_id": "request-placement-001",
        "precios.request_digest": "b" * 64,
        "precios.traversal_role": "primary",
        "precios.traversal_id": "traversal-placement-001",
        "precios.partition_id": "root",
    }


def _workers() -> dict[str, object]:
    return {
        "scriptName": SERVICE,
        "scriptVersion": {"id": VERSION},
        "truncated": False,
    }


def _custom_top_level() -> dict[str, object]:
    event: dict[str, object] = {
        "$metadata": {
            "service": SERVICE,
            "traceId": TRACE,
            "spanId": CUSTOM,
            "spanName": ORIGIN_EXECUTION_SPAN_NAME,
            "startTime": START,
            "endTime": START + 800,
        },
        "$workers": _workers(),
        "dataset": "cloudflare-workers",
        "source": {},
        "timestamp": START,
    }
    event.update(_standard())
    event.update(_custom_attributes())
    return event


def _fetch_top_level() -> dict[str, object]:
    event: dict[str, object] = {
        "$metadata": {
            "service": SERVICE,
            "traceId": TRACE,
            "spanId": "span-fetch-placement-001",
            "parentSpanId": CUSTOM,
            "spanName": "fetch",
            "startTime": START + 100,
            "endTime": START + 700,
        },
        "$workers": _workers(),
        "dataset": "cloudflare-workers",
        "source": {},
        "timestamp": START + 100,
        "url.full": "https://www.lacolonia.com/_v/segment/graphql/v1?workspace=master",
        "http.request.method": "GET",
        "http.response.status_code": 200,
        "http.response.body.size": 321,
    }
    event.update(_standard())
    return event


def _response(events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "success": True,
        "errors": [],
        "result": {"events": {"events": events, "count": len(events)}},
    }


def test_custom_y_fetch_con_atributos_top_level_son_aceptados() -> None:
    discovery = parse_cloudflare_trace_discovery_response(
        _response([_custom_top_level()]),
        authorization_id=AUTH,
        run_id=RUN,
    )
    assert discovery == (TRACE,)

    evidence = parse_cloudflare_trace_detail_response(
        _response([_custom_top_level(), _fetch_top_level()]),
        expected_trace_id=TRACE,
    )
    assert len(evidence) == 1
    assert evidence[0].authorization_id == AUTH
    assert evidence[0].fetch_response_body_size == 321


def test_mismo_atributo_en_source_y_top_level_con_mismo_valor_es_aceptado() -> None:
    custom = _custom_top_level()
    custom["source"] = {
        "service.name": SERVICE,
        "precios.authorization_id": AUTH,
    }
    result = parse_cloudflare_trace_discovery_response(
        _response([custom]),
        authorization_id=AUTH,
        run_id=RUN,
    )
    assert result == (TRACE,)


def test_conflicto_custom_entre_source_y_top_level_falla_cerrado() -> None:
    custom = _custom_top_level()
    custom["source"] = {"precios.authorization_id": "authorization-conflict"}
    with pytest.raises(CloudflareObservabilityAdapterError) as captured:
        parse_cloudflare_trace_discovery_response(
            _response([custom]),
            authorization_id=AUTH,
            run_id=RUN,
        )
    assert captured.value.code == "event_attribute_conflict:precios.authorization_id"


def test_conflicto_fetch_url_entre_source_y_top_level_falla_cerrado() -> None:
    custom = _custom_top_level()
    fetch = _fetch_top_level()
    fetch["source"] = {"url.full": "https://www.lacolonia.com/otra-ruta"}
    before = deepcopy(fetch)
    with pytest.raises(CloudflareObservabilityAdapterError) as captured:
        parse_cloudflare_trace_detail_response(
            _response([custom, fetch]),
            expected_trace_id=TRACE,
        )
    assert captured.value.code == "event_attribute_conflict:url.full"
    assert fetch == before
