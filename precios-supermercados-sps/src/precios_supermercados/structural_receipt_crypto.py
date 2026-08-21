"""Verificación Ed25519 de receipts de facet discovery.

Usa una clave pública confiable y un dominio de firma distinto del catálogo. Una
firma válida prueba autenticidad/integridad respecto de esa clave, no autoridad
productiva ni completitud del catálogo.
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

from precios_supermercados.structural_provenance import SignedStructuralReceipt

_B64URL = re.compile(r"[A-Za-z0-9_-]+\Z")


class StructuralReceiptCryptoError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise StructuralReceiptCryptoError(code, message)


def _decode(value: object, code: str, *, maximum: int) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
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
        raise StructuralReceiptCryptoError(code) from exc
    if not decoded:
        _fail(code)
    if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != value:
        _fail(code)
    return decoded


@dataclass(frozen=True, slots=True)
class VerifiedStructuralReceipt:
    receipt: SignedStructuralReceipt
    signing_key_id: str
    public_key_spki_sha256: str
    receipt_digest: str
    cryptographic_signature_verified: bool = True
    production_authority: bool = False


@dataclass(frozen=True, slots=True)
class _TrustedKey:
    public_key: Ed25519PublicKey
    spki_sha256: str


class Ed25519StructuralReceiptVerifier:
    def __init__(self, public_keys_spki_b64url: Mapping[str, str]) -> None:
        if not isinstance(public_keys_spki_b64url, Mapping) or not public_keys_spki_b64url:
            _fail("structural_public_keyring_invalid")
        parsed: dict[str, _TrustedKey] = {}
        for key_id, encoded in public_keys_spki_b64url.items():
            if (
                not isinstance(key_id, str)
                or not key_id
                or key_id.strip() != key_id
                or any(character.isspace() for character in key_id)
                or len(key_id) > 256
                or key_id in parsed
            ):
                _fail("structural_public_key_id_invalid")
            der = _decode(encoded, "structural_public_key_spki_invalid", maximum=4096)
            try:
                loaded = load_der_public_key(der)
            except (TypeError, ValueError) as exc:
                raise StructuralReceiptCryptoError("structural_public_key_spki_invalid") from exc
            if not isinstance(loaded, Ed25519PublicKey):
                _fail("structural_public_key_algorithm_invalid")
            parsed[key_id] = _TrustedKey(
                public_key=loaded,
                spki_sha256=hashlib.sha256(der).hexdigest(),
            )
        self._keys = MappingProxyType(parsed)

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def verify(self, receipt: SignedStructuralReceipt) -> VerifiedStructuralReceipt:
        if not isinstance(receipt, SignedStructuralReceipt):
            _fail("structural_receipt_type_invalid")
        trusted = self._keys.get(receipt.payload.signing_key_id)
        if trusted is None:
            _fail("structural_receipt_signing_key_untrusted")
        signature = _decode(
            receipt.signature_b64url,
            "structural_receipt_signature_invalid",
            maximum=1024,
        )
        if len(signature) != 64:
            _fail("structural_receipt_signature_length_invalid")
        try:
            trusted.public_key.verify(signature, receipt.signing_bytes())
        except InvalidSignature as exc:
            raise StructuralReceiptCryptoError("structural_receipt_signature_invalid") from exc
        return VerifiedStructuralReceipt(
            receipt=receipt,
            signing_key_id=receipt.payload.signing_key_id,
            public_key_spki_sha256=trusted.spki_sha256,
            receipt_digest=receipt.digest,
        )
