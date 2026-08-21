"""Verificación criptográfica Ed25519 de receipts edge v2.

La clave privada nunca participa en esta capa. El caller inyecta un keyring de
claves públicas SPKI previamente confiadas y el verifier comprueba exactamente
los bytes firmados por el Worker Cloudflare. Una firma válida demuestra
integridad/autenticidad respecto de esa clave, pero por sí sola NO concede
`production_authority` ni aceptación comercial.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import NoReturn

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_der_public_key

from precios_supermercados.edge_provenance import SignedEdgeReceipt

RECEIPT_SIGNATURE_DOMAIN = b"precios-sps/edge-receipt-signature/v2\0"
_B64URL = re.compile(r"[A-Za-z0-9_-]+\Z")


class EdgeReceiptCryptoError(ValueError):
    """Fallo de configuración o verificación criptográfica."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise EdgeReceiptCryptoError(code, message)


def _canonical_b64url_decode(value: object, code: str, *, max_length: int) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > max_length
        or value.strip() != value
        or "=" in value
        or "+" in value
        or "/" in value
        or not _B64URL.fullmatch(value)
    ):
        _fail(code)
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EdgeReceiptCryptoError(code) from exc
    if not decoded:
        _fail(code)
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if canonical != value:
        _fail(code)
    return decoded


def receipt_signing_bytes(receipt: SignedEdgeReceipt) -> bytes:
    if not isinstance(receipt, SignedEdgeReceipt):
        _fail("receipt_type_invalid")
    return RECEIPT_SIGNATURE_DOMAIN + receipt.payload.canonical_bytes()


@dataclass(frozen=True, slots=True)
class TrustedEd25519PublicKey:
    key_id: str
    public_key: Ed25519PublicKey
    spki_sha256: str


@dataclass(frozen=True, slots=True)
class CryptographicallyVerifiedEdgeReceipt:
    receipt: SignedEdgeReceipt
    signing_key_id: str
    public_key_spki_sha256: str
    receipt_digest: str
    cryptographic_signature_verified: bool = True
    production_authority: bool = False


class Ed25519ReceiptVerifier:
    """Keyring inmutable de claves públicas permitidas para receipts edge."""

    def __init__(self, public_keys_spki_b64url: Mapping[str, str]) -> None:
        if not isinstance(public_keys_spki_b64url, Mapping) or not public_keys_spki_b64url:
            _fail("public_keyring_invalid")

        parsed: dict[str, TrustedEd25519PublicKey] = {}
        for raw_key_id, raw_spki in public_keys_spki_b64url.items():
            if (
                not isinstance(raw_key_id, str)
                or not raw_key_id
                or raw_key_id.strip() != raw_key_id
                or any(char.isspace() for char in raw_key_id)
                or len(raw_key_id) > 256
            ):
                _fail("public_key_id_invalid")
            der = _canonical_b64url_decode(
                raw_spki,
                "public_key_spki_invalid",
                max_length=4096,
            )
            try:
                loaded = load_der_public_key(der)
            except (TypeError, ValueError) as exc:
                raise EdgeReceiptCryptoError("public_key_spki_invalid") from exc
            if not isinstance(loaded, Ed25519PublicKey):
                _fail("public_key_algorithm_invalid")
            parsed[raw_key_id] = TrustedEd25519PublicKey(
                key_id=raw_key_id,
                public_key=loaded,
                spki_sha256=hashlib.sha256(der).hexdigest(),
            )

        self._keys = MappingProxyType(parsed)

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def verify(self, receipt: SignedEdgeReceipt) -> CryptographicallyVerifiedEdgeReceipt:
        if not isinstance(receipt, SignedEdgeReceipt):
            _fail("receipt_type_invalid")
        if receipt.payload.signing_algorithm != "Ed25519":
            _fail("receipt_signing_algorithm_invalid")

        trusted_key = self._keys.get(receipt.payload.signing_key_id)
        if trusted_key is None:
            _fail("receipt_signing_key_untrusted")

        signature = _canonical_b64url_decode(
            receipt.signature_b64url,
            "receipt_signature_invalid",
            max_length=1024,
        )
        if len(signature) != 64:
            _fail("receipt_signature_length_invalid")

        try:
            trusted_key.public_key.verify(signature, receipt_signing_bytes(receipt))
        except InvalidSignature as exc:
            raise EdgeReceiptCryptoError("receipt_signature_invalid") from exc

        return CryptographicallyVerifiedEdgeReceipt(
            receipt=receipt,
            signing_key_id=trusted_key.key_id,
            public_key_spki_sha256=trusted_key.spki_sha256,
            receipt_digest=receipt.digest,
        )
