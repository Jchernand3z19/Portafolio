"""Validación offline del body GraphQL firmado por el gateway edge.

La capa sólo determina si los bytes representan una respuesta GraphQL íntegra y
coherente con el rango solicitado. No normaliza productos, no concede autoridad
productiva y no abre red.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, NoReturn

from precios_supermercados.la_colonia_edge_request import ValidatedLaColoniaEdgeRequest

MAX_EDGE_GRAPHQL_BODY_BYTES = 1_500_000


class LaColoniaEdgeBodyError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise LaColoniaEdgeBodyError(code, message)


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("json_duplicate_key", f"clave JSON duplicada: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail("json_non_finite_number", f"número JSON no finito: {value}")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _safe_non_negative_int(value: object, code: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > 2**53 - 1
    ):
        _fail(code)
    return value


@dataclass(frozen=True, slots=True)
class ValidatedLaColoniaEdgeBody:
    payload: Mapping[str, Any]
    records_filtered: int
    products_returned: int
    expected_products: int
    production_authority: bool = False


def validate_la_colonia_edge_body(
    raw_body: bytes,
    request: ValidatedLaColoniaEdgeRequest,
) -> ValidatedLaColoniaEdgeBody:
    """Valida bytes JSON y completitud de la página contra el request canónico."""

    if not isinstance(raw_body, bytes):
        _fail("body_type_invalid")
    if not raw_body:
        _fail("body_empty")
    if len(raw_body) > MAX_EDGE_GRAPHQL_BODY_BYTES:
        _fail("body_above_limit")
    if not isinstance(request, ValidatedLaColoniaEdgeRequest):
        _fail("request_contract_invalid")

    try:
        text = raw_body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LaColoniaEdgeBodyError("body_utf8_invalid") from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except LaColoniaEdgeBodyError:
        raise
    except json.JSONDecodeError as exc:
        raise LaColoniaEdgeBodyError("body_json_invalid") from exc

    if not isinstance(payload, dict):
        _fail("graphql_envelope_not_object")

    if "errors" in payload:
        errors = payload["errors"]
        if not isinstance(errors, list):
            _fail("graphql_errors_shape_invalid")
        if errors:
            _fail("graphql_errors_present")

    data = payload.get("data")
    if not isinstance(data, dict):
        _fail("graphql_data_missing")
    product_search = data.get("productSearch")
    if not isinstance(product_search, dict):
        _fail("graphql_product_search_missing")

    products = product_search.get("products")
    if not isinstance(products, list):
        _fail("graphql_products_missing")
    if any(not isinstance(product, dict) for product in products):
        _fail("graphql_product_shape_invalid")

    records_filtered = _safe_non_negative_int(
        product_search.get("recordsFiltered"),
        "graphql_records_filtered_invalid",
    )
    if records_filtered < len(products):
        _fail("graphql_records_filtered_below_products")

    remaining = max(records_filtered - request.from_index, 0)
    expected_products = min(request.page_size, remaining)
    if len(products) != expected_products:
        _fail("graphql_partial_or_overfull_page")

    frozen = _freeze(payload)
    if not isinstance(frozen, Mapping):
        _fail("graphql_envelope_not_object")
    return ValidatedLaColoniaEdgeBody(
        payload=frozen,
        records_filtered=records_filtered,
        products_returned=len(products),
        expected_products=expected_products,
    )
