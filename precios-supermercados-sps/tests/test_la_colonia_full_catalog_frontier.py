from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "obtener_catalogo_sps_la_colonia_particionado_v2.py"
spec = importlib.util.spec_from_file_location("frontier_runner", SCRIPT)
assert spec and spec.loader
frontier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontier)


def test_frontier_accepts_tree_starting_at_category_2() -> None:
    values = [
        {
            "key": "category-2",
            "value": "a",
            "quantity": 1200,
            "children": [],
        },
        {
            "key": "category-2",
            "value": "b",
            "quantity": 800,
            "children": [],
        },
    ]
    partitions = frontier._build_frontier(values)
    assert [item.quantity for item in partitions] == [1200, 800]
    assert partitions[0].path == (("category-2", "a"),)


def test_frontier_descends_only_when_category_exceeds_search_window() -> None:
    values = [
        {
            "key": "category-2",
            "value": "big",
            "quantity": 4200,
            "children": [
                {
                    "key": "category-3",
                    "value": "x",
                    "quantity": 2100,
                    "children": [],
                },
                {
                    "key": "category-3",
                    "value": "y",
                    "quantity": 2100,
                    "children": [],
                },
            ],
        },
        {
            "key": "category-2",
            "value": "small",
            "quantity": 300,
            "children": [
                {
                    "key": "category-3",
                    "value": "ignored",
                    "quantity": 300,
                    "children": [],
                }
            ],
        },
    ]
    partitions = frontier._build_frontier(values)
    assert [item.quantity for item in partitions] == [2100, 2100, 300]
    assert partitions[2].path == (("category-2", "small"),)


def test_frontier_rejects_oversized_parent_not_covered_by_children() -> None:
    values = [
        {
            "key": "category-2",
            "value": "big",
            "quantity": 3000,
            "children": [
                {
                    "key": "category-3",
                    "value": "x",
                    "quantity": 1000,
                    "children": [],
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="frontier_below_parent_quantity"):
        frontier._build_frontier(values)


def test_category_values_accepts_category_schema_even_if_type_differs() -> None:
    normalized = {
        "sampling": False,
        "facets": [
            {
                "type": "SOMETHING_NEW",
                "values": [
                    {
                        "key": "category-2",
                        "value": "a",
                        "quantity": 10,
                        "children": [],
                    }
                ],
            }
        ],
    }
    values = frontier._category_values(normalized)
    assert len(values) == 1
    assert values[0]["key"] == "category-2"


def test_partition_facets_keeps_root_and_frontier_path() -> None:
    facets = frontier.base._partition_facets(
        (("category-2", "a"), ("category-3", "b"))
    )
    assert facets == [
        {"key": "category-1", "value": "supermercado"},
        {"key": "category-2", "value": "a"},
        {"key": "category-3", "value": "b"},
    ]
