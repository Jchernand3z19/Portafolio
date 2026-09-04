from __future__ import annotations

from decimal import Decimal

from precios_supermercados.product_homologation import (
    SourceProductRecord,
    assign_taxonomy,
    homologate_products,
    presentations_compatible,
    profile_product,
    resolve_presentation,
)


def product(
    record_id: str,
    supermarket: str,
    name: str,
    *,
    brand: str | None = None,
    presentation: str | None = None,
    category: str | None = None,
    barcode: str | None = None,
) -> SourceProductRecord:
    return SourceProductRecord(
        source_record_id=record_id,
        supermarket_id=supermarket,
        source_name=name,
        source_brand=brand,
        source_presentation=presentation,
        source_category=category,
        barcode=barcode,
    )


def test_taxonomy_separates_category_subcategory_and_product_type() -> None:
    egg = assign_taxonomy(product("a", "colonial", "Huevos Rica Yema Grandes 15 Und"))
    corn = assign_taxonomy(product("b", "la_colonia", "Harina de Maíz Maseca 4.5 Lb"))
    milk = assign_taxonomy(product("c", "paiz", "Leche Semidescremada Dos Pinos 1 L"))

    assert (egg.category, egg.subcategory, egg.product_type) == (
        "Alimentos",
        "Huevos",
        "Huevo",
    )
    assert (corn.category, corn.subcategory, corn.product_type) == (
        "Alimentos",
        "Harinas",
        "Harina de maíz",
    )
    assert (milk.category, milk.subcategory, milk.product_type) == (
        "Alimentos",
        "Lácteos",
        "Leche",
    )


def test_specific_taxonomy_rule_wins_over_generic_word() -> None:
    dental = assign_taxonomy(
        product("a", "walmart", "Pasta Dental Colgate Triple Acción 75 ml")
    )
    assert dental.product_type == "Pasta dental"
    assert dental.subcategory == "Higiene oral"


def test_source_category_does_not_force_product_type() -> None:
    assignment = assign_taxonomy(
        product(
            "a",
            "paiz",
            "Salsa Kraft Barbecue Ahumada 1100 g",
            category="Abarrotes > Pastas y Salsas",
        )
    )
    assert assignment.product_type is None


def test_non_beverage_agua_rule_wins_before_generic_water() -> None:
    assignment = assign_taxonomy(
        product("a", "paiz", "Agua Micelar Garnier Todo En 1 - 400 ml")
    )
    assert assignment.product_type == "Agua micelar"
    assert assignment.category == "Cuidado personal"


def test_presentation_reconciles_one_pound_and_454_grams() -> None:
    left, left_status = resolve_presentation(
        product("a", "colonial", "Arroz Progreso 1 lb", presentation="1 lb")
    )
    right, right_status = resolve_presentation(
        product("b", "los_andes", "Arroz Progreso 454 g", presentation="454 g")
    )

    assert left is not None and right is not None
    assert left_status == "confirmed"
    assert right_status == "confirmed"
    assert presentations_compatible(left, right)


def test_ounce_is_not_silently_assumed_to_be_mass_or_volume() -> None:
    ounce, _ = resolve_presentation(
        product("a", "la_colonia", "Salsa Tabasco 5 Oz", presentation="5 Oz")
    )
    milliliters, _ = resolve_presentation(
        product("b", "paiz", "Salsa Tabasco 150 ml", presentation="150 ml")
    )
    assert ounce is not None and milliliters is not None
    assert ounce.dimension == "ounce"
    assert milliliters.dimension == "volume_ml"
    assert not presentations_compatible(ounce, milliliters)


def test_pricesmart_style_multipack_preserves_pack_count_and_total() -> None:
    signature, status = resolve_presentation(
        product(
            "a",
            "pricesmart",
            "Pepsi Gaseosa en Botella 12 Unidades / 1.25 L",
        )
    )
    assert status == "name_only"
    assert signature is not None
    assert signature.dimension == "volume_ml"
    assert signature.pack_count == 12
    assert signature.unit_amount_base == Decimal("1250")
    assert signature.total_base == Decimal("15000")


def test_pricesmart_multipack_is_not_same_presentation_as_single_unit() -> None:
    result = homologate_products(
        (
            product(
                "a",
                "pricesmart",
                "Pepsi Gaseosa en Botella 12 Unidades / 1.25 L",
                brand="Pepsi",
            ),
            product(
                "b",
                "walmart",
                "Gaseosa Pepsi botella - 1250 ml",
                brand="Pepsi",
            ),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.candidates == ()


def test_conflicting_source_and_advertised_presentations_fail_closed() -> None:
    signature, status = resolve_presentation(
        product(
            "a",
            "paiz",
            "Leche Semidescremada Dos Pinos en Polvo - 360 g",
            presentation="75 gr",
        )
    )
    assert signature is None
    assert status == "conflict"


def test_exact_valid_gtin_groups_products_across_supermarkets() -> None:
    result = homologate_products(
        (
            product(
                "colonial:1",
                "colonial",
                "Suavizante Downy Pureza 800 ml",
                brand="Downy",
                presentation="800 ml",
                barcode="7590002040003",
            ),
            product(
                "walmart:2",
                "walmart",
                "Downy Suavizante Pureza 800 ML",
                brand="Downy",
                presentation="800 ml",
                barcode="07590002040003",
            ),
        )
    )

    assert len(result.exact_gtin_groups) == 1
    group = result.exact_gtin_groups[0]
    assert group.canonical_gtin == "07590002040003"
    assert group.canonical_product_id == "prod_gtin_07590002040003"
    assert group.supermarket_ids == ("colonial", "walmart")
    assert group.comparison_status == "ready"
    assert group.conflict_reasons == ()
    assert result.candidates == ()


def test_same_gtin_keeps_identity_but_blocks_comparison_on_size_conflict() -> None:
    result = homologate_products(
        (
            product(
                "a",
                "la_colonia",
                "Maiz El Migo Dulce En Grano 240 g",
                brand="El Migo",
                presentation="240 g",
                barcode="012656001065",
            ),
            product(
                "b",
                "paiz",
                "Maíz Dulce En Granos El Migo - 148 g",
                brand="El Migo",
                presentation="148 g",
                barcode="012656001065",
            ),
        )
    )
    assert len(result.exact_gtin_groups) == 1
    group = result.exact_gtin_groups[0]
    assert group.comparison_status == "review_required"
    assert "cross_source_presentation_conflict" in group.conflict_reasons
    assert group.canonical_product_id.startswith("prod_gtin_")


def test_different_valid_gtins_never_become_text_candidate() -> None:
    result = homologate_products(
        (
            product(
                "a",
                "colonial",
                "Arroz Progreso Blanco 1 lb",
                brand="Progreso",
                presentation="1 lb",
                barcode="7590002040003",
            ),
            product(
                "b",
                "walmart",
                "Arroz Progreso Blanco 454 g",
                brand="Progreso",
                presentation="454 g",
                barcode="7501031311309",
            ),
        )
    )
    assert result.exact_gtin_groups == ()
    assert result.candidates == ()


def test_non_gtin_match_is_review_candidate_not_automatic_mapping() -> None:
    result = homologate_products(
        (
            product(
                "colonial:1",
                "colonial",
                "Harina de Maíz Maseca Original 4.5 lb",
                brand="Maseca",
                presentation="4.5 lb",
            ),
            product(
                "andes:2",
                "comisariato_los_andes",
                "Maseca Harina Maiz Original 2.04 kg",
                brand="MASECA",
                presentation="2.04 kg",
            ),
        ),
        candidate_threshold=Decimal("0.65"),
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.product_type == "Harina de maíz"
    assert candidate.normalized_brand == "maseca"
    assert candidate.status == "review_required"
    assert all(profile.canonical_product_id is None for profile in result.profiles)


def test_ambiguous_ounce_does_not_match_metric_without_gtin() -> None:
    result = homologate_products(
        (
            product(
                "a",
                "la_colonia",
                "Jugo Ocean Spray Arándano 64 Oz",
                brand="Ocean Spray",
                presentation="64 Oz",
            ),
            product(
                "b",
                "pricesmart",
                "Ocean Spray Jugo de Arándano 1.89 L",
                brand="Ocean Spray",
            ),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.candidates == ()


def test_brand_difference_blocks_candidate_even_when_name_and_size_are_similar() -> None:
    result = homologate_products(
        (
            product(
                "a", "colonial", "Arroz Progreso Blanco 1 lb",
                brand="Progreso", presentation="1 lb",
            ),
            product(
                "b", "paiz", "Arroz Great Value Blanco 454 g",
                brand="Great Value", presentation="454 g",
            ),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.candidates == ()


def test_same_supermarket_never_creates_cross_source_candidate() -> None:
    result = homologate_products(
        (
            product(
                "a", "colonial", "Café Passion Molido 1 lb",
                brand="Passion", presentation="1 lb",
            ),
            product(
                "b", "colonial", "Cafe Passion Molido 454 g",
                brand="Passion", presentation="454 g",
            ),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.candidates == ()


def test_summary_reports_classification_gtin_candidates_and_conflicts() -> None:
    result = homologate_products(
        (
            product(
                "a", "colonial", "Huevos Rica Yema 15 und",
                brand="Rica Yema", presentation="15 und",
            ),
            product(
                "b", "walmart", "Huevos Rica Yema 15 unidades",
                brand="Rica Yema", presentation="15 unidades",
            ),
            product(
                "c",
                "paiz",
                "Leche Dos Pinos en Polvo 360 g",
                brand="Dos Pinos",
                presentation="75 g",
            ),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.summary["source_products"] == 3
    assert result.summary["classified_product_type"] == 3
    assert result.summary["presentation_conflicts"] == 1
    assert result.summary["review_candidates"] == 1


def test_profile_preserves_source_fields_and_normalizes_comparison_fields() -> None:
    source = product(
        "a",
        "la_colonia",
        "CAFÉ Molido Passion 1 LB",
        brand="Passion ",
        presentation="1 LB",
        category="Abarrotes > Café",
    )
    profile = profile_product(source)
    assert profile.record.source_category == "Abarrotes > Café"
    assert profile.normalized_name == "cafe molido passion 1 lb"
    assert profile.normalized_brand == "passion"
    assert profile.taxonomy.product_type == "Café"
