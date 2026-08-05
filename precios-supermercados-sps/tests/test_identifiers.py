from dataclasses import replace
from decimal import Decimal

import pytest

from precios_supermercados.enums import AvailabilityStatus, SourceKeyType
from precios_supermercados.identifiers import (
    canonicalize_url,
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
    select_source_key,
)
from test_models import build_offer


def test_source_product_id_is_stable_for_exact_key_with_external_spaces():
    first = generate_source_product_id("super-demo", SourceKeyType.SKU, " SKU-001 ")
    second = generate_source_product_id("SUPER-DEMO", "sku", "SKU-001")
    assert first == second


@pytest.mark.parametrize(
    "source_key_type",
    [
        SourceKeyType.INTERNAL_ID,
        SourceKeyType.SKU,
        SourceKeyType.BARCODE,
        SourceKeyType.API_ID,
    ],
)
def test_non_url_source_keys_preserve_case(source_key_type):
    upper = generate_source_product_id("super-demo", source_key_type, "ABC-001")
    lower = generate_source_product_id("super-demo", source_key_type, "abc-001")
    assert upper != lower


def test_sku_values_with_different_case_have_different_ids():
    first = generate_source_product_id("super-demo", SourceKeyType.SKU, "SKU-001")
    second = generate_source_product_id("super-demo", SourceKeyType.SKU, "sku-001")
    assert first != second


def test_offer_id_is_stable_with_external_spaces():
    source_product_id = generate_source_product_id("super-demo", "sku", "SKU-001")
    first = generate_offer_id("super-demo", "sps-principal", source_product_id)
    second = generate_offer_id(" SUPER-DEMO ", "SPS-PRINCIPAL", f" {source_product_id.upper()} ")
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
    presentation_change = replace(original, total_content=Decimal("900"))

    original_hash = generate_state_hash(original)
    assert generate_state_hash(price_change) != original_hash
    assert generate_state_hash(availability_change) != original_hash
    assert generate_state_hash(promotion_change) != original_hash
    assert generate_state_hash(presentation_change) != original_hash


def test_cosmetic_changes_do_not_modify_state_hash():
    original = build_offer()
    cosmetic = replace(
        original,
        normalized_brand="  MARCA   DEMO ",
        category=" ABARROTES ",
        product_url="https://example.com/productos/arroz?utm_source=other&gclid=123",
        source_url="https://example.com/api/products/SKU-001?utm_campaign=other#detalle",
    )
    assert generate_state_hash(cosmetic) == generate_state_hash(original)


def test_optional_none_values_are_hashed_deterministically():
    incomplete = build_offer(
        normalized_brand=None,
        category=None,
        subcategory=None,
        unit_count=None,
        content_per_unit=None,
        measurement_unit=None,
        total_content=None,
    )
    same_state = replace(incomplete)
    interpreted = replace(incomplete, normalized_brand="Marca Demo")

    assert generate_state_hash(incomplete) == generate_state_hash(same_state)
    assert generate_state_hash(interpreted) != generate_state_hash(incomplete)


def test_stable_url_key_ignores_tracking_parameters():
    first = generate_source_product_id(
        "super-demo",
        SourceKeyType.STABLE_URL,
        "https://EXAMPLE.com/producto/123/?utm_source=a&color=rojo&gclid=1",
    )
    second = generate_source_product_id(
        "SUPER-DEMO",
        "stable_url",
        "https://example.com/producto/123?color=rojo&utm_campaign=b&fbclid=2#detalle",
    )
    assert first == second


def test_functional_parameter_can_change_stable_url_id():
    red = generate_source_product_id(
        "super-demo",
        SourceKeyType.STABLE_URL,
        "https://example.com/producto/123?color=rojo",
    )
    blue = generate_source_product_id(
        "super-demo",
        SourceKeyType.STABLE_URL,
        "https://example.com/producto/123?color=azul",
    )
    assert red != blue


def test_ref_parameter_is_preserved_as_potentially_functional():
    first = canonicalize_url("https://example.com/producto/123?ref=homepage")
    second = canonicalize_url("https://example.com/producto/123?ref=search")
    assert first.endswith("?ref=homepage")
    assert second.endswith("?ref=search")
    assert first != second


def test_source_key_priority_is_deterministic_and_preserves_case():
    key_type, key = select_source_key(
        internal_id=" INT-AbC-9 ",
        sku="SKU-001",
        barcode="7420000000012",
        stable_url="https://example.com/producto/123",
    )
    assert key_type is SourceKeyType.INTERNAL_ID
    assert key == "INT-AbC-9"


def test_canonicalize_url_removes_only_unambiguous_tracking_noise():
    url = canonicalize_url(
        "https://EXAMPLE.com/producto/123/?utm_source=x&color=rojo&gclid=1&ref=home#detalle"
    )
    assert url == "https://example.com/producto/123?color=rojo&ref=home"


@pytest.mark.parametrize(
    ("function", "args", "field_name"),
    [
        (generate_source_product_id, (" ", SourceKeyType.SKU, "SKU-001"), "supermarket_id"),
        (generate_source_product_id, ("super-demo", SourceKeyType.SKU, " "), "source_key"),
        (generate_offer_id, (" ", "sps-principal", "sp_123"), "supermarket_id"),
        (generate_offer_id, ("super-demo", " ", "sp_123"), "location_id"),
        (generate_offer_id, ("super-demo", "sps-principal", " "), "source_product_id"),
    ],
)
def test_identifier_functions_reject_empty_required_components(function, args, field_name):
    with pytest.raises(ValueError, match=field_name):
        function(*args)
