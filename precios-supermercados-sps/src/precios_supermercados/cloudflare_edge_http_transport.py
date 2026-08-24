"""Transporte HTTP productivo y fail-closed para el gateway edge de Cloudflare.

El origen se configura externamente y debe ser exclusivamente un origen HTTPS
``*.workers.dev`` sin path, query, fragmento, credenciales ni puerto explícito.
Cada llamada POST usa un path permitido por los clientes edge, cero reintentos,
redirecciones deshabilitadas y lectura acotada de la respuesta.

El bearer token nunca se incluye en excepciones ni representaciones públicas.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, NoReturn
from urllib.parse import urlsplit

import requests

_ALLOWED_PATHS = frozenset(
    {
        "/v1/initialize",
        "/v1/execute",
        "/v1/structural-execute",
        "/v1/catalog-execute",
    }
)
_DEFAULT_MAX_RESPONSE_BYTES = 3_000_000


class CloudflareEdgeHttpTransportError(RuntimeError):
    """El transporte no puede demostrar una llamada edge segura."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CloudflareEdgeHttpTransportError(code, message)


def _origin(value: object) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > 2048:
        _fail("edge_gateway_origin_invalid")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise CloudflareEdgeHttpTransportError("edge_gateway_origin_invalid") from exc
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or not host.endswith(".workers.dev")
        or host == "workers.dev"
        or host == "www.lacolonia.com"
        or host.endswith(".lacolonia.com")
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        _fail("edge_gateway_origin_invalid")
    return f"https://{host}"


def _bearer(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 20_000
        or any(character.isspace() for character in value)
    ):
        _fail("edge_gateway_bearer_invalid")
    return value


class CloudflareEdgeHttpTransport:
    """POST JSON acotado; no implementa retries ni sigue redirects."""

    def __init__(
        self,
        gateway_origin: str,
        *,
        session: requests.Session | Any | None = None,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 60.0,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        self._origin = _origin(gateway_origin)
        if (
            isinstance(connect_timeout_seconds, bool)
            or not isinstance(connect_timeout_seconds, (int, float))
            or not 0 < float(connect_timeout_seconds) <= 30
            or isinstance(read_timeout_seconds, bool)
            or not isinstance(read_timeout_seconds, (int, float))
            or not 0 < float(read_timeout_seconds) <= 120
        ):
            _fail("edge_gateway_timeout_invalid")
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or not 1024 <= max_response_bytes <= 5_000_000
        ):
            _fail("edge_gateway_response_limit_invalid")
        self._connect_timeout = float(connect_timeout_seconds)
        self._read_timeout = float(read_timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._session = session or requests.Session()

    @property
    def gateway_origin(self) -> str:
        return self._origin

    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        if path not in _ALLOWED_PATHS:
            _fail("edge_gateway_path_forbidden")
        token = _bearer(bearer_token)
        if not isinstance(payload, Mapping):
            _fail("edge_gateway_payload_invalid")
        try:
            encoded = json.dumps(
                dict(payload),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CloudflareEdgeHttpTransportError("edge_gateway_payload_invalid") from exc
        if not encoded or len(encoded) > 1_000_000:
            _fail("edge_gateway_payload_size_invalid")

        url = f"{self._origin}{path}"
        try:
            response = self._session.post(
                url,
                data=encoded,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=(self._connect_timeout, self._read_timeout),
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise CloudflareEdgeHttpTransportError("edge_gateway_transport_failed") from exc
        except Exception as exc:
            raise CloudflareEdgeHttpTransportError("edge_gateway_transport_failed") from exc

        try:
            status = int(response.status_code)
            if 300 <= status <= 399 or response.headers.get("Location"):
                _fail("edge_gateway_redirect_forbidden")
            if status != 200:
                _fail("edge_gateway_http_status_invalid")
            content_type = str(response.headers.get("Content-Type", "")).casefold()
            if "application/json" not in content_type:
                _fail("edge_gateway_content_type_invalid")
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_bytes = int(declared)
                except (TypeError, ValueError) as exc:
                    raise CloudflareEdgeHttpTransportError(
                        "edge_gateway_content_length_invalid"
                    ) from exc
                if declared_bytes < 0 or declared_bytes > self._max_response_bytes:
                    _fail("edge_gateway_response_above_limit")

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not isinstance(chunk, bytes):
                    _fail("edge_gateway_response_chunk_invalid")
                if not chunk:
                    continue
                total += len(chunk)
                if total > self._max_response_bytes:
                    _fail("edge_gateway_response_above_limit")
                chunks.append(chunk)
            if total == 0:
                _fail("edge_gateway_response_empty")
            try:
                value = json.loads(b"".join(chunks).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CloudflareEdgeHttpTransportError(
                    "edge_gateway_response_json_invalid"
                ) from exc
            if not isinstance(value, Mapping):
                _fail("edge_gateway_response_shape_invalid")
            return dict(value)
        finally:
            try:
                response.close()
            except Exception:
                pass
