"""Cliente Python offline-first para el gateway edge de provenance.

El módulo no contiene un transporte HTTP productivo ni una URL desplegada. El
caller debe inyectar explícitamente un transporte. La capa valida el contrato
del Worker, reconcilia la evidencia contra el request esperado y recalcula
hashes/identificadores, pero NO convierte esa coherencia en autoridad
productiva ni en aceptación comercial.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Protocol, TypeAlias

from precios_supermercados.edge_provenance import (
    EdgeReceiptPayload,
    SignedEdgeReceipt,
    canonical_json_bytes,
)

INITIALIZE_PATH = "/v1/initialize"
EXECUTE_PATH = "/v1/execute"
MAX_AUTHORIZATION_LIFETIME_MS = 45 * 60 * 1000
MAX_REQUESTS = 1000
MAX_RAW_BODY_BYTES = 1_500_000

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OPAQUE = re.compile(r"[^\s]{1,256}\Z")
_RUN_ID = re.compile(r"[0-9]+:[1-9][0-9]*\Z")
_B64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
_ALLOWED_ROLES = {"primary", "reconciliation"}


class EdgeGatewayClientError(ValueError):
    """Fallo estructural o de reconciliación del contrato edge."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> "NoReturn":  # type: ignore[name-defined]
    raise EdgeGatewayClientError(code, message)


# Importado tarde sólo para no mezclarlo con las dependencias de runtime.
from typing import NoReturn


