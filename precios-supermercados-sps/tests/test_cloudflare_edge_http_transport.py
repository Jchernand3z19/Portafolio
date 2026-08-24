from __future__ import annotations

import json

import pytest

from precios_supermercados.cloudflare_edge_http_transport import (
    CloudflareEdgeHttpTransport,
    CloudflareEdgeHttpTransportError,
)


class _Response:
    def __init__(self, body: bytes = b'{"ok":true}', *, status: int = 200, headers=None):
        self.status_code = status
        self.headers = headers or {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size: int):
        assert chunk_size == 64 * 1024
        yield self._body

    def close(self):
        self.closed = True


class _Session:
    def __init__(self, response: _Response | None = None):
        self.response = response or _Response()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_acepta_solo_origen_workers_dev_y_post_json_acotado() -> None:
    session = _Session()
    transport = CloudflareEdgeHttpTransport(
        "https://precios-sps.example.workers.dev/",
        session=session,
    )

    result = transport.post_json(
        "/v1/initialize",
        bearer_token="token-opaque",
        payload={"authorization": {"maxRequests": 2}},
    )

    assert result == {"ok": True}
    assert transport.gateway_origin == "https://precios-sps.example.workers.dev"
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == "https://precios-sps.example.workers.dev/v1/initialize"
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert kwargs["timeout"] == (10.0, 60.0)
    assert kwargs["headers"]["Authorization"] == "Bearer token-opaque"
    assert json.loads(kwargs["data"]) == {"authorization": {"maxRequests": 2}}


@pytest.mark.parametrize(
    "value",
    [
        "http://edge.workers.dev",
        "https://workers.dev",
        "https://edge.workers.dev/path",
        "https://edge.workers.dev?x=1",
        "https://edge.workers.dev#fragment",
        "https://user:pass@edge.workers.dev",
        "https://edge.workers.dev:443",
        "https://www.lacolonia.com",
    ],
)
def test_rechaza_destinos_que_no_sean_origen_workers_dev(value: str) -> None:
    with pytest.raises(CloudflareEdgeHttpTransportError) as captured:
        CloudflareEdgeHttpTransport(value, session=_Session())
    assert captured.value.code == "edge_gateway_origin_invalid"


def test_no_permite_path_arbitrario() -> None:
    transport = CloudflareEdgeHttpTransport(
        "https://edge.workers.dev",
        session=_Session(),
    )
    with pytest.raises(CloudflareEdgeHttpTransportError) as captured:
        transport.post_json(
            "/anything",
            bearer_token="token",
            payload={},
        )
    assert captured.value.code == "edge_gateway_path_forbidden"


def test_rechaza_redirect_y_cierra_respuesta() -> None:
    response = _Response(status=302, headers={"Content-Type": "application/json", "Location": "https://evil.invalid"})
    transport = CloudflareEdgeHttpTransport(
        "https://edge.workers.dev",
        session=_Session(response),
    )
    with pytest.raises(CloudflareEdgeHttpTransportError) as captured:
        transport.post_json("/v1/initialize", bearer_token="token", payload={})
    assert captured.value.code == "edge_gateway_redirect_forbidden"
    assert response.closed is True


def test_rechaza_respuesta_sobre_limite_antes_de_parsear() -> None:
    response = _Response(
        b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": "5000001",
        },
    )
    transport = CloudflareEdgeHttpTransport(
        "https://edge.workers.dev",
        session=_Session(response),
        max_response_bytes=3_000_000,
    )
    with pytest.raises(CloudflareEdgeHttpTransportError) as captured:
        transport.post_json("/v1/initialize", bearer_token="token", payload={})
    assert captured.value.code == "edge_gateway_response_above_limit"
    assert response.closed is True


def test_repr_de_error_no_expone_bearer() -> None:
    response = _Response(status=500)
    transport = CloudflareEdgeHttpTransport(
        "https://edge.workers.dev",
        session=_Session(response),
    )
    secret = "super-secret-bearer-token"
    with pytest.raises(CloudflareEdgeHttpTransportError) as captured:
        transport.post_json("/v1/initialize", bearer_token=secret, payload={})
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)
