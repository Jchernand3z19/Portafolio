from __future__ import annotations

from copy import deepcopy

from precios_supermercados.enums import RunStatus
from precios_supermercados.scrapers.la_colonia_operational_artifact import (
    assess_operational_catalog_artifact,
)


def _artifact():
    products = [
        {
            "source_key_type": "internal_id",
            "source_key": "sku-1",
            "source_name": "Producto Uno 500 Ml",
            "brand": "Marca Uno",
            "presentation": "500 Ml",
            "category": "Supermercado > Bebidas",
            "product_id": "prod-1",
            "item_id": "item-1",
            "reference": "ref-1",
            "ean": "7500000000001",
            "current_price": "35.5",
            "reported_regular_price": None,
            "is_promotion": False,
            "availability": "in_stock",
        },
        {
            "source_key_type": "internal_id",
            "source_key": "sku-2",
            "source_name": "Producto Dos",
            "brand": "Marca Dos",
            "presentation": None,
            "category": "Supermercado > Hogar",
            "product_id": "prod-2",
            "item_id": "item-2",
            "reference": "ref-2",
            "ean": "7500000000002",
            "current_price": "79.9",
            "reported_regular_price": "99.9",
            "is_promotion": True,
            "availability": "unknown",
        },
    ]
    return {
        "supermarket_id": "la_colonia",
        "location_id": "la_colonia_sps",
        "city": "San Pedro Sula",
        "result": "success",
        "catalog_complete": True,
        "validation_passed": True,
        "catalog_product_coverage": 1.0,
        "location_verified_same_run": True,
        "catalog_products_reported": 2,
        "unique_products_extracted": 2,
        "skus_extracted": 2,
        "skus_with_price": 2,
        "skus_without_price": 0,
        "partitions_detected": 1,
        "partitions_completed": 1,
        "duplicate_skus_across_partitions": 0,
        "catalog_accepted": False,
        "commercial_persistence": False,
        "production_authority": False,
        "extraction_enabled": False,
        "raw_context_persisted": False,
        "products": products,
    }


def test_complete_artifact_with_reviewable_fields_is_warning_not_rejected():
    assessment = assess_operational_catalog_artifact(_artifact())

    assert assessment.run_status is RunStatus.WARNING
    assert assessment.technical_catalog_complete is True
    assert assessment.ready_for_normalization is True
    assert assessment.catalog_accepted is False
    assert assessment.production_authority is False
    assert assessment.blockers == ()
    assert assessment.warnings == ("presentation_missing", "availability_unknown")
    assert assessment.sku_rows == 2
    assert assessment.unique_products == 2
    assert assessment.missing_presentations == 1
    assert assessment.unknown_availability == 1
    assert assessment.in_stock == 1
    assert assessment.out_of_stock == 0
    assert assessment.promotion_rows == 1


def test_exact_coverage_is_required_for_technical_completeness():
    artifact = _artifact()
    artifact["catalog_product_coverage"] = 0.5

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.run_status is RunStatus.REJECTED
    assert assessment.technical_catalog_complete is False
    assert assessment.ready_for_normalization is False
    assert "catalog_product_coverage_not_exact" in assessment.blockers


def test_duplicate_source_identity_rejects_the_artifact():
    artifact = _artifact()
    artifact["products"][1]["source_key"] = "sku-1"

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.run_status is RunStatus.REJECTED
    assert "duplicate_source_identity" in assessment.blockers


def test_nonpositive_price_rejects_the_artifact():
    artifact = _artifact()
    artifact["products"][0]["current_price"] = "0"

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.run_status is RunStatus.REJECTED
    assert "current_price_invalid" in assessment.blockers


def test_artifact_cannot_smuggle_commercial_authority():
    artifact = _artifact()
    artifact["production_authority"] = True
    artifact["catalog_accepted"] = True

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.run_status is RunStatus.REJECTED
    assert "production_authority_must_be_false" in assessment.blockers
    assert "catalog_accepted_must_be_false" in assessment.blockers
    assert assessment.production_authority is False
    assert assessment.catalog_accepted is False


def test_teaser_promotion_without_regular_price_is_reviewable_warning():
    artifact = _artifact()
    artifact["products"][0]["is_promotion"] = True

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.technical_catalog_complete is True
    assert "promotion_without_reported_regular_price" in assessment.warnings


def test_invalid_reported_regular_price_rejects_artifact():
    artifact = _artifact()
    artifact["products"][1]["reported_regular_price"] = "79.9"

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.run_status is RunStatus.REJECTED
    assert "reported_regular_price_not_greater" in assessment.blockers


def test_all_clean_rows_produce_success():
    artifact = deepcopy(_artifact())
    artifact["products"][1]["presentation"] = "1 Unidad"
    artifact["products"][1]["availability"] = "out_of_stock"

    assessment = assess_operational_catalog_artifact(artifact)

    assert assessment.run_status is RunStatus.SUCCESS
    assert assessment.technical_catalog_complete is True
    assert assessment.warnings == ()
