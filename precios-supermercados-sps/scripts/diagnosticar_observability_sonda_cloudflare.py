"""Diagnóstico sanitizado de la forma real de Workers Observability.

Lee únicamente evidencia física ya existente de la sonda controlada, vuelve a
verificar su firma Ed25519 y consulta Workers Observability. Nunca ejecuta la
sonda física, no conoce el gateway y no contiene rutas ni destinos de La Colonia.
El resultado expone sólo tipos, cantidades, nombres de campos acotados y
coincidencias booleanas con el nombre conocido del span controlado.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from precios_supermercados.cloudflare_controlled_probe_events_query import (
    build_trace_events_query,
)
from precios_supermercados.cloudflare_controlled_probe_observability import (
    CONTROLLED_PROBE_SERVICE,
    CONTROLLED_PROBE_SPAN_NAME,
    OBSERVABILITY_DATASET,
    ControlledProbeObservabilityError,
)
from precios_supermercados.cloudflare_controlled_probe_trace_query import (
    OBSERVABILITY_QUERY_PATH_TEMPLATE,
    build_trace_invocations_query,
    build_trace_summary_query,
    parse_trace_summary_response,
)
from precios_supermercados.cloudflare_controlled_probe_verifier import (
    verify_controlled_probe_artifact,
)
from precios_supermercados.cloudflare_observability_http_transport import (
    CloudflareObservabilityHttpTransport,
)

ARTIFACT_PATH = Path(".probe-evidence/cloudflare-probe-result.json")
SOURCE_RUN_ID = "32551882793"
SOURCE_RUN_ATTEMPT = 1
SOURCE_COMMIT_SHA = "cc15edef22709911beb1d1b027ae4c9992da1944"
MAX_EVENTS = 500
MAX_TRACE_CANDIDATES = 20
DIRECT_QUERY_ID_SERVICE = "precios-sps-controlled-probe-direct-span-service-v1"
DIRECT_QUERY_ID_ANY = "precios-sps-controlled-probe-direct-span-any-v1"

STANDARD_KEYS = (
    "service.name",
    "faas.invocation_id",
    "faas.version",
    "cloudflare.script_version.id",
    "cloudflare.script_name",
    "url.full",
    "http.request.method",
    "http.response.status_code",
    "http.response.body.size",
)

METADATA_KEYS = (
    "traceId",
    "spanId",
    "parentSpanId",
    "spanName",
    "service",
    "startTime",
    "endTime",
    "statusCode",
    "url",
    "origin",
    "type",
    "requestId",
)

FIXED_MATCH_PATHS = (
    ("$metadata", "spanName"),
    ("spanName",),
    ("source", "spanName"),
    ("source", "name"),
    ("source", "span.name"),
    ("source", "attributes", "span.name"),
    ("source", "attributes", "spanName"),
)


def _safe_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, Mapping):
        return "mapping"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "sequence"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__[:64]


def _safe_keys(values: object) -> list[str]:
    if not isinstance(values, Sequence) and not isinstance(values, set):
        values = tuple(values) if isinstance(values, Mapping) else ()
    return sorted(
        key
        for key in {str(value) for value in values}
        if 0 < len(key) <= 128 and "\n" not in key and "\r" not in key
    )[:100]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _value_at(event: Mapping[str, object], parts: tuple[str, ...]) -> object:
    current: object = event
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _filter(key: str, value: str) -> dict[str, object]:
    return {
        "kind": "filter",
        "key": key,
        "operation": "eq",
        "type": "string",
        "value": value,
    }


def _direct_custom_span_query(
    *,
    from_utc: datetime,
    to_utc: datetime,
    service_scoped: bool,
) -> dict[str, object]:
    filters = [_filter("$metadata.spanName", CONTROLLED_PROBE_SPAN_NAME)]
    query_id = DIRECT_QUERY_ID_ANY
    if service_scoped:
        filters.insert(0, _filter("$metadata.service", CONTROLLED_PROBE_SERVICE))
        query_id = DIRECT_QUERY_ID_SERVICE
    return {
        "queryId": query_id,
        "timeframe": {
            "from": int(from_utc.timestamp() * 1000),
            "to": int(to_utc.timestamp() * 1000),
        },
        "view": "events",
        "limit": MAX_EVENTS,
        "parameters": {
            "datasets": [OBSERVABILITY_DATASET],
            "filterCombination": "and",
            "filters": filters,
            "limit": MAX_EVENTS,
        },
    }


def _summarize_events(raw_events: Sequence[object]) -> dict[str, object]:
    top_keys: set[object] = set()
    metadata_keys: set[object] = set()
    workers_keys: set[object] = set()
    source_keys: set[object] = set()
    source_attributes_keys: set[object] = set()
    source_resource_keys: set[object] = set()
    match_paths: Counter[str] = Counter()
    standard_presence: Counter[str] = Counter()
    source_types: Counter[str] = Counter()
    metadata_presence: Counter[str] = Counter()
    precios_key_locations: set[str] = set()
    mapping_count = 0

    for raw_event in list(raw_events)[:MAX_EVENTS]:
        if not isinstance(raw_event, Mapping):
            continue
        mapping_count += 1
        event = raw_event
        top_keys.update(event.keys())
        metadata = _mapping(event.get("$metadata"))
        workers = _mapping(event.get("$workers"))
        metadata_keys.update(metadata.keys())
        workers_keys.update(workers.keys())

        source = event.get("source")
        if isinstance(source, Mapping):
            source_types["mapping"] += 1
            source_keys.update(source.keys())
            attributes = _mapping(source.get("attributes"))
            resource = _mapping(source.get("resource"))
            source_attributes_keys.update(attributes.keys())
            source_resource_keys.update(resource.keys())
        elif isinstance(source, str):
            source_types["string"] += 1
        elif source is None:
            source_types["missing"] += 1
        else:
            source_types[_safe_type(source)] += 1

        for key in METADATA_KEYS:
            if key in metadata:
                metadata_presence[key] += 1

        for parts in FIXED_MATCH_PATHS:
            if _value_at(event, parts) == CONTROLLED_PROBE_SPAN_NAME:
                match_paths[".".join(parts)] += 1

        containers = (
            ("top", event),
            ("source", _mapping(source)),
            ("source.attributes", _mapping(_mapping(source).get("attributes"))),
            ("source.resource", _mapping(_mapping(source).get("resource"))),
        )
        for label, container in containers:
            for key in STANDARD_KEYS:
                if key in container:
                    standard_presence[f"{label}:{key}"] += 1
            for key in container.keys():
                if isinstance(key, str) and key.startswith("precios.") and len(key) <= 128:
                    precios_key_locations.add(f"{label}:{key}")

    return {
        "raw_event_count": min(len(raw_events), MAX_EVENTS),
        "mapping_event_count": mapping_count,
        "top_keys": _safe_keys(top_keys),
        "metadata_keys": _safe_keys(metadata_keys),
        "workers_keys": _safe_keys(workers_keys),
        "source_keys": _safe_keys(source_keys),
        "source_attributes_keys": _safe_keys(source_attributes_keys),
        "source_resource_keys": _safe_keys(source_resource_keys),
        "source_types": dict(sorted(source_types.items())),
        "metadata_presence_counts": dict(sorted(metadata_presence.items())),
        "expected_custom_span_match_counts": dict(sorted(match_paths.items())),
        "standard_attribute_presence_counts": dict(sorted(standard_presence.items())),
        "precios_attribute_key_locations": sorted(precios_key_locations)[:100],
    }


def _raw_events(response: Mapping[str, object]) -> Sequence[object]:
    result = _mapping(response.get("result"))
    container = result.get("events")
    if isinstance(container, Mapping):
        return _sequence(container.get("events"))
    if isinstance(container, Sequence) and not isinstance(container, (str, bytes, bytearray)):
        return container
    return ()


def _raw_events_shape(response: Mapping[str, object]) -> dict[str, object]:
    result = _mapping(response.get("result"))
    container = result.get("events")
    events = _raw_events(response)
    container_keys: list[str] = []
    if isinstance(container, Mapping):
        container_keys = _safe_keys(container.keys())
    return {
        "result_keys": _safe_keys(result.keys()),
        "events_container_type": _safe_type(container),
        "events_container_keys": container_keys,
        "events": _summarize_events(events),
    }


def _raw_invocations_shape(response: Mapping[str, object]) -> dict[str, object]:
    result = _mapping(response.get("result"))
    invocations = result.get("invocations")
    events: list[object] = []
    group_count = 0
    group_value_types: Counter[str] = Counter()
    if isinstance(invocations, Mapping):
        group_count = min(len(invocations), 200)
        for raw_group in list(invocations.values())[:200]:
            group_value_types[_safe_type(raw_group)] += 1
            for event in _sequence(raw_group)[:MAX_EVENTS]:
                if len(events) >= MAX_EVENTS:
                    break
                events.append(event)
    return {
        "result_keys": _safe_keys(result.keys()),
        "invocations_type": _safe_type(invocations),
        "invocation_group_count": group_count,
        "invocation_group_value_types": dict(sorted(group_value_types.items())),
        "events": _summarize_events(events),
    }


def _direct_trace_relation(
    response: Mapping[str, object],
    candidate_trace_ids: Sequence[str],
) -> str:
    candidates = set(candidate_trace_ids)
    observed: set[str] = set()
    for raw_event in _raw_events(response)[:MAX_EVENTS]:
        metadata = _mapping(_mapping(raw_event).get("$metadata"))
        trace_id = metadata.get("traceId")
        if isinstance(trace_id, str) and trace_id:
            observed.add("candidate" if trace_id in candidates else "outside")
    if not observed:
        return "none"
    if len(observed) == 1:
        return next(iter(observed))
    return "mixed"


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("invalid_timestamp")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def _render(payload: Mapping[str, object]) -> None:
    safe = {
        **payload,
        "contains_no_event_values": True,
        "production_authority": False,
        "catalog_accepted": False,
    }
    rendered = json.dumps(safe, sort_keys=True, indent=2)
    comment_path = Path(os.environ["PROBE_DIAGNOSTIC_COMMENT_PATH"])
    comment_path.write_text(
        json.dumps(
            {
                "body": (
                    "## Sanitized Workers Observability shape diagnostic\n\n"
                    "```json\n" + rendered + "\n```"
                )
            }
        ),
        encoding="utf-8",
    )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        Path(summary_path).write_text(
            "## Sanitized Workers Observability shape diagnostic\n\n"
            "```json\n" + rendered + "\n```\n",
            encoding="utf-8",
        )
    print(rendered)


def main() -> int:
    try:
        artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
        verify_controlled_probe_artifact(
            artifact,
            public_key_spki_b64url=os.environ["PROBE_PUBLIC_KEY_SPKI_B64URL"],
            expected_commit_sha=SOURCE_COMMIT_SHA,
            expected_run_id=SOURCE_RUN_ID,
            expected_run_attempt=SOURCE_RUN_ATTEMPT,
        )
        receipt = artifact["receiptPayload"]
        start = _parse_utc(receipt["physical_started_at_utc"]) - timedelta(seconds=30)
        end = _parse_utc(receipt["response_completed_at_utc"]) + timedelta(seconds=30)

        account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        if len(account) != 32 or any(ch not in "0123456789abcdef" for ch in account):
            raise ValueError("invalid_account")
        path = OBSERVABILITY_QUERY_PATH_TEMPLATE.format(account_id=account)
        transport = CloudflareObservabilityHttpTransport()
        token = os.environ["PROBE_OBSERVABILITY_TOKEN"]

        discovery = transport.post_json(
            path,
            bearer_token=token,
            payload=build_trace_summary_query(from_utc=start, to_utc=end),
        )
        trace_ids = parse_trace_summary_response(discovery)
        candidates: list[dict[str, object]] = []
        for trace_id in trace_ids[:MAX_TRACE_CANDIDATES]:
            events_response = transport.post_json(
                path,
                bearer_token=token,
                payload=build_trace_events_query(
                    from_utc=start,
                    to_utc=end,
                    trace_id=trace_id,
                ),
            )
            invocations_response = transport.post_json(
                path,
                bearer_token=token,
                payload=build_trace_invocations_query(
                    from_utc=start,
                    to_utc=end,
                    trace_id=trace_id,
                ),
            )
            candidates.append(
                {
                    "events_view": _raw_events_shape(events_response),
                    "invocations_view": _raw_invocations_shape(invocations_response),
                }
            )

        direct_service = transport.post_json(
            path,
            bearer_token=token,
            payload=_direct_custom_span_query(
                from_utc=start,
                to_utc=end,
                service_scoped=True,
            ),
        )
        direct_any = transport.post_json(
            path,
            bearer_token=token,
            payload=_direct_custom_span_query(
                from_utc=start,
                to_utc=end,
                service_scoped=False,
            ),
        )

        _render(
            {
                "diagnostic_status": "shape_collected",
                "trace_candidate_count": len(trace_ids),
                "candidate_shapes": candidates,
                "direct_custom_span_views": {
                    "with_service": _raw_events_shape(direct_service),
                    "without_service": _raw_events_shape(direct_any),
                    "trace_relation": _direct_trace_relation(direct_any, trace_ids),
                },
            }
        )
    except ControlledProbeObservabilityError as exc:
        _render(
            {
                "diagnostic_status": "controlled_observability_error",
                "error_code": exc.code,
            }
        )
    except Exception as exc:
        _render(
            {
                "diagnostic_status": "unexpected_diagnostic_error",
                "error_type": type(exc).__name__[:64],
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
