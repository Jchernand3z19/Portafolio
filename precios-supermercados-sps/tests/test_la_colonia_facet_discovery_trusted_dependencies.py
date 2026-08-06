from precios_supermercados.scrapers.la_colonia_graphql import (
    ALLOWED_ORDER_BY,
    MAX_CATALOG_PAGE_SIZE,
)


def test_facet_discovery_coverage_dependencies_exist_in_trusted_main():
    assert MAX_CATALOG_PAGE_SIZE == 50
    assert "OrderByNameASC" in ALLOWED_ORDER_BY
