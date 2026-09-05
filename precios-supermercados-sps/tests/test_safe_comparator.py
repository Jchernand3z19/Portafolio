from __future__ import annotations

from precios_supermercados.product_homologation import SourceProductRecord, homologate_products, profile_product
from precios_supermercados.safe_comparator import (
    COMPARABLE,
    NOT_COMPARABLE,
    REVIEW_REQUIRED,
    compare_profiles,
    safe_group_decisions,
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


def decision(left: SourceProductRecord, right: SourceProductRecord):
    return compare_profiles(profile_product(left), profile_product(right))


def test_brand_and_presentation_alone_never_authorize_direct_comparison() -> None:
    result = decision(
        product(
            "la_colonia:passion-jaguar",
            "la_colonia",
            "Café Molido Passion Jaguar 1 lb",
            brand="Passion",
            presentation="1 lb",
        ),
        product(
            "colonial:passion-especial",
            "colonial",
            "Café Passion Especial 1 lb",
            brand="Passion",
            presentation="1 lb",
        ),
    )
    assert result.status == REVIEW_REQUIRED
    assert result.automatic_comparable is False
    assert result.reasons == ("strong_identity_missing",)


def test_passion_jaguar_and_especial_are_blocked_even_if_source_gtin_is_reused() -> None:
    result = decision(
        product(
            "la_colonia:passion-jaguar",
            "la_colonia",
            "Café Molido Passion Jaguar 1 lb",
            brand="Passion",
            presentation="1 lb",
            barcode="7590002040003",
        ),
        product(
            "colonial:passion-especial",
            "colonial",
            "Café Passion Especial 1 lb",
            brand="Passion",
            presentation="1 lb",
            barcode="7590002040003",
        ),
    )
    assert result.status == NOT_COMPARABLE
    assert result.automatic_comparable is False
    assert result.reasons == ("commercial_identity_conflict",)


def test_same_gtin_brand_variant_and_presentation_is_comparable() -> None:
    result = decision(
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
    assert result.status == COMPARABLE
    assert result.automatic_comparable is True
    assert result.reasons == ()
    assert result.canonical_product_id == "prod_gtin_07590002040003"


def test_different_presentation_is_never_directly_comparable() -> None:
    result = decision(
        product(
            "a",
            "la_colonia",
            "Maíz El Migo Dulce En Grano 240 g",
            brand="El Migo",
            presentation="240 g",
            barcode="012656001065",
        ),
        product(
            "b",
            "walmart",
            "Maíz El Migo Dulce En Grano 148 g",
            brand="El Migo",
            presentation="148 g",
            barcode="012656001065",
        ),
    )
    assert result.status == NOT_COMPARABLE
    assert "presentation_conflict" in result.reasons


def test_different_valid_gtin_is_not_comparable() -> None:
    result = decision(
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
    assert result.status == NOT_COMPARABLE
    assert result.reasons == ("different_gtin",)


def test_safe_group_requires_every_cross_supermarket_pair_to_pass() -> None:
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
    groups = safe_group_decisions(result)
    assert len(groups) == 1
    assert groups[0].status == COMPARABLE
    assert groups[0].automatic_comparable is True


def test_safe_group_demotes_existing_gtin_group_on_commercial_variant_conflict() -> None:
    result = homologate_products(
        (
            product(
                "la_colonia:1",
                "la_colonia",
                "Café Molido Passion Jaguar 1 lb",
                brand="Passion",
                presentation="1 lb",
                barcode="7590002040003",
            ),
            product(
                "colonial:2",
                "colonial",
                "Café Passion Especial 1 lb",
                brand="Passion",
                presentation="1 lb",
                barcode="07590002040003",
            ),
        )
    )
    assert result.exact_gtin_groups[0].comparison_status == "ready"
    groups = safe_group_decisions(result)
    assert groups[0].status == NOT_COMPARABLE
    assert "commercial_identity_conflict" in groups[0].reasons
