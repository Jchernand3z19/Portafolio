"""Construye el manifest físico desde trazas query ya redactadas.

La ruta legacy vuelve a reconciliar ``fetch_url`` y por tanto no puede consumir
tracing cuyo URL contenía ``regionId``. Este builder conserva las mismas
invariantes run-level, pero acepta únicamente páginas que ya pasaron por
``reconcile_context_bound_query_trace`` y cuya evidencia durable contiene hashes,
no el URL físico raw.

No abre red, no selecciona placement y mantiene ``production_authority=False``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NoReturn

from precios_supermercados.authenticated_provenance_plan import (
    AuthenticatedCatalogProvenancePlan,
)
from precios_supermercados.catalog_context_provenance import ContextBoundEdgeReceiptPayload
from precios_supermercados.context_bound_query_trace_evidence import (
    RedactedContextBoundQueryPage,
)
from precios_supermercados.edge_provenance_run import (
    EdgeProvenanceRunManifest,
    ExpectedProvenancePage,
    ProvenancePageRecord,
)


class ContextBoundQueryProvenanceRunError(ValueError):
    """Las páginas query redactadas no forman el plan autenticado exacto."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise ContextBoundQueryProvenanceRunError(code, message)


def _expected(page: RedactedContextBoundQueryPage) -> ExpectedProvenancePage:
    payload = page.page.verified_receipt.receipt.payload
    if not isinstance(payload, ContextBoundEdgeReceiptPayload):
        _fail("query_run_receipt_downgrade")
    if payload.context_placement != "query" or payload.context_value_path != ():
        _fail("query_run_query_placement_required")
    return ExpectedProvenancePage(
        traversal_role=payload.traversal_role,
        traversal_id=payload.traversal_id,
        partition_id=payload.partition_id,
        order_by=payload.order_by,
        from_index=payload.from_index,
        to_index=payload.to_index,
        request_digest=payload.request_digest,
    )


def _record(page: RedactedContextBoundQueryPage) -> ProvenancePageRecord:
    if not isinstance(page, RedactedContextBoundQueryPage):
        _fail("query_run_page_invalid")
    if page.platform_evidence_reconciled is not True or page.production_authority is not False:
        _fail("query_run_page_unreconciled")
    crypto = page.page
    if crypto.cryptographic_signature_verified is not True or crypto.production_authority is not False:
        _fail("query_run_crypto_page_invalid")
    payload = crypto.verified_receipt.receipt.payload
    if not isinstance(payload, ContextBoundEdgeReceiptPayload):
        _fail("query_run_receipt_downgrade")
    trace = page.trace_evidence
    if (
        trace.platform_evidence_reconciled is not True
        or trace.production_authority is not False
        or trace.context_fingerprint != payload.context_fingerprint
        or trace.wire_request_fingerprint != payload.wire_request_fingerprint
    ):
        _fail("query_run_redacted_trace_mismatch")
    identity_pairs = (
        (trace.authorization_id, payload.authorization_id),
        (trace.run_id, payload.run_id),
        (trace.approved_commit_sha, payload.approved_commit_sha),
        (trace.reservation_id, payload.reservation_id),
        (trace.request_id, payload.request_id),
        (trace.request_digest, payload.request_digest),
        (trace.traversal_role, payload.traversal_role),
        (trace.traversal_id, payload.traversal_id),
        (trace.partition_id, payload.partition_id),
        (trace.script_version_id, payload.collector_release_id),
    )
    if any(observed != expected for observed, expected in identity_pairs):
        _fail("query_run_trace_receipt_identity_mismatch")
    return ProvenancePageRecord(
        expected=_expected(page),
        request_id=payload.request_id,
        reservation_id=payload.reservation_id,
        nonce=payload.nonce,
        receipt_digest=crypto.verified_receipt.receipt_digest,
        worker_evidence_id=crypto.worker_evidence_id,
        physical_evidence_id=trace.physical_evidence_id,
        trace_id=trace.trace_id,
        custom_span_id=trace.custom_span_id,
        fetch_span_id=trace.fetch_span_id,
        raw_response_sha256=payload.raw_response_sha256,
        physical_started_at_utc=payload.physical_started_at_utc,
        response_completed_at_utc=payload.response_completed_at_utc,
    )


def _assert_unique(records: Sequence[ProvenancePageRecord], attribute: str, code: str) -> None:
    values = [getattr(record, attribute) for record in records]
    if len(set(values)) != len(values):
        _fail(code)


