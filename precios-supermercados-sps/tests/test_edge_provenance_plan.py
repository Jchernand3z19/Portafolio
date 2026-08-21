from __future__ import annotations

import dataclasses

import pytest

from precios_supermercados.edge_provenance_plan import (
    DerivedProvenancePlanError,
    derive_catalog_provenance_plan,
)
from precios_supermercados.la_colonia_edge_request import validate_la_colonia_edge_request
from precios_supermercados.scrapers.la_colonia_catalog_coverage import (
    PartitionSpec,
    StructuralDiscoveryReport,
)


def _structure(*, status: str = "VALID", errors: tuple[str, ...] = ()) -> StructuralDiscoveryReport:
    leaves = (
        PartitionSpec(
            name="partition-0001",
            facet_key="category-2",
            facet_value="abarrotes",
            expected_products=3,
            _category_path=(("category-1", "supermercado"), ("category-2", "abarrotes")),
        ),
        PartitionSpec(
            name="partition-0002",
            facet_key="category-2",
            facet_value="bebidas",
            expected_products=1,
            _category_path=(("category-1", "supermercado"), ("category-2", "bebidas")),
        ),
        PartitionSpec(
            name="partition-0003",
            facet_key="category-2",
            facet_value="sin-stock-estructural",
            expected_products=0,
            _category_path=(("category-1", "supermercado"), ("category-2", "sin-stock-estructural")),
        ),
    )
    return StructuralDiscoveryReport(
        run_id="run-derived-plan-001",
        tree_digest="a" * 64,
        nodes_seen=5,
        positive_nodes=4,
        valid_leaves=leaves,
        invalid_positive_leaves=0,
        duplicate_structural_nodes=0,
        discovered_leaf_identities=("b" * 64, "c" * 64, "d" * 64),
        errors=errors,
        structural_status=status,
        root_total=4,
    )


def _derive():
    return derive_catalog_provenance_plan(
        _structure(),
        page_size=2,
        primary_traversal_id="traversal-primary-001",
        reconciliation_traversal_id="traversal-reconciliation-001",
        primary_order_by="OrderByNameASC",
        reconciliation_order_by="OrderByNameDESC",
    )


def test_deriva_todas_las_paginas_de_ambos_traversals() -> None:
    plan = _derive()

    assert plan.run_id == "run-derived-plan-001"
    assert plan.page_size == 2
    assert plan.request_count == 6
    assert len(plan.primary_pages) == 3
    assert len(plan.reconciliation_pages) == 3
    assert plan.production_authority is False

    primary_ranges = [
        (page.partition_id, page.from_index, page.to_index)
        for page in plan.primary_pages
    ]
    assert primary_ranges == [
        ("partition-0001", 0, 1),
        ("partition-0001", 2, 3),
        ("partition-0002", 0, 1),
    ]
    assert all(page.partition_id != "partition-0003" for page in plan.pages)


def test_digests_se_derivan_del_builder_y_validador_independiente() -> None:
    plan = _derive()

    for page in plan.pages:
        # El plan no expone una URL propia. Reconstruimos la URL sólo desde el
        # fixture estructural para comprobar que el digest fue derivado y no
        # copiado de un argumento libre.
        partition = next(
            item for item in _structure().valid_leaves if item.name == page.partition_id
        )
        page_size = plan.page_size
        page_number = page.from_index // page_size + 1
        from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url

        url = build_product_search_url(
            page=page_number,
            page_size=page_size,
            query=partition.facet_value,
            category_map=partition.facet_key,
            order_by=page.order_by,
        )
        validated = validate_la_colonia_edge_request(url)
        assert page.request_digest == validated.canonical_request_sha256
        assert page.from_index == validated.from_index
        assert page.to_index == validated.to_index


def test_digest_del_plan_es_determinista_y_sensible_al_plan() -> None:
    left = _derive()
    right = _derive()
    assert left.digest == right.digest
    assert len(left.digest) == 64

    changed = derive_catalog_provenance_plan(
        dataclasses.replace(_structure(), tree_digest="e" * 64),
        page_size=2,
        primary_traversal_id="traversal-primary-001",
        reconciliation_traversal_id="traversal-reconciliation-001",
        primary_order_by="OrderByNameASC",
        reconciliation_order_by="OrderByNameDESC",
    )
    assert changed.digest != left.digest


def test_estructura_invalida_no_puede_autodefinir_un_plan() -> None:
    with pytest.raises(DerivedProvenancePlanError, match="derived_plan_structure_not_valid"):
        derive_catalog_provenance_plan(
            _structure(status="INVALID", errors=("leaf_union_below_root_total",)),
            page_size=2,
            primary_traversal_id="traversal-primary-001",
            reconciliation_traversal_id="traversal-reconciliation-001",
            primary_order_by="OrderByNameASC",
            reconciliation_order_by="OrderByNameDESC",
        )


def test_orders_y_traversals_deben_ser_independientes() -> None:
    with pytest.raises(DerivedProvenancePlanError, match="derived_plan_orders_not_distinct"):
        derive_catalog_provenance_plan(
            _structure(),
            page_size=2,
            primary_traversal_id="traversal-primary-001",
            reconciliation_traversal_id="traversal-reconciliation-001",
            primary_order_by="OrderByNameASC",
            reconciliation_order_by="OrderByNameASC",
        )

    with pytest.raises(
        DerivedProvenancePlanError,
        match="derived_plan_traversal_ids_not_distinct",
    ):
        derive_catalog_provenance_plan(
            _structure(),
            page_size=2,
            primary_traversal_id="same-traversal",
            reconciliation_traversal_id="same-traversal",
            primary_order_by="OrderByNameASC",
            reconciliation_order_by="OrderByNameDESC",
        )


def test_page_size_no_puede_exceder_limite_canonico() -> None:
    with pytest.raises(DerivedProvenancePlanError, match="derived_plan_page_size_invalid"):
        derive_catalog_provenance_plan(
            _structure(),
            page_size=51,
            primary_traversal_id="traversal-primary-001",
            reconciliation_traversal_id="traversal-reconciliation-001",
            primary_order_by="OrderByNameASC",
            reconciliation_order_by="OrderByNameDESC",
        )


def test_catalogo_sin_paginas_positivas_falla_cerrado() -> None:
    empty = dataclasses.replace(
        _structure(),
        valid_leaves=(
            PartitionSpec(
                name="partition-0001",
                facet_key="category-1",
                facet_value="vacio",
                expected_products=0,
                _category_path=(("category-1", "vacio"),),
            ),
        ),
        root_total=0,
    )
    with pytest.raises(DerivedProvenancePlanError, match="derived_plan_pages_empty"):
        derive_catalog_provenance_plan(
            empty,
            page_size=50,
            primary_traversal_id="traversal-primary-001",
            reconciliation_traversal_id="traversal-reconciliation-001",
            primary_order_by="OrderByNameASC",
            reconciliation_order_by="OrderByNameDESC",
        )
