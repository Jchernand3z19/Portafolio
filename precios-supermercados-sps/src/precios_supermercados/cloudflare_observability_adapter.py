"""Adapter offline para Workers Observability Telemetry.

No realiza HTTP ni contiene credenciales de Cloudflare. El flujo es deliberadamente
de dos pasos porque los atributos custom sólo pertenecen al custom span y no se
propagan automáticamente al child span de ``fetch``:

1. discovery por ``authorization_id``/``run_id`` para obtener trace IDs;
2. detalle por ``$metadata.traceId`` para recuperar custom span + fetch child.

La evidencia resultante permanece sin autoridad productiva hasta validar este
adapter contra una respuesta real de la plataforma y separar la identidad que
consulta Observability de la identidad del collector.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from precios_supermercados.cloudflare_trace_evidence import (
    CLOUD_PLATFORM,
    CLOUD_PROVIDER,
    ORIGIN_EXECUTION_SPAN_NAME,
    TRACE_CONTRACT_VERSION,
    CloudflareOriginTraceEvidence,
)

OBSERVABILITY_DATASET = "cloudflare-workers"
DISCOVERY_QUERY_ID = "precios-sps-origin-trace-discovery-v1"
DETAIL_QUERY_ID = "precios-sps-origin-trace-detail-v1"
DEFAULT_WORKER_SERVICE = "precios-sps-provenance"
MAX_QUERY_EVENTS = 100
MAX_QUERY_WINDOW = timedelta(minutes=15)
_SAFE_INTEGER_MAX = 2**53 - 1

_CUSTOM_ATTRIBUTES = (
    "precios.trace_contract_version",
    "precios.collector_provider",
    "precios.authorization_id",
    "precios.run_id",
    "precios.approved_commit_sha",
    "precios.reservation_id",
    "precios.request_id",
    "precios.request_digest",
    "precios.traversal_role",
    "precios.traversal_id",
    "precios.partition_id",
)


class CloudflareObservabilityAdapterError(ValueError):
    """La respuesta de Observability no puede convertirse de forma segura."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CloudflareObservabilityAdapterError(code, message)


def _mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(code)
    for key in value:
        if not isinstance(key, str):
            _fail(code)
    return value


def _sequence(value: object, code: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail(code)
    return value


def _text(value: object, code: str, *, maximum: int = 20_000) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(character.isspace() for character in value)
    ):
        _fail(code)
    return value


def _safe_integer(value: object, code: str, *, minimum: int = 0, maximum: int = _SAFE_INTEGER_MAX) -> int:
    if isinstance(value, bool):
        _fail(code)
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    else:
        _fail(code)
    if not minimum <= parsed <= maximum:
        _fail(code)
    return parsed


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _fail(code)
    return value.astimezone(timezone.utc)


def _epoch_ms(value: object, code: str) -> datetime:
    milliseconds = _safe_integer(value, code, minimum=1)
    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise CloudflareObservabilityAdapterError(code) from exc


def _filter(key: str, value: str) -> dict[str, object]:
    return {
        "kind": "filter",
        "key": key,
        "operation": "eq",
        "type": "string",
        "value": value,
    }


def _query_window(from_utc: datetime, to_utc: datetime) -> tuple[int, int]:
    start = _utc(from_utc, "query_from_invalid")
    end = _utc(to_utc, "query_to_invalid")
    if end <= start:
        _fail("query_window_invalid")
    if end - start > MAX_QUERY_WINDOW:
        _fail("query_window_too_wide")
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _query_payload(
    *,
    query_id: str,
    from_ms: int,
    to_ms: int,
    filters: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "queryId": query_id,
        "timeframe": {"from": from_ms, "to": to_ms},
        "view": "events",
        "limit": MAX_QUERY_EVENTS,
        "parameters": {
            "datasets": [OBSERVABILITY_DATASET],
            "filterCombination": "and",
            "filters": filters,
            "limit": MAX_QUERY_EVENTS,
        },
    }


