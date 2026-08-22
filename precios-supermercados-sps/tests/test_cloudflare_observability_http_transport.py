from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from precios_supermercados.cloudflare_observability_http_transport import (
    CloudflareObservabilityHttpError,
    CloudflareObservabilityHttpTransport,
)

ACCOUNT = "a" * 32
PATH = f"/accounts/{ACCOUNT}/workers/observability/telemetry/query"
URL = f"https://api.cloudflare.com/client/v4{PATH}"


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, url: str = URL, content_type: str = "application/json"):
        self._body = io.BytesIO(body)
        self.status = status
        self._url = url
        self.headers = {"Content-Type": content_type}
        self.closed = False

    def read(self, amount: int) -> bytes:
        return self._body.read(amount)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        self.closed = True


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def test_transport_fija_host_metodo_headers_y_path() -> None:
    response = FakeResponse(json.dumps({"success": True, "result": {}}).encode())
    opener = FakeOpener(response=response)
    transport = CloudflareObservabilityHttpTransport(opener=opener)

    result = transport.post_json(PATH, bearer_token="token-test", payload={"queryId": "q1"})

    assert result["success"] is True
    request, timeout = opener.calls[0]
    assert request.full_url == URL
    assert request.method == "POST"
    assert request.get_header("Authorization") == "Bearer token-test"
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data) == {"queryId": "q1"}
    assert timeout == 20.0
    assert response.closed is True


def test_transport_rechaza_paths_arbitrarios_antes_de_red() -> None:
    opener = FakeOpener(response=FakeResponse(b"{}"))
    transport = CloudflareObservabilityHttpTransport(opener=opener)
    for path in (
        "/accounts/" + ACCOUNT + "/workers/scripts",
        "https://www.lacolonia.com/",
        "/accounts/not-an-id/workers/observability/telemetry/query",
        PATH + "/extra",
    ):
        with pytest.raises(CloudflareObservabilityHttpError) as exc:
            transport.post_json(path, bearer_token="token-test", payload={"queryId": "q1"})
        assert exc.value.code == "cloudflare_observability_path_forbidden"
    assert opener.calls == []


def test_transport_rechaza_redirect_y_no_lo_sigue() -> None:
    error = HTTPError(URL, 302, "Found", {"Location": "https://example.com/"}, None)
    transport = CloudflareObservabilityHttpTransport(opener=FakeOpener(error=error))
    with pytest.raises(CloudflareObservabilityHttpError) as exc:
        transport.post_json(PATH, bearer_token="token-test", payload={"queryId": "q1"})
    assert exc.value.code == "cloudflare_observability_redirect_rejected"


def test_transport_rechaza_url_final_content_type_y_json_invalidos() -> None:
    cases = (
        (FakeResponse(b"{}", url="https://example.com/"), "cloudflare_observability_response_url_mismatch"),
        (FakeResponse(b"{}", content_type="text/html"), "cloudflare_observability_content_type_invalid"),
        (FakeResponse(b"not-json"), "cloudflare_observability_json_invalid"),
    )
    for response, code in cases:
        transport = CloudflareObservabilityHttpTransport(opener=FakeOpener(response=response))
        with pytest.raises(CloudflareObservabilityHttpError) as exc:
            transport.post_json(PATH, bearer_token="token-test", payload={"queryId": "q1"})
        assert exc.value.code == code


def test_transport_rechaza_token_con_espacios_y_timeout_inseguro() -> None:
    opener = FakeOpener(response=FakeResponse(b"{}"))
    transport = CloudflareObservabilityHttpTransport(opener=opener)
    with pytest.raises(CloudflareObservabilityHttpError) as exc:
        transport.post_json(PATH, bearer_token="bad token", payload={"queryId": "q1"})
    assert exc.value.code == "cloudflare_observability_bearer_invalid"
    assert opener.calls == []

    for timeout in (0, -1, 61, True):
        with pytest.raises(CloudflareObservabilityHttpError):
            CloudflareObservabilityHttpTransport(timeout_seconds=timeout)
