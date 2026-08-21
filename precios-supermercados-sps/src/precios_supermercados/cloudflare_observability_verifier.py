"""Verifier offline-first para correlacionar receipts con Workers Observability.

Este módulo no implementa HTTP. El transporte hacia la API de Cloudflare debe
inyectarse explícitamente y el token se recibe por llamada, nunca se persiste.
El resultado continúa con ``production_authority=False``: usar una API real no
basta hasta demostrar separación de credenciales/identidad y validar la forma
real de la telemetría desplegada.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from typing import NoReturn, Protocol

from precios_supermercados.cloudflare_observability_adapter import (
    MAX_QUERY_EVENTS,
    CloudflareObservabilityAdapterError,
    build_cloudflare_trace_detail_query,
    build_cloudflare_trace_discovery_query,
    parse_cloudflare_trace_detail_response,
    parse_cloudflare_trace_discovery_response,
)
from precios_supermercados.cloudflare_trace_evidence import (
    CloudflareTraceEvidenceError,
    PlatformReconciledEdgePage,
    reconcile_cloudflare_origin_trace,
)
from precios_supermercados.edge_crypto_page import CryptographicallyVerifiedEdgeCatalogPage

OBSERVABILITY_QUERY_PATH_TEMPLATE = "/accounts/{account_id}/workers/observability/telemetry/query"
QUERY_WINDOW_MARGIN = timedelta(seconds=30)
MAX_DETAIL_QUERIES = MAX_QUERY_EVENTS

_ACCOUNT_ID = re.compile(r"[0-9a-f]{32}\Z")


class CloudflareObservabilityVerifierError(ValueError):
    """Fallo de transporte, fencing o reconciliación del verifier."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CloudflareObservabilityVerifierError(code, message)


def _account_id(value: object) -> str:
    if not isinstance(value, str) or not _ACCOUNT_ID.fullmatch(value):
        _fail("account_id_invalid")
    return value


def _bearer(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 20_000
        or any(character.isspace() for character in value)
    ):
        _fail("bearer_token_invalid")
    return value


class CloudflareObservabilityTransport(Protocol):
    """Única frontera de I/O; la implementación productiva vive fuera del core."""

    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class CloudflareObservabilityVerifierClient:
    """Consulta discovery/detail y reconcilia telemetría contra un receipt firmado."""

    def __init__(
        self,
        account_id: str,
        transport: CloudflareObservabilityTransport,
    ) -> None:
        self._account_id = _account_id(account_id)
        if transport is None or not callable(getattr(transport, "post_json", None)):
            _fail("transport_invalid")
        self._transport = transport
        self._path = OBSERVABILITY_QUERY_PATH_TEMPLATE.format(account_id=self._account_id)

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def query_path(self) -> str:
        return self._path

    def _post(
        self,
        payload: Mapping[str, object],
        *,
        bearer_token: str,
    ) -> Mapping[str, object]:
        try:
            response = self._transport.post_json(
                self._path,
                bearer_token=bearer_token,
                payload=payload,
            )
        except Exception as exc:
            raise CloudflareObservabilityVerifierError("observability_transport_error") from exc
        if not isinstance(response, Mapping):
            _fail("observability_transport_response_invalid")
        return response

    def reconcile_page(
        self,
        page: CryptographicallyVerifiedEdgeCatalogPage,
        *,
        bearer_token: str,
    ) -> PlatformReconciledEdgePage:
        """Obtiene la telemetría mínima necesaria y exige una única coincidencia."""

        if not isinstance(page, CryptographicallyVerifiedEdgeCatalogPage):
            _fail("crypto_page_invalid")
        if page.cryptographic_signature_verified is not True:
            _fail("crypto_page_signature_unverified")
        token = _bearer(bearer_token)
        receipt_payload = page.verified_receipt.receipt.payload
        start = receipt_payload.physical_started_at_utc - QUERY_WINDOW_MARGIN
        end = receipt_payload.response_completed_at_utc + QUERY_WINDOW_MARGIN

        try:
            discovery_query = build_cloudflare_trace_discovery_query(
                from_utc=start,
                to_utc=end,
                authorization_id=receipt_payload.authorization_id,
                run_id=receipt_payload.run_id,
            )
            discovery_response = self._post(discovery_query, bearer_token=token)
            trace_ids = parse_cloudflare_trace_discovery_response(
                discovery_response,
                authorization_id=receipt_payload.authorization_id,
                run_id=receipt_payload.run_id,
            )
        except CloudflareObservabilityAdapterError as exc:
            raise CloudflareObservabilityVerifierError(f"discovery_{exc.code}") from exc

        if len(trace_ids) > MAX_DETAIL_QUERIES:
            _fail("trace_count_above_limit")

        candidates = []
        for trace_id in trace_ids:
            try:
                detail_query = build_cloudflare_trace_detail_query(
                    from_utc=start,
                    to_utc=end,
                    trace_id=trace_id,
                )
                detail_response = self._post(detail_query, bearer_token=token)
                candidates.extend(
                    parse_cloudflare_trace_detail_response(
                        detail_response,
                        expected_trace_id=trace_id,
                    )
                )
            except CloudflareObservabilityAdapterError as exc:
                raise CloudflareObservabilityVerifierError(f"detail_{exc.code}") from exc

        try:
            return reconcile_cloudflare_origin_trace(page, candidates)
        except CloudflareTraceEvidenceError as exc:
            raise CloudflareObservabilityVerifierError(f"reconciliation_{exc.code}") from exc
