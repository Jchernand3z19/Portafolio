from __future__ import annotations

import pytest

from precios_supermercados.edge_gateway_client import (
    EdgeExecutionRequest,
    EdgeGatewayClient,
    EdgeGatewayClientError,
)
from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url
from test_edge_gateway_client import FakeTransport, completed_response, context, execution


def test_digest_del_contexto_debe_coincidir_con_calculo_python_independiente() -> None:
    origin_url = build_product_search_url(
        page=1,
        page_size=50,
        order_by="OrderByNameASC",
    )
    with pytest.raises(EdgeGatewayClientError) as captured:
        EdgeExecutionRequest(
            origin_url=origin_url,
            context=context(request_digest="f" * 64),
        )
    assert captured.value.code == "request_digest_origin_mismatch"


def test_url_no_builder_canonico_falla_antes_de_transportar() -> None:
    origin_url = build_product_search_url(
        page=1,
        page_size=50,
        order_by="OrderByNameASC",
    )
    with pytest.raises(EdgeGatewayClientError) as captured:
        EdgeExecutionRequest(
            origin_url=f"{origin_url}&debug=1",
            context=context(),
        )
    assert captured.value.code == "origin_request_origin_query_parameter_order_or_set_invalid"


def test_receipt_no_puede_cambiar_rango_aunque_recalcule_evidence_id() -> None:
    request = execution()
    response = completed_response(request, from_index=1, to_index=50)
    client = EdgeGatewayClient(FakeTransport([response]))
    with pytest.raises(EdgeGatewayClientError) as captured:
        client.execute(request, bearer_token="token")
    assert captured.value.code == "receipt_range_independent_mismatch"


def test_receipt_no_puede_cambiar_order_by_aunque_recalcule_evidence_id() -> None:
    request = execution()
    response = completed_response(request, order_by="OrderByPriceDESC")
    client = EdgeGatewayClient(FakeTransport([response]))
    with pytest.raises(EdgeGatewayClientError) as captured:
        client.execute(request, bearer_token="token")
    assert captured.value.code == "receipt_order_by_independent_mismatch"
