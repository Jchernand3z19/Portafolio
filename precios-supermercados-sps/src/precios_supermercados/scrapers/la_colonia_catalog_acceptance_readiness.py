"""Assessment fail-closed previo a la autoridad productiva del catálogo.

Esta capa NO elimina el gate ``trusted_collector_provenance_unavailable`` y NO
convierte evidencia offline en aceptación comercial. Su función es distinguir
con precisión dos estados que antes quedaban mezclados:

- el catálogo y su provenance satisfacen todos los invariantes técnicos
  demostrables offline;
- existe autoridad productiva real para aceptar ese catálogo.

El segundo estado permanece falso hasta que exista una atestación productiva
separada, obtenida de infraestructura desplegada y verificada. Ningún booleano
del caller puede concederla aquí.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NoReturn

from precios_supermercados.canonical_authenticated_provenance_plan import (
    CANONICAL_CATALOG_REQUEST_LIMIT,
    CanonicalAuthenticatedProvenancePlanError,
    derive_canonical_authenticated_catalog_plan,
)
from precios_supermercados.scrapers.la_colonia_catalog_coverage import (
    CatalogCoverageReport,
    _evaluate_canonical_catalog_coverage,
)
from precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer import (
    VerifiedCatalogProvenanceRun,
)
from precios_supermercados.structural_discovery_manifest import VerifiedStructuralDiscovery

_TRUST_GATE = "trusted_collector_provenance_unavailable"
_AUTHORITY_BLOCKER = "production_authority_not_established"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class CatalogAcceptanceReadinessError(ValueError):
    """La evidencia no forma un candidato canónico coherente de aceptación."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CatalogAcceptanceReadinessError(code, message)


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _fail(code)
    return value


@dataclass(frozen=True, slots=True)
class VerifiedCatalogAcceptanceReadiness:
    """Resultado técnico que deliberadamente NO concede aceptación productiva."""

    coverage: CatalogCoverageReport
    discovery_digest: str
    authenticated_plan_digest: str
    provenance_manifest_digest: str
    technical_catalog_complete: bool
    ready_for_productive_authority_evidence: bool
    catalog_accepted: bool
    blockers: tuple[str, ...]
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.coverage, CatalogCoverageReport):
            _fail("readiness_coverage_invalid")
        object.__setattr__(
            self,
            "discovery_digest",
            _sha256(self.discovery_digest, "readiness_discovery_digest_invalid"),
        )
        object.__setattr__(
            self,
            "authenticated_plan_digest",
            _sha256(
                self.authenticated_plan_digest,
                "readiness_authenticated_plan_digest_invalid",
            ),
        )
        object.__setattr__(
            self,
            "provenance_manifest_digest",
            _sha256(
                self.provenance_manifest_digest,
                "readiness_provenance_manifest_digest_invalid",
            ),
        )
        if not isinstance(self.technical_catalog_complete, bool):
            _fail("readiness_technical_catalog_complete_invalid")
        if not isinstance(self.ready_for_productive_authority_evidence, bool):
            _fail("readiness_productive_authority_readiness_invalid")
        if self.ready_for_productive_authority_evidence != self.technical_catalog_complete:
            _fail("readiness_productive_authority_readiness_inconsistent")
        if self.catalog_accepted is not False:
            _fail("readiness_catalog_acceptance_forbidden")
        if self.production_authority is not False:
            _fail("readiness_production_authority_forbidden")
        if not isinstance(self.blockers, tuple) or any(
            not isinstance(item, str) or not item for item in self.blockers
        ):
            _fail("readiness_blockers_invalid")
        if len(set(self.blockers)) != len(self.blockers):
            _fail("readiness_blockers_duplicate")
        mandatory = {_TRUST_GATE, _AUTHORITY_BLOCKER}
        if not mandatory.issubset(self.blockers):
            _fail("readiness_authority_blocker_missing")
        technical_blockers = tuple(
            item for item in self.blockers if item not in mandatory
        )
        if self.technical_catalog_complete != (len(technical_blockers) == 0):
            _fail("readiness_technical_state_inconsistent")
        if self.coverage.accepted is not False:
            _fail("readiness_coverage_must_remain_unaccepted")
        if _TRUST_GATE not in self.coverage._reasons:
            _fail("readiness_coverage_trust_gate_missing")


