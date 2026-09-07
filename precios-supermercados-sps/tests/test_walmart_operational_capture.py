from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_walmart_operativo as operational  # noqa: E402


def product(product_id: str) -> dict:
    return {"productId": product_id, "items": [{"itemId": product_id}]}


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
        return self.responses[tag], {
            "tag": tag,
            "url": f"https://www.walmart.com.hn/{tag}",
            "sha256": tag.encode().hex().ljust(64, "0")[:64],
            "observed_at": "2026-09-07T20:51:41Z",
        }


def total_drift_responses() -> dict[str, dict]:
    prefix = "seller/category-1/electronica"
    recovery = f"{prefix}/recovery-total-drift"
    return {
        f"{prefix}/page-001": page(5, "1", "2"),
        f"{recovery}/page-001": page(5, "1", "2"),
        f"{recovery}/page-002": page(5, "3", "4"),
        f"{recovery}/page-003": page(5, "5"),
    }


def test_category_total_drift_restarts_category_and_requires_exact_membership(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    capture = FakeCapture(total_drift_responses())

    products, evidence, final_total, recovery = operational._capture_category(
        capture,
        seller="seller",
        category="electronica",
        expected_total=4,
        common={},
        facets_root="/facets/seller",
    )

    assert set(products) == {"1", "2", "3", "4", "5"}
    assert final_total == 5
    assert len(evidence) == 3
    assert recovery == {
        "category": "electronica",
        "strategy": "parent_category_exact_restart",
        "trigger_tag": "seller/category-1/electronica/page-001",
        "trigger_sha256": "73656c6c65722f63617465676f72792d312f656c656374726f6e6963612f7061",
        "trigger_observed_at": "2026-09-07T20:51:41Z",
        "previous_total": 4,
        "recovered_total": 5,
    }


def test_category_total_drift_rejects_a_second_change(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    responses = total_drift_responses()
    responses[
        "seller/category-1/electronica/recovery-total-drift/page-001"
    ] = page(6, "1", "2")

    with pytest.raises(RuntimeError, match="category_total_changed_again"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )


def test_category_total_recovery_rejects_repeated_membership(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    responses = total_drift_responses()
    responses[
        "seller/category-1/electronica/recovery-total-drift/page-002"
    ] = page(5, "2", "3")

    with pytest.raises(RuntimeError, match="product_membership_overlap"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )


def test_prepartitioned_category_does_not_guess_a_new_parent_total(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", {"electronica"})
    responses = {
        "seller/electronica/category2-facets": {
            "facets": [
                {
                    "key": "category-2",
                    "values": [{"value": "audio", "quantity": 4}],
                }
            ]
        },
        "seller/category-1/electronica/category-2/audio/page-001": page(5, "1", "2"),
    }

    with pytest.raises(RuntimeError, match="category2_partition_total_changed"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )
