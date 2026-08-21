from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest

from precios_supermercados.la_colonia_edge_request import (
    EXPECTED_GRAPHQL_QUERY_SHA256,
    LaColoniaEdgeRequestError,
    validate_la_colonia_edge_request,
)
from precios_supermercados.scrapers.la_colonia_graphql import (
    PRODUCT_SEARCH_QUERY,
    build_product_search_url,
)


def _pairs(url: str) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(url).query, keep_blank_values=True, strict_parsing=True)


def _with_pairs(url: str, pairs: list[tuple[str, str]]) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), ""))


def _mutate_variables(url: str, mutate, *, compact: bool = True) -> str:
    pairs = _pairs(url)
    result: list[tuple[str, str]] = []
    for key, value in pairs:
        if key != "variables":
            result.append((key, value))
            continue
        variables = json.loads(value)
        mutate(variables)
        serialized = (
            json.dumps(variables, separators=(",", ":"))
            if compact
            else json.dumps(variables)
        )
        result.append((key, serialized))
    return _with_pairs(url, result)


def _code(error: BaseException, expected: str) -> bool:
    return isinstance(error, LaColoniaEdgeRequestError) and error.code == expected


def test_builder_catalog_url_es_aceptada_y_reconstruida_exactamente() -> None:
    url = build_product_search_url(page=3, page_size=50, order_by="OrderByPriceDESC")
    validated = validate_la_colonia_edge_request(url)

    assert validated.source_url == url
    assert validated.from_index == 100
    assert validated.to_index == 149
    assert validated.page_size == 50
    assert validated.order_by == "OrderByPriceDESC"
    assert validated.query_value == "supermercado"
    assert validated.selected_facets == (("category-1", "supermercado"),)
    assert validated.graphql_query_sha256 == EXPECTED_GRAPHQL_QUERY_SHA256
    assert len(validated.canonical_request_sha256) == 64


def test_builder_full_text_unicode_conserva_forma_canonica() -> None:
    url = build_product_search_url(
        page=2,
        page_size=10,
        full_text="café molido",
        order_by="OrderByNameASC",
    )
    validated = validate_la_colonia_edge_request(url)
    assert validated.full_text == "café molido"
    assert validated.query_value == ""
    assert validated.selected_facets == ()
    assert validated.from_index == 10
    assert validated.to_index == 19


def test_parametro_duplicado_falla_cerrado() -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")
    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(f"{url}&workspace=master")
    assert captured.value.code == "origin_query_parameter_duplicate"


def test_reordenar_parametros_externos_no_es_builder_canonico() -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")
    pairs = _pairs(url)
    reordered = _with_pairs(url, [pairs[1], pairs[0], *pairs[2:]])
    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(reordered)
    assert captured.value.code == "origin_query_parameter_order_or_set_invalid"


def test_query_graphql_alterada_falla_aunque_variables_sean_validas() -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")
    pairs = [(key, f"{value} " if key == "query" else value) for key, value in _pairs(url)]
    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(_with_pairs(url, pairs))
    assert captured.value.code == "graphql_query_mismatch"


def test_json_de_variables_con_espacios_es_semanticamente_valido_pero_no_canonico() -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")
    altered = _mutate_variables(url, lambda _: None, compact=False)
    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(altered)
    assert captured.value.code == "variables_json_noncanonical"


def test_orden_de_claves_de_variables_debe_ser_el_del_builder() -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")

    def reorder(value: dict[str, object]) -> None:
        query = value.pop("query")
        value["query"] = query

    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(_mutate_variables(url, reorder))
    assert captured.value.code == "variables_shape_or_order_invalid"


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.__setitem__("hideUnavailableItems", True), "hide_unavailable_must_be_false"),
        (lambda value: value.__setitem__("skusFilter", "FIRST_AVAILABLE"), "skus_filter_must_be_all"),
        (lambda value: value.__setitem__("to", 50), "page_size_above_limit"),
        (lambda value: (value.__setitem__("from", 1), value.__setitem__("to", 10)), "range_not_builder_page"),
        (lambda value: value.__setitem__("orderBy", "OrderByScoreDESC"), "order_by_not_allowed"),
        (lambda value: value.__setitem__("selectedFacets", []), "facet_mode_shape_mismatch"),
        (
            lambda value: value.__setitem__(
                "selectedFacets",
                [{"key": "category-0", "value": "supermercado"}],
            ),
            "selected_facet_key_invalid",
        ),
        (
            lambda value: value.__setitem__(
                "selectedFacets",
                [
                    {"key": "category-1", "value": "supermercado"},
                    {"key": "category-2", "value": "supermercado"},
                ],
            ),
            "facet_mode_shape_mismatch",
        ),
        (
            lambda value: value.__setitem__(
                "selectedFacets",
                [{"key": "category-1", "value": "otra-categoria"}],
            ),
            "facet_value_query_mismatch",
        ),
    ],
)
def test_variables_fuera_del_contrato_fallan_cerrado(mutate, code: str) -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")
    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(_mutate_variables(url, mutate))
    assert captured.value.code == code


def test_full_text_no_puede_mezclarse_con_query_o_facets() -> None:
    url = build_product_search_url(
        page=1,
        page_size=10,
        full_text="café",
        order_by="OrderByNameASC",
    )

    def mix(value: dict[str, object]) -> None:
        value["query"] = "supermercado"
        value["selectedFacets"] = [{"key": "category-1", "value": "supermercado"}]

    with pytest.raises(LaColoniaEdgeRequestError) as captured:
        validate_la_colonia_edge_request(_mutate_variables(url, mix))
    assert captured.value.code == "full_text_mode_shape_mismatch"


def test_fragmento_y_host_distinto_fallan_antes_de_digest() -> None:
    url = build_product_search_url(page=1, page_size=10, order_by="OrderByNameASC")
    with pytest.raises(LaColoniaEdgeRequestError) as fragment_error:
        validate_la_colonia_edge_request(f"{url}#unexpected")
    assert fragment_error.value.code == "origin_path_invalid"

    with pytest.raises(LaColoniaEdgeRequestError) as host_error:
        validate_la_colonia_edge_request(url.replace("www.lacolonia.com", "example.com", 1))
    assert host_error.value.code == "origin_target_invalid"


def test_query_sha_fijo_corresponde_al_query_python_actual() -> None:
    import hashlib

    assert EXPECTED_GRAPHQL_QUERY_SHA256 == hashlib.sha256(
        PRODUCT_SEARCH_QUERY.encode("utf-8")
    ).hexdigest()