def _assert_context_binding(discovery, plan, provenance: VerifiedCatalogProvenanceRun) -> None:
    collection = provenance.collection
    manifest = provenance.manifest

    if collection.plan_digest != plan.digest:
        _fail("readiness_collection_plan_digest_mismatch")
    if collection.discovery_digest != discovery.digest:
        _fail("readiness_collection_discovery_digest_mismatch")

    expected_manifest = {
        "run_id": plan.run_id,
        "authorization_id": plan.authorization_id,
        "approved_commit_sha": plan.approved_commit_sha,
        "collector_release_id": plan.collector_release_id,
        "collector_code_sha256": plan.collector_code_sha256,
        "collector_signing_key_id": plan.collector_signing_key_id,
        "primary_traversal_id": plan.plan.primary_traversal_id,
        "reconciliation_traversal_id": plan.plan.reconciliation_traversal_id,
        "primary_order_by": plan.plan.primary_order_by,
        "reconciliation_order_by": plan.plan.reconciliation_order_by,
    }
    for name, expected in expected_manifest.items():
        if getattr(manifest, name) != expected:
            _fail(f"readiness_manifest_{name}_mismatch")
    if manifest.request_count != plan.request_count:
        _fail("readiness_manifest_request_count_mismatch")

    expected_pages = {page.identity for page in plan.pages}
    observed_pages = {record.expected.identity for record in manifest.pages}
    if observed_pages != expected_pages or len(manifest.pages) != len(expected_pages):
        _fail("readiness_manifest_page_set_mismatch")

    primary = collection.primary
    reconciliation = collection.reconciliation
    traversal_bindings = (
        (
            primary,
            plan.plan.primary_traversal_id,
            plan.plan.primary_order_by,
            "primary",
        ),
        (
            reconciliation,
            plan.plan.reconciliation_traversal_id,
            plan.plan.reconciliation_order_by,
            "reconciliation",
        ),
    )
    for traversal, traversal_id, order_by, label in traversal_bindings:
        if traversal.run_id != plan.run_id:
            _fail(f"readiness_{label}_run_id_mismatch")
        if traversal.tree_digest != discovery.tree_digest:
            _fail(f"readiness_{label}_tree_digest_mismatch")
        if traversal.traversal_id != traversal_id:
            _fail(f"readiness_{label}_traversal_id_mismatch")
        if traversal.order_by != order_by:
            _fail(f"readiness_{label}_order_by_mismatch")

    if provenance.production_authority is not False:
        _fail("readiness_provenance_authority_forbidden")
    if collection.production_authority is not False:
        _fail("readiness_collection_authority_forbidden")
    if manifest.production_authority is not False:
        _fail("readiness_manifest_authority_forbidden")


def assess_verified_catalog_acceptance_readiness(
    *,
    discovery: VerifiedStructuralDiscovery,
    provenance: VerifiedCatalogProvenanceRun,
) -> VerifiedCatalogAcceptanceReadiness:
    """Evalúa completitud real sin permitir que el caller conceda autoridad.

    ``technical_catalog_complete`` sólo puede ser verdadero cuando la única
    razón que impide la aceptación canónica es el gate explícito de trusted
    collector. Aun en ese caso ``catalog_accepted`` permanece falso.
    """

    if not isinstance(discovery, VerifiedStructuralDiscovery):
        _fail("readiness_discovery_invalid")
    if discovery.production_authority is not False:
        _fail("readiness_discovery_authority_forbidden")
    if not isinstance(provenance, VerifiedCatalogProvenanceRun):
        _fail("readiness_provenance_invalid")

    try:
        plan = derive_canonical_authenticated_catalog_plan(discovery)
    except CanonicalAuthenticatedProvenancePlanError as exc:
        raise CatalogAcceptanceReadinessError(
            f"readiness_plan_{exc.code}"
        ) from exc

    _assert_context_binding(discovery, plan, provenance)

    coverage = _evaluate_canonical_catalog_coverage(
        discovery.structure,
        provenance.collection.primary,
        provenance.collection.reconciliation,
        request_limit=CANONICAL_CATALOG_REQUEST_LIMIT,
    )
    reasons = tuple(coverage._reasons)
    if _TRUST_GATE not in reasons:
        _fail("readiness_coverage_trust_gate_missing")

    technical_reasons = tuple(reason for reason in reasons if reason != _TRUST_GATE)
    technical_complete = len(technical_reasons) == 0
    blockers = tuple(
        dict.fromkeys(
            (
                *technical_reasons,
                _TRUST_GATE,
                _AUTHORITY_BLOCKER,
            )
        )
    )
    return VerifiedCatalogAcceptanceReadiness(
        coverage=coverage,
        discovery_digest=discovery.digest,
        authenticated_plan_digest=plan.digest,
        provenance_manifest_digest=provenance.manifest.digest,
        technical_catalog_complete=technical_complete,
        ready_for_productive_authority_evidence=technical_complete,
        catalog_accepted=False,
        blockers=blockers,
    )
