from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precios_supermercados.cloudflare_controlled_probe_verifier import (
    CONTROLLED_PROBE_ENVIRONMENT,
    CONTROLLED_PROBE_ORIGIN_PATH,
    CONTROLLED_PROBE_PURPOSE,
    CONTROLLED_PROBE_REF,
    CONTROLLED_PROBE_REPOSITORY,
    CONTROLLED_PROBE_REPOSITORY_ID,
    CONTROLLED_PROBE_SCHEMA_VERSION,
    CONTROLLED_PROBE_SIGNATURE_DOMAIN,
    CONTROLLED_PROBE_SIGNING_KEY_ID,
    CONTROLLED_PROBE_SUBJECT,
    CONTROLLED_PROBE_WORKFLOW_REF,
    ControlledProbeVerificationError,
    verify_controlled_probe_artifact,
)
from precios_supermercados.edge_provenance import canonical_json_bytes

SHA = "a" * 40
RUN_ID = "32550000000"
RUN_ATTEMPT = 1
HOST = "precios-sps-controlled-origin.example-account.workers.dev"
CHALLENGE = "runtime-challenge-001"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _artifact(
    *,
    host: str = HOST,
    commit_sha: str = SHA,
    run_id: str = RUN_ID,
    run_attempt: int = RUN_ATTEMPT,
) -> tuple[dict[str, object], str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    raw_body = json.dumps(
        {
            "ok": True,
            "purpose": CONTROLLED_PROBE_PURPOSE,
            "challenge": CHALLENGE,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    probe_id = f"github-{run_id}-{run_attempt}"
    canonical_request = {
        "challenge": CHALLENGE,
        "method": "GET",
        "probe_id": probe_id,
        "purpose": CONTROLLED_PROBE_PURPOSE,
        "target_host": host,
        "target_path": CONTROLLED_PROBE_ORIGIN_PATH,
        "target_scheme": "https",
    }
    receipt: dict[str, object] = {
        "approved_commit_sha": commit_sha,
        "canonical_request_sha256": hashlib.sha256(
            canonical_json_bytes(canonical_request)
        ).hexdigest(),
        "collector_provider": "cloudflare_workers",
        "collector_principal": "cloudflare-worker:precios-sps-controlled-probe",
        "collector_release_id": "cf-probe-version-001",
        "durable_object_name": f"github-run:{run_id}:{run_attempt}",
        "github_environment": CONTROLLED_PROBE_ENVIRONMENT,
        "github_ref": CONTROLLED_PROBE_REF,
        "github_repository": CONTROLLED_PROBE_REPOSITORY,
        "github_repository_id": CONTROLLED_PROBE_REPOSITORY_ID,
        "github_run_attempt": run_attempt,
        "github_run_id": run_id,
        "github_workflow_ref": CONTROLLED_PROBE_WORKFLOW_REF,
        "oidc_jti": "probe-jti-001",
        "oidc_subject": CONTROLLED_PROBE_SUBJECT,
        "physical_started_at_utc": "2033-05-18T03:33:20.000Z",
        "probe_id": probe_id,
        "purpose": CONTROLLED_PROBE_PURPOSE,
        "raw_response_sha256": hashlib.sha256(raw_body).hexdigest(),
        "response_body_bytes": len(raw_body),
        "response_completed_at_utc": "2033-05-18T03:33:20.125Z",
        "response_status": 200,
        "schema_version": CONTROLLED_PROBE_SCHEMA_VERSION,
        "signing_algorithm": "Ed25519",
        "signing_key_id": CONTROLLED_PROBE_SIGNING_KEY_ID,
        "target_host": host,
        "target_path": CONTROLLED_PROBE_ORIGIN_PATH,
        "target_scheme": "https",
    }
    receipt_bytes = canonical_json_bytes(receipt)
    signature = _b64url(private_key.sign(CONTROLLED_PROBE_SIGNATURE_DOMAIN + receipt_bytes))
    evidence_id = hashlib.sha256(
        CONTROLLED_PROBE_SIGNATURE_DOMAIN
        + receipt_bytes
        + b"\0"
        + signature.encode("ascii")
    ).hexdigest()
    return (
        {
            "ok": True,
            "decision": "PROBE_COMPLETED",
            "replayed": False,
            "purpose": CONTROLLED_PROBE_PURPOSE,
            "rawBodyB64Url": _b64url(raw_body),
            "receiptPayload": receipt,
            "signatureB64Url": signature,
            "signingKeyId": CONTROLLED_PROBE_SIGNING_KEY_ID,
            "evidenceId": evidence_id,
        },
        _b64url(public_key),
    )


def _verify(artifact: dict[str, object], public_key: str):
    return verify_controlled_probe_artifact(
        artifact,
        public_key_spki_b64url=public_key,
        expected_commit_sha=SHA,
        expected_run_id=RUN_ID,
        expected_run_attempt=RUN_ATTEMPT,
    )


def test_verifies_signature_body_request_and_oidc_context_independently() -> None:
    artifact, public_key = _artifact()

    verified = _verify(artifact, public_key)

    assert verified.cryptographic_signature_verified is True
    assert verified.production_authority is False
    assert verified.catalog_accepted is False
    assert verified.target_host == HOST
    assert verified.github_run_id == RUN_ID
    assert verified.github_run_attempt == RUN_ATTEMPT
    assert verified.evidence_id == artifact["evidenceId"]


def test_rejects_signature_from_a_different_key() -> None:
    artifact, _ = _artifact()
    _, other_public_key = _artifact()

    with pytest.raises(ControlledProbeVerificationError) as exc:
        _verify(artifact, other_public_key)

    assert exc.value.code == "probe_signature_verification_failed"


def test_rejects_signed_receipt_tampering() -> None:
    artifact, public_key = _artifact()
    tampered = deepcopy(artifact)
    tampered["receiptPayload"]["collector_release_id"] = "forged-release"

    with pytest.raises(ControlledProbeVerificationError) as exc:
        _verify(tampered, public_key)

    assert exc.value.code == "probe_signature_verification_failed"


def test_rejects_raw_body_tampering_before_it_can_be_evidence() -> None:
    artifact, public_key = _artifact()
    tampered = deepcopy(artifact)
    body = json.dumps(
        {"ok": True, "purpose": CONTROLLED_PROBE_PURPOSE, "challenge": "other-challenge-001"},
        separators=(",", ":"),
    ).encode("utf-8")
    tampered["rawBodyB64Url"] = _b64url(body)

    with pytest.raises(ControlledProbeVerificationError) as exc:
        _verify(tampered, public_key)

    assert exc.value.code == "probe_raw_body_size_mismatch" or exc.value.code == "probe_raw_body_hash_mismatch"


def test_even_validly_signed_probe_evidence_cannot_target_la_colonia() -> None:
    artifact, public_key = _artifact(host="www.lacolonia.com")

    with pytest.raises(ControlledProbeVerificationError) as exc:
        _verify(artifact, public_key)

    assert exc.value.code == "probe_receipt_target_host_forbidden"


def test_rejects_different_github_run_or_commit_context() -> None:
    artifact, public_key = _artifact()

    with pytest.raises(ControlledProbeVerificationError) as run_exc:
        verify_controlled_probe_artifact(
            artifact,
            public_key_spki_b64url=public_key,
            expected_commit_sha=SHA,
            expected_run_id="32550000001",
            expected_run_attempt=RUN_ATTEMPT,
        )
    assert run_exc.value.code == "probe_receipt_run_id_mismatch"

    with pytest.raises(ControlledProbeVerificationError) as commit_exc:
        verify_controlled_probe_artifact(
            artifact,
            public_key_spki_b64url=public_key,
            expected_commit_sha="b" * 40,
            expected_run_id=RUN_ID,
            expected_run_attempt=RUN_ATTEMPT,
        )
    assert commit_exc.value.code == "probe_receipt_commit_mismatch"


def test_rejects_extension_fields_in_artifact_or_receipt() -> None:
    artifact, public_key = _artifact()
    top_extra = deepcopy(artifact)
    top_extra["productionAuthority"] = True
    with pytest.raises(ControlledProbeVerificationError) as top_exc:
        _verify(top_extra, public_key)
    assert top_exc.value.code == "probe_artifact_shape_invalid"

    receipt_extra = deepcopy(artifact)
    receipt_extra["receiptPayload"]["catalog_accepted"] = True
    with pytest.raises(ControlledProbeVerificationError) as receipt_exc:
        _verify(receipt_extra, public_key)
    assert receipt_exc.value.code == "probe_receipt_shape_invalid"
