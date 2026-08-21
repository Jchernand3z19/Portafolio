"""Preflight con Script Settings ligado a un plan de catálogo autenticado.

La frontera recomendada deriva internamente el manifest run-level desde el plan
autenticado y las páginas físicas reconciliadas antes de aplicar la verificación
independiente de Script Settings. No acepta un manifest caller-controlled.

No abre red, no despliega y ``production_authority`` permanece siempre ``False``.
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
from precios_supermercados.cloudflare_live_preflight import CloudflareDeploymentEvidence
from precios_supermercados.cloudflare_preflight_settings_binding import (
    CloudflareSettingsBindingError,
    CloudflareSettingsBoundPreflightAssessment,
    bind_script_settings_to_preflight,
)
from precios_supermercados.cloudflare_script_settings import CloudflareScriptSettingsEvidence
from precios_supermercados.cloudflare_trace_evidence import PlatformReconciledEdgePage


class AuthenticatedSettingsPreflightError(ValueError):
    """La composición autenticada con Script Settings no es coherente."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise AuthenticatedSettingsPreflightError(code, message)


def bind_authenticated_script_settings_preflight(
    *,
    authenticated_plan: AuthenticatedCatalogProvenancePlan,
    reconciled_pages: Sequence[PlatformReconciledEdgePage],
    deployment: CloudflareDeploymentEvidence,
    settings: CloudflareScriptSettingsEvidence,
) -> CloudflareSettingsBoundPreflightAssessment:
    """Deriva el manifest autenticado y después liga Script Settings al preflight."""

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
    if not isinstance(settings, CloudflareScriptSettingsEvidence):
        _fail("settings_evidence_invalid")
    if settings.production_authority is not False:
        _fail("settings_authority_invalid")

    try:
        manifest = build_authenticated_edge_provenance_run_manifest(
            authenticated_plan=authenticated_plan,
            reconciled_pages=reconciled_pages,
        )
    except AuthenticatedProvenanceRunError as exc:
        raise AuthenticatedSettingsPreflightError(f"authenticated_run_{exc.code}") from exc

    try:
        assessment = bind_script_settings_to_preflight(
            manifest=manifest,
            deployment=deployment,
            settings=settings,
        )
    except CloudflareSettingsBindingError as exc:
        raise AuthenticatedSettingsPreflightError(f"settings_preflight_{exc.code}") from exc

    if assessment.production_authority is not False:
        _fail("assessment_authority_invalid")
    return assessment
