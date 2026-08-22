"""Publica sólo un fingerprint estructural sanitizado del diagnóstico Observability.

Consume el archivo ya sanitizado producido por ``diagnosticar_observability_sonda_cloudflare.py``
y publica commit statuses sobre el SHA inmutable de ``main``. No recibe credenciales de
Cloudflare, no lee el artefacto físico y no contiene ninguna ruta hacia La Colonia.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


EXPECTED_REPOSITORY = "Jchernand3z19/Portafolio"
CONTEXT_PREFIX = "precios-sps/obs"
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SAFE_ERROR = re.compile(r"[a-z0-9_.:-]{1,80}\Z")
_ALLOWED_STATUS = {
    "shape_collected",
    "controlled_observability_error",
    "unexpected_diagnostic_error",
    "started_without_summary",
}
_ALLOWED_LOCATION_PREFIXES = {
    "top": "top",
    "source": "source",
    "source.attributes": "attrs",
    "source.resource": "resource",
}


@dataclass(frozen=True, slots=True)
class CommitStatus:
    context: str
    state: str = "success"
    description: str = "sanitized Observability fingerprint"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _safe_nonnegative_int(value: object, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        return 0
    return value


def _extract_payload(comment_path: Path) -> Mapping[str, object]:
    envelope = json.loads(comment_path.read_text(encoding="utf-8"))
    if not isinstance(envelope, Mapping) or set(envelope) != {"body"}:
        raise ValueError("diagnostic_envelope_invalid")
    body = envelope["body"]
    if not isinstance(body, str) or len(body) > 200_000:
        raise ValueError("diagnostic_body_invalid")
    marker = "```json\n"
    start = body.find(marker)
    end = body.rfind("\n```")
    if start < 0 or end <= start:
        raise ValueError("diagnostic_json_block_missing")
    payload = json.loads(body[start + len(marker) : end])
    if not isinstance(payload, Mapping):
        raise ValueError("diagnostic_payload_invalid")
    if payload.get("contains_no_event_values") is not True:
        raise ValueError("diagnostic_not_sanitized")
    if payload.get("production_authority") is not False:
        raise ValueError("diagnostic_authority_invalid")
    if payload.get("catalog_accepted") is not False:
        raise ValueError("diagnostic_catalog_acceptance_invalid")
    return payload


def _presence(values: Mapping[str, object], suffix: str) -> set[str]:
    locations: set[str] = set()
    for raw_key, raw_count in values.items():
        if not isinstance(raw_key, str) or not raw_key.endswith(f":{suffix}"):
            continue
        if _safe_nonnegative_int(raw_count, maximum=500) <= 0:
            continue
        raw_prefix = raw_key[: -(len(suffix) + 1)]
        mapped = _ALLOWED_LOCATION_PREFIXES.get(raw_prefix)
        if mapped:
            locations.add(mapped)
    return locations


def _location_label(locations: set[str]) -> str:
    if not locations:
        return "none"
    if len(locations) == 1:
        return next(iter(locations))
    return "mixed"


def _source_label(source_types: Mapping[str, object]) -> str:
    present = {
        key
        for key in ("mapping", "string", "missing")
        if _safe_nonnegative_int(source_types.get(key), maximum=500) > 0
    }
    if len(present) == 1:
        return next(iter(present))
    if len(present) > 1:
        return "mixed"
    return "other"


def build_statuses(payload: Mapping[str, object]) -> tuple[CommitStatus, ...]:
    status = payload.get("diagnostic_status")
    if status not in _ALLOWED_STATUS:
        raise ValueError("diagnostic_status_invalid")

    contexts: list[str] = [f"{CONTEXT_PREFIX}/result/{status}"]
    if status == "controlled_observability_error":
        code = payload.get("error_code")
        if not isinstance(code, str) or not _SAFE_ERROR.fullmatch(code):
            code = "invalid-safe-code"
        contexts.append(f"{CONTEXT_PREFIX}/error/{code}"[:100])
    elif status == "unexpected_diagnostic_error":
        error_type = payload.get("error_type")
        if not isinstance(error_type, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", error_type):
            error_type = "Unknown"
        contexts.append(f"{CONTEXT_PREFIX}/unexpected/{error_type}")
    elif status == "shape_collected":
        trace_count = _safe_nonnegative_int(payload.get("trace_candidate_count"), maximum=10_000)
        contexts.append(f"{CONTEXT_PREFIX}/trace-candidates/{min(trace_count, 999)}")

        custom_span = False
        precios_attrs = False
        mapping_events = False
        source_labels: set[str] = set()
        http_locations: set[str] = set()
        url_locations: set[str] = set()

        for candidate in _sequence(payload.get("candidate_shapes"))[:20]:
            candidate_map = _mapping(candidate)
            for view_name in ("events_view", "invocations_view"):
                view = _mapping(candidate_map.get(view_name))
                events = _mapping(view.get("events"))
                mapping_events = mapping_events or _safe_nonnegative_int(
                    events.get("mapping_event_count"), maximum=500
                ) > 0
                source_types = _mapping(events.get("source_types"))
                source_labels.add(_source_label(source_types))

                matches = _mapping(events.get("expected_custom_span_match_counts"))
                custom_span = custom_span or any(
                    _safe_nonnegative_int(value, maximum=500) > 0 for value in matches.values()
                )
                precios_attrs = precios_attrs or bool(
                    _sequence(events.get("precios_attribute_key_locations"))
                )
                standard = _mapping(events.get("standard_attribute_presence_counts"))
                http_locations.update(_presence(standard, "http.response.status_code"))
                url_locations.update(_presence(standard, "url.full"))

        source_label = next(iter(source_labels)) if len(source_labels) == 1 else "mixed"
        contexts.extend(
            [
                f"{CONTEXT_PREFIX}/mapping-events/{'yes' if mapping_events else 'no'}",
                f"{CONTEXT_PREFIX}/custom-span/{'yes' if custom_span else 'no'}",
                f"{CONTEXT_PREFIX}/precios-attrs/{'yes' if precios_attrs else 'no'}",
                f"{CONTEXT_PREFIX}/source/{source_label}",
                f"{CONTEXT_PREFIX}/http-status/{_location_label(http_locations)}",
                f"{CONTEXT_PREFIX}/url-full/{_location_label(url_locations)}",
            ]
        )

    deduped = tuple(dict.fromkeys(contexts))
    if any(len(context) > 100 or "\n" in context or "\r" in context for context in deduped):
        raise ValueError("diagnostic_status_context_invalid")
    return tuple(CommitStatus(context=context) for context in deduped)


def _publish_status(*, repository: str, sha: str, token: str, status: CommitStatus) -> None:
    if repository != EXPECTED_REPOSITORY or not _SHA1.fullmatch(sha):
        raise ValueError("github_identity_invalid")
    if not token or len(token) > 4096:
        raise ValueError("github_token_invalid")
    body = json.dumps(
        {
            "state": status.state,
            "context": status.context,
            "description": status.description,
        },
        sort_keys=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/statuses/{sha}",
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 201:
                raise RuntimeError("github_status_publish_failed")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"github_status_publish_http_{exc.code}") from exc


def main() -> int:
    payload = _extract_payload(Path(os.environ["PROBE_DIAGNOSTIC_COMMENT_PATH"]))
    statuses = build_statuses(payload)
    repository = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    token = os.environ["GH_TOKEN"]
    for status in statuses:
        _publish_status(repository=repository, sha=sha, token=token, status=status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
