from __future__ import annotations

import pytest

from precios_supermercados.scrapers.la_colonia_catalog_partitions import (
    discover_leaf_category_partitions,
    estimate_partition_request_plan,
)


def nested_facets():
    return [
        {
            "type": "CATEGORYTREE",
            "values": [
                {
                    "key": "category-1",
                    "value": "supermercado",
                    "quantity": 9,
                    "children": [
                        {
                            "key": "category-2",
                            "value": "bebidas",
                            "quantity": 5,
                            "children": [
                                {
                                    "key": "category-3",
                                    "value": "agua",
                                    "quantity": 2,
                                    "children": [],
                                },
                                {
                                    "key": "category-3",
                                    "value": "jugos",
                                    "quantity": 3,
                                    "children": [],
                                },
                            ],
                        },
                        {
                            "key": "category-2",
                            "value": "alimentos",
                            "quantity": 4,
                            "children": [
                                {
                                    "key": "category-3",
                                    "value": "granos",
                                    "quantity": 4,
                                    "children": [],
                                }
                            ],
                        },
                    ],
                },
                {
                    "key": "category-1",
                    "value": "vacia",
                    "quantity": 0,
                    "children": [],
                },
            ],
        }
    ]


def test_discovers_only_positive_leaf_categories():
    partitions = discover_leaf_category_partitions(nested_facets())

    assert len(partitions) == 3
    assert [item.name for item in partitions] == [
        "partition-0001",
        "partition-0002",
        "partition-0003",
    ]
    assert {item.facet_key for item in partitions} == {"category-3"}
    assert sorted(item.expected_products for item in partitions) == [2, 3, 4]
    assert all(item.leaf for item in partitions)


def test_sampled_facets_are_rejected_as_incomplete_discovery():
    with pytest.raises(ValueError, match="muestreadas"):
        discover_leaf_category_partitions(nested_facets(), sampling=True)


def test_duplicate_leaf_is_deduplicated_but_conflicting_quantity_is_rejected():
    facets = nested_facets()
    duplicate = {"type": "CATEGORYTREE", "values": [facets[0]["values"][0]]}
    assert len(discover_leaf_category_partitions([*facets, duplicate])) == 3

    duplicate["values"][0] = {
        **duplicate["values"][0],
        "quantity": 7,
    }
    with pytest.raises(ValueError, match="cantidades incompatibles"):
        discover_leaf_category_partitions([*facets, duplicate])


def test_partition_limit_is_enforced_before_requests():
    with pytest.raises(ValueError, match="supera el límite"):
        discover_leaf_category_partitions(nested_facets(), max_partitions=2)


def test_request_plan_reserves_recovery_and_optional_reconciliation():
    partitions = discover_leaf_category_partitions(nested_facets())
    plan = estimate_partition_request_plan(
        partitions,
        page_size=2,
        recovery_windows_per_partition=2,
        reconcile_with_second_order=True,
        request_limit=20,
    )

    assert plan.primary_requests == 5
    assert plan.recovery_reserve == 6
    assert plan.reconciliation_requests == 5
    assert plan.requests_planned == 16
    assert plan.within_limit is True


def test_request_plan_rejects_budget_without_executing_traffic():
    partitions = discover_leaf_category_partitions(nested_facets())
    plan = estimate_partition_request_plan(
        partitions,
        page_size=2,
        recovery_windows_per_partition=2,
        reconcile_with_second_order=True,
        request_limit=15,
    )

    assert plan.requests_planned == 16
    assert plan.within_limit is False
