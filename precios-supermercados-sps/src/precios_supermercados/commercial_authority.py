"""Atestación criptográfica separada para autoridad comercial productiva.

La provenance física del collector demuestra que un request real ocurrió, pero no
concede por sí sola autoridad para mutar ``current/history``. Esta capa añade una
raíz de confianza distinta: una clave Ed25519 explícitamente permitida para firmar
una aceptación comercial ligada a un run, ubicación y digests concretos.

Una firma válida aquí tampoco sustituye la política específica de la fuente. El
resultado criptográfico debe reconciliarse contra la readiness técnica real antes
de convertirse en una decisión ``catalog_accepted=True``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import NoReturn

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_der_public_key

from .edge_provenance import canonical_json_bytes
from .enums import RunStatus

COMMERCIAL_AUTHORITY_SCHEMA_VERSION = "1"
COMMERCIAL_AUTHORITY_SCOPE = "catalog_acceptance"
COMMERCIAL_AUTHORITY_SIGNATURE_DOMAIN = (
    b"precios-sps/commercial-authority-attestation/v1\0"
)
_AUTHORITY_EVIDENCE_PREFIX = "caev1_"
_B64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED_STATUSES = frozenset({RunStatus.SUCCESS, RunStatus.WARNING})
_CRYPTO_VERIFICATION_SEAL = object()


class CommercialAuthorityError(ValueError):
    """La atestación de autoridad no puede validarse de forma segura."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CommercialAuthorityError(code, message)


