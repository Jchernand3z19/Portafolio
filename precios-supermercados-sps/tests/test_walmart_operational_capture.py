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


def facets(key: str, **values: int) -> dict:
    return {
        "facets": [
            {
                "key": key,
                "values": [
                    {"value": value, "quantity": quantity}
                    for value, quantity in values.items()
                ],
            }
        ]
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


def category2_drift_responses() -> dict[str, dict]:
    prefix = "seller/category-1/electronica/category-2"
    recovery = "/recovery-total-drift"
    return {
        "seller/electronica/category2-facets": facets("category-2", audio=4, video=2),
        f"{prefix}/audio/page-001": page(5, "1", "2"),
        "seller/electronica/category2-facets/recovery-total-drift": facets(
            "category-2", audio=5, video=2
        ),
        f"{prefix}/audio{recovery}/page-001": page(5, "1", "2"),
        f"{prefix}/audio{recovery}/page-002": page(5, "3", "4"),
        f"{prefix}/audio{recovery}/page-003": page(5, "5"),
        f"{prefix}/video{recovery}/page-001": page(2, "6", "7"),
        "seller/electronica/category2-facets/recovery-confirmation": facets(
            "category-2", audio=5, video=2
        ),
    }


def membership_shift_responses() -> dict[str, dict]:
    parent = "seller/category-1/electronica"
    recovery = "/recovery-membership-overlap"
    facet_prefix = "seller/electronica/category2-facets"
    return {
        f"{parent}/page-001": page(4, "1", "2"),
        f"{parent}/page-002": page(4, "2", "3"),
        f"{facet_prefix}{recovery}": facets("category-2", audio=2, video=2),
        f"{parent}/category-2/audio{recovery}/page-001": page(2, "1", "2"),
        f"{parent}/category-2/video{recovery}/page-001": page(2, "3", "4"),
        f"{facet_prefix}/recovery-membership-confirmation": facets(
            "category-2", audio=2, video=2
        ),
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


def test_category2_total_drift_rechecks_facets_and_restarts_all_child_partitions(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", {"electronica"})
    capture = FakeCapture(category2_drift_responses())

    products, evidence, final_total, recovery = operational._capture_category(
        capture,
        seller="seller",
        category="electronica",
        expected_total=6,
        common={},
        facets_root="/facets/seller",
    )

    assert set(products) == {"1", "2", "3", "4", "5", "6", "7"}
    assert final_total == 7
    assert len(evidence) == 4
    assert recovery is not None
    assert recovery["strategy"] == "category2_exact_restart"
    assert recovery["previous_total"] == 6
    assert recovery["recovered_total"] == 7
    assert recovery["previous_partition_total"] == 4
    assert recovery["recovered_partition_total"] == 5
    assert capture.calls[-1] == "seller/electronica/category2-facets/recovery-confirmation"


def test_category2_total_drift_requires_facet_confirmation_of_observed_total(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", {"electronica"})
    responses = category2_drift_responses()
    responses["seller/electronica/category2-facets/recovery-total-drift"] = facets(
        "category-2", audio=4, video=2
    )

    with pytest.raises(RuntimeError, match="category2_drift_not_confirmed"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=6,
            common={},
            facets_root="/facets/seller",
        )


def test_category2_total_recovery_fails_closed_if_facets_change_again(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", {"electronica"})
    responses = category2_drift_responses()
    responses["seller/electronica/category2-facets/recovery-confirmation"] = facets(
        "category-2", audio=5, video=3
    )

    with pytest.raises(RuntimeError, match="category2_changed_during_recovery"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=6,
            common={},
            facets_root="/facets/seller",
        )


def test_membership_shift_repartitions_category2_and_confirms_facets(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    capture = FakeCapture(membership_shift_responses())

    products, evidence, final_total, recovery = operational._capture_category(
        capture,
        seller="seller",
        category="electronica",
        expected_total=4,
        common={},
        facets_root="/facets/seller",
    )

    assert set(products) == {"1", "2", "3", "4"}
    assert len(evidence) == 2
    assert final_total == 4
    assert recovery is not None
    assert recovery["strategy"] == "category2_exact_membership_restart"
    assert recovery["trigger_tag"].endswith("page-002")
    assert recovery["duplicate_product_count"] == 1
    assert recovery["previous_total"] == recovery["recovered_total"] == 4
    assert capture.calls[-1].endswith("recovery-membership-confirmation")


def test_store_reports_membership_recovery_separately_from_total_recovery(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    monkeypatch.setattr(operational, "parse_products", _parsed_products)
    responses = membership_shift_responses()
    responses.update(
        {
            "seller/facets-before": facets("category-1", electronica=4),
            "seller/root-before": page(4, "root"),
            "seller/facets-after": facets("category-1", electronica=4),
            "seller/root-after": page(4, "root"),
        }
    )

    snapshot = operational.capture_store(
        FakeCapture(responses),
        seller="seller",
        location_id="location",
        city="city",
        store_name="store",
        home_sha="h" * 64,
    )

    assert snapshot["category_total_recoveries"] == []
    assert [item["strategy"] for item in snapshot["membership_recoveries"]] == [
        "category2_exact_membership_restart"
    ]


def test_membership_recovery_requires_exact_child_total(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = membership_shift_responses()
    responses[
        "seller/electronica/category2-facets/recovery-membership-overlap"
    ] = facets("category-2", audio=2, video=1)

    with pytest.raises(RuntimeError, match="category2_membership_total_mismatch"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )


def test_membership_recovery_rejects_another_overlap(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = membership_shift_responses()
    responses[
        "seller/category-1/electronica/category-2/video/recovery-membership-overlap/page-001"
    ] = page(2, "2", "3")

    with pytest.raises(RuntimeError, match="category_membership_changed_again"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )


def test_membership_recovery_rejects_partition_total_change(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = membership_shift_responses()
    responses[
        "seller/category-1/electronica/category-2/video/recovery-membership-overlap/page-001"
    ] = page(3, "3", "4")

    with pytest.raises(RuntimeError, match="category_changed_during_membership_recovery"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )


def test_membership_recovery_rejects_changed_confirmation(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = membership_shift_responses()
    responses[
        "seller/electronica/category2-facets/recovery-membership-confirmation"
    ] = facets("category-2", audio=1, video=3)

    with pytest.raises(RuntimeError, match="category2_changed_during_membership_recovery"):
        operational._capture_category(
            FakeCapture(responses),
            seller="seller",
            category="electronica",
            expected_total=4,
            common={},
            facets_root="/facets/seller",
        )


def _parsed_products(products: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    rows = [
        {
            "source_key": item["productId"],
            "current_price": 1,
            "availability": "available",
            "is_promotion": False,
        }
        for item in products
    ]
    return rows, {row["source_key"]: {} for row in rows}


def final_facet_drift_responses(*, confirmation_electronica: int = 1) -> dict[str, dict]:
    return {
        "seller/facets-before": facets("category-1", electronica=2, abarrotes=2),
        "seller/root-before": page(4, "root"),
        "seller/category-1/electronica/page-001": page(2, "1", "2"),
        "seller/category-1/abarrotes/page-001": page(2, "3", "4"),
        "seller/facets-after": facets("category-1", electronica=1, abarrotes=2),
        "seller/category-1/electronica/recovery-final-facet/page-001": page(1, "1"),
        "seller/facets-after/recovery-confirmation": facets(
            "category-1", electronica=confirmation_electronica, abarrotes=2
        ),
        "seller/root-after": page(3, "root"),
    }


def test_final_facet_drift_recaptures_only_changed_category_and_confirms(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    monkeypatch.setattr(operational, "parse_products", _parsed_products)
    capture = FakeCapture(final_facet_drift_responses())

    snapshot = operational.capture_store(
        capture,
        seller="seller",
        location_id="location",
        city="city",
        store_name="store",
        home_sha="h" * 64,
    )

    assert snapshot["catalog_products_reported"] == 3
    assert snapshot["unique_products_extracted"] == 3
    assert {row["source_key"] for row in snapshot["products"]} == {"1", "3", "4"}
    assert [item["strategy"] for item in snapshot["category_total_recoveries"]] == [
        "final_facet_exact_category_restart"
    ]
    assert snapshot["category_total_recoveries"][0]["previous_total"] == 2
    assert snapshot["category_total_recoveries"][0]["recovered_total"] == 1
    evidence_tags = {item["tag"] for item in snapshot["page_evidence"]}
    assert "seller/category-1/electronica/page-001" not in evidence_tags
    assert "seller/category-1/electronica/recovery-final-facet/page-001" in evidence_tags
    assert "seller/category-1/abarrotes/page-001" in evidence_tags
    assert snapshot["binding_evidence"]["facet_recovery_confirmation_sha256"]


def test_final_facet_recovery_fails_if_catalog_changes_again(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = final_facet_drift_responses(confirmation_electronica=2)

    with pytest.raises(RuntimeError, match="catalog_changed_during_final_recovery"):
        operational.capture_store(
            FakeCapture(responses),
            seller="seller",
            location_id="location",
            city="city",
            store_name="store",
            home_sha="h" * 64,
        )


def test_final_facet_recovery_fails_on_category_shape_change(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = final_facet_drift_responses()
    responses["seller/facets-after"] = facets("category-1", electronica=1, nuevo=2)

    with pytest.raises(RuntimeError, match="catalog_category_shape_changed"):
        operational.capture_store(
            FakeCapture(responses),
            seller="seller",
            location_id="location",
            city="city",
            store_name="store",
            home_sha="h" * 64,
        )


def test_final_facet_category_restart_rejects_another_total_change(monkeypatch):
    monkeypatch.setattr(operational, "PAGE_SIZE", 2)
    monkeypatch.setattr(operational, "CATEGORY2_PARTITIONS", set())
    responses = final_facet_drift_responses()
    responses["seller/category-1/electronica/recovery-final-facet/page-001"] = page(
        2, "1"
    )

    with pytest.raises(RuntimeError, match="category_changed_during_final_recovery"):
        operational.capture_store(
            FakeCapture(responses),
            seller="seller",
            location_id="location",
            city="city",
            store_name="store",
            home_sha="h" * 64,
        )
