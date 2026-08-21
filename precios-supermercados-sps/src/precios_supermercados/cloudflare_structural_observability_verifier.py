"""Verifier offline-first de Workers Observability para facet discovery.

No implementa HTTP. El transporte se inyecta explícitamente y el bearer token se
recibe sólo durante la llamada. La reconciliación termina siempre con
``production_authority=False`` hasta cerrar la separación productiva real.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from typing import NoReturn, Protocol

from precios_supermercados.cloudflare_structural_observability_adapter import (
    MAX_QUERY_EVENTS,
    CloudflareStructuralObservabilityAdapterError,
    build_cloudflare_structural_trace_detail_query,
    build_cloudflare_structural_trace_discovery_query,
    parse_cloudflare_structural_trace_detail_response,
    parse_cloudflare_structural_trace_discovery_response,
)
from precios_supermercados.cloudflare_structural_trace_evidence import (
    CloudflareStructuralTraceEvidenceError,
    PlatformReconciledStructuralObservation,
    reconcile_cloudflare_structural_trace,
)
from precios_supermercados.edge_structural_observation import (
    CryptographicallyVerifiedStructuralObservation,
)

OBSERVABILITY_QUERY_PATH_TEMPLATE = "/accounts/{account_id}/workers/observability/telemetry/query"
QUERY_WINDOW_MARGIN = timedelta(seconds=30)
MAX_DETAIL_QUERIES = MAX_QUERY_EVENTS
_ACCOUNT_ID = re.compile(r"[0-9a-f]{32}\Z")


class CloudflareStructuralObservabilityVerifierError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CloudflareStructuralObservabilityVerifierError(code, message)


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


class CloudflareStructuralObservabilityTransport(Protocol):
    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class CloudflareStructuralObservabilityVerifierClient:
    """Consulta discovery/detail para una observación estructural autenticada."""

    def __init__(
        self,
        account_id: str,
        transport: CloudflareStructuralObservabilityTransport,
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
            raise CloudflareStructuralObservabilityVerifierError(
                "observability_transport_error"
            ) from exc
        if not isinstance(response, Mapping):
            _fail("observability_transport_response_invalid")
        return response

    def reconcile_observation(
        self,
        observation: CryptographicallyVerifiedStructuralObservation,
        *,
        bearer_token: str,
    ) -> PlatformReconciledStructuralObservation:
        if not isinstance(observation, CryptographicallyVerifiedStructuralObservation):
            _fail("structural_observation_invalid")
        if observation.cryptographic_signature_verified is not True:
            _fail("structural_observation_signature_unverified")
        if observation.structural_body_validated is not True:
            _fail("structural_observation_body_unvalidated")

        token = _bearer(bearer_token)
        receipt_payload = observation.verified_receipt.receipt.payload
        start = receipt_payload.physical_started_at_utc - QUERY_WINDOW_MARGIN
        end = receipt_payload.response_completed_at_utc + QUERY_WINDOW_MARGIN

        try:
            discovery_query = build_cloudflare_structural_trace_discovery_query(
                from_utc=start,
                to_utc=end,
                authorization_id=receipt_payload.authorization_id,
                run_id=receipt_payload.run_id,
                request_kind=receipt_payload.request_kind,
            )
            discovery_response = self._post(discovery_query, bearer_token=token)
            trace_ids = parse_cloudflare_structural_trace_discovery_response(
                discovery_response,
                authorization_id=receipt_payload.authorization_id,
                run_id=receipt_payload.run_id,
                request_kind=receipt_payload.request_kind,
            )
        except CloudflareStructuralObservabilityAdapterError as exc:
            raise CloudflareStructuralObservabilityVerifierError(
                f"discovery_{exc.code}"
            ) from exc

        if len(trace_ids) > MAX_DETAIL_QUERIES:
            _fail("trace_count_above_limit")

        candidates = []
        for trace_id in trace_ids:
            try:
                detail_query = build_cloudflare_structural_trace_detail_query(
                    from_utc=start,
                    to_utc=end,
                    trace_id=trace_id,
                )
                detail_response = self._post(detail_query, bearer_token=token)
                candidates.extend(
                    parse_cloudflare_structural_trace_detail_response(
                        detail_response,
                        expected_trace_id=trace_id,
                    )
                )
            except CloudflareStructuralObservabilityAdapterError as exc:
                raise CloudflareStructuralObservabilityVerifierError(
                    f"detail_{exc.code}"
                ) from exc

        try:
            return reconcile_cloudflare_structural_trace(observation, candidates)
        except CloudflareStructuralTraceEvidenceError as exc:
            raise CloudflareStructuralObservabilityVerifierError(
                f"reconciliation_{exc.code}"
            ) from exc