def build_cloudflare_trace_discovery_query(
    *,
    from_utc: datetime,
    to_utc: datetime,
    authorization_id: str,
    run_id: str,
    service_name: str = DEFAULT_WORKER_SERVICE,
) -> dict[str, object]:
    """Localiza únicamente custom spans de una autorización/ejecución."""

    from_ms, to_ms = _query_window(from_utc, to_utc)
    authorization = _text(authorization_id, "authorization_id_invalid", maximum=128)
    run = _text(run_id, "run_id_invalid", maximum=256)
    service = _text(service_name, "service_name_invalid", maximum=256)
    return _query_payload(
        query_id=DISCOVERY_QUERY_ID,
        from_ms=from_ms,
        to_ms=to_ms,
        filters=[
            _filter("$metadata.service", service),
            _filter("$metadata.spanName", ORIGIN_EXECUTION_SPAN_NAME),
            _filter("precios.authorization_id", authorization),
            _filter("precios.run_id", run),
            _filter("precios.trace_contract_version", TRACE_CONTRACT_VERSION),
        ],
    )


def build_cloudflare_trace_detail_query(
    *,
    from_utc: datetime,
    to_utc: datetime,
    trace_id: str,
    service_name: str = DEFAULT_WORKER_SERVICE,
) -> dict[str, object]:
    """Recupera todos los eventos de un trace para observar su child ``fetch``."""

    from_ms, to_ms = _query_window(from_utc, to_utc)
    trace = _text(trace_id, "trace_id_invalid", maximum=512)
    service = _text(service_name, "service_name_invalid", maximum=256)
    return _query_payload(
        query_id=DETAIL_QUERY_ID,
        from_ms=from_ms,
        to_ms=to_ms,
        filters=[
            _filter("$metadata.service", service),
            _filter("$metadata.traceId", trace),
        ],
    )


