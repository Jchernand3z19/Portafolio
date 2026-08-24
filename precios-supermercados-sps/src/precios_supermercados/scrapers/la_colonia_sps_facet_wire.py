"""Aplica offline el placement SPS observado a una request estructural cerrada.

Este módulo no descubre contexto y no abre red. Consume únicamente un
``PreparedSpsFacetExecution`` ya verificado y produce material de transporte
redactado. El valor de ``regionId`` sólo puede revelarse de forma explícita a una
capa de ejecución futura.

Las operaciones estructurales vigentes son GET. Por eso sólo se pueden aplicar de
forma demostrable placements ``query`` o ``header``. Si la observación futura
encuentra ``regionId`` únicamente en body, esta capa falla cerrada: no transforma
silenciosamente un contrato GET en otro transporte.

La evidencia live también observó cambios de sesión VTEX. Por eso el material que
sale de aquí **no es suficiente para un cliente HTTP nuevo**: la futura ejecución
debe usar el mismo ``BrowserContext`` Playwright que estableció y verificó SPS, de
modo que conserve sus cookies de sesión/segmento además del ``regionId`` fuerte.
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from precios_supermercados.scrapers.la_colonia_sps_facet_context import (
    ConfirmedSpsFacetBinding,
    PreparedSpsFacetExecution,
    RequestContextPlacement,
    SpsFacetContextError,
)


class SpsFacetWireError(ValueError):
    """El contexto confirmado no puede aplicarse al request estructural."""


def _wire_fingerprint(method: str, url: str, headers: Mapping[str, str]) -> str:
    payload = json.dumps(
        {
            "method": method,
            "url": url,
            "headers": dict(sorted(headers.items(), key=lambda item: item[0].casefold())),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PreparedSpsFacetWireRequest:
    """Material de transporte con raw context oculto de representaciones públicas."""

    __slots__ = (
        "method",
        "placement",
        "wire_key",
        "base_request_digest",
        "wire_request_fingerprint",
        "_url",
        "_headers",
        "_binding_source_key",
    )

    def __init__(
        self,
        *,
        method: str,
        placement: RequestContextPlacement,
        wire_key: str,
        base_request_digest: str,
        url: str,
        headers: Mapping[str, str],
        binding_source_key: str,
    ) -> None:
        if method != "GET":
            raise SpsFacetWireError("facet_wire_method_invalid")
        if placement not in {RequestContextPlacement.QUERY, RequestContextPlacement.HEADER}:
            raise SpsFacetWireError("facet_wire_placement_invalid")
        if not isinstance(wire_key, str) or not wire_key:
            raise SpsFacetWireError("facet_wire_key_invalid")
        if not isinstance(base_request_digest, str) or len(base_request_digest) != 64:
            raise SpsFacetWireError("facet_base_request_digest_invalid")
        self.method = method
        self.placement = placement
        self.wire_key = wire_key
        self.base_request_digest = base_request_digest
        self._url = url
        self._headers = MappingProxyType(dict(headers))
        self._binding_source_key = binding_source_key
        self.wire_request_fingerprint = _wire_fingerprint(method, url, headers)

    def __repr__(self) -> str:
        return (
            "PreparedSpsFacetWireRequest("
            f"method={self.method!r}, placement={self.placement.value!r}, "
            f"wire_key={self.wire_key!r}, "
            f"base_request_digest={self.base_request_digest!r}, "
            f"wire_request_fingerprint={self.wire_request_fingerprint!r}, "
            "url='<redacted>', headers='<redacted>', "
            "requires_same_browser_context=True)"
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "placement": self.placement.value,
            "wire_key": self.wire_key,
            "base_request_digest": self.base_request_digest,
            "wire_request_fingerprint": self.wire_request_fingerprint,
            "requires_same_browser_context": True,
            "network_executed": False,
            "production_authority": False,
            "catalog_accepted": False,
            "extraction_enabled": False,
            "raw_values_exposed": False,
        }

    def reveal_for_transport(
        self,
        binding: ConfirmedSpsFacetBinding,
    ) -> tuple[str, Mapping[str, str]]:
        if not isinstance(binding, ConfirmedSpsFacetBinding):
            raise SpsFacetWireError("confirmed_sps_binding_required")
        if binding.source_key != self._binding_source_key:
            raise SpsFacetWireError("sps_binding_changed")
        return self._url, MappingProxyType(dict(self._headers))


def prepare_sps_facet_wire_request(
    execution: PreparedSpsFacetExecution,
) -> PreparedSpsFacetWireRequest:
    """Aplica exactamente placement + wire key observados, todavía sin HTTP."""

    if not isinstance(execution, PreparedSpsFacetExecution):
        raise SpsFacetWireError("prepared_sps_facet_execution_required")
    try:
        raw = execution.context.reveal_for_transport(execution.binding)
    except SpsFacetContextError as exc:
        raise SpsFacetWireError(str(exc)) from exc
    if not isinstance(raw, str) or not raw or len(raw) > 4096:
        raise SpsFacetWireError("sps_region_wire_value_invalid")

    base_url = execution.structural_request.source_url
    placement = execution.context.placement
    wire_key = execution.context.wire_key
    headers: dict[str, str] = {}

    if placement is RequestContextPlacement.QUERY:
        parsed = urlsplit(base_url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if any(key.casefold() == wire_key.casefold() for key, _ in pairs):
            raise SpsFacetWireError("sps_region_query_key_already_present")
        query = urlencode([*pairs, (wire_key, raw)])
        url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment)
        )
    elif placement is RequestContextPlacement.HEADER:
        url = base_url
        headers[wire_key] = raw
    elif placement is RequestContextPlacement.BODY:
        raise SpsFacetWireError("sps_region_body_transport_not_supported")
    else:  # pragma: no cover - enum cerrado
        raise SpsFacetWireError("sps_region_placement_invalid")

    return PreparedSpsFacetWireRequest(
        method="GET",
        placement=placement,
        wire_key=wire_key,
        base_request_digest=execution.structural_request.canonical_request_sha256,
        url=url,
        headers=headers,
        binding_source_key=execution.binding.source_key,
    )
