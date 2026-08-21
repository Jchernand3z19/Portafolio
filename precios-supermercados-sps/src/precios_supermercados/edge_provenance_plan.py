"""Derivación cerrada del plan de provenance del catálogo de La Colonia.

El manifest run-level no debe recibir una lista de páginas elegida libremente por
el caller: una lista truncada podría ser internamente consistente y aun así no
representar el universo estructural descubierto. Este módulo deriva todas las
páginas esperadas exclusivamente desde ``StructuralDiscoveryReport`` válido y
los dos órdenes canónicos de traversal.

No abre red, no consume Cloudflare y no concede autoridad productiva.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import NoReturn

from precios_supermercados.edge_provenance import canonical_json_bytes
from precios_supermercados.edge_provenance_run import ExpectedProvenancePage
from precios_supermercados.la_colonia_edge_request import validate_la_colonia_edge_request
from precios_supermercados.scrapers.la_colonia_catalog_coverage import (
    StructuralDiscoveryReport,
)
from precios_supermercados.scrapers.la_colonia_graphql import (
    ALLOWED_ORDER_BY,
    MAX_CATALOG_PAGE_SIZE,
    build_product_search_url,
)

DERIVED_PROVENANCE_PLAN_SCHEMA_VERSION = "1"
_DERIVED_PLAN_DOMAIN = b"precios-sps/derived-provenance-plan/v1\0"


class DerivedProvenancePlanError(ValueError):
    """La estructura no permite derivar un plan cerrado y reproducible."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise DerivedProvenancePlanError(code, message)


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


@dataclass(frozen=True, slots=True)
class DerivedCatalogProvenancePlan:
    """Plan exacto de primary + reconciliation derivado de evidencia estructural."""

    run_id: str
    tree_digest: str
    page_size: int
    primary_traversal_id: str
    reconciliation_traversal_id: str
    primary_order_by: str
    reconciliation_order_by: str
    pages: tuple[ExpectedProvenancePage, ...]
    schema_version: str = DERIVED_PROVENANCE_PLAN_SCHEMA_VERSION
    production_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != DERIVED_PROVENANCE_PLAN_SCHEMA_VERSION:
            _fail("derived_plan_schema_invalid")
        _text(self.run_id, "derived_plan_run_id_invalid")
        if (
            not isinstance(self.tree_digest, str)
            or len(self.tree_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.tree_digest)
        ):
            _fail("derived_plan_tree_digest_invalid")
        if (
            isinstance(self.page_size, bool)
            or not isinstance(self.page_size, int)
            or not 1 <= self.page_size <= MAX_CATALOG_PAGE_SIZE
        ):
            _fail("derived_plan_page_size_invalid")
        for name in ("primary_traversal_id", "reconciliation_traversal_id"):
            _text(getattr(self, name), f"derived_plan_{name}_invalid")
        if self.primary_traversal_id == self.reconciliation_traversal_id:
            _fail("derived_plan_traversal_ids_not_distinct")
        if self.primary_order_by not in ALLOWED_ORDER_BY:
            _fail("derived_plan_primary_order_invalid")
        if self.reconciliation_order_by not in ALLOWED_ORDER_BY:
            _fail("derived_plan_reconciliation_order_invalid")
        if self.primary_order_by == self.reconciliation_order_by:
            _fail("derived_plan_orders_not_distinct")
        if not self.pages:
            _fail("derived_plan_pages_empty")
        if any(not isinstance(page, ExpectedProvenancePage) for page in self.pages):
            _fail("derived_plan_page_invalid")
        identities = [page.identity for page in self.pages]
        if len(set(identities)) != len(identities):
            _fail("derived_plan_page_duplicate")
        if self.production_authority is not False:
            _fail("derived_plan_production_authority_forbidden")

    @property
    def request_count(self) -> int:
        return len(self.pages)

    @property
    def primary_pages(self) -> tuple[ExpectedProvenancePage, ...]:
        return tuple(page for page in self.pages if page.traversal_role == "primary")

    @property
    def reconciliation_pages(self) -> tuple[ExpectedProvenancePage, ...]:
        return tuple(page for page in self.pages if page.traversal_role == "reconciliation")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "page_size": self.page_size,
            "pages": [page.canonical_dict() for page in self.pages],
            "primary_order_by": self.primary_order_by,
            "primary_traversal_id": self.primary_traversal_id,
            "reconciliation_order_by": self.reconciliation_order_by,
            "reconciliation_traversal_id": self.reconciliation_traversal_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "tree_digest": self.tree_digest,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            _DERIVED_PLAN_DOMAIN + canonical_json_bytes(self.canonical_dict())
        ).hexdigest()


