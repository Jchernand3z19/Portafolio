from __future__ import annotations

import base64
import copy

import pytest

from precios_supermercados.edge_gateway_client import EdgeGatewayClient, EdgeGatewayClientError
from test_edge_gateway_client import FakeTransport, completed_response, execution


def test_signature_ed25519_debe_tener_64_bytes() -> None:
    request = execution()
    response = completed_response(request)
    short_signature = base64.urlsafe_b64encode(b"x" * 32).decode("ascii").rstrip("=")
    response["signatureB64Url"] = short_signature
    response["receiptPayload"]["signing_key_id"] = response["signingKeyId"]  # type: ignore[index]

    with pytest.raises(EdgeGatewayClientError) as captured:
        EdgeGatewayClient(FakeTransport([copy.deepcopy(response)])).execute(request, bearer_token="token")

    assert captured.value.code == "receipt_signature_length_invalid"
