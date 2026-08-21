from __future__ import annotations

import json

import pytest

from precios_supermercados.la_colonia_edge_structural_body import (
    LaColoniaEdgeStructuralBodyError,
    validate_la_colonia_structural_body,
)
from precios_supermercados.la_colonia_edge_structural_request import (
    build_structural_discovery_url,
    validate_la_colonia_structural_request,
)


def _request(kind: str):
    return validate_la_colonia_structural_request(build_structural_discovery_url(kind))


def _raw(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def test_root_total_normaliza_entero_positivo() -> None:
    body = validate_la_colonia_structural_body(
        _raw({"data": {"productSearch": {"recordsFiltered": 4321}}}),
        _request("root_total"),
    )
    assert body.request_kind == "root_total"
    assert body.records_filtered == 4321
    assert body.normalized_payload == {"recordsFiltered": 4321}
    assert body.production_authority is False


def test_category_tree_normaliza_control_sampling_y_facets() -> None:
    facet = {
        "type": "CATEGORY",
        "values": [
            {
                "key": "category-1",
                "value": "supermercado",
                "quantity": 7,
                "children": [],
            }
        ],
    }
    body = validate_la_colonia_structural_body(
        _raw(
            {
                "data": {
                    "productSearch": {"recordsFiltered": 7},
                    "facets": {"sampling": False, "facets": [facet]},
                }
            }
        ),
        _request("category_tree"),
    )
    assert body.records_filtered == 7
    assert body.normalized_payload["sampling"] is False
    assert len(body.normalized_payload["facets"]) == 1
    assert isinstance(body.normalized_payload["facets"], tuple)


def test_graphql_errors_fallan_cerrado() -> None:
    with pytest.raises(LaColoniaEdgeStructuralBodyError) as exc:
        validate_la_colonia_structural_body(
            _raw(
                {
                    "data": {"productSearch": {"recordsFiltered": 10}},
                    "errors": [{"message": "origin failure"}],
                }
            ),
            _request("root_total"),
        )
    assert exc.value.code == "structural_graphql_errors_present"


def test_duplicate_json_key_falla_cerrado() -> None:
    raw = b'{"data":{"productSearch":{"recordsFiltered":5,"recordsFiltered":6}}}'
    with pytest.raises(LaColoniaEdgeStructuralBodyError) as exc:
        validate_la_colonia_structural_body(raw, _request("root_total"))
    assert exc.value.code == "structural_json_duplicate_key"


@pytest.mark.parametrize(
    ("literal", "code"),
    [
        ("NaN", "structural_json_non_finite_number"),
        ("Infinity", "structural_json_non_finite_number"),
        ("1e999", "structural_json_non_finite_number"),
    ],
)
def test_numeros_no_finitos_fallan(literal: str, code: str) -> None:
    raw = f'{{"data":{{"productSearch":{{"recordsFiltered":5}},"facets":{{"sampling":false,"facets":[{{"type":"CATEGORY","values":[{{"key":"category-1","value":"x","quantity":{literal},"children":[]}}]}}]}}}}}}'.encode()
    with pytest.raises(LaColoniaEdgeStructuralBodyError) as exc:
        validate_la_colonia_structural_body(raw, _request("category_tree"))
    assert exc.value.code == code


@pytest.mark.parametrize("value", [True, 0, -1, "7", 7.0])
def test_records_filtered_no_admite_coercion(value: object) -> None:
    with pytest.raises(LaColoniaEdgeStructuralBodyError) as exc:
        validate_la_colonia_structural_body(
            _raw({"data": {"productSearch": {"recordsFiltered": value}}}),
            _request("root_total"),
        )
    assert exc.value.code == "structural_records_filtered_invalid"


def test_root_rechaza_payload_de_tree_y_tree_rechaza_root() -> None:
    tree_data = {
        "data": {
            "productSearch": {"recordsFiltered": 1},
            "facets": {"sampling": False, "facets": []},
        }
    }
    with pytest.raises(LaColoniaEdgeStructuralBodyError) as root_exc:
        validate_la_colonia_structural_body(_raw(tree_data), _request("root_total"))
    assert root_exc.value.code == "structural_root_data_shape_invalid"

    with pytest.raises(LaColoniaEdgeStructuralBodyError) as tree_exc:
        validate_la_colonia_structural_body(
            _raw({"data": {"productSearch": {"recordsFiltered": 1}}}),
            _request("category_tree"),
        )
    assert tree_exc.value.code == "structural_tree_data_shape_invalid"


def test_envelope_con_campos_inesperados_falla() -> None:
    with pytest.raises(LaColoniaEdgeStructuralBodyError) as exc:
        validate_la_colonia_structural_body(
            _raw(
                {
                    "data": {"productSearch": {"recordsFiltered": 1}},
                    "extensions": {"debug": True},
                }
            ),
            _request("root_total"),
        )
    assert exc.value.code == "structural_graphql_envelope_fields_invalid"


def test_body_es_inmutable_en_profundidad() -> None:
    body = validate_la_colonia_structural_body(
        _raw(
            {
                "data": {
                    "productSearch": {"recordsFiltered": 1},
                    "facets": {
                        "sampling": False,
                        "facets": [{"type": "CATEGORY", "values": []}],
                    },
                }
            }
        ),
        _request("category_tree"),
    )
    with pytest.raises(TypeError):
        body.normalized_payload["sampling"] = True  # type: ignore[index]
