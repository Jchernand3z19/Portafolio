"""Cliente fail-closed para ``/v1/structural-execute``.

v1 mantiene compatibilidad histórica; v2 exige provenance ligada al ``regionId``;
v3 exige además las señales de sesión VTEX confirmadas para SPS. Los valores raw
sólo viajan hacia el collector autenticado y nunca se aceptan de vuelta como
provenance pública.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from typing import NoReturn, Protocol, TypeAlias

from precios_supermercados.la_colonia_edge_structural_request import (
    LaColoniaEdgeStructuralRequestError,
    ValidatedLaColoniaStructuralRequest,
    validate_la_colonia_structural_request,
)
from precios_supermercados.structural_location_context import StructuralEdgeLocationContext
from precios_supermercados.structural_provenance import (
    SignedStructuralReceipt,
    StructuralProvenanceError,
    StructuralReceiptPayload,
)

STRUCTURAL_EXECUTE_PATH = "/v1/structural-execute"
MAX_RAW_BODY_BYTES = 1_500_000

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OPAQUE = re.compile(r"[^\s]{1,512}\Z")
_RUN_ID = re.compile(r"[0-9]+:[1-9][0-9]*\Z")
_B64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
_REQUEST_KINDS = {"root_total", "category_tree"}
_COMPLETED_DECISIONS = {"ORIGIN_COMPLETED", "REPLAY_COMPLETED"}
_LOCATION_FIELDS = {
    "location_id",
    "binding_source_key",
    "binding_evidence",
    "context_fingerprint",
    "context_placement",
    "context_wire_key",
    "context_value_path",
    "wire_request_fingerprint",
}
_SESSION_FIELDS = {
    "session_context_complete",
    "vtexsegment_fingerprint",
    "vtexsession_fingerprint",
}


class StructuralEdgeGatewayClientError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise StructuralEdgeGatewayClientError(code, message)


def _exact_keys(value: object, expected: set[str], code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != expected:
        _fail(code)
    return value


def _text(value: object, code: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > maximum:
        _fail(code)
    return value


def _opaque(value: object, code: str, *, maximum: int = 512) -> str:
    text = _text(value, code, maximum=maximum)
    if not _OPAQUE.fullmatch(text):
        _fail(code)
    return text


def _sha1(value: object, code: str) -> str:
    text = _text(value, code, maximum=40)
    if not _SHA1.fullmatch(text):
        _fail(code)
    return text


def _sha256(value: object, code: str) -> str:
    text = _text(value, code, maximum=64)
    if not _SHA256.fullmatch(text):
        _fail(code)
    return text


def _int(value: object, code: str, *, minimum: int = 0, maximum: int = 2**53 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail(code)
    return value


def _optional_int(value: object, code: str) -> int | None:
    if value is None:
        return None
    return _int(value, code, minimum=1)


def _canonical_b64url_decode(value: object, code: str, *, maximum: int = 3_000_000) -> bytes:
    text = _text(value, code, maximum=maximum)
    if "=" in text or "+" in text or "/" in text or not _B64URL.fullmatch(text):
        _fail(code)
    padding = "=" * ((4 - len(text) % 4) % 4)
    try:
        decoded = base64.b64decode(text + padding, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise StructuralEdgeGatewayClientError(code) from exc
    if not decoded:
        _fail(code)
    if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != text:
        _fail(code)
    return decoded


def _timestamp(value: object, code: str) -> datetime:
    text = _text(value, code, maximum=64)
    if not text.endswith("Z"):
        _fail(code)
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise StructuralEdgeGatewayClientError(code) from exc
    if parsed.tzinfo is None:
        _fail(code)
    return parsed


def _validated_origin(value: object) -> ValidatedLaColoniaStructuralRequest:
    if not isinstance(value, str):
        _fail("origin_url_invalid")
    try:
        return validate_la_colonia_structural_request(value)
    except LaColoniaEdgeStructuralRequestError as exc:
        raise StructuralEdgeGatewayClientError(f"origin_request_{exc.code}") from exc


def _parse_receipt_payload(value: object) -> StructuralReceiptPayload:
    if not isinstance(value, Mapping):
        _fail("structural_receipt_payload_shape_invalid")
    all_names = {item.name for item in fields(StructuralReceiptPayload)}
    base_names = all_names - _LOCATION_FIELDS - _SESSION_FIELDS
    schema = value.get("schema_version")
    if schema == "1":
        expected = base_names
    elif schema == "2":
        expected = base_names | _LOCATION_FIELDS
    elif schema == "3":
        expected = all_names
    else:
        expected = set()
    if not expected or set(value) != expected:
        _fail("structural_receipt_payload_shape_invalid")

    payload = dict(value)
    payload["physical_started_at_utc"] = _timestamp(
        payload.get("physical_started_at_utc"),
        "structural_receipt_physical_started_at_invalid",
    )
    payload["response_completed_at_utc"] = _timestamp(
        payload.get("response_completed_at_utc"),
        "structural_receipt_response_completed_at_invalid",
    )
    if schema in {"2", "3"}:
        path = payload.get("context_value_path")
        if not isinstance(path, list) or any(not isinstance(item, str) for item in path):
            _fail("structural_receipt_context_value_path_invalid")
        payload["context_value_path"] = tuple(path)
    try:
        return StructuralReceiptPayload(**payload)  # type: ignore[arg-type]
    except StructuralProvenanceError as exc:
        raise StructuralEdgeGatewayClientError(f"structural_receipt_{exc.code}") from exc


class StructuralEdgeGatewayTransport(Protocol):
    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class StructuralEdgeRequestContext:
    authorization_id: str
    run_id: str
    approved_commit_sha: str
    reservation_id: str
    request_id: str
    request_digest: str
    nonce: str
    request_kind: str

    def __post_init__(self) -> None:
        for name in ("authorization_id", "reservation_id", "request_id", "nonce"):
            object.__setattr__(self, name, _opaque(getattr(self, name), f"{name}_invalid"))
        run_id = _opaque(self.run_id, "run_id_invalid")
        if not _RUN_ID.fullmatch(run_id):
            _fail("run_id_invalid")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(
            self,
            "approved_commit_sha",
            _sha1(self.approved_commit_sha, "approved_commit_sha_invalid"),
        )
        object.__setattr__(
            self,
            "request_digest",
            _sha256(self.request_digest, "request_digest_invalid"),
        )
        if self.request_kind not in _REQUEST_KINDS:
            _fail("request_kind_invalid")

    def wire_dict(self) -> dict[str, object]:
        return {
            "authorizationId": self.authorization_id,
            "runId": self.run_id,
            "approvedCommitSha": self.approved_commit_sha,
            "reservationId": self.reservation_id,
            "requestId": self.request_id,
            "requestDigest": self.request_digest,
            "nonce": self.nonce,
            "requestKind": self.request_kind,
        }


@dataclass(frozen=True, slots=True)
class StructuralEdgeExecutionRequest:
    origin_url: str
    context: StructuralEdgeRequestContext
    location_context: StructuralEdgeLocationContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, StructuralEdgeRequestContext):
            _fail("request_context_invalid")
        if self.location_context is not None and not isinstance(
            self.location_context,
            StructuralEdgeLocationContext,
        ):
            _fail("location_context_invalid")
        origin = _validated_origin(self.origin_url)
        if origin.request_kind != self.context.request_kind:
            _fail("request_kind_origin_mismatch")
        if origin.canonical_request_sha256 != self.context.request_digest:
            _fail("request_digest_origin_mismatch")
        object.__setattr__(self, "origin_url", origin.source_url)

    def wire_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "originUrl": self.origin_url,
            "requestContext": self.context.wire_dict(),
        }
        if self.location_context is not None:
            payload["locationContext"] = self.location_context.wire_dict()
        return payload


@dataclass(frozen=True, slots=True)
class StructuralEdgeGatewayWait:
    reason: str
    not_before_ms: int | None
    in_flight_reservation_id: str | None
    production_authority: bool = False


@dataclass(frozen=True, slots=True)
class StructuralEdgeGatewayDenied:
    reason: str
    production_authority: bool = False


@dataclass(frozen=True, slots=True)
class StructuralEdgeGatewayEvidence:
    response_status: int
    raw_body: bytes
    receipt: SignedStructuralReceipt
    worker_evidence_id: str
    replayed: bool
    cryptographic_signature_verified: bool = False
    production_authority: bool = False


StructuralEdgeExecutionResult: TypeAlias = (
    StructuralEdgeGatewayEvidence | StructuralEdgeGatewayWait | StructuralEdgeGatewayDenied
)


class StructuralEdgeGatewayClient:
    def __init__(self, transport: StructuralEdgeGatewayTransport) -> None:
        if transport is None or not callable(getattr(transport, "post_json", None)):
            _fail("transport_invalid")
        self._transport = transport

    @staticmethod
    def _bearer(value: object) -> str:
        token = _text(value, "bearer_token_invalid", maximum=20_000)
        if any(character.isspace() for character in token):
            _fail("bearer_token_invalid")
        return token

    @staticmethod
    def _root(response: object) -> Mapping[str, object]:
        if not isinstance(response, Mapping):
            _fail("transport_response_invalid")
        if response.get("ok") is not True:
            error = response.get("error")
            if isinstance(error, str) and error:
                _fail(f"worker_{error}")
            _fail("worker_error_response_invalid")
        return response

    def execute(
        self,
        request: StructuralEdgeExecutionRequest,
        *,
        bearer_token: str,
    ) -> StructuralEdgeExecutionResult:
        if not isinstance(request, StructuralEdgeExecutionRequest):
            _fail("execution_request_invalid")
        try:
            response = self._transport.post_json(
                STRUCTURAL_EXECUTE_PATH,
                bearer_token=self._bearer(bearer_token),
                payload=request.wire_payload(),
            )
        except StructuralEdgeGatewayClientError:
            raise
        except Exception as exc:
            raise StructuralEdgeGatewayClientError("transport_error") from exc
        root = self._root(response)
        decision = root.get("decision")
        if decision in _COMPLETED_DECISIONS:
            return self._completed(root, request)
        if decision == "WAIT":
            return self._wait(root)
        if decision == "DENY":
            return self._denied(root)
        _fail("execution_decision_invalid")

    @staticmethod
    def _wait(root: Mapping[str, object]) -> StructuralEdgeGatewayWait:
        source = _exact_keys(
            root,
            {"ok", "decision", "reason", "notBeforeMs", "inFlightReservationId"},
            "wait_response_shape_invalid",
        )
        reason = _opaque(source.get("reason"), "wait_reason_invalid")
        in_flight = source.get("inFlightReservationId")
        if in_flight is not None:
            in_flight = _opaque(in_flight, "wait_in_flight_reservation_invalid")
        return StructuralEdgeGatewayWait(
            reason=reason,
            not_before_ms=_optional_int(source.get("notBeforeMs"), "wait_not_before_invalid"),
            in_flight_reservation_id=in_flight,
        )

    @staticmethod
    def _denied(root: Mapping[str, object]) -> StructuralEdgeGatewayDenied:
        source = _exact_keys(
            root,
            {"ok", "decision", "reason"},
            "deny_response_shape_invalid",
        )
        return StructuralEdgeGatewayDenied(
            reason=_opaque(source.get("reason"), "deny_reason_invalid")
        )

    @staticmethod
    def _completed(
        root: Mapping[str, object],
        request: StructuralEdgeExecutionRequest,
    ) -> StructuralEdgeGatewayEvidence:
        source = _exact_keys(
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
            "completed_response_shape_invalid",
        )
        decision = source.get("decision")
        replayed = source.get("replayed")
        if not isinstance(replayed, bool):
            _fail("completed_replayed_invalid")
        if replayed is not (decision == "REPLAY_COMPLETED"):
            _fail("completed_replay_decision_mismatch")
        status = _int(
            source.get("responseStatus"),
            "completed_status_invalid",
            minimum=100,
            maximum=599,
        )
        if status != 200:
            _fail("completed_status_invalid")
        raw_body = _canonical_b64url_decode(
            source.get("rawBodyB64Url"),
            "completed_body_invalid",
        )
        if len(raw_body) > MAX_RAW_BODY_BYTES:
            _fail("completed_body_above_limit")
        signature = _text(
            source.get("signatureB64Url"),
            "completed_signature_invalid",
            maximum=1024,
        )
        if len(
            _canonical_b64url_decode(
                signature,
                "completed_signature_invalid",
                maximum=1024,
            )
        ) != 64:
            _fail("completed_signature_length_invalid")
        signing_key_id = _opaque(
            source.get("signingKeyId"),
            "completed_signing_key_id_invalid",
        )
        evidence_id = _sha256(
            source.get("evidenceId"),
            "completed_evidence_id_invalid",
        )
        payload = _parse_receipt_payload(source.get("receiptPayload"))
        if payload.signing_key_id != signing_key_id:
            _fail("completed_signing_key_mismatch")

        context = request.context
        for attr, expected in (
            ("authorization_id", context.authorization_id),
            ("run_id", context.run_id),
            ("approved_commit_sha", context.approved_commit_sha),
            ("reservation_id", context.reservation_id),
            ("request_id", context.request_id),
            ("request_digest", context.request_digest),
            ("nonce", context.nonce),
            ("request_kind", context.request_kind),
        ):
            if getattr(payload, attr) != expected:
                _fail(f"completed_{attr}_mismatch")

        origin = _validated_origin(request.origin_url)
        if payload.canonical_request_sha256 != origin.canonical_request_sha256:
            _fail("completed_canonical_request_mismatch")
        if payload.graphql_query_sha256 != origin.graphql_query_sha256:
            _fail("completed_graphql_query_mismatch")
        if payload.response_status != status:
            _fail("completed_receipt_status_mismatch")
        if payload.raw_response_sha256 != hashlib.sha256(raw_body).hexdigest():
            _fail("completed_body_hash_mismatch")
        if payload.response_body_bytes != len(raw_body):
            _fail("completed_body_size_mismatch")

        requested_location = request.location_context
        if requested_location is None:
            if payload.location_context_bound:
                _fail("completed_unrequested_location_context")
        else:
            if not payload.location_context_bound:
                _fail("completed_location_context_missing")
            if requested_location.session_context_complete:
                if not payload.session_context_bound:
                    _fail("completed_session_context_missing")
            elif payload.session_context_bound:
                _fail("completed_unrequested_session_context")

            expected_location = requested_location.public_dict()
            for attr, expected in (
                ("location_id", expected_location["location_id"]),
                ("binding_source_key", expected_location["binding_source_key"]),
                ("binding_evidence", expected_location["binding_evidence"]),
                ("context_fingerprint", expected_location["context_fingerprint"]),
                ("context_placement", expected_location["placement"]),
                ("context_wire_key", expected_location["wire_key"]),
                ("context_value_path", tuple(expected_location["value_path"])),
                (
                    "wire_request_fingerprint",
                    expected_location["wire_request_fingerprint"],
                ),
            ):
                if getattr(payload, attr) != expected:
                    _fail(f"completed_{attr}_mismatch")

            if requested_location.session_context_complete:
                session = requested_location.session_context
                assert session is not None
                expected_signals = dict(session.signal_fingerprints)
                if payload.session_context_complete is not True:
                    _fail("completed_session_context_incomplete")
                if payload.vtexsegment_fingerprint != expected_signals["vtexsegment"]:
                    _fail("completed_vtexsegment_fingerprint_mismatch")
                if payload.vtexsession_fingerprint != expected_signals["vtexsession"]:
                    _fail("completed_vtexsession_fingerprint_mismatch")

        try:
            receipt = SignedStructuralReceipt(
                payload=payload,
                signature_b64url=signature,
            )
        except StructuralProvenanceError as exc:
            raise StructuralEdgeGatewayClientError(f"signed_receipt_{exc.code}") from exc
        if receipt.digest != evidence_id:
            _fail("completed_evidence_id_mismatch")
        return StructuralEdgeGatewayEvidence(
            response_status=status,
            raw_body=raw_body,
            receipt=receipt,
            worker_evidence_id=evidence_id,
            replayed=replayed,
        )
