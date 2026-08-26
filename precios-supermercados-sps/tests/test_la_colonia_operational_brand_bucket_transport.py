from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo as operational  # noqa: E402


def _values(count: int, *, quantity: int = 10, prefix: str = "brand") -> list[dict[str, object]]:
    return [
        {"key": "brand", "value": f"{prefix}-{index:03d}", "quantity": quantity}
        for index in range(count)
    ]


def _flatten(partitions: tuple[object, ...]) -> list[str]:
    values: list[str] = []
    for partition in partitions:
        values.extend(value for key, value in partition.path if key == "brand")
    return values


def test_brand_count_limit_splits_even_when_quantity_fits() -> None:
    values = _values(10, quantity=1)
    partitions = operational._build_brand_buckets(
        values,
        estimate_capacity=100,
        page_size=50,
        max_brands=3,
        max_url_bytes=100_000,
    )

    assert len(partitions) == 4
    assert max(len(partition.path) for partition in partitions) <= 3
    assert sorted(_flatten(partitions)) == sorted(str(item["value"]) for item in values)


def test_exact_encoded_url_limit_splits_bucket() -> None:
    first = "marca-" + ("a" * 120)
    second = "marca-" + ("b" * 120)
    single_size = max(
        operational._bucket_url_bytes([first], page_size=50),
        operational._bucket_url_bytes([second], page_size=50),
    )
    pair_size = operational._bucket_url_bytes([first, second], page_size=50)
    assert pair_size > single_size
    limit = single_size + ((pair_size - single_size) // 2)

    partitions = operational._build_brand_buckets(
        [
            {"key": "brand", "value": first, "quantity": 1},
            {"key": "brand", "value": second, "quantity": 1},
        ],
        estimate_capacity=100,
        page_size=50,
        max_brands=10,
        max_url_bytes=limit,
    )

    assert len(partitions) == 2
    for partition in partitions:
        bucket_values = [value for key, value in partition.path if key == "brand"]
        assert operational._bucket_url_bytes(bucket_values, page_size=50) <= limit


def test_single_brand_that_cannot_fit_transport_fails_closed() -> None:
    value = "marca-" + ("x" * 200)
    single_size = operational._bucket_url_bytes([value], page_size=50)

    with pytest.raises(ValueError, match="single_brand_url_too_long"):
        operational._build_brand_buckets(
            [{"key": "brand", "value": value, "quantity": 1}],
            estimate_capacity=100,
            page_size=50,
            max_brands=10,
            max_url_bytes=single_size - 1,
        )


def test_default_transport_contract_preserves_all_brands_and_quantities() -> None:
    values = _values(137, quantity=7, prefix="marca-larga-controlada")
    partitions = operational._build_brand_buckets(values, page_size=50)

    expected_values = sorted(str(item["value"]) for item in values)
    assert sorted(_flatten(partitions)) == expected_values
    assert len(_flatten(partitions)) == len(set(_flatten(partitions)))
    assert sum(partition.quantity for partition in partitions) == 137 * 7
    assert max(len(partition.path) for partition in partitions) <= operational.MAX_BRANDS_PER_BUCKET
    for partition in partitions:
        bucket_values = [value for key, value in partition.path if key == "brand"]
        assert (
            operational._bucket_url_bytes(bucket_values, page_size=50)
            <= operational.MAX_PRODUCT_SEARCH_URL_BYTES
        )


def test_transport_preflight_covers_primary_and_reverse_recovery_orders() -> None:
    values = [f"marca-{index:02d}" for index in range(12)]
    facets = operational.core._partition_facets(operational._bucket_path(values))
    max_page = operational.core.SEARCH_WINDOW_MAX_PRODUCTS // 50

    primary = operational._product_url(
        selected_facets=facets,
        page=max_page,
        page_size=50,
        order_by=operational.PRIMARY_ORDER_BY,
    )
    recovery = operational._product_url(
        selected_facets=facets,
        page=max_page,
        page_size=50,
        order_by=operational.RECOVERY_ORDER_BY,
    )
    measured = operational._bucket_url_bytes(values, page_size=50)

    assert measured == max(len(primary.encode("utf-8")), len(recovery.encode("utf-8")))
    assert measured <= operational.MAX_PRODUCT_SEARCH_URL_BYTES
