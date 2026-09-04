from __future__ import annotations

from decimal import Decimal

from precios_supermercados.product_homologation import (
    SourceProductRecord,
    assign_taxonomy,
    homologate_products,
    normalize_brand,
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


def test_source_category_is_preserved_but_does_not_drive_product_type() -> None:
    source = product(
        "a",
        "paiz",
        "Salsa Kraft Barbecue Ahumada 1100 g",
        category="Abarrotes > Pastas y Salsas",
    )
    assignment = assign_taxonomy(source)
    assert source.source_category == "Abarrotes > Pastas y Salsas"
    assert assignment.product_type == "Salsa"
    assert assignment.subcategory == "Salsas y aderezos"


def test_head_product_noun_wins_over_ingredient_words() -> None:
    assert assign_taxonomy(
        product("a", "la_colonia", "Atún Bumble Bee En Agua 142 Gr")
    ).product_type == "Atún"
    assert assign_taxonomy(
        product("b", "la_colonia", "Chocolate Kinder Sorpresa Con Leche 20 Gr")
    ).product_type == "Chocolate"
    assert assign_taxonomy(
        product("c", "la_colonia", "Sopa De Pollo Con Salsa Picante 64 Gr")
    ).product_type == "Sopa"
    assert assign_taxonomy(
        product("d", "paiz", "Pan De Harina De Trigo Integral Monarca - 600 g")
    ).product_type == "Pan"


def test_generic_source_brand_placeholders_do_not_participate_in_matching() -> None:
    assert normalize_brand("RMS") is None
    assert normalize_brand("Marca COMANDES") is None
    assert normalize_brand("SIN MARCA") is None
    assert normalize_brand("Great Value") == "great value"

    result = homologate_products(
        (
            product(
                "a",
                "colonial",
                "Arroz Progreso Blanco 1 lb",
                brand="RMS",
                presentation="1 lb",
            ),
            product(
                "b",
                "walmart",
                "Arroz Progreso Blanco 454 g",
                brand="Progreso",
                presentation="454 g",
            ),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.candidates == ()


def test_presentation_reconciles_one_pound_and_454_grams() -> None:
    left, left_status = resolve_presentation(
        product("a", "colonial", "Arroz Progreso 1 lb", presentation="1 lb")
    )
    right, right_status = resolve_presentation(
        product("b", "walmart", "Arroz Progreso 454 g", presentation="454 g")
    )

    assert left is not None and right is not None
    assert left_status == "confirmed"
    assert right_status == "confirmed"
    assert presentations_compatible(left, right)


def test_plain_ounce_is_not_silently_assumed_mass_or_volume() -> None:
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


def test_explicit_fluid_ounce_is_normalized_as_volume() -> None:
    fluid_ounce, status = resolve_presentation(
        product("a", "walmart", "Jabón Líquido 8 fl oz")
    )
    assert status == "name_only"
    assert fluid_ounce is not None
    assert fluid_ounce.dimension == "volume_ml"
    assert abs(fluid_ounce.total_base - Decimal("236.5882365")) < Decimal("0.0001")


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


def test_ambiguous_pack_notation_fails_closed() -> None:
    signature, status = resolve_presentation(
        product("a", "paiz", "Atún Bumble Bee En Agua 3 Pack - 142 g")
    )
    assert signature is None
    assert status == "ambiguous_multipack"


def test_packaging_words_doy_pack_and_tetra_pack_are_not_multipacks() -> None:
    doy, doy_status = resolve_presentation(
        product(
            "a",
            "la_colonia",
            "Mayonesa Hellmanns Doy Pack 380 Gr",
            presentation="380 Gr",
        )
    )
    tetra, tetra_status = resolve_presentation(
        product(
            "b",
            "la_colonia",
            "Jugo Del Monte Néctar De Pera Tetra Pack 200 Ml",
            presentation="200 Ml",
        )
    )

    assert doy is not None and doy.total_base == Decimal("380")
    assert doy_status == "confirmed"
    assert tetra is not None and tetra.total_base == Decimal("200")
    assert tetra_status == "confirmed"


def test_single_unit_never_matches_multipack_candidate() -> None:
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


def test_non_paiz_source_name_presentation_conflict_fails_closed() -> None:
    signature, status = resolve_presentation(
        product(
            "a",
            "la_colonia",
            "Leche Dos Pinos en Polvo - 360 g",
            presentation="75 gr",
        )
    )
    assert signature is None
    assert status == "conflict"


def test_paiz_prefers_advertised_name_over_known_noisy_source_presentation() -> None:
    signature, status = resolve_presentation(
        product(
            "a",
            "paiz",
            "Leche Semidescremada Dos Pinos en Polvo - 360 g",
            presentation="75 gr",
        )
    )
    assert signature is not None
    assert signature.dimension == "mass_g"
    assert signature.total_base == Decimal("360")
    assert status == "name_preferred_source_conflict"


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
                "walmart",
                "Maíz Dulce En Granos El Migo - 148 g",
                brand="El Migo",
                presentation="148 g",
                barcode="012656001065",
            ),
        )
    )
    group = result.exact_gtin_groups[0]
    assert group.comparison_status == "review_required"
    assert "cross_source_presentation_conflict" in group.conflict_reasons
    assert group.canonical_product_id.startswith("prod_gtin_")


def test_same_gtin_taxonomy_disagreement_is_retained_for_review() -> None:
    result = homologate_products(
        (
            product(
                "a",
                "la_colonia",
                "Leche Dos Pinos Chocolate 200 ml",
                brand="Dos Pinos",
                presentation="200 ml",
                barcode="7590002040003",
            ),
            product(
                "b",
                "walmart",
                "Chocolate Dos Pinos Bebida 200 ml",
                brand="Dos Pinos",
                presentation="200 ml",
                barcode="7590002040003",
            ),
        )
    )
    group = result.exact_gtin_groups[0]
    assert group.comparison_status == "review_required"
    assert group.conflict_reasons == ("product_type_conflict",)


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
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.exact_gtin_groups == ()
    assert result.candidates == ()


def test_non_gtin_match_is_review_candidate_not_automatic_mapping() -> None:
    result = homologate_products(
        (
            product(
                "la_colonia:1",
                "la_colonia",
                "Harina de Maíz Maseca Original 4.5 lb",
                brand="Maseca",
                presentation="4.5 lb",
            ),
            product(
                "pricesmart:2",
                "pricesmart",
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
