from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "obtener_catalogo_sps_la_colonia_particionado_v3.py"
spec = importlib.util.spec_from_file_location("brand_runner", SCRIPT)
assert spec and spec.loader
brand = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = brand
spec.loader.exec_module(brand)


def test_brand_values_selects_brand_facet_without_persisting_names() -> None:
    normalized = {
        "facets": [
            {
                "type": "BRAND",
                "values": [
                    {"key": "brand", "value": "a", "quantity": 120},
                    {"key": "brand", "value": "b", "quantity": 80},
                ],
            },
            {
                "type": "CATEGORYTREE",
                "values": [
                    {"key": "category-2", "value": "c", "quantity": 200}
                ],
            },
        ]
    }
    values = brand._brand_values(normalized)
    assert [item["quantity"] for item in values] == [120, 80]


def test_brand_frontier_creates_disjoint_selected_facets() -> None:
    values = [
        {"key": "brand", "value": "a", "quantity": 1200},
        {"key": "brand", "value": "b", "quantity": 800},
    ]
    partitions = brand._build_brand_frontier(values)
    assert [item.quantity for item in partitions] == [1200, 800]
    assert partitions[0].path == (("brand", "a"),)
    assert brand.frontier.base._partition_facets(partitions[0].path) == [
        {"key": "category-1", "value": "supermercado"},
        {"key": "brand", "value": "a"},
    ]


def test_brand_frontier_rejects_partition_above_vtex_window() -> None:
    with pytest.raises(ValueError, match="brand_partition_exceeds_search_window"):
        brand._build_brand_frontier(
            [{"key": "brand", "value": "a", "quantity": 2501}]
        )


def test_brand_frontier_rejects_conflicting_duplicate_value() -> None:
    with pytest.raises(ValueError, match="duplicate_brand_quantity_conflict"):
        brand._build_brand_frontier(
            [
                {"key": "brand", "value": "a", "quantity": 10},
                {"key": "brand", "value": "a", "quantity": 11},
            ]
        )


def test_brand_values_requires_actual_brand_key() -> None:
    with pytest.raises(ValueError, match="brand_values_missing"):
        brand._brand_values(
            {
                "facets": [
                    {
                        "type": "BRAND",
                        "values": [
                            {"key": "category-2", "value": "x", "quantity": 10}
                        ],
                    }
                ]
            }
        )
