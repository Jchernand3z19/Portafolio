from __future__ import annotations

import pytest

from precios_supermercados.la_colonia_edge_body import (
    LaColoniaEdgeBodyError,
    validate_la_colonia_edge_body,
)
from precios_supermercados.la_colonia_edge_request import validate_la_colonia_edge_request
from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url


def test_exponente_json_que_desborda_a_infinito_falla_cerrado() -> None:
    request = validate_la_colonia_edge_request(
        build_product_search_url(page=1, page_size=1, order_by="OrderByNameASC")
    )
    raw = b'{"data":{"productSearch":{"recordsFiltered":1,"products":[{"price":1e999}]}}}'
    with pytest.raises(LaColoniaEdgeBodyError) as captured:
        validate_la_colonia_edge_body(raw, request)
    assert captured.value.code == "json_non_finite_number"
