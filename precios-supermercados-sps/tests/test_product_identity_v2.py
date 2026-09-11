from __future__ import annotations

from decimal import Decimal

import pytest

from precios_supermercados.product_homologation import SourceProductRecord
from precios_supermercados.product_homologation_persistence import NORMALIZATION_VERSION
from precios_supermercados.product_identity_v2 import (
    IDENTITY_NORMALIZATION_VERSION,
    assign_taxonomy_v2,
    canonical_egg_size,
    candidate_presentations_compatible,
    homologate_products_v2,
    profile_product_v2,
    resolve_brand,
    resolve_presentation_v2,
    build_brand_lexicon,
)


def product(
    record_id: str,
    supermarket: str,
    name: str,
    *,
    brand: str | None = None,
    presentation: str | None = None,
    barcode: str | None = None,
) -> SourceProductRecord:
    return SourceProductRecord(
        source_record_id=record_id,
        supermarket_id=supermarket,
        source_name=name,
        source_brand=brand,
        source_presentation=presentation,
        barcode=barcode,
    )


@pytest.mark.parametrize(
    "suffix",
    ["u", "Un", "UN", "ud", "uds", "und", "unds", "unidad", "unidades"],
)
def test_count_aliases_normalize_to_same_signature(suffix: str) -> None:
    signature, status = resolve_presentation_v2(
        product("a", "colonial", f"Huevos Bonovo Grande 30 {suffix}", brand="Bonovo")
    )
    assert status == "name_only"
    assert signature is not None
    assert signature.dimension == "count"
    assert signature.total_base == Decimal("30")
    assert signature.pack_count == 30


def test_mass_volume_and_imperial_aliases_are_normalized_for_comparison() -> None:
    mg, _ = resolve_presentation_v2(product("mg", "a", "Suplemento 500 mg"))
    gram, _ = resolve_presentation_v2(product("g", "b", "Suplemento 0.5 g"))
    libra, _ = resolve_presentation_v2(product("lb", "a", "Arroz 1 libra"))
    grams, _ = resolve_presentation_v2(product("gr", "b", "Arroz 453.59237 gramos"))
    liter, _ = resolve_presentation_v2(product("l", "a", "Leche 1 L"))
    ml, _ = resolve_presentation_v2(product("ml", "b", "Leche 1000 ml"))

    assert mg is not None and gram is not None and mg.total_base == gram.total_base == Decimal("0.5")
    assert libra is not None and grams is not None and libra.total_base == grams.total_base
    assert liter is not None and ml is not None and liter.total_base == ml.total_base == Decimal("1000")


def test_multipack_remains_structured_and_not_equal_to_single_unit() -> None:
    multi, _ = resolve_presentation_v2(
        product("a", "pricesmart", "Pepsi 6 x 355 ml", brand="Pepsi")
    )
    single, _ = resolve_presentation_v2(
        product("b", "walmart", "Pepsi 355 ml", brand="Pepsi")
    )
    assert multi is not None and single is not None
    assert multi.pack_count == 6
    assert multi.total_base == Decimal("2130")
    assert not candidate_presentations_compatible(multi, single)


def test_egg_grade_g_is_not_parsed_as_grams() -> None:
    record = product(
        "colonial:9884",
        "colonial",
        "Norteño Huevos 30G UND",
        brand="Norteño",
    )
    taxonomy = assign_taxonomy_v2(record)
    signature, status = resolve_presentation_v2(record, taxonomy)
    assert taxonomy.product_type == "Huevo"
    assert canonical_egg_size(record, taxonomy) == "Grande"
    assert signature is not None and signature.dimension == "count"
    assert signature.total_base == Decimal("30")
    assert status == "name_only"


def test_real_grams_are_not_reinterpreted_as_egg_grade() -> None:
    record = product("kinder", "colonial", "KINDER Huevo Sorpresa Niño 20 g")
    taxonomy = assign_taxonomy_v2(record)
    signature, _ = resolve_presentation_v2(record, taxonomy)
    assert taxonomy.product_type == "Chocolate"
    assert canonical_egg_size(record, taxonomy) is None
    assert signature is not None and signature.dimension == "mass_g"
    assert signature.total_base == Decimal("20")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Bonovo Huevo G 30 und", "Grande"),
        ("Huevos Bonovo Cartón M 30Un", "Mediano"),
        ("Huevos Bonovo Cartón P 15Un", "Pequeño"),
        ("Bonovo Huevo XL 10 uni", "Extra grande"),
        ("Bonovo Huevo Extra Grande 10 unidades", "Extra grande"),
    ],
)
def test_egg_sizes_have_canonical_semantics(name: str, expected: str) -> None:
    record = product("egg", "colonial", name, brand="Bonovo")
    assert canonical_egg_size(record, assign_taxonomy_v2(record)) == expected


