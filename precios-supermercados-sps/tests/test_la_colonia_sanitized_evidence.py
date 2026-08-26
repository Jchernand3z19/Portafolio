from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from precios_supermercados.models import RawProduct
from precios_supermercados.scrapers.la_colonia_sanitized_evidence import (
    OPERATIONAL_ARTIFACT_SCHEMA_VERSION,
    SANITIZED_PRODUCT_FIELDS,
    SanitizedEvidenceError,
    sanitize_operational_product,
)


def _raw_product(**overrides) -> RawProduct:
    raw_values = {
        "product_id": "123",
        "item_id": "456",
        "reference": "REF-456",
        "ean": "7500000000001",
        "brand": "Marca",
        "category": "Supermercado > Bebidas",
        "subcategory": "Bebidas",
        "presentation": "500 Ml",
        "current_price": "35.50",
        "reported_regular_price": "40.00",
        "source_list_price": "40.00",
        "is_promotion": True,
        "promotion_evidence": ["Oferta"],
        "availability": "unknown",
        "availability_evidence": "price_positive_quantity_zero",
        "available_quantity": "0",
        "measurement_unit": "un",
        "unit_multiplier": "1",
        "weighted_product": False,
        # Estos valores simulan material que nunca debe proyectarse.
        "cookie": "session-secret",
        "regionId": "raw-region-secret",
        "authorization": "bearer-secret",
    }
    raw_values.update(overrides.pop("raw_values", {}))
    values = {
        "supermarket_id": "la_colonia",
        "location_id": "la_colonia_online",
        "source_key_type": "internal_id",
        "source_key": "456",
        "source_name": "Producto 500 Ml",
        "product_url": "https://www.lacolonia.com/producto-500-ml/p",
        "observed_at_utc": datetime(2026, 8, 26, tzinfo=timezone.utc),
        "scrape_run_id": "run-test",
        "extractor_version": "0.3.1",
        "schema_version": "1.0.0",
        "source_url": (
            "https://www.lacolonia.com/_v/segment/graphql/v1?"
            "variables=raw-region-secret"
        ),
        "source_sku": "REF-456",
        "source_brand": "Marca",
        "source_presentation": "500 Ml",
        "source_category": "Supermercado > Bebidas",
        "location_status": "unknown",
        "raw_values": raw_values,
    }
    values.update(overrides)
    return RawProduct(**values)


def test_schema_version_is_v8():
    assert OPERATIONAL_ARTIFACT_SCHEMA_VERSION == "8"


def test_sanitizer_keeps_explainable_availability_without_sensitive_context():
    product = sanitize_operational_product(_raw_product())

    assert tuple(product) == SANITIZED_PRODUCT_FIELDS
    assert product["product_url"] == "https://www.lacolonia.com/producto-500-ml/p"
    assert product["availability"] == "unknown"
    assert product["availability_evidence"] == "price_positive_quantity_zero"
    assert product["available_quantity"] == "0"
    assert product["subcategory"] == "Bebidas"
    assert product["measurement_unit"] == "un"
    assert product["unit_multiplier"] == "1"
    assert product["weighted_product"] is False

    rendered = json.dumps(product, ensure_ascii=False)
    assert "source_url" not in product
    assert "cookie" not in product
    assert "authorization" not in product
    assert "regionId" not in product
    assert "raw-region-secret" not in rendered
    assert "session-secret" not in rendered
    assert "bearer-secret" not in rendered


def test_product_url_must_be_public_canonical_lacolonia_url():
    raw = _raw_product(product_url="https://www.lacolonia.com/producto/p?region=secret")

    with pytest.raises(SanitizedEvidenceError, match="product_url_not_public_canonical"):
        sanitize_operational_product(raw)


def test_availability_evidence_must_be_known():
    raw = _raw_product(raw_values={"availability_evidence": "invented"})

    with pytest.raises(SanitizedEvidenceError, match="availability_evidence_invalid"):
        sanitize_operational_product(raw)


def test_available_quantity_is_canonicalized_and_may_be_zero():
    raw = _raw_product(raw_values={"available_quantity": "0.000"})

    product = sanitize_operational_product(raw)

    assert product["available_quantity"] == "0"


def test_raw_product_source_url_is_never_reused_as_public_product_url():
    raw = _raw_product(
        source_url="https://www.lacolonia.com/private-like-path?token=secret",
    )

    product = sanitize_operational_product(raw)

    assert product["product_url"] == "https://www.lacolonia.com/producto-500-ml/p"
    assert "secret" not in json.dumps(product)
