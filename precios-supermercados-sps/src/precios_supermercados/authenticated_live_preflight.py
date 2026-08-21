"""Preflight de alto nivel ligado al plan de catálogo autenticado.

Esta composición evita que la frontera recomendada de preflight reciba un
``EdgeProvenanceRunManifest`` caller-controlled. Reconstruye primero el manifest
run-level desde ``AuthenticatedCatalogProvenancePlan`` y las páginas físicas
reconciliadas, y sólo entonces ejecuta el preflight Cloudflare existente.

No consulta red, no despliega y nunca concede autoridad productiva.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NoReturn

from precios_supermercados.authenticated_provenance_plan import (
    AuthenticatedCatalogProvenancePlan,
)
from precios_supermercados.authenticated_provenance_run import (
    AuthenticatedProvenanceRunError,
    build_authenticated_edge_provenance_run_manifest,
)
from precios_supermercados.cloudflare_live_preflight import (
    CloudflareDeploymentEvidence,
    CloudflareLivePreflightAssessment,
    CloudflareLivePreflightError,
    assess_cloudflare_live_preflight,
)
from precios_supermercados.cloudflare_trace_evidence import PlatformReconciledEdgePage


class AuthenticatedLivePreflightError(ValueError):
    """La composición autenticada no produjo un preflight coherente."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise AuthenticatedLivePreflightError(code, message)


def assess_authenticated_cloudflare_live_preflight(
    *,
    authenticated_plan: AuthenticatedCatalogProvenancePlan,
    reconciled_pages: Sequence[PlatformReconciledEdgePage],
    deployment: CloudflareDeploymentEvidence,
) -> CloudflareLivePreflightAssessment:
    """Deriva el manifest autenticado y ejecuta el preflight sin aceptarlo como input."""

    if not isinstance(authenticated_plan, AuthenticatedCatalogProvenancePlan):
        _fail("authenticated_plan_invalid")
    if authenticated_plan.production_authority is not False:
        _fail("authenticated_plan_authority_invalid")
    if not isinstance(reconciled_pages, Sequence) or isinstance(reconciled_pages, (str, bytes)):
        _fail("reconciled_pages_invalid")
    if not isinstance(deployment, CloudflareDeploymentEvidence):
        _fail("deployment_evidence_invalid")
    if deployment.production_authority is not False:
        _fail("deployment_authority_invalid")

    try:
        manifest = build_authenticated_edge_provenance_run_manifest(
            authenticated_plan=authenticated_plan,
            reconciled_pages=reconciled_pages,
        )
    except AuthenticatedProvenanceRunError as exc:
        raise AuthenticatedLivePreflightError(f"authenticated_run_{exc.code}") from exc

    try:
        assessment = assess_cloudflare_live_preflight(manifest, deployment)
    except CloudflareLivePreflightError as exc:
        raise AuthenticatedLivePreflightError(f"cloudflare_preflight_{exc.code}") from exc

    if assessment.run_manifest_digest != manifest.digest:
        _fail("assessment_run_manifest_digest_mismatch")
    if assessment.production_authority is not False:
        _fail("assessment_authority_invalid")
    return assessment