def build_context_bound_query_provenance_run_manifest(
    *,
    authenticated_plan: AuthenticatedCatalogProvenancePlan,
    reconciled_pages: Sequence[RedactedContextBoundQueryPage],
) -> EdgeProvenanceRunManifest:
    """Cierra un plan autenticado usando sólo provenance query redactado."""

    if not isinstance(authenticated_plan, AuthenticatedCatalogProvenancePlan):
        _fail("query_run_authenticated_plan_invalid")
    if authenticated_plan.production_authority is not False or authenticated_plan.plan.production_authority is not False:
        _fail("query_run_authenticated_plan_authority_forbidden")
    if not isinstance(reconciled_pages, Sequence) or isinstance(reconciled_pages, (str, bytes, bytearray)):
        _fail("query_run_pages_invalid")
    pages = tuple(reconciled_pages)
    if not pages or any(not isinstance(page, RedactedContextBoundQueryPage) for page in pages):
        _fail("query_run_pages_invalid")
    if len(pages) != authenticated_plan.request_count:
        _fail("query_run_request_count_mismatch")

    records = tuple(_record(page) for page in pages)
    expected_identities = {page.identity for page in authenticated_plan.pages}
    observed_identities = {record.expected.identity for record in records}
    if len(observed_identities) != len(records):
        _fail("query_run_observed_identity_duplicate")
    if observed_identities != expected_identities:
        _fail("query_run_expected_pages_mismatch")

    _assert_unique(records, "request_id", "query_run_request_id_reused")
    _assert_unique(records, "reservation_id", "query_run_reservation_id_reused")
    _assert_unique(records, "nonce", "query_run_nonce_reused")
    _assert_unique(records, "receipt_digest", "query_run_receipt_reused")
    _assert_unique(records, "worker_evidence_id", "query_run_worker_evidence_reused")
    _assert_unique(records, "physical_evidence_id", "query_run_physical_evidence_reused")
    _assert_unique(records, "fetch_span_id", "query_run_fetch_span_reused")

    first_payload = pages[0].page.verified_receipt.receipt.payload
    invariant_names = (
        "run_id",
        "authorization_id",
        "approved_commit_sha",
        "github_repository",
        "github_repository_id",
        "github_ref",
        "github_workflow_ref",
        "github_environment",
        "collector_provider",
        "collector_principal",
        "collector_release_id",
        "collector_code_sha256",
        "signing_key_id",
        "location_id",
        "binding_source_key",
        "binding_evidence",
        "context_fingerprint",
        "context_placement",
        "context_wire_key",
        "context_value_path",
    )
    for page in pages[1:]:
        payload = page.page.verified_receipt.receipt.payload
        if not isinstance(payload, ContextBoundEdgeReceiptPayload):
            _fail("query_run_receipt_downgrade")
        for name in invariant_names:
            if getattr(payload, name) != getattr(first_payload, name):
                _fail(f"query_run_context_{name}_mismatch")

    if first_payload.context_placement != "query" or first_payload.context_value_path != ():
        _fail("query_run_query_placement_required")
    plan_bindings = {
        "run_id": authenticated_plan.run_id,
        "authorization_id": authenticated_plan.authorization_id,
        "approved_commit_sha": authenticated_plan.approved_commit_sha,
        "collector_release_id": authenticated_plan.collector_release_id,
        "collector_code_sha256": authenticated_plan.collector_code_sha256,
        "signing_key_id": authenticated_plan.collector_signing_key_id,
    }
    for name, expected_value in plan_bindings.items():
        if getattr(first_payload, name) != expected_value:
            _fail(f"query_run_plan_{name}_mismatch")

    by_identity = {record.expected.identity: record for record in records}
    ordered_records = tuple(by_identity[page.identity] for page in authenticated_plan.pages)
    manifest = EdgeProvenanceRunManifest(
        run_id=first_payload.run_id,
        authorization_id=first_payload.authorization_id,
        approved_commit_sha=first_payload.approved_commit_sha,
        github_repository=first_payload.github_repository,
        github_repository_id=first_payload.github_repository_id,
        github_ref=first_payload.github_ref,
        github_workflow_ref=first_payload.github_workflow_ref,
        github_environment=first_payload.github_environment,
        collector_provider=first_payload.collector_provider,
        collector_principal=first_payload.collector_principal,
        collector_release_id=first_payload.collector_release_id,
        collector_code_sha256=first_payload.collector_code_sha256,
        collector_signing_key_id=first_payload.signing_key_id,
        primary_traversal_id=authenticated_plan.plan.primary_traversal_id,
        reconciliation_traversal_id=authenticated_plan.plan.reconciliation_traversal_id,
        primary_order_by=authenticated_plan.plan.primary_order_by,
        reconciliation_order_by=authenticated_plan.plan.reconciliation_order_by,
        pages=ordered_records,
    )
    if manifest.request_count != authenticated_plan.request_count:
        _fail("query_run_manifest_request_count_mismatch")
    if manifest.production_authority is not False:
        _fail("query_run_manifest_authority_forbidden")
    return manifest