def _pages_for_order(
    *,
    structure: StructuralDiscoveryReport,
    traversal_role: str,
    traversal_id: str,
    order_by: str,
    page_size: int,
) -> tuple[ExpectedProvenancePage, ...]:
    pages: list[ExpectedProvenancePage] = []
    for partition in structure.valid_leaves:
        if partition.expected_products <= 0:
            continue
        page_count = math.ceil(partition.expected_products / page_size)
        for page_number in range(1, page_count + 1):
            source_url = build_product_search_url(
                page=page_number,
                page_size=page_size,
                query=partition.facet_value,
                category_map=partition.facet_key,
                order_by=order_by,
            )
            validated = validate_la_colonia_edge_request(source_url)
            if validated.selected_facets != ((partition.facet_key, partition.facet_value),):
                _fail("derived_plan_partition_request_mismatch")
            pages.append(
                ExpectedProvenancePage(
                    traversal_role=traversal_role,
                    traversal_id=traversal_id,
                    partition_id=partition.name,
                    order_by=order_by,
                    from_index=validated.from_index,
                    to_index=validated.to_index,
                    request_digest=validated.canonical_request_sha256,
                )
            )
    return tuple(pages)


def derive_catalog_provenance_plan(
    structure: StructuralDiscoveryReport,
    *,
    page_size: int,
    primary_traversal_id: str,
    reconciliation_traversal_id: str,
    primary_order_by: str,
    reconciliation_order_by: str,
) -> DerivedCatalogProvenancePlan:
    """Deriva el conjunto completo de páginas; el caller no aporta digests/rangos."""

    if not isinstance(structure, StructuralDiscoveryReport):
        _fail("derived_plan_structure_invalid")
    if not structure.valid:
        _fail("derived_plan_structure_not_valid")
    if structure.errors:
        _fail("derived_plan_structure_has_errors")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= MAX_CATALOG_PAGE_SIZE
    ):
        _fail("derived_plan_page_size_invalid")
    primary_id = _text(primary_traversal_id, "derived_plan_primary_traversal_id_invalid")
    reconciliation_id = _text(
        reconciliation_traversal_id,
        "derived_plan_reconciliation_traversal_id_invalid",
    )
    if primary_id == reconciliation_id:
        _fail("derived_plan_traversal_ids_not_distinct")
    if primary_order_by not in ALLOWED_ORDER_BY:
        _fail("derived_plan_primary_order_invalid")
    if reconciliation_order_by not in ALLOWED_ORDER_BY:
        _fail("derived_plan_reconciliation_order_invalid")
    if primary_order_by == reconciliation_order_by:
        _fail("derived_plan_orders_not_distinct")

    primary = _pages_for_order(
        structure=structure,
        traversal_role="primary",
        traversal_id=primary_id,
        order_by=primary_order_by,
        page_size=page_size,
    )
    reconciliation = _pages_for_order(
        structure=structure,
        traversal_role="reconciliation",
        traversal_id=reconciliation_id,
        order_by=reconciliation_order_by,
        page_size=page_size,
    )
    if not primary or not reconciliation:
        _fail("derived_plan_pages_empty")
    if len(primary) != len(reconciliation):
        _fail("derived_plan_traversal_page_count_mismatch")

    return DerivedCatalogProvenancePlan(
        run_id=structure.run_id,
        tree_digest=structure.tree_digest,
        page_size=page_size,
        primary_traversal_id=primary_id,
        reconciliation_traversal_id=reconciliation_id,
        primary_order_by=primary_order_by,
        reconciliation_order_by=reconciliation_order_by,
        pages=(*primary, *reconciliation),
    )
