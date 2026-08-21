from __future__ import annotations

from precios_supermercados.edge_gateway_client import EdgeGatewayClient, EdgeGatewayEvidence
from test_edge_gateway_client import FakeTransport, completed_response, execution


def test_evidence_structural_no_se_convierte_en_autoridad_productiva() -> None:
    request = execution()
    result = EdgeGatewayClient(FakeTransport([completed_response(request)])).execute(
        request,
        bearer_token="token",
    )
    assert isinstance(result, EdgeGatewayEvidence)
    assert result.cryptographic_signature_verified is False
    assert result.production_authority is False
