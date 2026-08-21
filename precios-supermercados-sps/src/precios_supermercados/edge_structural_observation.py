"""Frontera criptográfica para las observaciones estructurales de La Colonia.

Compone request canónico, receipt Ed25519, bytes exactos y body GraphQL validado.
La firma se verifica antes de parsear el body. El resultado prueba integridad y
coherencia interna respecto de una clave pública confiable, pero no demuestra
por sí solo independencia física/productiva.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import NoReturn

from precios_supermercados.la_colonia_edge_structural_body import (
    LaColoniaEdgeStructuralBodyError,
    ValidatedStructuralDiscoveryBody,
    validate_la_colonia_structural_body,
)
from precios_supermercados.la_colonia_edge_structural_request import (
    LaColoniaEdgeStructuralRequestError,
    ValidatedLaColoniaStructuralRequest,
    validate_la_colonia_structural_request,
)
from precios_supermercados.structural_provenance import SignedStructuralReceipt
from precios_supermercados.structural_receipt_crypto import (
    Ed25519StructuralReceiptVerifier,
    StructuralReceiptCryptoError,
    VerifiedStructuralReceipt,
)


class EdgeStructuralObservationError(ValueError):
    """El request, receipt o body estructural no forman una evidencia coherente."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise EdgeStructuralObservationError(code, message)


@dataclass(frozen=True, slots=True)
class CryptographicallyVerifiedStructuralObservation:
    """Una respuesta estructural autenticada y validada, aún no productiva."""

    request: ValidatedLaColoniaStructuralRequest
    body: ValidatedStructuralDiscoveryBody
    verified_receipt: VerifiedStructuralReceipt
    raw_body_sha256: str
    cryptographic_signature_verified: bool = True
    structural_body_validated: bool = True
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.request, ValidatedLaColoniaStructuralRequest):
            _fail("structural_observation_request_invalid")
        if not isinstance(self.body, ValidatedStructuralDiscoveryBody):
            _fail("structural_observation_body_invalid")
        if not isinstance(self.verified_receipt, VerifiedStructuralReceipt):
            _fail("structural_observation_receipt_invalid")
        if self.cryptographic_signature_verified is not True:
            _fail("structural_observation_signature_unverified")
        if self.structural_body_validated is not True:
            _fail("structural_observation_body_unvalidated")
        if self.production_authority is not False:
            _fail("structural_observation_production_authority_forbidden")

    @property
    def request_kind(self) -> str:
        return self.request.request_kind

    @property
    def source_url(self) -> str:
        return self.request.source_url

    @property
    def normalized_payload(self):
        return self.body.normalized_payload

    @property
    def records_filtered(self) -> int:
        return self.body.records_filtered


class EdgeStructuralObservationVerifier:
    """Revalida de forma independiente todas las capas de facet discovery."""

    def __init__(self, receipt_verifier: Ed25519StructuralReceiptVerifier) -> None:
        if not isinstance(receipt_verifier, Ed25519StructuralReceiptVerifier):
            _fail("structural_receipt_verifier_invalid")
        self._receipt_verifier = receipt_verifier

    def verify(
        self,
        *,
        source_url: str,
        raw_body: bytes,
        signed_receipt: SignedStructuralReceipt,
    ) -> CryptographicallyVerifiedStructuralObservation:
        if not isinstance(signed_receipt, SignedStructuralReceipt):
            _fail("structural_signed_receipt_invalid")
        if not isinstance(raw_body, bytes):
            _fail("structural_raw_body_invalid")

        # Autenticamos primero el receipt. El body de origen no se parsea hasta
        # que la metadata que lo describe haya superado Ed25519.
        try:
            verified_receipt = self._receipt_verifier.verify(signed_receipt)
        except StructuralReceiptCryptoError as exc:
            raise EdgeStructuralObservationError(f"structural_receipt_crypto_{exc.code}") from exc

        try:
            request = validate_la_colonia_structural_request(source_url)
        except LaColoniaEdgeStructuralRequestError as exc:
            raise EdgeStructuralObservationError(f"structural_request_{exc.code}") from exc

        payload = verified_receipt.receipt.payload
        if payload.request_kind != request.request_kind:
            _fail("structural_receipt_request_kind_mismatch")
        if payload.request_digest != request.canonical_request_sha256:
            _fail("structural_receipt_request_digest_mismatch")
        if payload.canonical_request_sha256 != request.canonical_request_sha256:
            _fail("structural_receipt_canonical_request_digest_mismatch")
        if payload.graphql_query_sha256 != request.graphql_query_sha256:
            _fail("structural_receipt_graphql_query_digest_mismatch")
        if payload.http_method != "GET":
            _fail("structural_receipt_http_method_mismatch")
        if (
            payload.target_scheme != "https"
            or payload.target_host != "www.lacolonia.com"
            or payload.target_path != "/_v/segment/graphql/v1"
        ):
            _fail("structural_receipt_target_mismatch")
        if payload.response_status != 200:
            _fail("structural_receipt_status_mismatch")

        raw_body_sha256 = hashlib.sha256(raw_body).hexdigest()
        if payload.raw_response_sha256 != raw_body_sha256:
            _fail("structural_receipt_raw_body_hash_mismatch")
        if payload.response_body_bytes != len(raw_body):
            _fail("structural_receipt_raw_body_size_mismatch")

        try:
            body = validate_la_colonia_structural_body(raw_body, request)
        except LaColoniaEdgeStructuralBodyError as exc:
            raise EdgeStructuralObservationError(f"structural_body_{exc.code}") from exc
        if body.request_kind != request.request_kind:
            _fail("structural_body_request_kind_mismatch")

        return CryptographicallyVerifiedStructuralObservation(
            request=request,
            body=body,
            verified_receipt=verified_receipt,
            raw_body_sha256=raw_body_sha256,
        )
