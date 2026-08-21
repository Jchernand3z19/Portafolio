from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Mapping

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from precios_supermercados.authenticated_provenance_plan import (
    derive_authenticated_catalog_provenance_plan,
)
from precios_supermercados.canonical_authenticated_provenance_plan import (
    derive_canonical_authenticated_catalog_plan,
)
from precios_supermercados.edge_catalog_page import EdgeCatalogPageFetcher
from precios_supermercados.edge_crypto_page import EdgeCatalogPageCryptoVerifier
from precios_supermercados.edge_gateway_client import EXECUTE_PATH, EdgeGatewayClient
from precios_supermercados.edge_provenance import EdgeReceiptPayload, canonical_json_bytes
from precios_supermercados.edge_receipt_crypto import (
    RECEIPT_SIGNATURE_DOMAIN,
    Ed25519ReceiptVerifier,
)
from precios_supermercados.la_colonia_edge_request import validate_la_colonia_edge_request
from precios_supermercados.scrapers.la_colonia_verified_catalog_transport import (
    VerifiedCatalogEdgeTransport,
    VerifiedCatalogEdgeTransportError,
)
from test_canonical_authenticated_provenance_plan import _discovery

TOKEN = "oidc.catalog.transport.test"
KEY_ID = "cloudflare-ed25519-v1"
BASE = datetime(2026, 8, 21, 23, 20, 0, tzinfo=timezone.utc)


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _plan_and_key():
    private = Ed25519PrivateKey.generate()
    public_der = private.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    public_hash = hashlib.sha256(public_der).hexdigest()
    discovery = _discovery()
    discovery = replace(
        discovery,
        root_total=replace(discovery.root_total, public_key_spki_sha256=public_hash),
        category_tree=replace(discovery.category_tree, public_key_spki_sha256=public_hash),
    )
    plan = derive_canonical_authenticated_catalog_plan(discovery)
    return plan, private, _b64url(public_der)


class _DynamicGatewayTransport:
    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        plan,
        *,
        wait_first: bool = False,
        collector_code_override: str | None = None,
    ) -> None:
        self.private_key = private_key
        self.plan = plan
        self.wait_first = wait_first
        self.collector_code_override = collector_code_override
        self.calls: list[tuple[str, str, Mapping[str, object]]] = []
        self.origin_calls = 0

    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.calls.append((path, bearer_token, payload))
        if self.wait_first:
            self.wait_first = False
            return {
                "ok": True,
                "decision": "WAIT",
                "reason": "pacing_interval",
                "notBeforeMs": 2_000_000_001_500,
                "inFlightReservationId": None,
            }

        self.origin_calls += 1
        assert path == EXECUTE_PATH
        origin_url = payload["originUrl"]
        context = payload["requestContext"]
        assert isinstance(origin_url, str)
        assert isinstance(context, Mapping)
        validated = validate_la_colonia_edge_request(origin_url)

        remaining = max(7 - validated.from_index, 0)
        returned = min(validated.page_size, remaining)
        raw = json.dumps(
            {
                "data": {
                    "productSearch": {
                        "recordsFiltered": 7,
                        "products": [
                            {"productId": f"product-{index}"}
                            for index in range(returned)
                        ],
                    }
                }
            },
            separators=(",", ":"),
        ).encode("utf-8")
        started = BASE + timedelta(seconds=(self.origin_calls - 1) * 2)
        completed = started + timedelta(milliseconds=200)
        discovery = self.plan.discovery
        receipt = EdgeReceiptPayload(
            run_id=str(context["runId"]),
            request_id=str(context["requestId"]),
            reservation_id=str(context["reservationId"]),
            authorization_id=str(context["authorizationId"]),
            approved_commit_sha=str(context["approvedCommitSha"]),
            request_digest=str(context["requestDigest"]),
            traversal_id=str(context["traversalId"]),
            traversal_role=str(context["traversalRole"]),  # type: ignore[arg-type]
            order_by=validated.order_by,
            partition_id=str(context["partitionId"]),
            from_index=validated.from_index,
            to_index=validated.to_index,
            http_method="GET",
            target_scheme="https",
            target_host="www.lacolonia.com",
            target_path="/_v/segment/graphql/v1",
            canonical_request_sha256=validated.canonical_request_sha256,
            raw_response_sha256=hashlib.sha256(raw).hexdigest(),
            response_status=200,
            response_body_bytes=len(raw),
            physical_started_at_utc=started,
            response_completed_at_utc=completed,
            github_repository=discovery.github_repository,
            github_repository_id=discovery.github_repository_id,
            github_ref=discovery.github_ref,
            github_workflow_ref=discovery.github_workflow_ref,
            github_environment=discovery.github_environment,
            github_run_id=discovery.github_run_id,
            github_run_attempt=discovery.github_run_attempt,
            oidc_subject=discovery.oidc_subject,
            oidc_jti=f"oidc-catalog-{self.origin_calls}",
            collector_provider="cloudflare_workers",
            collector_principal=discovery.collector_principal,
            collector_execution=f"execution-catalog-{self.origin_calls}",
            collector_release_id=discovery.collector_release_id,
            collector_code_sha256=(
                self.collector_code_override or discovery.collector_code_sha256
            ),
            signing_algorithm="Ed25519",
            signing_key_id=KEY_ID,
            nonce=str(context["nonce"]),
        )
        signature = self.private_key.sign(
            RECEIPT_SIGNATURE_DOMAIN + receipt.canonical_bytes()
        )
        signature_b64 = _b64url(signature)
        receipt_dict = receipt.canonical_dict()
        evidence_id = hashlib.sha256(
            canonical_json_bytes(receipt_dict) + b"\0" + signature_b64.encode("ascii")
        ).hexdigest()
        return {
            "ok": True,
            "decision": "ORIGIN_COMPLETED",
            "replayed": False,
            "responseStatus": 200,
            "rawBodyB64Url": _b64url(raw),
            "receiptPayload": receipt_dict,
            "signatureB64Url": signature_b64,
            "signingKeyId": KEY_ID,
            "evidenceId": evidence_id,
        }


