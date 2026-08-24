from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "precios-supermercados-sps/scripts/ejecutar_facets_context_bound_la_colonia.py"


def _module():
    spec = importlib.util.spec_from_file_location("facet_oidc_stream_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = False

    def iter_content(self, *, chunk_size: int):
        assert chunk_size == 16 * 1024
        assert self.closed is False
        self.events.append("response-read")
        yield json.dumps({"value": "oidc-token"}).encode("utf-8")

    def close(self) -> None:
        self.closed = True
        self.events.append("response-close")


class _Session:
    def __init__(self, response: _Response, events: list[str]) -> None:
        self.response = response
        self.events = events
        self.closed = False

    def get(self, *_args, **kwargs):
        assert kwargs["stream"] is True
        assert kwargs["allow_redirects"] is False
        assert self.closed is False
        self.events.append("session-get")
        return self.response

    def close(self) -> None:
        self.closed = True
        self.events.append("session-close")


def test_oidc_stream_se_consume_antes_de_cerrar_response_y_session(monkeypatch) -> None:
    module = _module()
    events: list[str] = []
    response = _Response(events)
    session = _Session(response, events)
    monkeypatch.setattr(module.requests, "Session", lambda: session)
    monkeypatch.setenv(
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "https://token.actions.githubusercontent.com/oidc?foo=bar",
    )
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")

    assert module._request_oidc_token() == "oidc-token"
    assert events == [
        "session-get",
        "response-read",
        "response-close",
        "session-close",
    ]
    assert response.closed is True
    assert session.closed is True
