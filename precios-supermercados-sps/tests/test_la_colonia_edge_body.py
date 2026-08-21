from __future__ import annotations

import json

import pytest

from precios_supermercados.la_colonia_edge_body import (
    LaColoniaEdgeBodyError,
    validate_la_colonia_edge_body,
)
from precios_supermercados.la_colonia_edge_request import validate_la_colonia_edge_request
from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url


def request(*, page: int = 1, page_size: int = 2):
    return validate_la_colonia_edge_request(
        build_product_search_url(
            page=page,
            page_size=page_size,
            order_by="OrderByNameASC",
        )
    )


def body(*, records_filtered: int, products: list[object], errors: object = None) -> bytes:
    payload: dict[str, object] = {
        "data": {
            "productSearch": {
                "recordsFiltered": records_filtered,
                "products": products,
            }
        }
    }
    if errors is not None:
        payload["errors"] = errors
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def assert_code(raw: bytes, expected: str, *, page: int = 1, page_size: int = 2) -> None:
    with pytest.raises(LaColoniaEdgeBodyError) as captured:
        validate_la_colonia_edge_body(raw, request(page=page, page_size=page_size))
    assert captured.value.code == expected


def test_pagina_completa_se_valida_y_permanece_sin_autoridad() -> None:
    validated = validate_la_colonia_edge_body(
        body(records_filtered=3, products=[{"productId": "1"}, {"productId": "2"}]),
        request(),
    )
    assert validated.records_filtered == 3
    assert validated.products_returned == 2
    assert validated.expected_products == 2
    assert validated.production_authority is False
    assert validated.payload["data"]["productSearch"]["products"][0]["productId"] == "1"


def test_ultima_pagina_y_catalogo_vacio_son_coherentes() -> None:
    last_page = validate_la_colonia_edge_body(
        body(records_filtered=3, products=[{"productId": "3"}]),
        request(page=2),
    )
    assert last_page.products_returned == 1
    assert last_page.expected_products == 1

    empty = validate_la_colonia_edge_body(
        body(records_filtered=0, products=[]),
        request(),
    )
    assert empty.products_returned == 0
    assert empty.expected_products == 0


def test_payload_resultante_es_inmutable_en_profundidad() -> None:
    validated = validate_la_colonia_edge_body(
        body(records_filtered=1, products=[{"nested": {"x": [1, 2]}}]),
        request(),
    )
    with pytest.raises(TypeError):
        validated.payload["data"]["productSearch"] = {}  # type: ignore[index]
    assert validated.payload["data"]["productSearch"]["products"][0]["nested"]["x"] == (1, 2)


def test_utf8_json_y_top_level_invalidos_fallan_cerrado() -> None:
    assert_code(b"\xff", "body_utf8_invalid")
    assert_code(b"{not-json", "body_json_invalid")
    assert_code(b"[]", "graphql_envelope_not_object")


def test_claves_json_duplicadas_y_numeros_no_finitos_fallan_cerrado() -> None:
    duplicate = b'{"data":{"productSearch":{"recordsFiltered":1,"recordsFiltered":1,"products":[{}]}}}'
    assert_code(duplicate, "json_duplicate_key")
    non_finite = b'{"data":{"productSearch":{"recordsFiltered":NaN,"products":[]}}}'
    assert_code(non_finite, "json_non_finite_number")


def test_errores_graphql_nunca_se_aceptan_como_evidencia_utilizable() -> None:
    assert_code(
        body(records_filtered=1, products=[{}], errors=[{"message": "backend failure"}]),
        "graphql_errors_present",
    )
    malformed = b'{"errors":{},"data":{"productSearch":{"recordsFiltered":0,"products":[]}}}'
    assert_code(malformed, "graphql_errors_shape_invalid")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"data":null}', "graphql_data_missing"),
        (b'{"data":{}}', "graphql_product_search_missing"),
        (b'{"data":{"productSearch":{"recordsFiltered":0}}}', "graphql_products_missing"),
        (b'{"data":{"productSearch":{"recordsFiltered":1,"products":[1]}}}', "graphql_product_shape_invalid"),
        (b'{"data":{"productSearch":{"recordsFiltered":"1","products":[{}]}}}', "graphql_records_filtered_invalid"),
        (b'{"data":{"productSearch":{"recordsFiltered":true,"products":[{}]}}}', "graphql_records_filtered_invalid"),
        (b'{"data":{"productSearch":{"recordsFiltered":1,"products":[{},{}]}}}', "graphql_records_filtered_below_products"),
    ],
)
def test_shape_graphql_invalido_falla_cerrado(raw: bytes, code: str) -> None:
    assert_code(raw, code)


def test_pagina_parcial_falla_aunque_json_y_records_filtered_sean_validos() -> None:
    assert_code(
        body(records_filtered=5, products=[{"productId": "1"}]),
        "graphql_partial_or_overfull_page",
    )


def test_pagina_solicitada_fuera_del_total_debe_estar_vacia() -> None:
    validated = validate_la_colonia_edge_body(
        body(records_filtered=1, products=[]),
        request(page=2),
    )
    assert validated.expected_products == 0

    assert_code(
        body(records_filtered=1, products=[{}]),
        "graphql_partial_or_overfull_page",
        page=2,
    )
