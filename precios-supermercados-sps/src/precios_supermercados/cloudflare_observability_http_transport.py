"""Transporte HTTPS mínimo para la API de Workers Observability.

El host es fijo, sólo se admite el endpoint de telemetry/query, no hay retries ni
redirects y la respuesta está acotada. El token se recibe por llamada y nunca se
persiste. Este adapter no concede autoridad; sólo satisface los Protocol de los
verificadores de Observability.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

CLOUDFLARE_API_ORIGIN = "https://api.cloudflare.com"
CLOUDFLARE_API_PREFIX = "/client/v4"
MAX_OBSERVABILITY_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20.0

_QUERY_PATH = re.compile(
    r"/accounts/[0-9a-f]{32}/workers/observability/telemetry/query\Z"
)


class CloudflareObservabilityHttpError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise CloudflareObservabilityHttpError(code, message)


def _bearer(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 20_000
        or any(character.isspace() for character in value)
    ):
        _fail("cloudflare_observability_bearer_invalid")
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        del req, fp, code, msg, headers, newurl
        return None


class CloudflareObservabilityHttpTransport:
    """POST JSON únicamente contra el endpoint oficial fijo de Cloudflare."""

    def __init__(self, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, opener=None) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            _fail("cloudflare_observability_timeout_invalid")
        timeout = float(timeout_seconds)
        if not 0 < timeout <= 60:
            _fail("cloudflare_observability_timeout_invalid")
        self._timeout = timeout
        self._opener = opener or build_opener(_NoRedirect())

    def post_json(
        self,
        path: str,
        *,
        bearer_token: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        if not isinstance(path, str) or not _QUERY_PATH.fullmatch(path):
            _fail("cloudflare_observability_path_forbidden")
        if not isinstance(payload, Mapping) or any(not isinstance(key, str) for key in payload):
            _fail("cloudflare_observability_payload_invalid")
        token = _bearer(bearer_token)
        try:
            body = json.dumps(
                dict(payload),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CloudflareObservabilityHttpError("cloudflare_observability_payload_invalid") from exc
        if len(body) > 512 * 1024:
            _fail("cloudflare_observability_payload_too_large")

        url = CLOUDFLARE_API_ORIGIN + CLOUDFLARE_API_PREFIX + path
        request = Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "precios-sps-observability-verifier/1",
            },
            method="POST",
        )
        try:
            response = self._opener.open(request, timeout=self._timeout)
        except HTTPError as exc:
            if 300 <= exc.code <= 399:
                raise CloudflareObservabilityHttpError("cloudflare_observability_redirect_rejected") from exc
            raise CloudflareObservabilityHttpError(
                f"cloudflare_observability_http_{exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CloudflareObservabilityHttpError("cloudflare_observability_network_error") from exc

        try:
            status = getattr(response, "status", None)
            if status != 200:
                _fail("cloudflare_observability_http_status_invalid")
            final_url = response.geturl()
            if final_url != url:
                _fail("cloudflare_observability_response_url_mismatch")
            content_type = response.headers.get("Content-Type", "")
            if not isinstance(content_type, str) or "application/json" not in content_type.lower():
                _fail("cloudflare_observability_content_type_invalid")
            raw = response.read(MAX_OBSERVABILITY_RESPONSE_BYTES + 1)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        if len(raw) > MAX_OBSERVABILITY_RESPONSE_BYTES:
            _fail("cloudflare_observability_response_too_large")
        try:
            decoded = json.loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudflareObservabilityHttpError("cloudflare_observability_json_invalid") from exc
        if not isinstance(decoded, Mapping):
            _fail("cloudflare_observability_json_shape_invalid")
        return decoded
