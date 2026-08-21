"""Composición canónica del run manifest desde un plan autenticado.

Esta capa evita que la API de alto nivel reciba ``expected_pages`` elegidas por
el caller. El conjunto esperado proviene exclusivamente de
``AuthenticatedCatalogProvenancePlan`` y se vuelve a reconciliar con el manifest
run-level existente. No concede autoridad productiva ni abre red.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NoReturn

from precios_supermercados.authenticated_provenance_plan import (
    AuthenticatedCatalogProvenancePlan,
)
from precios_supermercados.cloudflare_trace_evidence import PlatformReconciledEdgePage
from precios_supermercados.edge_provenance_run import (
    EdgeProvenanceRunError,
    EdgeProvenanceRunManifest,
    build_edge_provenance_run_manifest,
)


class AuthenticatedProvenanceRunError(ValueError):
    """El manifest observado no coincide con el plan autenticado."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise AuthenticatedProvenanceRunError(code, message)


def build_authenticated_edge_provenance_run_manifest(
    *,
    authenticated_plan: AuthenticatedCatalogProvenancePlan,
    reconciled_pages: Sequence[PlatformReconciledEdgePage],
) -> EdgeProvenanceRunManifest:
    """Construye el run manifest sin aceptar un plan de páginas caller-controlled."""

    if not isinstance(authenticated_plan, AuthenticatedCatalogProvenancePlan):
        _fail("authenticated_plan_invalid")
    if authenticated_plan.production_authority is not False:
        _fail("authenticated_plan_authority_invalid")
    if authenticated_plan.plan.production_authority is not False:
        _fail("derived_plan_authority_invalid")
    if not isinstance(reconciled_pages, Sequence) or isinstance(reconciled_pages, (str, bytes)):
        _fail("reconciled_pages_invalid")

    try:
        manifest = build_edge_provenance_run_manifest(
            expected_pages=authenticated_plan.pages,
            reconciled_pages=reconciled_pages,
        )
    except EdgeProvenanceRunError as exc:
        raise AuthenticatedProvenanceRunError(f"run_manifest_{exc.code}") from exc

    expected_bindings = {
        "run_id": authenticated_plan.run_id,
        "authorization_id": authenticated_plan.authorization_id,
        "approved_commit_sha": authenticated_plan.approved_commit_sha,
        "collector_release_id": authenticated_plan.collector_release_id,
        "collector_code_sha256": authenticated_plan.collector_code_sha256,
        "collector_signing_key_id": authenticated_plan.collector_signing_key_id,
        "primary_traversal_id": authenticated_plan.plan.primary_traversal_id,
        "reconciliation_traversal_id": authenticated_plan.plan.reconciliation_traversal_id,
        "primary_order_by": authenticated_plan.plan.primary_order_by,
        "reconciliation_order_by": authenticated_plan.plan.reconciliation_order_by,
    }
    for name, expected in expected_bindings.items():
        if getattr(manifest, name) != expected:
            _fail(f"run_manifest_{name}_mismatch")

    if manifest.request_count != authenticated_plan.request_count:
        _fail("run_manifest_request_count_mismatch")

    expected_identities = {page.identity for page in authenticated_plan.pages}
    manifest_identities = {record.expected.identity for record in manifest.pages}
    if manifest_identities != expected_identities:
        _fail("run_manifest_expected_pages_mismatch")

    if manifest.production_authority is not False:
        _fail("run_manifest_authority_invalid")
    return manifest
