from __future__ import annotations

from datetime import timezone
from typing import Any

import pytest

from precios_supermercados.cloudflare_observability_verifier import (
    CloudflareObservabilityVerifierClient,
)
from precios_supermercados.cloudflare_trace_evidence import ORIGIN_EXECUTION_SPAN_NAME
from precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer import (
    PhysicallyReconciledCatalogCollection,
    VerifiedCatalogPhysicalFinalizationError,
    VerifiedCatalogPhysicalFinalizer,
)
from test_la_colonia_verified_catalog_transport import _collector

ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
TOKEN = "cloudflare-catalog-finalizer-token-test"
SERVICE = "precios-sps-provenance"


def _response(events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "success": True,
        "errors": [],
        "result": {"events": {"events": events, "count": len(events)}},
    }


def _base_event(
    page,
    *,
    trace_id: str,
    span_id: str,
    span_name: str,
    start_ms: int,
    end_ms: int,
) -> dict[str, object]:
    payload = page.verified_receipt.receipt.payload
    return {
        "$metadata": {
            "service": SERVICE,
            "traceId": trace_id,
            "spanId": span_id,
            "spanName": span_name,
            "startTime": start_ms,
            "endTime": end_ms,
        },
        "$workers": {
            "scriptName": SERVICE,
            "scriptVersion": {"id": payload.collector_release_id},
            "truncated": False,
        },
        "dataset": "cloudflare-workers",
        "source": {},
        "timestamp": start_ms,
        "cloud.provider": "cloudflare",
        "cloud.platform": "cloudflare.workers",
        "faas.invocation_id": f"invocation-{trace_id}",
        "service.name": SERVICE,
        "cloudflare.script_version.id": payload.collector_release_id,
    }


