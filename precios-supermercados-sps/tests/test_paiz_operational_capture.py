from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_paiz_operativo as operational  # noqa: E402


def product(product_id: str, *, name: str | None = None) -> dict:
    return {
        "productId": product_id,
        "productName": name or f"Product {product_id}",
        "items": [{"itemId": product_id, "ean": f"ean-{product_id}"}],
    }


def page(total: int, *product_ids: str) -> dict:
    return {
        "recordsFiltered": total,
        "products": [product(product_id) for product_id in product_ids],
    }


class FakeCapture:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, _seller, tag, _path, _query):
        self.calls.append(tag)
        doc = self.responses[tag]
        return doc, {
            "url": f"https://www.paiz.com.hn/{tag}",
            "sha256": tag.encode().hex().ljust(64, "0")[:64],
            "observed_at": "2026-09-07T18:00:00Z",
        }


def recovery_responses() -> dict[str, dict]:
    prefix = "seller/category-1/abarrotes"
    return {
        f"{prefix}/page-001": page(4, "1", "2"),
        f"{prefix}/page-002": page(4, "2", "3"),
        f"{prefix}/recovery-category-2-facets": {
            "facets": [
                {
                    "key": "category-2",
                    "values": [
                        {"value": "comestibles", "quantity": 2},
                        {"value": "bebidas", "quantity": 2},
                    ],
                }
            ]
        },
        f"{prefix}/recovery/category-2/comestibles/page-001": page(2, "1", "2"),
        f"{prefix}/recovery/category-2/bebidas/page-001": page(2, "3", "4"),
    }


def test_identical_product_repeated_between_pages_triggers_exact_repartition(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    capture = FakeCapture(recovery_responses())

    products, evidence, recovery = operational._capture_category(
        capture,
        seller="seller",
        category="abarrotes",
        expected_total=4,
        common={},
    )

    assert set(products) == {"1", "2", "3", "4"}
    assert len(evidence) == 2
    assert recovery is not None
    assert recovery["strategy"] == "category_2_exhaustive_repartition"
    assert recovery["trigger_tag"].endswith("page-002")
    assert recovery["duplicate_product_count"] == 1


def test_identical_product_repeated_between_categories_is_reconciled_by_source_identity():
    first = {"1": product("1"), "2": product("2")}
    second = {"2": copy.deepcopy(first["2"]), "3": product("3")}

    overlap = operational._merge_exact_products(
        first,
        second,
        tag="seller/category-1/second",
        recover_on_identical_overlap=False,
    )

    assert overlap == {"2"}
    assert set(first) == {"1", "2", "3"}


def test_non_identity_document_drift_triggers_exact_repartition(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    responses = recovery_responses()
    repeated = product("2", name="Updated display name")
    repeated["link"] = "/updated-link/p"
    responses["seller/category-1/abarrotes/page-002"] = {
        "recordsFiltered": 4,
        "products": [repeated, product("3")],
    }

    products, _evidence, recovery = operational._capture_category(
        FakeCapture(responses),
        seller="seller",
        category="abarrotes",
        expected_total=4,
        common={},
    )

    assert set(products) == {"1", "2", "3", "4"}
    assert recovery is not None
    assert recovery["trigger_tag"].endswith("page-002")


def test_contradictory_source_identity_remains_fail_closed():
    first = {"2": product("2")}
    changed = product("2")
    changed["items"][0]["itemId"] = "different-item"

    with pytest.raises(RuntimeError, match="product_identity_conflict"):
        operational._merge_exact_products(
            first,
            {"2": changed},
            tag="seller/category-1/abarrotes/page-002",
            recover_on_identical_overlap=False,
        )


def test_repartition_rejects_duplicate_membership_that_cannot_reach_exact_coverage(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    responses = recovery_responses()
    responses[
        "seller/category-1/abarrotes/recovery/category-2/bebidas/page-001"
    ] = page(2, "2", "3")

    with pytest.raises(RuntimeError, match="category_recovery_incomplete"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="abarrotes",
            expected_total=4,
            common={},
        )


def test_short_page_never_produces_an_incomplete_snapshot(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    responses = recovery_responses()
    responses["seller/category-1/abarrotes/page-002"] = page(4, "3")

    with pytest.raises(RuntimeError, match="page_count_changed"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="abarrotes",
            expected_total=4,
            common={},
        )


def test_category_two_recovery_requires_exact_parent_total(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    responses = recovery_responses()
    responses["seller/category-1/abarrotes/recovery-category-2-facets"] = {
        "facets": [
            {
                "key": "category-2",
                "values": [{"value": "comestibles", "quantity": 3}],
            }
        ]
    }

    with pytest.raises(RuntimeError, match="category_2_total_mismatch"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="abarrotes",
            expected_total=4,
            common={},
        )
