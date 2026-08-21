"""Deriva el plan canónico de catálogo desde un discovery estructural verificado."""

from __future__ import annotations

from typing import NoReturn

from precios_supermercados.authenticated_provenance_plan import (
    AuthenticatedCatalogProvenancePlan,
    AuthenticatedProvenancePlanError,
    derive_authenticated_catalog_provenance_plan,
)
from precios_supermercados.scrapers.la_colonia_facet_discovery import (
    FACET_DISCOVERY_PAGE_SIZE,
    FACET_DISCOVERY_REQUEST_LIMIT,
)
from precios_supermercados.structural_discovery_manifest import VerifiedStructuralDiscovery

CANONICAL_CATALOG_PAGE_SIZE = FACET_DISCOVERY_PAGE_SIZE
CANONICAL_CATALOG_REQUEST_LIMIT = FACET_DISCOVERY_REQUEST_LIMIT
CANONICAL_PRIMARY_ORDER_BY = "OrderByNameASC"
CANONICAL_RECONCILIATION_ORDER_BY = "OrderByNameDESC"


class CanonicalAuthenticatedProvenancePlanError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CanonicalAuthenticatedProvenancePlanError(code, message)


def _traversal_id(run_id: str, role: str) -> str:
    if role not in {"primary", "reconciliation"}:
        _fail("canonical_plan_traversal_role_invalid")
    return f"{run_id}:{role}"


def derive_canonical_authenticated_catalog_plan(
    discovery: VerifiedStructuralDiscovery,
) -> AuthenticatedCatalogProvenancePlan:
    """Fija page size, órdenes y traversal IDs; el caller no aporta overrides."""
    if not isinstance(discovery, VerifiedStructuralDiscovery):
        _fail("canonical_plan_discovery_invalid")
    if discovery.production_authority is not False:
        _fail("canonical_plan_discovery_authority_invalid")

    primary_id = _traversal_id(discovery.run_id, "primary")
    reconciliation_id = _traversal_id(discovery.run_id, "reconciliation")
    try:
        plan = derive_authenticated_catalog_provenance_plan(
            discovery,
            page_size=CANONICAL_CATALOG_PAGE_SIZE,
            primary_traversal_id=primary_id,
            reconciliation_traversal_id=reconciliation_id,
            primary_order_by=CANONICAL_PRIMARY_ORDER_BY,
            reconciliation_order_by=CANONICAL_RECONCILIATION_ORDER_BY,
        )
    except AuthenticatedProvenancePlanError as exc:
        raise CanonicalAuthenticatedProvenancePlanError(
            f"authenticated_{exc.code}"
        ) from exc

    if plan.request_count > CANONICAL_CATALOG_REQUEST_LIMIT:
        _fail("canonical_plan_request_limit_exceeded")
    if plan.plan.page_size != CANONICAL_CATALOG_PAGE_SIZE:
        _fail("canonical_plan_page_size_mismatch")
    if plan.plan.primary_order_by != CANONICAL_PRIMARY_ORDER_BY:
        _fail("canonical_plan_primary_order_mismatch")
    if plan.plan.reconciliation_order_by != CANONICAL_RECONCILIATION_ORDER_BY:
        _fail("canonical_plan_reconciliation_order_mismatch")
    if plan.plan.primary_traversal_id != primary_id:
        _fail("canonical_plan_primary_traversal_mismatch")
    if plan.plan.reconciliation_traversal_id != reconciliation_id:
        _fail("canonical_plan_reconciliation_traversal_mismatch")
    if len(plan.primary_pages) != len(plan.reconciliation_pages):
        _fail("canonical_plan_traversal_page_count_mismatch")
    if plan.production_authority is not False:
        _fail("canonical_plan_authority_forbidden")
    return plan