def _transport(*, wait_first: bool = False, collector_code_override: str | None = None):
    plan, private, public_b64 = _plan_and_key()
    wire = _DynamicGatewayTransport(
        private,
        plan,
        wait_first=wait_first,
        collector_code_override=collector_code_override,
    )
    client = EdgeGatewayClient(wire)
    fetcher = EdgeCatalogPageFetcher(client)
    crypto = EdgeCatalogPageCryptoVerifier(Ed25519ReceiptVerifier({KEY_ID: public_b64}))
    token_calls: list[int] = []

    def token_provider() -> str:
        token_calls.append(1)
        return TOKEN

    transport = VerifiedCatalogEdgeTransport(
        plan,
        fetcher,
        crypto,
        bearer_token_provider=token_provider,
    )
    return transport, wire, token_calls


def test_ejecuta_exactamente_primary_y_reconciliation_del_plan() -> None:
    transport, wire, token_calls = _transport()
    assert transport.total_pages == 2
    assert transport.completed_pages == 0

    primary = transport.execute_next()
    reconciliation = transport.execute_next()

    assert primary.verified_receipt.receipt.payload.traversal_role == "primary"
    assert reconciliation.verified_receipt.receipt.payload.traversal_role == "reconciliation"
    assert primary.verified_receipt.receipt.payload.request_id != reconciliation.verified_receipt.receipt.payload.request_id
    assert primary.verified_receipt.receipt.payload.reservation_id != reconciliation.verified_receipt.receipt.payload.reservation_id
    assert primary.verified_receipt.receipt.payload.nonce != reconciliation.verified_receipt.receipt.payload.nonce
    assert transport.complete is True
    assert transport.completed_pages == transport.total_pages == 2
    assert transport.next_expected is None
    assert len(transport.pages) == 2
    assert token_calls == [1, 1]
    assert len(wire.calls) == 2
    assert all(call[0] == EXECUTE_PATH for call in wire.calls)
    assert all(call[1] == TOKEN for call in wire.calls)
    assert all(page.production_authority is False for page in transport.pages)

    with pytest.raises(VerifiedCatalogEdgeTransportError) as captured:
        transport.execute_next()
    assert captured.value.code == "catalog_plan_already_complete"
    assert len(wire.calls) == 2


def test_wait_no_avanza_cursor_y_no_hay_retry_oculto() -> None:
    transport, wire, token_calls = _transport(wait_first=True)
    expected = transport.next_expected

    with pytest.raises(VerifiedCatalogEdgeTransportError) as captured:
        transport.execute_next()

    assert captured.value.code == "catalog_fetch_edge_gateway_wait"
    assert transport.next_expected == expected
    assert transport.completed_pages == 0
    assert len(wire.calls) == 1
    assert token_calls == [1]

    page = transport.execute_next()
    assert page.verified_receipt.receipt.payload.traversal_role == "primary"
    assert transport.completed_pages == 1
    assert len(wire.calls) == 2


def test_fence_firmado_distinto_del_discovery_falla_sin_avanzar() -> None:
    transport, wire, _token_calls = _transport(collector_code_override="f" * 64)

    with pytest.raises(VerifiedCatalogEdgeTransportError) as captured:
        transport.execute_next()

    assert captured.value.code == "catalog_signed_fence_mismatch"
    assert transport.completed_pages == 0
    assert len(wire.calls) == 1


def test_plan_no_canonico_se_rechaza_antes_de_gateway() -> None:
    canonical, private, public_b64 = _plan_and_key()
    discovery = canonical.discovery
    noncanonical = derive_authenticated_catalog_provenance_plan(
        discovery,
        page_size=10,
        primary_traversal_id=f"{discovery.run_id}:primary",
        reconciliation_traversal_id=f"{discovery.run_id}:reconciliation",
        primary_order_by="OrderByNameASC",
        reconciliation_order_by="OrderByNameDESC",
    )
    wire = _DynamicGatewayTransport(private, canonical)
    fetcher = EdgeCatalogPageFetcher(EdgeGatewayClient(wire))
    crypto = EdgeCatalogPageCryptoVerifier(Ed25519ReceiptVerifier({KEY_ID: public_b64}))

    with pytest.raises(VerifiedCatalogEdgeTransportError) as captured:
        VerifiedCatalogEdgeTransport(
            noncanonical,
            fetcher,
            crypto,
            bearer_token_provider=lambda: TOKEN,
        )

    assert captured.value.code == "catalog_plan_not_canonical"
    assert wire.calls == []


def test_ids_derivados_son_reproducibles_para_mismo_plan() -> None:
    first, first_wire, _ = _transport()
    second, second_wire, _ = _transport()
    first.execute_next()
    second.execute_next()
    first_context = first_wire.calls[0][2]["requestContext"]
    second_context = second_wire.calls[0][2]["requestContext"]
    assert isinstance(first_context, Mapping)
    assert isinstance(second_context, Mapping)
    assert first_context["requestId"] == second_context["requestId"]
    assert first_context["reservationId"] == second_context["reservationId"]
    assert first_context["nonce"] == second_context["nonce"]