def _raw_events(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    envelope = _mapping(payload, "observability_response_invalid")
    if envelope.get("success") is not True:
        _fail("observability_response_unsuccessful")
    errors = envelope.get("errors")
    if errors not in (None, []):
        _fail("observability_response_errors")

    result = _mapping(envelope.get("result"), "observability_result_invalid")
    events_container = _mapping(result.get("events"), "observability_events_container_invalid")
    events = _sequence(events_container.get("events"), "observability_events_invalid")
    if len(events) > MAX_QUERY_EVENTS:
        _fail("observability_events_above_limit")
    count = events_container.get("count")
    if count is not None:
        declared_count = _safe_integer(count, "observability_events_count_invalid")
        if declared_count > len(events):
            _fail("observability_events_truncated")

    result_events: list[Mapping[str, object]] = []
    for index, event in enumerate(events):
        event_map = _mapping(event, f"event_{index}_invalid")
        if event_map.get("dataset") != OBSERVABILITY_DATASET:
            _fail(f"event_{index}_dataset_invalid")
        metadata = _mapping(event_map.get("$metadata"), f"event_{index}_metadata_invalid")
        workers = event_map.get("$workers")
        if workers is not None:
            worker_map = _mapping(workers, f"event_{index}_workers_invalid")
            if worker_map.get("truncated") is True:
                _fail(f"event_{index}_truncated")
        if metadata.get("truncated") is True:
            _fail(f"event_{index}_metadata_truncated")
        result_events.append(event_map)
    return tuple(result_events)


def _relevant_parts(
    event: Mapping[str, object],
    *,
    prefix: str,
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    metadata = _mapping(event.get("$metadata"), f"{prefix}_metadata_invalid")
    source = _mapping(event.get("source"), f"{prefix}_source_invalid")
    workers = _mapping(event.get("$workers"), f"{prefix}_workers_invalid")
    if workers.get("truncated") is True:
        _fail(f"{prefix}_truncated")
    return metadata, source, workers


def _custom_span_context(source: Mapping[str, object]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in _CUSTOM_ATTRIBUTES:
        values[key] = _text(source.get(key), f"custom_attribute_{key}_invalid", maximum=512)
    if values["precios.trace_contract_version"] != TRACE_CONTRACT_VERSION:
        _fail("custom_trace_contract_version_invalid")
    if values["precios.collector_provider"] != "cloudflare_workers":
        _fail("custom_collector_provider_invalid")
    return values


def parse_cloudflare_trace_discovery_response(
    payload: Mapping[str, object],
    *,
    authorization_id: str,
    run_id: str,
    service_name: str = DEFAULT_WORKER_SERVICE,
) -> tuple[str, ...]:
    """Valida discovery y devuelve trace IDs únicos; no confía sólo en filtros API."""

    authorization = _text(authorization_id, "authorization_id_invalid", maximum=128)
    run = _text(run_id, "run_id_invalid", maximum=256)
    service = _text(service_name, "service_name_invalid", maximum=256)
    trace_ids: list[str] = []
    for index, event in enumerate(_raw_events(payload)):
        metadata, source, workers = _relevant_parts(event, prefix=f"discovery_{index}")
        if metadata.get("spanName") != ORIGIN_EXECUTION_SPAN_NAME:
            _fail("discovery_span_name_invalid")
        context = _custom_span_context(source)
        if context["precios.authorization_id"] != authorization:
            _fail("discovery_authorization_mismatch")
        if context["precios.run_id"] != run:
            _fail("discovery_run_mismatch")
        _, _, _, observed_service, _ = _standard_span_identity(
            metadata,
            source,
            workers,
            prefix=f"discovery_{index}",
        )
        if observed_service != service:
            _fail("discovery_service_mismatch")
        trace_ids.append(_text(metadata.get("traceId"), "discovery_trace_id_invalid", maximum=512))

    if len(set(trace_ids)) != len(trace_ids):
        _fail("discovery_trace_id_duplicate")
    return tuple(trace_ids)


def _standard_span_identity(
    metadata: Mapping[str, object],
    source: Mapping[str, object],
    workers: Mapping[str, object],
    *,
    prefix: str,
) -> tuple[str, str, str, str, str]:
    trace_id = _text(metadata.get("traceId"), f"{prefix}_trace_id_invalid", maximum=512)
    span_id = _text(metadata.get("spanId"), f"{prefix}_span_id_invalid", maximum=512)
    invocation_id = _text(source.get("faas.invocation_id"), f"{prefix}_invocation_id_invalid", maximum=512)
    service = _text(source.get("service.name"), f"{prefix}_service_invalid", maximum=256)
    version = _text(source.get("cloudflare.script_version.id"), f"{prefix}_script_version_invalid", maximum=512)

    if source.get("cloud.provider") != CLOUD_PROVIDER:
        _fail(f"{prefix}_cloud_provider_invalid")
    if source.get("cloud.platform") != CLOUD_PLATFORM:
        _fail(f"{prefix}_cloud_platform_invalid")
    if metadata.get("service") != service:
        _fail(f"{prefix}_service_metadata_mismatch")
    worker_script = workers.get("scriptName")
    if worker_script is not None and worker_script != service:
        _fail(f"{prefix}_worker_script_mismatch")
    script_version = workers.get("scriptVersion")
    if script_version is not None:
        script_version_map = _mapping(script_version, f"{prefix}_worker_script_version_invalid")
        if script_version_map.get("id") != version:
            _fail(f"{prefix}_worker_script_version_mismatch")
    return trace_id, span_id, invocation_id, service, version


def _span_times(metadata: Mapping[str, object], *, prefix: str) -> tuple[datetime, datetime]:
    start = _epoch_ms(metadata.get("startTime"), f"{prefix}_start_time_invalid")
    end = _epoch_ms(metadata.get("endTime"), f"{prefix}_end_time_invalid")
    if end < start:
        _fail(f"{prefix}_time_order_invalid")
    return start, end


def _source_mapping_if_present(event: Mapping[str, object]) -> Mapping[str, object] | None:
    source = event.get("source")
    if not isinstance(source, Mapping):
        return None
    if any(not isinstance(key, str) for key in source):
        return None
    return source


def _metadata(event: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(event.get("$metadata"), "event_metadata_invalid")


def _is_fetch_child(event: Mapping[str, object], custom_span_id: str, trace_id: str) -> bool:
    metadata = _metadata(event)
    source = _source_mapping_if_present(event)
    if source is None:
        return False
    return (
        metadata.get("parentSpanId") == custom_span_id
        and metadata.get("traceId") == trace_id
        and "url.full" in source
        and "http.request.method" in source
        and "http.response.status_code" in source
        and "http.response.body.size" in source
    )


def _build_trace_evidence(
    *,
    custom_event: Mapping[str, object],
    fetch_event: Mapping[str, object],
) -> CloudflareOriginTraceEvidence:
    custom_metadata, custom_source, custom_workers = _relevant_parts(custom_event, prefix="custom")
    fetch_metadata, fetch_source, fetch_workers = _relevant_parts(fetch_event, prefix="fetch")
    custom_trace_id, custom_span_id, custom_invocation, service, version = _standard_span_identity(
        custom_metadata,
        custom_source,
        custom_workers,
        prefix="custom",
    )
    fetch_trace_id, fetch_span_id, fetch_invocation, fetch_service, fetch_version = _standard_span_identity(
        fetch_metadata,
        fetch_source,
        fetch_workers,
        prefix="fetch",
    )
    if fetch_trace_id != custom_trace_id:
        _fail("fetch_trace_id_mismatch")
    if fetch_metadata.get("parentSpanId") != custom_span_id:
        _fail("fetch_parent_span_mismatch")
    if fetch_invocation != custom_invocation:
        _fail("fetch_invocation_mismatch")
    if fetch_service != service:
        _fail("fetch_service_mismatch")
    if fetch_version != version:
        _fail("fetch_script_version_mismatch")

    context = _custom_span_context(custom_source)
    custom_start, custom_end = _span_times(custom_metadata, prefix="custom")
    fetch_start, fetch_end = _span_times(fetch_metadata, prefix="fetch")

    return CloudflareOriginTraceEvidence(
        trace_id=custom_trace_id,
        custom_span_id=custom_span_id,
        fetch_span_id=fetch_span_id,
        fetch_parent_span_id=_text(fetch_metadata.get("parentSpanId"), "fetch_parent_span_id_invalid", maximum=512),
        faas_invocation_id=custom_invocation,
        service_name=service,
        script_version_id=version,
        custom_span_name=ORIGIN_EXECUTION_SPAN_NAME,
        trace_contract_version=context["precios.trace_contract_version"],
        cloud_provider=CLOUD_PROVIDER,
        cloud_platform=CLOUD_PLATFORM,
        collector_provider=context["precios.collector_provider"],
        authorization_id=context["precios.authorization_id"],
        run_id=context["precios.run_id"],
        approved_commit_sha=context["precios.approved_commit_sha"],
        reservation_id=context["precios.reservation_id"],
        request_id=context["precios.request_id"],
        request_digest=context["precios.request_digest"],
        traversal_role=context["precios.traversal_role"],
        traversal_id=context["precios.traversal_id"],
        partition_id=context["precios.partition_id"],
        fetch_url=_text(fetch_source.get("url.full"), "fetch_url_invalid"),
        fetch_method=_text(fetch_source.get("http.request.method"), "fetch_method_invalid", maximum=16),
        fetch_status=_safe_integer(fetch_source.get("http.response.status_code"), "fetch_status_invalid", minimum=100, maximum=599),
        fetch_response_body_size=_safe_integer(fetch_source.get("http.response.body.size"), "fetch_body_size_invalid"),
        custom_started_at_utc=custom_start,
        custom_completed_at_utc=custom_end,
        fetch_started_at_utc=fetch_start,
        fetch_completed_at_utc=fetch_end,
    )


def parse_cloudflare_trace_detail_response(
    payload: Mapping[str, object],
    *,
    expected_trace_id: str,
    service_name: str = DEFAULT_WORKER_SERVICE,
) -> tuple[CloudflareOriginTraceEvidence, ...]:
    """Extrae custom-span + child fetch de un trace completo y no truncado."""

    trace_id = _text(expected_trace_id, "expected_trace_id_invalid", maximum=512)
    service = _text(service_name, "service_name_invalid", maximum=256)
    events = _raw_events(payload)

    for event in events:
        metadata = _metadata(event)
        observed_trace = metadata.get("traceId")
        if observed_trace is not None and observed_trace != trace_id:
            _fail("detail_trace_id_mismatch")
        observed_service = metadata.get("service")
        if observed_service is not None and observed_service != service:
            _fail("detail_service_mismatch")

    custom_events = [
        event for event in events if _metadata(event).get("spanName") == ORIGIN_EXECUTION_SPAN_NAME
    ]
    evidences: list[CloudflareOriginTraceEvidence] = []
    for custom_event in custom_events:
        custom_metadata, _custom_source, _custom_workers = _relevant_parts(custom_event, prefix="custom")
        custom_trace_id = _text(custom_metadata.get("traceId"), "custom_trace_id_invalid", maximum=512)
        if custom_trace_id != trace_id:
            _fail("custom_trace_id_mismatch")
        custom_span_id = _text(custom_metadata.get("spanId"), "custom_span_id_invalid", maximum=512)
        fetch_candidates = [
            event for event in events if _is_fetch_child(event, custom_span_id, custom_trace_id)
        ]
        if not fetch_candidates:
            _fail("origin_fetch_span_missing")
        if len(fetch_candidates) != 1:
            _fail("origin_fetch_span_not_unique")
        evidences.append(_build_trace_evidence(custom_event=custom_event, fetch_event=fetch_candidates[0]))

    physical_ids = [evidence.physical_evidence_id for evidence in evidences]
    if len(set(physical_ids)) != len(physical_ids):
        _fail("physical_evidence_duplicate")
    return tuple(evidences)
