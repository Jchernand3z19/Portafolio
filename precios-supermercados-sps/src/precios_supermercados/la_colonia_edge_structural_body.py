"""Validación estricta de respuestas GraphQL de facet discovery.

Recibe únicamente bytes ya capturados por la frontera edge. No abre red. Rechaza
JSON ambiguo/no finito y normaliza las dos respuestas exactas que alimentan el
análisis estructural existente.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, NoReturn

from precios_supermercados.la_colonia_edge_structural_request import (
    ValidatedLaColoniaStructuralRequest,
)

MAX_STRUCTURAL_GRAPHQL_BODY_BYTES = 1_500_000


class LaColoniaEdgeStructuralBodyError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise LaColoniaEdgeStructuralBodyError(code, message)


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("structural_json_duplicate_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail("structural_json_non_finite_number", value)


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("structural_json_non_finite_number")
        return
    if isinstance(value, dict):
        for nested in value.values():
            _reject_non_finite(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _reject_non_finite(nested)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(nested) for key, nested in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(nested) for nested in value)
    return value


def _positive_int(value: object, code: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > 2**53 - 1
    ):
        _fail(code)
    return value


def _graphql_data(raw_body: bytes) -> dict[str, Any]:
    if not isinstance(raw_body, bytes):
        _fail("structural_body_type_invalid")
    if not raw_body:
        _fail("structural_body_empty")
    if len(raw_body) > MAX_STRUCTURAL_GRAPHQL_BODY_BYTES:
        _fail("structural_body_above_limit")
    try:
        text = raw_body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LaColoniaEdgeStructuralBodyError("structural_body_utf8_invalid") from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except LaColoniaEdgeStructuralBodyError:
        raise
    except json.JSONDecodeError as exc:
        raise LaColoniaEdgeStructuralBodyError("structural_body_json_invalid") from exc
    _reject_non_finite(payload)
    if not isinstance(payload, dict):
        _fail("structural_graphql_envelope_not_object")
    unexpected = set(payload) - {"data", "errors"}
    if unexpected:
        _fail("structural_graphql_envelope_fields_invalid")
    if "errors" in payload:
        errors = payload["errors"]
        if not isinstance(errors, list):
            _fail("structural_graphql_errors_shape_invalid")
        if errors:
            _fail("structural_graphql_errors_present")
    data = payload.get("data")
    if not isinstance(data, dict):
        _fail("structural_graphql_data_missing")
    return data


@dataclass(frozen=True, slots=True)
class ValidatedStructuralDiscoveryBody:
    request_kind: str
    payload: Mapping[str, Any]
    normalized_payload: Mapping[str, Any]
    records_filtered: int
    production_authority: bool = False

    def __post_init__(self) -> None:
        if self.production_authority is not False:
            _fail("structural_body_production_authority_forbidden")


def validate_la_colonia_structural_body(
    raw_body: bytes,
    request: ValidatedLaColoniaStructuralRequest,
) -> ValidatedStructuralDiscoveryBody:
    if not isinstance(request, ValidatedLaColoniaStructuralRequest):
        _fail("structural_request_contract_invalid")
    data = _graphql_data(raw_body)

    product_search = data.get("productSearch")
    if not isinstance(product_search, dict):
        _fail("structural_product_search_missing")
    records_filtered = _positive_int(
        product_search.get("recordsFiltered"),
        "structural_records_filtered_invalid",
    )

    if request.request_kind == "root_total":
        if set(data) != {"productSearch"}:
            _fail("structural_root_data_shape_invalid")
        normalized: dict[str, Any] = {"recordsFiltered": records_filtered}
    elif request.request_kind == "category_tree":
        if set(data) != {"productSearch", "facets"}:
            _fail("structural_tree_data_shape_invalid")
        facets = data.get("facets")
        if not isinstance(facets, dict):
            _fail("structural_facets_missing")
        if set(facets) != {"sampling", "facets"}:
            _fail("structural_facets_shape_invalid")
        sampling = facets.get("sampling")
        facet_values = facets.get("facets")
        if not isinstance(sampling, bool):
            _fail("structural_sampling_invalid")
        if not isinstance(facet_values, list):
            _fail("structural_facets_list_invalid")
        if any(not isinstance(facet, dict) for facet in facet_values):
            _fail("structural_facet_item_invalid")
        normalized = {
            "recordsFiltered": records_filtered,
            "sampling": sampling,
            "facets": facet_values,
        }
    else:
        _fail("structural_request_kind_invalid")

    frozen_payload = _freeze({"data": data})
    frozen_normalized = _freeze(normalized)
    if not isinstance(frozen_payload, Mapping) or not isinstance(frozen_normalized, Mapping):
        _fail("structural_body_freeze_failed")
    return ValidatedStructuralDiscoveryBody(
        request_kind=request.request_kind,
        payload=frozen_payload,
        normalized_payload=frozen_normalized,
        records_filtered=records_filtered,
    )
