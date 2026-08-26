from __future__ import annotations

from pathlib import Path

from precios_supermercados.la_colonia_product_normalization import (
    load_override_registry,
    normalize_product_row,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = (
    ROOT / "config" / "supermercados" / "la-colonia-product-normalization-overrides"
)


def _row(**changes):
    row = {
        "source_key_type": "internal_id",
        "source_key": "x",
        "source_name": "Producto 473 Ml",
        "brand": "Marca",
        "presentation": "473 Ml",
        "category": "Supermercado > Categoría > Subcategoría",
        "product_id": "p",
        "item_id": "i",
        "reference": "sku",
        "ean": "123",
    }
    row.update(changes)
    return row


def test_direct_source_presentation_keeps_source_and_normalizes_measure() -> None:
    item = normalize_product_row(_row())
    assert item["source_presentation"] == "473 Ml"
    assert item["presentation_normalized"] == "473 ml"
    assert item["presentation_kind"] == "physical"
    assert item["measurement_unit"] == "ml"
    assert item["total_content"] == "473"
    assert item["normalization_status"] == "ready"


def test_direct_weighted_and_count_presentations_are_distinct() -> None:
    weighted = normalize_product_row(_row(presentation="X 3 Lb"))
    counted = normalize_product_row(_row(presentation="12Und"))
    assert weighted["presentation_normalized"] == "3 lb"
    assert weighted["presentation_kind"] == "weighted"
    assert weighted["content_scope"] == "sale_basis"
    assert counted["presentation_normalized"] == "12 unidades"
    assert counted["unit_count"] == "12"


def test_new_explicit_multipack_is_normalized_without_guessing() -> None:
    item = normalize_product_row(
        _row(source_name="Crema Dental Ejemplo 2X100 Ml", presentation="")
    )
    assert item["presentation_normalized"] == "2 x 100 ml"
    assert item["unit_count"] == "2"
    assert item["content_per_unit"] == "100"
    assert item["total_content"] == "200"
    assert item["normalization_status"] == "ready"


def test_tint_code_is_not_interpreted_as_count() -> None:
    item = normalize_product_row(
        _row(source_name="Tinte Ejemplo Rubio 5U", presentation="")
    )
    assert item["normalization_status"] == "pending"
    assert item["presentation_normalized"] == ""


def test_registry_contains_reviewed_catalog_exceptions_and_forced_unit_repairs() -> None:
    registry = load_override_registry(REGISTRY_PATH)
    assert len(registry) == 938
    for source_key, expected in {
        "15711": "1500 ml",
        "1886": "397 g",
        "12533": "500 ml",
        "5141": "820 g",
        "4295": "241 g",
        "4296": "425 g",
    }.items():
        assert registry[source_key]["presentation"]["presentation_normalized"] == expected


def test_registry_reproduces_reviewed_examples() -> None:
    registry = load_override_registry(REGISTRY_PATH)
    examples = {
        "1752": "1 unidad",
        "4612": "1 mazo",
        "8519": "1 bandeja",
        "14945": "1 unidad",
        "16289": "2 x 100 ml",
    }
    for source_key, expected in examples.items():
        assert registry[source_key]["presentation"]["presentation_normalized"] == expected


def test_changed_known_product_does_not_reuse_stale_override() -> None:
    row = _row(source_key="known", source_name="Producto Nuevo Sin Presentación", presentation="")
    registry = {
        "known": {
            "source_signature": "0" * 64,
            "presentation": {"presentation_normalized": "1 unidad"},
        }
    }
    item = normalize_product_row(row, registry=registry)
    assert item["normalization_status"] == "review_required"
    assert item["presentation_normalized"] == ""


def test_registry_brand_category_override_is_kept_separate_from_source() -> None:
    registry = load_override_registry(REGISTRY_PATH)
    entry = registry["17691"]
    assert entry["field_overrides"]["normalized_brand"] == "American Legend"
    assert entry["field_overrides"]["subcategory"] == "Ropa"


def test_known_brand_typo_is_normalized_without_rewriting_source() -> None:
    registry = load_override_registry(REGISTRY_PATH)
    entry = registry["17724"]
    assert entry["field_overrides"]["normalized_brand"] == "American Legend"
