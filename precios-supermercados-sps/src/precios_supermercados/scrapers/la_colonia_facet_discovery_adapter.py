"""Adaptador HTTP confiable para las dos consultas cerradas de facet discovery.

No acepta URL, query, operationName, variables, facets ni headers externos.
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .la_colonia_facet_discovery import FacetDiscoveryRequest

FACET_DISCOVERY_HOST = "www.lacolonia.com"
FACET_DISCOVERY_ENDPOINT = "https://www.lacolonia.com/_v/segment/graphql/v1"
FACET_DISCOVERY_TIMEOUT_SECONDS = 20
FACET_DISCOVERY_USER_AGENT = "precios-supermercados-sps-facet-discovery/1.0"
FACET_DISCOVERY_MAX_REQUESTS = 2
FACET_DISCOVERY_MAX_RETRIES = 0
ROOT_TOTAL_OPERATION = "FacetDiscoveryRootTotal"
CATEGORY_TREE_OPERATION = "FacetDiscoveryCategoryTree"

ROOT_TOTAL_QUERY = """
query FacetDiscoveryRootTotal(
  $query: String
  $fullText: String
  $selectedFacets: [SelectedFacetInput]
  $from: Int
  $to: Int
) {
  productSearch(
    query: $query
    fullText: $fullText
    selectedFacets: $selectedFacets
    from: $from
    to: $to
    hideUnavailableItems: false
  ) @context(provider: "vtex.search-graphql") {
    recordsFiltered
  }
}
""".strip()

_CATEGORY_VALUE_FIELDS = """
key
value
quantity
children {
  key
  value
  quantity
  children {
    key
    value
    quantity
    children {
      key
      value
      quantity
      children {
        key
        value
        quantity
        children {
          key
          value
          quantity
          children {
            key
            value
            quantity
            children {
              key
              value
              quantity
              children {
                key
                value
                quantity
              }
            }
          }
        }
      }
    }
  }
}
""".strip()

CATEGORY_TREE_QUERY = f"""
query FacetDiscoveryCategoryTree(
  $query: String
  $fullText: String
  $selectedFacets: [SelectedFacetInput]
  $from: Int
  $to: Int
) {{
  productSearch(
    query: $query
    fullText: $fullText
    selectedFacets: $selectedFacets
    from: $from
    to: $to
    hideUnavailableItems: false
  ) @context(provider: "vtex.search-graphql") {{
    recordsFiltered
  }}
  facets(
    fullText: $fullText
    selectedFacets: $selectedFacets
    from: $from
    to: $to
    categoryTreeBehavior: show
  ) @context(provider: "vtex.search-graphql") {{
    sampling
    facets {{
      type
      values {{
        {_CATEGORY_VALUE_FIELDS}
      }}
    }}
  }}
}}
""".strip()

_FIXED_VARIABLES: Mapping[str, Any] = {
    "query": "",
    "fullText": "",
    "selectedFacets": [],
    "from": 0,
    "to": 0,
}


class FacetDiscoveryTransportError(RuntimeError):
    """Fallo HTTP, GraphQL o de seguridad sin reintento automático."""


@dataclass(frozen=True, slots=True)
class FixedGraphQLOperation:
    name: str
    query: str


_OPERATIONS = {
    "root_total": FixedGraphQLOperation(ROOT_TOTAL_OPERATION, ROOT_TOTAL_QUERY),
    "category_tree": FixedGraphQLOperation(CATEGORY_TREE_OPERATION, CATEGORY_TREE_QUERY),
}


def _default_opener(request: Request, timeout: float):
    return urlopen(request, timeout=timeout, context=ssl.create_default_context())


class LaColoniaFacetDiscoveryAdapter:
    """Transporte cerrado con host HTTPS fijo, dos requests y cero reintentos."""

    max_retries = FACET_DISCOVERY_MAX_RETRIES
    max_requests = FACET_DISCOVERY_MAX_REQUESTS

    def __init__(
        self,
        *,
        opener: Callable[[Request, float], Any] = _default_opener,
        timeout_seconds: float = FACET_DISCOVERY_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds != FACET_DISCOVERY_TIMEOUT_SECONDS:
            raise ValueError("El timeout de facet discovery es fijo")
        parsed = urlparse(FACET_DISCOVERY_ENDPOINT)
        if parsed.scheme != "https" or parsed.hostname != FACET_DISCOVERY_HOST:
            raise ValueError("Endpoint facet discovery no autorizado")
        if not callable(opener):
            raise ValueError("opener debe ser callable")
        self._opener = opener
        self._timeout_seconds = timeout_seconds
        self._requests_attempted = 0

    @property
    def requests_attempted(self) -> int:
        return self._requests_attempted

    def __call__(self, logical_request: FacetDiscoveryRequest) -> Mapping[str, Any]:
        if not isinstance(logical_request, FacetDiscoveryRequest):
            raise FacetDiscoveryTransportError("Solicitud lógica inválida")
        operation = _OPERATIONS.get(logical_request.name)
        if operation is None:
            raise FacetDiscoveryTransportError("Operación facet discovery no autorizada")
        if self._requests_attempted >= FACET_DISCOVERY_MAX_REQUESTS:
            raise FacetDiscoveryTransportError("Máximo de dos solicitudes excedido")
        self._requests_attempted += 1
        payload = self._execute(operation)
        if logical_request.name == "root_total":
            return self._normalize_root(payload)
        return self._normalize_tree(payload)

    def _execute(self, operation: FixedGraphQLOperation) -> Mapping[str, Any]:
        params = {
            "workspace": "master",
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "es-HN",
            "operationName": operation.name,
            "query": operation.query,
            "variables": json.dumps(_FIXED_VARIABLES, separators=(",", ":")),
        }
        url = f"{FACET_DISCOVERY_ENDPOINT}?{urlencode(params)}"
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != FACET_DISCOVERY_HOST:
            raise FacetDiscoveryTransportError("Destino HTTP no autorizado")
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": FACET_DISCOVERY_USER_AGENT,
            },
        )
        try:
            response = self._opener(request, self._timeout_seconds)
            raw = response.read()
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise FacetDiscoveryTransportError("Fallo HTTP sin reintento") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, AttributeError) as exc:
            raise FacetDiscoveryTransportError("Respuesta JSON inválida") from exc
        if not isinstance(decoded, Mapping):
            raise FacetDiscoveryTransportError("Respuesta GraphQL inválida")
        if decoded.get("errors"):
            raise FacetDiscoveryTransportError("GraphQL devolvió errores")
        data = decoded.get("data")
        if not isinstance(data, Mapping):
            raise FacetDiscoveryTransportError("GraphQL no devolvió data")
        return data

    @staticmethod
    def _normalize_root(data: Mapping[str, Any]) -> Mapping[str, Any]:
        product_search = data.get("productSearch")
        if not isinstance(product_search, Mapping):
            raise FacetDiscoveryTransportError("Falta productSearch raíz")
        value = product_search.get("recordsFiltered")
        if isinstance(value, bool):
            raise FacetDiscoveryTransportError("recordsFiltered raíz inválido")
        try:
            total = int(value)
        except (TypeError, ValueError) as exc:
            raise FacetDiscoveryTransportError("recordsFiltered raíz inválido") from exc
        if total <= 0:
            raise FacetDiscoveryTransportError("recordsFiltered raíz debe ser positivo")
        return {"recordsFiltered": total}

    @staticmethod
    def _normalize_tree(data: Mapping[str, Any]) -> Mapping[str, Any]:
        product_search = data.get("productSearch")
        facets = data.get("facets")
        if not isinstance(product_search, Mapping) or not isinstance(facets, Mapping):
            raise FacetDiscoveryTransportError("Falta respuesta de control o facets")
        value = product_search.get("recordsFiltered")
        if isinstance(value, bool):
            raise FacetDiscoveryTransportError("recordsFiltered de control inválido")
        try:
            total = int(value)
        except (TypeError, ValueError) as exc:
            raise FacetDiscoveryTransportError("recordsFiltered de control inválido") from exc
        if total <= 0:
            raise FacetDiscoveryTransportError("recordsFiltered de control debe ser positivo")
        return {
            "recordsFiltered": total,
            "sampling": facets.get("sampling"),
            "facets": facets.get("facets"),
        }
