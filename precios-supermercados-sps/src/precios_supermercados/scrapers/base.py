"""Infraestructura mínima y segura para extractores de supermercados."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from email.message import Message
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from precios_supermercados.models import RawProduct


class ScraperError(RuntimeError):
    """Error controlado durante una extracción."""


class RobotsPolicyError(ScraperError):
    """La URL solicitada está fuera de las rutas permitidas."""


class HttpStatusError(ScraperError):
    """La fuente respondió con un estado HTTP no aceptable."""

    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"HTTP {status_code} al consultar {url}")
        self.status_code = status_code
        self.url = url


class BlockedResponseError(HttpStatusError):
    """La fuente respondió con bloqueo, CAPTCHA o control equivalente."""


class RateLimitedError(HttpStatusError):
    """La fuente mantuvo una respuesta 429 después de los reintentos permitidos."""


class EmptyResponseError(ScraperError):
    """La respuesta válida no contiene productos para la muestra esperada."""


class StructureChangedError(ScraperError):
    """La respuesta ya no contiene la estructura esperada."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Respuesta HTTP pequeña, fácil de sustituir en pruebas offline."""

    status_code: int
    url: str
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Mapping[str, Any]:
        try:
            value = json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise StructureChangedError("La respuesta no es JSON válido") from exc
        if not isinstance(value, Mapping):
            raise StructureChangedError("La respuesta JSON no es un objeto")
        return value


@dataclass(slots=True)
class ExtractionMetrics:
    """Métricas mínimas exigidas para aceptar o rechazar una ejecución."""

    pages_discovered: int = 0
    pages_processed: int = 0
    page_coverage: float = 0.0
    products_discovered: int = 0
    products_extracted: int = 0
    products_with_price: int = 0
    products_pending_review: int = 0
    duplicate_products: int = 0
    errors: int = 0
    structural_events: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Resultado controlado sin persistencia ni historial."""

    products: tuple[RawProduct, ...]
    metrics: ExtractionMetrics
    quality_events: tuple[str, ...]
    accepted: bool
    source_url: str


Transport = Callable[[str, Mapping[str, str], float], HttpResponse]


class SafeHttpClient:
    """Cliente GET limitado a hosts y rutas expresamente permitidas."""

    _BLOCK_MARKERS = (
        "captcha",
        "cf-chl-",
        "access denied",
        "robot check",
        "unusual traffic",
    )

    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        forbidden_path_prefixes: tuple[str, ...],
        user_agent: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 1.5,
        transport: Transport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser mayor que cero")
        if max_retries < 0 or max_retries > 3:
            raise ValueError("max_retries debe estar entre 0 y 3")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds no puede ser negativo")
        self.allowed_hosts = {host.casefold() for host in allowed_hosts}
        self.forbidden_path_prefixes = tuple(
            prefix.casefold() for prefix in forbidden_path_prefixes
        )
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.transport = transport or self._urllib_transport
        self.sleeper = sleeper

    def validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise RobotsPolicyError("Solo se permiten URLs HTTPS")
        if parsed.hostname is None or parsed.hostname.casefold() not in self.allowed_hosts:
            raise RobotsPolicyError(f"Host no permitido: {parsed.hostname or '<vacío>'}")
        path = parsed.path.casefold() or "/"
        if any(path.startswith(prefix) for prefix in self.forbidden_path_prefixes):
            raise RobotsPolicyError(f"Ruta excluida por política: {parsed.path}")

    def get(self, url: str) -> HttpResponse:
        self.validate_url(url)
        headers = {
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": self.user_agent,
        }
        last_response: HttpResponse | None = None

        for attempt in range(self.max_retries + 1):
            if attempt:
                self.sleeper(self.retry_delay_seconds)
            try:
                response = self.transport(url, headers, self.timeout_seconds)
            except (TimeoutError, URLError) as exc:
                if attempt >= self.max_retries:
                    raise ScraperError(f"No fue posible consultar {url}: {exc}") from exc
                continue

            self.validate_url(response.url)
            last_response = response
            status = response.status_code

            if status == 403:
                raise BlockedResponseError(status, response.url)
            if status == 429:
                if attempt >= self.max_retries:
                    raise RateLimitedError(status, response.url)
                retry_after = _retry_after_seconds(response.headers)
                self.sleeper(min(retry_after, 30.0))
                continue
            if 500 <= status <= 599:
                if attempt >= self.max_retries:
                    raise HttpStatusError(status, response.url)
                continue
            if status >= 400:
                raise HttpStatusError(status, response.url)

            lowered = response.text.casefold()
            if any(marker in lowered for marker in self._BLOCK_MARKERS):
                raise BlockedResponseError(status, response.url)
            return response

        assert last_response is not None
        raise HttpStatusError(last_response.status_code, last_response.url)

    def get_json(self, url: str) -> Mapping[str, Any]:
        return self.get(url).json()

    @staticmethod
    def _urllib_transport(
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    status_code=int(response.status),
                    url=response.geturl(),
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except HTTPError as exc:
            headers_message: Message = exc.headers
            return HttpResponse(
                status_code=int(exc.code),
                url=exc.geturl(),
                headers=dict(headers_message.items()),
                body=exc.read(),
            )


def _retry_after_seconds(headers: Mapping[str, str]) -> float:
    raw_value = next(
        (value for key, value in headers.items() if key.casefold() == "retry-after"),
        None,
    )
    if raw_value is None:
        return 1.0
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return 1.0