def _exact_keys(value: object, expected: set[str], code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(code)
    actual = set(value)
    if actual != expected:
        _fail(code)
    return value


def _text(value: object, code: str, *, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        _fail(code)
    if len(value) > max_length:
        _fail(code)
    return value


def _opaque(value: object, code: str) -> str:
    text = _text(value, code, max_length=256)
    if not _OPAQUE.fullmatch(text):
        _fail(code)
    return text


def _sha1(value: object, code: str) -> str:
    text = _text(value, code, max_length=40)
    if not _SHA1.fullmatch(text):
        _fail(code)
    return text


def _sha256(value: object, code: str) -> str:
    text = _text(value, code, max_length=64)
    if not _SHA256.fullmatch(text):
        _fail(code)
    return text


def _integer(value: object, code: str, *, minimum: int = 0, maximum: int = 2**53 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(code)
    if value < minimum or value > maximum:
        _fail(code)
    return value


def _canonical_b64url_decode(value: object, code: str, *, allow_empty: bool = False) -> bytes:
    text = _text(value, code, max_length=3_000_000)
    if "=" in text or "+" in text or "/" in text or not _B64URL.fullmatch(text):
        _fail(code)
    padding = "=" * ((4 - len(text) % 4) % 4)
    try:
        decoded = base64.b64decode(text + padding, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EdgeGatewayClientError(code) from exc
    if not decoded and not allow_empty:
        _fail(code)
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if canonical != text:
        _fail(code)
    return decoded


def _parse_timestamp(value: object, code: str) -> datetime:
    text = _text(value, code, max_length=64)
    if not text.endswith("Z"):
        _fail(code)
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise EdgeGatewayClientError(code) from exc
    if parsed.tzinfo is None:
        _fail(code)
    return parsed


def _worker_evidence_id(payload: Mapping[str, object], signature_b64url: str) -> str:
    material = canonical_json_bytes(dict(payload)) + b"\0" + signature_b64url.encode("ascii")
    return hashlib.sha256(material).hexdigest()


class EdgeGatewayTransport(Protocol):
    """Transporte explícitamente inyectado; este módulo nunca abre red por sí solo."""

    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class EdgeAuthorizationRequest:
    authorization_id: str
    run_id: str
    approved_commit_sha: str
    created_at_ms: int
    expires_at_ms: int
    max_requests: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "authorization_id", _opaque(self.authorization_id, "authorization_id_invalid"))
        run_id = _opaque(self.run_id, "run_id_invalid")
        if not _RUN_ID.fullmatch(run_id):
            _fail("run_id_invalid")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "approved_commit_sha", _sha1(self.approved_commit_sha, "approved_commit_sha_invalid"))
        created = _integer(self.created_at_ms, "created_at_ms_invalid", minimum=1)
        expires = _integer(self.expires_at_ms, "expires_at_ms_invalid", minimum=created + 1)
        if expires - created > MAX_AUTHORIZATION_LIFETIME_MS:
            _fail("authorization_lifetime_above_limit")
        _integer(self.max_requests, "max_requests_invalid", minimum=1, maximum=MAX_REQUESTS)

    def wire_payload(self) -> dict[str, object]:
        return {
            "authorization": {
                "authorizationId": self.authorization_id,
                "runId": self.run_id,
                "approvedCommitSha": self.approved_commit_sha,
                "createdAtMs": self.created_at_ms,
                "expiresAtMs": self.expires_at_ms,
                "maxRequests": self.max_requests,
            }
        }


@dataclass(frozen=True, slots=True)
class EdgeRequestContext:
    authorization_id: str
    run_id: str
    approved_commit_sha: str
    reservation_id: str
    request_id: str
    request_digest: str
    nonce: str
    traversal_role: str
    traversal_id: str
    partition_id: str

    def __post_init__(self) -> None:
        for name in (
            "authorization_id",
            "reservation_id",
            "request_id",
            "nonce",
            "traversal_id",
            "partition_id",
        ):
            object.__setattr__(self, name, _opaque(getattr(self, name), f"{name}_invalid"))
        run_id = _opaque(self.run_id, "run_id_invalid")
        if not _RUN_ID.fullmatch(run_id):
            _fail("run_id_invalid")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "approved_commit_sha", _sha1(self.approved_commit_sha, "approved_commit_sha_invalid"))
        object.__setattr__(self, "request_digest", _sha256(self.request_digest, "request_digest_invalid"))
        if self.traversal_role not in _ALLOWED_ROLES:
            _fail("traversal_role_invalid")

    def wire_dict(self) -> dict[str, object]:
        return {
            "authorizationId": self.authorization_id,
            "runId": self.run_id,
            "approvedCommitSha": self.approved_commit_sha,
            "reservationId": self.reservation_id,
            "requestId": self.request_id,
            "requestDigest": self.request_digest,
            "nonce": self.nonce,
            "traversalRole": self.traversal_role,
            "traversalId": self.traversal_id,
            "partitionId": self.partition_id,
        }


@dataclass(frozen=True, slots=True)
class EdgeExecutionRequest:
    origin_url: str
    context: EdgeRequestContext

    def __post_init__(self) -> None:
        url = _text(self.origin_url, "origin_url_invalid", max_length=20_000)
        if not url.startswith("https://"):
            _fail("origin_url_invalid")
        object.__setattr__(self, "origin_url", url)
        if not isinstance(self.context, EdgeRequestContext):
            _fail("request_context_invalid")

    def wire_payload(self) -> dict[str, object]:
        return {"originUrl": self.origin_url, "requestContext": self.context.wire_dict()}


@dataclass(frozen=True, slots=True)
class EdgeGatewayInitialized:
    authorization_id: str
    run_id: str
    state: str
    requests_used: int
    remaining_requests: int
    production_authority: bool = False


@dataclass(frozen=True, slots=True)
class EdgeGatewayWait:
    reason: str
    not_before_ms: int | None
    in_flight_reservation_id: str | None
    production_authority: bool = False


@dataclass(frozen=True, slots=True)
class EdgeGatewayDenied:
    reason: str
    production_authority: bool = False


@dataclass(frozen=True, slots=True)
class EdgeGatewayEvidence:
    response_status: int
    raw_body: bytes
    receipt: SignedEdgeReceipt
    worker_evidence_id: str
    replayed: bool
    cryptographic_signature_verified: bool = False
    production_authority: bool = False


EdgeExecutionResult: TypeAlias = EdgeGatewayEvidence | EdgeGatewayWait | EdgeGatewayDenied


class EdgeGatewayClient:
    """Adapta respuestas del Worker a evidencia Python fail-closed."""

    def __init__(self, transport: EdgeGatewayTransport) -> None:
        if transport is None or not callable(getattr(transport, "post_json", None)):
            _fail("transport_invalid")
        self._transport = transport

    @staticmethod
    def _bearer(value: object) -> str:
        token = _text(value, "bearer_token_invalid", max_length=20_000)
        if any(char.isspace() for char in token):
            _fail("bearer_token_invalid")
        return token

    def initialize(self, authorization: EdgeAuthorizationRequest, *, bearer_token: str) -> EdgeGatewayInitialized:
        if not isinstance(authorization, EdgeAuthorizationRequest):
            _fail("authorization_request_invalid")
        response = self._transport.post_json(
            INITIALIZE_PATH,
            bearer_token=self._bearer(bearer_token),
            payload=authorization.wire_payload(),
        )
        root = self._root_or_error(response)
        _exact_keys(root, {"ok", "decision", "authorization"}, "initialize_response_shape_invalid")
        if root["ok"] is not True or root["decision"] != "INITIALIZED":
            _fail("initialize_response_invalid")
        summary = _exact_keys(
            root["authorization"],
            {
                "authorizationId",
                "runId",
                "state",
                "maxRequests",
                "requestsUsed",
                "remainingRequests",
                "minStartIntervalMs",
                "lastPhysicalStartMs",
                "terminalAtMs",
                "terminalReason",
                "reservationCounts",
            },
            "initialize_summary_shape_invalid",
        )
        authorization_id = _opaque(summary["authorizationId"], "initialize_authorization_id_invalid")
        run_id = _opaque(summary["runId"], "initialize_run_id_invalid")
        if authorization_id != authorization.authorization_id or run_id != authorization.run_id:
            _fail("initialize_context_mismatch")
        max_requests = _integer(summary["maxRequests"], "initialize_max_requests_invalid", minimum=1, maximum=MAX_REQUESTS)
        if max_requests != authorization.max_requests:
            _fail("initialize_budget_mismatch")
        requests_used = _integer(summary["requestsUsed"], "initialize_requests_used_invalid", maximum=max_requests)
        remaining = _integer(summary["remainingRequests"], "initialize_remaining_requests_invalid", maximum=max_requests)
        if requests_used + remaining != max_requests:
            _fail("initialize_budget_accounting_invalid")
        state = _text(summary["state"], "initialize_state_invalid", max_length=32)
        if state not in {"active", "consumed", "rejected", "expired"}:
            _fail("initialize_state_invalid")
        return EdgeGatewayInitialized(
            authorization_id=authorization_id,
            run_id=run_id,
            state=state,
            requests_used=requests_used,
            remaining_requests=remaining,
        )

    def execute(self, request: EdgeExecutionRequest, *, bearer_token: str) -> EdgeExecutionResult:
        if not isinstance(request, EdgeExecutionRequest):
            _fail("execution_request_invalid")
        response = self._transport.post_json(
            EXECUTE_PATH,
            bearer_token=self._bearer(bearer_token),
            payload=request.wire_payload(),
        )
        root = self._root_or_error(response)
        decision = root.get("decision")
        if decision == "WAIT":
            return self._parse_wait(root)
        if decision == "DENY":
            return self._parse_deny(root)
        if decision in {"ORIGIN_COMPLETED", "REPLAY_COMPLETED"}:
            return self._parse_evidence(root, request)
        _fail("execute_decision_invalid")

    @staticmethod
    def _root_or_error(response: object) -> Mapping[str, object]:
        if not isinstance(response, Mapping):
            _fail("gateway_response_invalid")
        if response.get("ok") is False:
            root = _exact_keys(response, {"ok", "error"}, "gateway_error_shape_invalid")
            error = _opaque(root["error"], "gateway_error_code_invalid")
            raise EdgeGatewayClientError(f"gateway_{error}")
        if response.get("ok") is not True:
            _fail("gateway_response_invalid")
        return response

    @staticmethod
    def _parse_wait(root: Mapping[str, object]) -> EdgeGatewayWait:
        value = _exact_keys(
            root,
            {"ok", "decision", "reason", "notBeforeMs", "inFlightReservationId"},
            "wait_response_shape_invalid",
        )
        reason = _opaque(value["reason"], "wait_reason_invalid")
        not_before_raw = value["notBeforeMs"]
        not_before = None if not_before_raw is None else _integer(not_before_raw, "wait_not_before_invalid", minimum=1)
        inflight_raw = value["inFlightReservationId"]
        inflight = None if inflight_raw is None else _opaque(inflight_raw, "wait_inflight_reservation_invalid")
        return EdgeGatewayWait(reason=reason, not_before_ms=not_before, in_flight_reservation_id=inflight)

    @staticmethod
    def _parse_deny(root: Mapping[str, object]) -> EdgeGatewayDenied:
        value = _exact_keys(root, {"ok", "decision", "reason"}, "deny_response_shape_invalid")
        return EdgeGatewayDenied(reason=_opaque(value["reason"], "deny_reason_invalid"))

    @staticmethod
    def _parse_evidence(root: Mapping[str, object], request: EdgeExecutionRequest) -> EdgeGatewayEvidence:
        value = _exact_keys(
            root,
            {
                "ok",
                "decision",
                "replayed",
                "responseStatus",
                "rawBodyB64Url",
                "receiptPayload",
                "signatureB64Url",
                "signingKeyId",
                "evidenceId",
            },
            "evidence_response_shape_invalid",
        )
        replayed = value["replayed"]
        if not isinstance(replayed, bool):
            _fail("evidence_replayed_invalid")
        expected_replayed = value["decision"] == "REPLAY_COMPLETED"
        if replayed is not expected_replayed:
            _fail("evidence_replay_decision_mismatch")

        status = _integer(value["responseStatus"], "evidence_status_invalid", minimum=100, maximum=599)
        raw_body = _canonical_b64url_decode(value["rawBodyB64Url"], "evidence_raw_body_invalid")
        if len(raw_body) > MAX_RAW_BODY_BYTES:
            _fail("evidence_raw_body_above_limit")

        payload_source = _exact_keys(
            value["receiptPayload"],
            {field.name for field in fields(EdgeReceiptPayload)},
            "receipt_payload_shape_invalid",
        )
        payload_data = dict(payload_source)
        payload_data["physical_started_at_utc"] = _parse_timestamp(
            payload_data["physical_started_at_utc"],
            "receipt_physical_started_at_invalid",
        )
        payload_data["response_completed_at_utc"] = _parse_timestamp(
            payload_data["response_completed_at_utc"],
            "receipt_response_completed_at_invalid",
        )
        try:
            payload = EdgeReceiptPayload(**payload_data)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise EdgeGatewayClientError("receipt_payload_invalid") from exc
        if payload.canonical_dict() != dict(payload_source):
            _fail("receipt_payload_noncanonical")

        signature = _text(value["signatureB64Url"], "receipt_signature_invalid", max_length=1024)
        _canonical_b64url_decode(signature, "receipt_signature_invalid")
        signing_key_id = _opaque(value["signingKeyId"], "receipt_signing_key_id_invalid")
        if signing_key_id != payload.signing_key_id:
            _fail("receipt_signing_key_mismatch")
        try:
            receipt = SignedEdgeReceipt(payload=payload, signature_b64url=signature)
        except ValueError as exc:
            raise EdgeGatewayClientError("signed_receipt_invalid") from exc

        body_hash = hashlib.sha256(raw_body).hexdigest()
        if body_hash != payload.raw_response_sha256:
            _fail("receipt_raw_body_hash_mismatch")
        if len(raw_body) != payload.response_body_bytes:
            _fail("receipt_raw_body_size_mismatch")
        if status != payload.response_status:
            _fail("receipt_response_status_mismatch")
        if payload.canonical_request_sha256 != payload.request_digest:
            _fail("receipt_request_digest_mismatch")

        context = request.context
        expected_pairs = {
            "authorization_id": context.authorization_id,
            "run_id": context.run_id,
            "approved_commit_sha": context.approved_commit_sha,
            "reservation_id": context.reservation_id,
            "request_id": context.request_id,
            "request_digest": context.request_digest,
            "nonce": context.nonce,
            "traversal_role": context.traversal_role,
            "traversal_id": context.traversal_id,
            "partition_id": context.partition_id,
        }
        for name, expected in expected_pairs.items():
            if getattr(payload, name) != expected:
                _fail(f"receipt_{name}_context_mismatch")

        if payload.collector_provider != "cloudflare_workers":
            _fail("receipt_collector_provider_mismatch")
        expected_run_id = f"{payload.github_run_id}:{payload.github_run_attempt}"
        if payload.run_id != expected_run_id:
            _fail("receipt_github_run_fence_mismatch")

        evidence_id = _sha256(value["evidenceId"], "evidence_id_invalid")
        computed_evidence_id = _worker_evidence_id(payload_source, signature)
        if evidence_id != computed_evidence_id:
            _fail("evidence_id_mismatch")

        return EdgeGatewayEvidence(
            response_status=status,
            raw_body=raw_body,
            receipt=receipt,
            worker_evidence_id=evidence_id,
            replayed=replayed,
        )
