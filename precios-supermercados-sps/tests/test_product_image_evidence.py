from __future__ import annotations

import pytest

from precios_supermercados.product_image_evidence import (
    ProductImageEvidenceError,
    build_product_image_rows,
    collect_detail_image_rows,
    image_pairs_from_mappings,
    validate_snapshot_images,
)


def test_build_rows_preserves_gallery_order_and_deduplicates_urls() -> None:
    rows = build_product_image_rows(
        source_key_type="item_id",
        source_key="sku-1",
        images=[
            ("https://cdn.example/front.jpg", "front"),
            ("https://cdn.example/back.jpg", "back"),
            ("https://cdn.example/front.jpg", "duplicate"),
        ],
    )
    assert [(row["source_position"], row["is_primary"]) for row in rows] == [
        (0, True),
        (1, False),
    ]
    assert [row["source_image_id"] for row in rows] == ["front", "back"]


def test_mapping_images_follow_declared_position() -> None:
    assert image_pairs_from_mappings(
        [
            {"url": "https://cdn.example/back.jpg", "id": 2, "position": 2},
            {"url": "https://cdn.example/front.jpg", "id": 1, "position": 1},
        ],
        url_key="url",
        id_key="id",
        position_key="position",
    ) == [
        ("https://cdn.example/front.jpg", "1"),
        ("https://cdn.example/back.jpg", "2"),
    ]


def test_snapshot_images_must_reference_an_offer_and_be_contiguous() -> None:
    rows = build_product_image_rows(
        source_key_type="item_id",
        source_key="sku-1",
        images=[("https://cdn.example/front.jpg", None)],
    )
    snapshot = {"image_capture_status": "complete", "product_images": rows}
    assert validate_snapshot_images(
        snapshot, product_identities={("item_id", "sku-1")}
    ) == tuple(rows)

    snapshot["product_images"][0]["source_position"] = 1
    with pytest.raises(ProductImageEvidenceError, match="positions_not_contiguous"):
        validate_snapshot_images(snapshot, product_identities={("item_id", "sku-1")})


def test_missing_extension_remains_backward_compatible() -> None:
    assert validate_snapshot_images({}, product_identities=set()) == ()


def test_collects_temporary_detail_galleries_in_product_order() -> None:
    gallery = build_product_image_rows(
        source_key_type="item_id",
        source_key="sku-1",
        images=[("https://cdn.example/front.jpg", None)],
    )
    assert collect_detail_image_rows(
        [{"source_key": "sku-1"}], {"sku-1": {"product_images": gallery}}
    ) == gallery


@pytest.mark.parametrize("url", ["http://cdn.example/a.jpg", "javascript:alert(1)", " x "])
def test_only_clean_https_urls_are_accepted(url: str) -> None:
    with pytest.raises(ProductImageEvidenceError, match="image_url_invalid"):
        build_product_image_rows(
            source_key_type="sku", source_key="1", images=[(url, None)]
        )
