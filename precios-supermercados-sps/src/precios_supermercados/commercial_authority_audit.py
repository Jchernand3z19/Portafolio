"""Metadatos públicos y re-verificables de una autoridad comercial validada.

El ``crev1_*`` liga autoridad + payload durable, pero es deliberadamente opaco.
Para auditoría futura también se conserva la atestación firmada canónica y la
identidad de la clave pública que la verificó. No contiene secretos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .commercial_authority import CryptographicallyVerifiedCommercialAuthority
from .edge_provenance import canonical_json_bytes

_CA_EVIDENCE = re.compile(r"caev1_[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_AUDIT_SEAL = object()


class CommercialAuthorityAuditError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CommercialAuthorityAuditMetadata:
    """Snapshot sellado de evidencia pública derivado de una firma ya verificada."""

    authority_evidence_id: str
    authority_attestation_json: str
    authority_signing_key_id: str
    authority_public_key_spki_sha256: str
    authority_decided_at_utc: datetime
    _audit_seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._audit_seal is not _AUDIT_SEAL:
            raise CommercialAuthorityAuditError("authority_audit_unsealed")
        if not _CA_EVIDENCE.fullmatch(self.authority_evidence_id):
            raise CommercialAuthorityAuditError("authority_audit_evidence_id_invalid")
        if (
            not isinstance(self.authority_attestation_json, str)
            or not self.authority_attestation_json
            or len(self.authority_attestation_json.encode("utf-8")) > 16 * 1024
        ):
            raise CommercialAuthorityAuditError("authority_audit_attestation_invalid")
        if (
            not isinstance(self.authority_signing_key_id, str)
            or not self.authority_signing_key_id
            or self.authority_signing_key_id.strip() != self.authority_signing_key_id
        ):
            raise CommercialAuthorityAuditError("authority_audit_signing_key_invalid")
        if not _SHA256.fullmatch(self.authority_public_key_spki_sha256):
            raise CommercialAuthorityAuditError("authority_audit_public_key_digest_invalid")
        decided = self.authority_decided_at_utc
        if (
            not isinstance(decided, datetime)
            or decided.tzinfo is None
            or decided.utcoffset() is None
            or decided.utcoffset().total_seconds() != 0
        ):
            raise CommercialAuthorityAuditError("authority_audit_decided_at_invalid")
        object.__setattr__(self, "authority_decided_at_utc", decided.astimezone(timezone.utc))

    @classmethod
    def from_verified(
        cls,
        verified: CryptographicallyVerifiedCommercialAuthority,
    ) -> "CommercialAuthorityAuditMetadata":
        if not isinstance(verified, CryptographicallyVerifiedCommercialAuthority):
            raise CommercialAuthorityAuditError("verified_commercial_authority_required")
        attestation = verified.attestation
        payload = canonical_json_bytes(
            {
                "claims": attestation.claims.canonical_dict(),
                "signature_b64url": attestation.signature_b64url,
            }
        ).decode("utf-8")
        return cls(
            authority_evidence_id=verified.authority_evidence_id,
            authority_attestation_json=payload,
            authority_signing_key_id=verified.signing_key_id,
            authority_public_key_spki_sha256=verified.public_key_spki_sha256,
            authority_decided_at_utc=attestation.claims.decided_at_utc,
            _audit_seal=_AUDIT_SEAL,
        )
