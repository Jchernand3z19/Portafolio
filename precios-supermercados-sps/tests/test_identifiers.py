from dataclasses import replace
from decimal import Decimal

from precios_supermercados.enums import AvailabilityStatus, SourceKeyType
from precios_supermercados.identifiers import (
    canonicalize_url,
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
    select_source_key,
)
from test_models import build_offer


def test_source_product_id_is_stable():
    first = generate_source_product_id("super-demo", SourceKeyType.SKU, " SKU-001 ")
    second = generate_source_product_id("SUPER-DEMO", "sku", "sku-001")
    assert first == second


def test_offer_id_is_stable():
    source_product_id = generate_source_product_id("super-demo", "sku", "SKU-001")
    first = generate_offer_id("super-demo", "sps-principal", source_product_id)
    second = generate_offer_id(" SUPER-DEMO ", "SPS-PRINCIPAL", source_product_id.upper())
    assert first == second


def test_price_does_not_change_product_or_offer_identity():
    original = build_offer(current_price=Decimal("32.50"))
    changed_price = replace(original, current_price=Decimal("29.99"))
    assert original.source_product_id == changed_price.source_product_id
    assert original.offer_id == changed_price.offer_id


def test_relevant_changes_modify_state_hash():
    original = build_offer()
    price_change = replace(original, current_price=Decimal("31.00"))
    availability_change = replace(original, availability=AvailabilityStatus.OUT_OF_STOCK)
    promotion_change = replace(original, is_promotion=True)

    original_hash = generate_state_hash(original)
    assert generate_state_hash(price_change) != original_hash
    assert generate_state_hash(availability_change) != original_hash
    assert generate_state_hash(promotion_change) != original_hash


def test_cosmetic_changes_do_not_modify_state_hash():
    original = build_offer()
    cosmetic = replace(
        original,
        normalized_brand="  MARCA   DEMO ",
        product_url="https://example.com/productos/arroz?utm_source=other&gclid=123",
        source_url="https://example.com/api/products/SKU-001?utm_campaign=other#detalle",
    )
    assert generate_state_hash(cosmetic) == generate_state_hash(original)


def test_stable_url_key_ignores_tracking_parameters():
    first = generate_source_product_id(
        "super-demo",
        SourceKeyType.STABLE_URL,
        "https://EXAMPLE.com/producto/123/?utm_source=a&color=rojo",
    )
    second = generate_source_product_id(
        "SUPER-DEMO",
        "stable_url",
        "https://example.com/producto/123?color=rojo&utm_campaign=b#detalle",
    )
    assert first == second


def test_source_key_priority_is_deterministic():
    key_type, key = select_source_key(
        internal_id="INT-9",
        sku="SKU-001",
        barcode="7420000000012",
        stable_url="https://example.com/producto/123",
    )
    assert key_type is SourceKeyType.INTERNAL_ID
    assert key == "INT-9"


def test_canonicalize_url_removes_only_tracking_noise():
    url = canonicalize_url(
        "https://EXAMPLE.com/producto/123/?utm_source=x&color=rojo&gclid=1#detalle"
    )
    assert url == "https://example.com/producto/123?color=rojo"
