"""Consulta GraphQL pública y mínima utilizada por el extractor de La Colonia."""

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.parse import urlencode

GRAPHQL_ENDPOINT = "https://www.lacolonia.com/_v/segment/graphql/v1"

# Basada en QueryProductSearchV3 de vtex.store-resources. Se solicitan solo
# los campos necesarios para la prueba controlada y se aliasa el nombre
# histórico `commertialOffer` al nombre correcto usado internamente.
PRODUCT_SEARCH_QUERY = """
query productSearchV3(
  $query: String
  $fullText: String
  $selectedFacets: [SelectedFacetInput]
  $orderBy: String
  $from: Int
  $to: Int
  $hideUnavailableItems: Boolean
  $skusFilter: ItemsFilter = ALL_AVAILABLE
) {
  productSearch(
    query: $query
    fullText: $fullText
    selectedFacets: $selectedFacets
    orderBy: $orderBy
    from: $from
    to: $to
    hideUnavailableItems: $hideUnavailableItems
  ) @context(provider: "vtex.search-graphql") {
    recordsFiltered
    products {
      productId
      productName
      productReference
      linkText
      brand
      categories
      items(filter: $skusFilter) {
        itemId
        name
        nameComplete
        ean
        referenceId {
          Key
          Value
        }
        measurementUnit
        unitMultiplier
        images {
          imageUrl
        }
        sellers {
          sellerId
          sellerDefault
          commercialOffer: commertialOffer {
            Price
            ListPrice
            AvailableQuantity
            discountHighlights {
              name
            }
            teasers {
              name
            }
          }
        }
      }
    }
  }
}
""".strip()


def build_product_search_url(
    *,
    page: int = 1,
    page_size: int = 5,
    query: str = "supermercado",
    category_map: str = "category-1",
) -> str:
    """Construye una consulta GET pública limitada a una sola página."""

    if page < 1:
        raise ValueError("page debe ser mayor o igual que 1")
    if not 1 <= page_size <= 5:
        raise ValueError("La prueba controlada admite entre 1 y 5 productos")
    if not query.strip() or not category_map.strip():
        raise ValueError("query y category_map no pueden estar vacíos")

    from_index = (page - 1) * page_size
    variables: Mapping[str, Any] = {
        "query": query,
        "fullText": "",
        "selectedFacets": [{"key": category_map, "value": query}],
        "orderBy": "OrderByReleaseDateDESC",
        "from": from_index,
        "to": from_index + page_size - 1,
        "hideUnavailableItems": False,
        "skusFilter": "ALL_AVAILABLE",
    }
    params = {
        "workspace": "master",
        "maxAge": "short",
        "appsEtag": "remove",
        "domain": "store",
        "locale": "es-HN",
        "operationName": "productSearchV3",
        "query": PRODUCT_SEARCH_QUERY,
        "variables": json.dumps(variables, separators=(",", ":")),
    }
    return f"{GRAPHQL_ENDPOINT}?{urlencode(params)}"
