"""Attestation run-level para un manifest completo de provenance edge.

El contrato liga el manifest cerrado a una identidad de verifier separada del
collector. Sigue siendo offline y no concede autoridad productiva por sí solo.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NoReturn

from precios_supermercados.edge_provenance import canonical_json_bytes
from precios_supermercados.edge_provenance_run import EdgeProvenanceRunManifest

RUN_ATTESTATION_SCHEMA_VERSION = "1"
RUN_ATTESTATION_DOMAIN = b"precios-sps/edge-run-attestation/v1\0"
EVIDENCE_SOURCE = "cloudflare_workers_observability_rest"
_ALLOWED_VERIFIER_PROVIDERS = {"github_actions", "cloudflare_workers", "google_cloud_run"}
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ACCOUNT_ID = re.compile(r"[0-9a-f]{32}\Z")


class EdgeRunAttestationError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise EdgeRunAttestationError(code, message)


def _text(value: object, code: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(character.isspace() for character in value)
    ):
        _fail(code)
    return value


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


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _fail(code)
    return value.astimezone(timezone.utc)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _unique_sha256_tuple(values: object, code: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        _fail(code)
    normalized = tuple(_sha256(value, code) for value in values)
    if len(set(normalized)) != len(normalized):
        _fail(f"{code}_duplicate")
    return normalized


def _unique_text_tuple(values: object, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple) or (not values and not allow_empty):
        _fail(code)
    normalized = tuple(_text(value, code) for value in values)
    if len(set(normalized)) != len(normalized):
        _fail(f"{code}_duplicate")
    return normalized


@dataclass(frozen=True, slots=True)
class EdgeRunAttestationPayload:
    manifest_digest: str
    run_id: str
    authorization_id: str
    approved_commit_sha: str
    collector_provider: str
    collector_principal: str
    collector_release_id: str
    collector_code_sha256: str
    collector_signing_key_id: str
    collector_receipt_digests: tuple[str, ...]
    worker_evidence_ids: tuple[str, ...]
    physical_evidence_ids: tuple[str, ...]
    trace_ids: tuple[str, ...]
    fetch_span_ids: tuple[str, ...]
    primary_traversal_id: str
    reconciliation_traversal_id: str
    primary_order_by: str
    reconciliation_order_by: str
    verified_request_count: int
    evidence_source: str
    evidence_account_id_sha256: str
    verification_started_at_utc: datetime
    verification_completed_at_utc: datetime
    verdict: Literal["VERIFIED", "REJECTED"]
    reasons: tuple[str, ...]
    verifier_provider: str
    verifier_principal: str
    verifier_execution: str
    verifier_code_sha256: str
    signing_algorithm: Literal["Ed25519"]
    verifier_signing_key_id: str
    schema_version: str = RUN_ATTESTATION_SCHEMA_VERSION
    production_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != RUN_ATTESTATION_SCHEMA_VERSION:
            _fail("attestation_schema_version_invalid")
        object.__setattr__(self, "manifest_digest", _sha256(self.manifest_digest, "manifest_digest_invalid"))
        object.__setattr__(self, "approved_commit_sha", _sha1(self.approved_commit_sha, "approved_commit_sha_invalid"))
        object.__setattr__(self, "collector_code_sha256", _sha256(self.collector_code_sha256, "collector_code_sha256_invalid"))
        object.__setattr__(self, "evidence_account_id_sha256", _sha256(self.evidence_account_id_sha256, "evidence_account_id_sha256_invalid"))
        object.__setattr__(self, "verifier_code_sha256", _sha256(self.verifier_code_sha256, "verifier_code_sha256_invalid"))
        for name in (
            "run_id", "authorization_id", "collector_provider", "collector_principal",
            "collector_release_id", "collector_signing_key_id", "primary_traversal_id",
            "reconciliation_traversal_id", "primary_order_by", "reconciliation_order_by",
            "verifier_provider", "verifier_principal", "verifier_execution", "verifier_signing_key_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), f"{name}_invalid"))

        if self.primary_traversal_id == self.reconciliation_traversal_id:
            _fail("attestation_traversal_ids_not_distinct")
        if self.primary_order_by == self.reconciliation_order_by:
            _fail("attestation_order_by_not_distinct")
        if self.evidence_source != EVIDENCE_SOURCE:
            _fail("evidence_source_invalid")
        if self.verifier_provider not in _ALLOWED_VERIFIER_PROVIDERS:
            _fail("verifier_provider_invalid")
        if self.signing_algorithm != "Ed25519":
            _fail("attestation_signing_algorithm_invalid")
        if self.verifier_principal == self.collector_principal:
            _fail("verifier_principal_not_separate")
        if self.verifier_signing_key_id == self.collector_signing_key_id:
            _fail("verifier_signing_key_not_separate")

        receipts = _unique_sha256_tuple(self.collector_receipt_digests, "collector_receipt_digests_invalid")
        workers = _unique_sha256_tuple(self.worker_evidence_ids, "worker_evidence_ids_invalid")
        physical = _unique_sha256_tuple(self.physical_evidence_ids, "physical_evidence_ids_invalid")
        traces = _unique_text_tuple(self.trace_ids, "trace_ids_invalid")
        fetches = _unique_text_tuple(self.fetch_span_ids, "fetch_span_ids_invalid")
        if len({len(receipts), len(workers), len(physical), len(traces), len(fetches)}) != 1:
            _fail("attestation_evidence_count_mismatch")
        if isinstance(self.verified_request_count, bool) or not isinstance(self.verified_request_count, int):
            _fail("verified_request_count_invalid")
        if self.verified_request_count <= 0 or self.verified_request_count != len(receipts):
            _fail("verified_request_count_invalid")

        started = _utc(self.verification_started_at_utc, "verification_started_at_invalid")
        completed = _utc(self.verification_completed_at_utc, "verification_completed_at_invalid")
        if completed < started:
            _fail("attestation_verification_time_order_invalid")
        object.__setattr__(self, "verification_started_at_utc", started)
        object.__setattr__(self, "verification_completed_at_utc", completed)

        if self.verdict not in {"VERIFIED", "REJECTED"}:
            _fail("attestation_verdict_invalid")
        reasons = _unique_text_tuple(self.reasons, "attestation_reasons_invalid", allow_empty=True)
        if self.verdict == "VERIFIED" and reasons:
            _fail("verified_attestation_has_reasons")
        if self.verdict == "REJECTED" and not reasons:
            _fail("rejected_attestation_missing_reason")
        if self.production_authority is not False:
            _fail("attestation_production_authority_forbidden")

        object.__setattr__(self, "collector_receipt_digests", receipts)
        object.__setattr__(self, "worker_evidence_ids", workers)
        object.__setattr__(self, "physical_evidence_ids", physical)
        object.__setattr__(self, "trace_ids", traces)
        object.__setattr__(self, "fetch_span_ids", fetches)
        object.__setattr__(self, "reasons", reasons)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "approved_commit_sha": self.approved_commit_sha,
            "authorization_id": self.authorization_id,
            "collector_code_sha256": self.collector_code_sha256,
            "collector_principal": self.collector_principal,
            "collector_provider": self.collector_provider,
            "collector_receipt_digests": list(self.collector_receipt_digests),
            "collector_release_id": self.collector_release_id,
            "collector_signing_key_id": self.collector_signing_key_id,
            "evidence_account_id_sha256": self.evidence_account_id_sha256,
            "evidence_source": self.evidence_source,
            "fetch_span_ids": list(self.fetch_span_ids),
            "manifest_digest": self.manifest_digest,
            "physical_evidence_ids": list(self.physical_evidence_ids),
            "primary_order_by": self.primary_order_by,
            "primary_traversal_id": self.primary_traversal_id,
            "reasons": list(self.reasons),
            "reconciliation_order_by": self.reconciliation_order_by,
            "reconciliation_traversal_id": self.reconciliation_traversal_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "signing_algorithm": self.signing_algorithm,
            "trace_ids": list(self.trace_ids),
            "verdict": self.verdict,
            "verification_completed_at_utc": _iso_z(self.verification_completed_at_utc),
            "verification_started_at_utc": _iso_z(self.verification_started_at_utc),
            "verified_request_count": self.verified_request_count,
            "verifier_code_sha256": self.verifier_code_sha256,
            "verifier_execution": self.verifier_execution,
            "verifier_principal": self.verifier_principal,
            "verifier_provider": self.verifier_provider,
            "verifier_signing_key_id": self.verifier_signing_key_id,
            "worker_evidence_ids": list(self.worker_evidence_ids),
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(RUN_ATTESTATION_DOMAIN + canonical_json_bytes(self.canonical_dict())).hexdigest()


def build_verified_edge_run_attestation_payload(
    manifest: EdgeProvenanceRunManifest,
    *,
    observability_account_id: str,
    verification_started_at_utc: datetime,
    verification_completed_at_utc: datetime,
    verifier_provider: str,
    verifier_principal: str,
    verifier_execution: str,
    verifier_code_sha256: str,
    verifier_signing_key_id: str,
) -> EdgeRunAttestationPayload:
    """Deriva un payload VERIFIED exclusivamente desde el manifest cerrado."""

    if not isinstance(manifest, EdgeProvenanceRunManifest):
        _fail("run_manifest_invalid")
    if manifest.production_authority is not False:
        _fail("run_manifest_authority_invalid")
    if not isinstance(observability_account_id, str) or not _ACCOUNT_ID.fullmatch(observability_account_id):
        _fail("observability_account_id_invalid")
    started = _utc(verification_started_at_utc, "verification_started_at_invalid")
    completed = _utc(verification_completed_at_utc, "verification_completed_at_invalid")
    if started < manifest.latest_response_completed_at_utc:
        _fail("verification_started_before_manifest_completed")

    return EdgeRunAttestationPayload(
        manifest_digest=manifest.digest,
        run_id=manifest.run_id,
        authorization_id=manifest.authorization_id,
        approved_commit_sha=manifest.approved_commit_sha,
        collector_provider=manifest.collector_provider,
        collector_principal=manifest.collector_principal,
        collector_release_id=manifest.collector_release_id,
        collector_code_sha256=manifest.collector_code_sha256,
        collector_signing_key_id=manifest.collector_signing_key_id,
        collector_receipt_digests=tuple(page.receipt_digest for page in manifest.pages),
        worker_evidence_ids=tuple(page.worker_evidence_id for page in manifest.pages),
        physical_evidence_ids=tuple(page.physical_evidence_id for page in manifest.pages),
        trace_ids=tuple(page.trace_id for page in manifest.pages),
        fetch_span_ids=tuple(page.fetch_span_id for page in manifest.pages),
        primary_traversal_id=manifest.primary_traversal_id,
        reconciliation_traversal_id=manifest.reconciliation_traversal_id,
        primary_order_by=manifest.primary_order_by,
        reconciliation_order_by=manifest.reconciliation_order_by,
        verified_request_count=manifest.request_count,
        evidence_source=EVIDENCE_SOURCE,
        evidence_account_id_sha256=hashlib.sha256(observability_account_id.encode("ascii")).hexdigest(),
        verification_started_at_utc=started,
        verification_completed_at_utc=completed,
        verdict="VERIFIED",
        reasons=(),
        verifier_provider=verifier_provider,
        verifier_principal=verifier_principal,
        verifier_execution=verifier_execution,
        verifier_code_sha256=verifier_code_sha256,
        signing_algorithm="Ed25519",
        verifier_signing_key_id=verifier_signing_key_id,
    )