def test_huevo_token_does_not_pollute_unrelated_product_types() -> None:
    assert assign_taxonomy_v2(product("a", "x", "LONG LIFE tallarin de huevo 400grs.")).product_type == "Pasta"
    assert assign_taxonomy_v2(product("b", "x", "Kraft Mayonesa de Huevos de Gallina Libres 887 ml")).product_type == "Mayonesa"
    assert assign_taxonomy_v2(product("c", "x", "KINDER Huevo Sorpresa Niño 20g")).product_type == "Chocolate"
    assert assign_taxonomy_v2(product("d", "x", "RES Huevos de Toro X Libra")).product_type is None


def test_generic_source_brand_can_be_recovered_only_from_known_brand_in_name() -> None:
    records = (
        product("trusted", "walmart", "Huevos Bonovo 30 unidades", brand="Bonovo"),
        product("generic", "colonial", "Bonovo Huevo G 30 und", brand="RMS"),
        product("unknown", "andes", "Huevos especiales 30 und", brand="Marca COMANDES"),
    )
    lexicon = build_brand_lexicon(records)
    generic = resolve_brand(records[1], brand_lexicon=lexicon)
    unknown = resolve_brand(records[2], brand_lexicon=lexicon)
    assert generic.canonical_brand == "bonovo"
    assert generic.source == "name_known_brand"
    assert unknown.canonical_brand is None
    assert unknown.source == "missing"


def test_nutri_yema_554g_vs_1_2lb_becomes_review_candidate_without_auto_merge() -> None:
    records = (
        product(
            "colonial:10593",
            "colonial",
            "Nutri Yema Claras de Huevo 554gr",
            brand="Nutri Yema",
            presentation=None,
        ),
        product(
            "comisariato_los_andes:46232",
            "comisariato_los_andes",
            "Claras de huevo liquidas doy pack 1.2 lb",
            brand="Marca COMANDES",
            presentation="UN",
        ),
    )
    result = homologate_products_v2(records)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.status == "review_required"
    assert candidate.left_supermarket_id != candidate.right_supermarket_id
    profiles = {profile.record.source_record_id: profile for profile in result.profiles}
    left = profiles["colonial:10593"]
    right = profiles["comisariato_los_andes:46232"]
    assert left.presentation is not None and left.presentation.total_base == Decimal("554")
    assert right.presentation is not None
    assert abs(right.presentation.total_base - Decimal("544.310844")) < Decimal("0.000001")
    assert candidate_presentations_compatible(left.presentation, right.presentation)
    assert all(profile.canonical_product_id is None for profile in result.profiles)


def test_candidate_tolerance_does_not_make_500g_equal_554g() -> None:
    five_hundred, _ = resolve_presentation_v2(product("a", "x", "Claras de huevo 500 g"))
    five_fifty_four, _ = resolve_presentation_v2(product("b", "y", "Claras de huevo 554 g"))
    assert five_hundred is not None and five_fifty_four is not None
    assert not candidate_presentations_compatible(five_hundred, five_fifty_four)


def test_different_flavor_or_variant_remains_separate() -> None:
    flavor = homologate_products_v2(
        (
            product("a", "a", "Leche Marca Vainilla 1 L", brand="Marca"),
            product("b", "b", "Leche Marca Chocolate 1 L", brand="Marca"),
        ),
        candidate_threshold=Decimal("0"),
    )
    variant = homologate_products_v2(
        (
            product("c", "a", "Refresco Cola Original 1 L", brand="Cola"),
            product("d", "b", "Refresco Cola Zero 1 L", brand="Cola"),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert flavor.candidates == ()
    assert variant.candidates == ()


def test_different_valid_gtins_remain_hard_conflict() -> None:
    result = homologate_products_v2(
        (
            product("a", "a", "Arroz Progreso 1 lb", brand="Progreso", barcode="7590002040003"),
            product("b", "b", "Arroz Progreso 454 g", brand="Progreso", barcode="7501031311309"),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert result.candidates == ()
    assert result.exact_gtin_groups == ()


def test_candidate_graph_does_not_create_transitive_canonical_identity() -> None:
    result = homologate_products_v2(
        (
            product("a", "a", "Leche Demo Entera 1000 ml", brand="Demo"),
            product("b", "b", "Demo Leche Entera 1 L", brand="Demo"),
            product("c", "c", "Leche Demo Entera 1000 ml", brand="Demo"),
        ),
        candidate_threshold=Decimal("0"),
    )
    assert len(result.candidates) == 3
    assert all(profile.canonical_product_id is None for profile in result.profiles)
    assert result.exact_gtin_groups == ()


def test_persistence_contract_is_versioned_with_identity_v2() -> None:
    assert NORMALIZATION_VERSION == IDENTITY_NORMALIZATION_VERSION == "product-homologation-v2"


def test_profile_v2_preserves_raw_evidence() -> None:
    record = product(
        "a",
        "colonial",
        "Bonovo Huevo G 30 und",
        brand="RMS",
        presentation="UN",
    )
    profile = profile_product_v2(record, brand_lexicon=frozenset({"bonovo"}))
    assert profile.record.source_brand == "RMS"
    assert profile.record.source_presentation == "UN"
    assert profile.normalized_brand == "bonovo"
    assert profile.presentation is not None and profile.presentation.total_base == Decimal("30")