def _events(page, index: int, *, fetch_span_id: str | None = None):
    payload = page.verified_receipt.receipt.payload
    start_ms = int(payload.physical_started_at_utc.astimezone(timezone.utc).timestamp() * 1000)
    end_ms = int(payload.response_completed_at_utc.astimezone(timezone.utc).timestamp() * 1000)
    trace_id = f"trace-catalog-finalizer-{index}"
    custom_span_id = f"custom-catalog-finalizer-{index}"
    fetch_span_id = fetch_span_id or f"fetch-catalog-finalizer-{index}"
    custom = _base_event(
        page,
        trace_id=trace_id,
        span_id=custom_span_id,
        span_name=ORIGIN_EXECUTION_SPAN_NAME,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    custom.update(
        {
            "precios.trace_contract_version": "1",
            "precios.collector_provider": "cloudflare_workers",
            "precios.authorization_id": payload.authorization_id,
            "precios.run_id": payload.run_id,
            "precios.approved_commit_sha": payload.approved_commit_sha,
            "precios.reservation_id": payload.reservation_id,
            "precios.request_id": payload.request_id,
            "precios.request_digest": payload.request_digest,
            "precios.traversal_role": payload.traversal_role,
            "precios.traversal_id": payload.traversal_id,
            "precios.partition_id": payload.partition_id,
        }
    )
    fetch = _base_event(
        page,
        trace_id=trace_id,
        span_id=fetch_span_id,
        span_name="fetch",
        start_ms=start_ms + 10,
        end_ms=max(start_ms + 10, end_ms - 10),
    )
    metadata = fetch["$metadata"]
    assert isinstance(metadata, dict)
    metadata["parentSpanId"] = custom_span_id
    fetch.update(
        {
            "url.full": page.source_url,
            "http.request.method": "GET",
            "http.response.status_code": 200,
            "http.response.body.size": payload.response_body_bytes,
        }
    )
    return custom, fetch


class _FakeObservabilityTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post_json(self, path: str, *, bearer_token: str, payload: Any) -> Any:
        self.calls.append({"path": path, "bearer_token": bearer_token, "payload": payload})
        if not self.responses:
            raise AssertionError("unexpected observability call")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _completed_collector():
    collector, _gateway, _discovery = _collector()
    collector.collect_all()
    return collector


def _responses_for(collector, *, duplicate_second_fetch: bool = False):
    responses: list[dict[str, object]] = []
    pages = tuple(item.page for item in collector.observations)
    for index, page in enumerate(pages):
        forced = "fetch-catalog-finalizer-0" if duplicate_second_fetch and index == 1 else None
        custom, fetch = _events(page, index, fetch_span_id=forced)
        responses.append(_response([custom]))
        responses.append(_response([custom, fetch]))
    return responses


def _finalizer_for(collector, *, responses=None, token_provider=None):
    transport = _FakeObservabilityTransport(
        _responses_for(collector) if responses is None else list(responses)
    )
    client = CloudflareObservabilityVerifierClient(ACCOUNT_ID, transport)
    token_calls: list[int] = []

    def default_token_provider() -> str:
        token_calls.append(1)
        return TOKEN

    finalizer = VerifiedCatalogPhysicalFinalizer(
        client,
        bearer_token_provider=token_provider or default_token_provider,
    )
    return finalizer, transport, token_calls


def test_finaliza_todas_las_paginas_y_construye_manifest_exacto() -> None:
    collector = _completed_collector()
    finalizer, transport, token_calls = _finalizer_for(collector)

    result = finalizer.finalize(collector)

    assert isinstance(result, PhysicallyReconciledCatalogCollection)
    assert result.collection.plan_digest == collector.authenticated_plan.digest
    assert len(result.reconciled_pages) == collector.requests_expected == 4
    assert result.run_manifest.request_count == collector.requests_expected
    assert tuple(record.expected for record in result.run_manifest.pages) == tuple(
        collector.authenticated_plan.pages
    )
    assert len({page.physical_evidence_id for page in result.reconciled_pages}) == 4
    assert len({page.trace_evidence.fetch_span_id for page in result.reconciled_pages}) == 4
    assert result.production_authority is False
    assert result.run_manifest.production_authority is False
    assert finalizer.finalized is True
    assert finalizer.account_id == ACCOUNT_ID
    assert token_calls == [1]
    assert len(transport.calls) == 8
    assert all(call["bearer_token"] == TOKEN for call in transport.calls)


def test_incompleto_falla_antes_de_token_y_observability() -> None:
    collector, _gateway, _discovery = _collector()
    transport = _FakeObservabilityTransport([])
    client = CloudflareObservabilityVerifierClient(ACCOUNT_ID, transport)
    token_calls: list[int] = []

    def token_provider() -> str:
        token_calls.append(1)
        return TOKEN

    finalizer = VerifiedCatalogPhysicalFinalizer(
        client,
        bearer_token_provider=token_provider,
    )
    collector.collect_next()

    with pytest.raises(VerifiedCatalogPhysicalFinalizationError) as captured:
        finalizer.finalize(collector)

    assert captured.value.code == "verified_catalog_collector_incomplete"
    assert token_calls == []
    assert transport.calls == []


def test_telemetria_faltante_en_primera_pagina_detiene_sin_polling_ni_retry() -> None:
    collector = _completed_collector()
    finalizer, transport, token_calls = _finalizer_for(
        collector,
        responses=[_response([])],
    )

    with pytest.raises(VerifiedCatalogPhysicalFinalizationError) as captured:
        finalizer.finalize(collector)

    assert captured.value.code == "page_0_observability_reconciliation_matching_trace_missing"
    assert token_calls == [1]
    assert len(transport.calls) == 1


def test_segunda_finalizacion_mismo_collector_es_idempotente_sin_queries() -> None:
    collector = _completed_collector()
    finalizer, transport, token_calls = _finalizer_for(collector)
    first = finalizer.finalize(collector)
    calls = len(transport.calls)

    second = finalizer.finalize(collector)

    assert second is first
    assert len(transport.calls) == calls
    assert token_calls == [1]


def test_finalizer_no_puede_ligarse_a_otro_collector() -> None:
    collector = _completed_collector()
    finalizer, transport, _token_calls = _finalizer_for(collector)
    finalizer.finalize(collector)
    calls = len(transport.calls)
    other = _completed_collector()

    with pytest.raises(VerifiedCatalogPhysicalFinalizationError) as captured:
        finalizer.finalize(other)

    assert captured.value.code == "finalizer_already_bound_to_other_collector"
    assert len(transport.calls) == calls


def test_fetch_span_reutilizado_falla_en_segunda_pagina() -> None:
    collector = _completed_collector()
    finalizer, transport, _token_calls = _finalizer_for(
        collector,
        responses=_responses_for(collector, duplicate_second_fetch=True),
    )

    with pytest.raises(VerifiedCatalogPhysicalFinalizationError) as captured:
        finalizer.finalize(collector)

    assert captured.value.code == "physical_fetch_span_reused"
    assert len(transport.calls) == 4


def test_token_invalido_falla_antes_de_observability() -> None:
    collector = _completed_collector()
    finalizer, transport, _token_calls = _finalizer_for(
        collector,
        token_provider=lambda: "token con espacios",
    )

    with pytest.raises(VerifiedCatalogPhysicalFinalizationError) as captured:
        finalizer.finalize(collector)

    assert captured.value.code == "observability_bearer_token_invalid"
    assert transport.calls == []