def _text(value: object, code: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _fail(code)
    return value


def _sha256(value: object, code: str) -> str:
    text = _text(value, code, maximum=64)
    if not _SHA256.fullmatch(text):
        _fail(code)
    return text


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _fail(code)
    if value.utcoffset().total_seconds() != 0:
        _fail(code)
    return value.astimezone(timezone.utc)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


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
        raise CommercialAuthorityError(code) from exc
    if not decoded:
        _fail(code)
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if canonical != value:
        _fail(code)
    return decoded


@dataclass(frozen=True, slots=True)
class CommercialAuthorityClaims:
    """Claims firmados de una aceptación comercial one-run/one-location."""

    supermarket_id: str
    location_id: str
    scrape_run_id: str
    source_authorization_id: str
    run_status: RunStatus | str
    decided_at_utc: datetime
    discovery_digest: str
    authenticated_plan_digest: str
    provenance_manifest_digest: str
    signing_key_id: str
    signing_algorithm: str = "Ed25519"
    scope: str = COMMERCIAL_AUTHORITY_SCOPE
    schema_version: str = COMMERCIAL_AUTHORITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COMMERCIAL_AUTHORITY_SCHEMA_VERSION:
            _fail("authority_schema_version_invalid")
        if self.scope != COMMERCIAL_AUTHORITY_SCOPE:
            _fail("authority_scope_invalid")
        if self.signing_algorithm != "Ed25519":
            _fail("authority_signing_algorithm_invalid")
        for name in (
            "supermarket_id",
            "location_id",
            "scrape_run_id",
            "source_authorization_id",
            "signing_key_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), f"authority_{name}_invalid"),
            )
        try:
            status = (
                self.run_status
                if isinstance(self.run_status, RunStatus)
                else RunStatus(self.run_status)
            )
        except (TypeError, ValueError) as exc:
            raise CommercialAuthorityError("authority_run_status_invalid") from exc
        if status not in _ALLOWED_STATUSES:
            _fail("authority_run_status_not_commercial")
        object.__setattr__(self, "run_status", status)
        object.__setattr__(
            self,
            "decided_at_utc",
            _utc(self.decided_at_utc, "authority_decided_at_invalid"),
        )
        for name in (
            "discovery_digest",
            "authenticated_plan_digest",
            "provenance_manifest_digest",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), f"authority_{name}_invalid"),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "authenticated_plan_digest": self.authenticated_plan_digest,
            "decided_at_utc": _iso_z(self.decided_at_utc),
            "discovery_digest": self.discovery_digest,
            "location_id": self.location_id,
            "provenance_manifest_digest": self.provenance_manifest_digest,
            "run_status": self.run_status.value,
            "schema_version": self.schema_version,
            "scope": self.scope,
            "scrape_run_id": self.scrape_run_id,
            "signing_algorithm": self.signing_algorithm,
            "signing_key_id": self.signing_key_id,
            "source_authorization_id": self.source_authorization_id,
            "supermarket_id": self.supermarket_id,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class SignedCommercialAuthorityAttestation:
    claims: CommercialAuthorityClaims
    signature_b64url: str

    def __post_init__(self) -> None:
        if not isinstance(self.claims, CommercialAuthorityClaims):
            _fail("authority_claims_invalid")
        _text(self.signature_b64url, "authority_signature_invalid", maximum=1024)

    @property
    def authority_evidence_id(self) -> str:
        material = canonical_json_bytes(
            {
                "claims": self.claims.canonical_dict(),
                "signature_b64url": self.signature_b64url,
            }
        )
        return _AUTHORITY_EVIDENCE_PREFIX + hashlib.sha256(
            COMMERCIAL_AUTHORITY_SIGNATURE_DOMAIN + material
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class TrustedCommercialAuthorityPublicKey:
    key_id: str
    public_key: Ed25519PublicKey
    spki_sha256: str


@dataclass(frozen=True, slots=True)
class CryptographicallyVerifiedCommercialAuthority:
    """Capability sellada: sólo ``Ed25519CommercialAuthorityVerifier`` puede crearla."""

    attestation: SignedCommercialAuthorityAttestation
    authority_evidence_id: str
    signing_key_id: str
    public_key_spki_sha256: str
    _verification_seal: object = field(repr=False, compare=False)
    cryptographic_signature_verified: bool = True
    production_authority: bool = False
    catalog_accepted: bool = False

    def __post_init__(self) -> None:
        if self._verification_seal is not _CRYPTO_VERIFICATION_SEAL:
            _fail("verified_authority_unsealed")
        if not isinstance(self.attestation, SignedCommercialAuthorityAttestation):
            _fail("verified_authority_attestation_invalid")
        if self.authority_evidence_id != self.attestation.authority_evidence_id:
            _fail("verified_authority_evidence_id_mismatch")
        if self.signing_key_id != self.attestation.claims.signing_key_id:
            _fail("verified_authority_signing_key_mismatch")
        _sha256(
            self.public_key_spki_sha256,
            "verified_authority_public_key_digest_invalid",
        )
        if self.cryptographic_signature_verified is not True:
            _fail("verified_authority_signature_required")
        if self.production_authority is not False or self.catalog_accepted is not False:
            _fail("verified_authority_policy_promotion_forbidden")


def commercial_authority_signing_bytes(claims: CommercialAuthorityClaims) -> bytes:
    if not isinstance(claims, CommercialAuthorityClaims):
        _fail("authority_claims_invalid")
    return COMMERCIAL_AUTHORITY_SIGNATURE_DOMAIN + claims.canonical_bytes()


class Ed25519CommercialAuthorityVerifier:
    """Keyring inmutable dedicado exclusivamente a atestaciones comerciales."""

    def __init__(self, public_keys_spki_b64url: Mapping[str, str]) -> None:
        if not isinstance(public_keys_spki_b64url, Mapping) or not public_keys_spki_b64url:
            _fail("authority_public_keyring_invalid")
        parsed: dict[str, TrustedCommercialAuthorityPublicKey] = {}
        for raw_key_id, raw_spki in public_keys_spki_b64url.items():
            key_id = _text(raw_key_id, "authority_public_key_id_invalid", maximum=256)
            if any(character.isspace() for character in key_id):
                _fail("authority_public_key_id_invalid")
            der = _canonical_b64url_decode(
                raw_spki,
                "authority_public_key_spki_invalid",
                max_length=4096,
            )
            try:
                loaded = load_der_public_key(der)
            except (TypeError, ValueError) as exc:
                raise CommercialAuthorityError("authority_public_key_spki_invalid") from exc
            if not isinstance(loaded, Ed25519PublicKey):
                _fail("authority_public_key_algorithm_invalid")
            parsed[key_id] = TrustedCommercialAuthorityPublicKey(
                key_id=key_id,
                public_key=loaded,
                spki_sha256=hashlib.sha256(der).hexdigest(),
            )
        self._keys = MappingProxyType(parsed)

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def verify(
        self,
        attestation: SignedCommercialAuthorityAttestation,
    ) -> CryptographicallyVerifiedCommercialAuthority:
        if not isinstance(attestation, SignedCommercialAuthorityAttestation):
            _fail("authority_attestation_invalid")
        claims = attestation.claims
        trusted_key = self._keys.get(claims.signing_key_id)
        if trusted_key is None:
            _fail("authority_signing_key_untrusted")
        signature = _canonical_b64url_decode(
            attestation.signature_b64url,
            "authority_signature_invalid",
            max_length=1024,
        )
        if len(signature) != 64:
            _fail("authority_signature_length_invalid")
        try:
            trusted_key.public_key.verify(
                signature,
                commercial_authority_signing_bytes(claims),
            )
        except InvalidSignature as exc:
            raise CommercialAuthorityError("authority_signature_invalid") from exc
        return CryptographicallyVerifiedCommercialAuthority(
            attestation=attestation,
            authority_evidence_id=attestation.authority_evidence_id,
            signing_key_id=trusted_key.key_id,
            public_key_spki_sha256=trusted_key.spki_sha256,
            _verification_seal=_CRYPTO_VERIFICATION_SEAL,
        )
