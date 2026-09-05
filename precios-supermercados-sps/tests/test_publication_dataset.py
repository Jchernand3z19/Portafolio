from __future__ import annotations

from precios_supermercados.price_analytics import ComparisonScope, CurrentPriceObservation, analyze_current_prices
from precios_supermercados.product_homologation import SourceProductRecord, homologate_products
from precios_supermercados.publication_dataset import build_publication_dataset


def product(record_id: str, supermarket: str) -> SourceProductRecord:
    return SourceProductRecord(
        source_record_id=record_id,
        supermarket_id=supermarket,
        source_name="Suavizante Downy Pureza 800 ml",
        source_brand="Downy",
        source_presentation="800 ml",
        barcode="7590002040003",
    )


def test_publication_dataset_exposes_safe_denominator_and_no_internal_authority() -> None:
    homologation = homologate_products((product("colonial:1", "colonial"), product("walmart:2", "walmart")))
    result = analyze_current_prices(
        homologation,
        (
            CurrentPriceObservation("colonial:1", "colonial", "colonial_sps", 10000),
            CurrentPriceObservation("walmart:2", "walmart", "walmart_sps", 12000),
        ),
        ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps"))),
    )
    dataset = build_publication_dataset(result)
    document = dataset.as_json_object()

    assert document["schema"] == "precios-sps-publication/v1"
    assert document["comparison_policy"] == "fail_closed_strong_identity_and_commercial_consistency"
    assert document["currency"] == "HNL"
    assert len(document["products"]) == 1
    assert document["products"][0]["best_supermarket_id"] == "colonial"
    assert document["products"][0]["best_price"] == "100.00"
    assert document["products"][0]["savings_vs_highest"] == "20.00"
    assert len(document["offers"]) == 2
    assert sum(row["is_best_price"] for row in document["offers"]) == 1
    assert all(
        row["denominator_definition"] == "products_comparable_and_priced_in_every_supermarket_in_scope"
        for row in document["common_basket"]
    )
    serialized = repr(document)
    assert "token" not in serialized.casefold()
    assert "database_url" not in serialized.casefold()
    assert "auth" not in serialized.casefold()


def test_publication_marks_all_exact_price_ties_as_best() -> None:
    homologation = homologate_products((product("colonial:1", "colonial"), product("walmart:2", "walmart")))
    result = analyze_current_prices(
        homologation,
        (
            CurrentPriceObservation("colonial:1", "colonial", "colonial_sps", 10000),
            CurrentPriceObservation("walmart:2", "walmart", "walmart_sps", 10000),
        ),
        ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps"))),
    )
    dataset = build_publication_dataset(result)

    assert sum(row.is_best_price for row in dataset.offers) == 2
    assert sum(row.is_cheapest for row in dataset.common_basket) == 2


def test_publication_dataset_counts_excluded_unsafe_groups_without_publishing_prices() -> None:
    records = (
        SourceProductRecord(
            source_record_id="a",
            supermarket_id="colonial",
            source_name="Café Passion Especial 1 lb",
            source_brand="Passion",
            source_presentation="1 lb",
            barcode="7590002040003",
        ),
        SourceProductRecord(
            source_record_id="b",
            supermarket_id="walmart",
            source_name="Café Passion Jaguar 1 lb",
            source_brand="Passion",
            source_presentation="1 lb",
            barcode="07590002040003",
        ),
    )
    result = analyze_current_prices(
        homologate_products(records),
        (
            CurrentPriceObservation("a", "colonial", "colonial_sps", 21000),
            CurrentPriceObservation("b", "walmart", "walmart_sps", 29000),
        ),
        ComparisonScope((("colonial", "colonial_sps"), ("walmart", "walmart_sps"))),
    )
    dataset = build_publication_dataset(result)
    assert dataset.offers == ()
    assert dataset.products == ()
    assert dataset.excluded_group_counts == {"not_comparable": 1}
    assert all(row.product_count == 0 for row in dataset.common_basket)
    assert not any(row.is_cheapest for row in dataset.common_basket)
