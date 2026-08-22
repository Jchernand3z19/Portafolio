"""Infraestructura mínima y segura para extractores de supermercados."""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping
from urllib.error import URLError
from urllib.parse import urlsplit

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


class ExternalNetworkDeniedError(ScraperError):
    """El transporte real permanece cerrado salvo una ruta explícitamente autorizada."""


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
    """Métricas separadas de páginas, productos y SKU."""

    pages_discovered: int = 0
    pages_processed: int = 0
    page_coverage: float = 0.0
    products_discovered: int = 0
    products_requested: int = 0
    products_returned: int = 0
    skus_returned: int = 0
    skus_extracted: int = 0
    duplicate_skus: int = 0
    skus_with_price: int = 0
    skus_pending_review: int = 0
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


@dataclass(frozen=True, slots=True)
class OfflineTestTransport:
    """Harness explícito sin autoridad; sólo se admite en pruebas offline."""

    handler: Transport

    def __post_init__(self) -> None:
        if not callable(self.handler):
            raise ValueError("handler debe ser callable")
        module = getattr(self.handler, "__module__", self.handler.__class__.__module__)
        if not str(module).split(".")[-1].startswith("test_"):
            raise ValueError("OfflineTestTransport sólo admite handlers de módulos test_*")

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        return self.handler(url, headers, timeout)


class SafeHttpClient:
    """Cliente GET limitado a hosts y rutas expresamente permitidas."""

    _BLOCK_MARKERS = (
        "captcha",
        "cf-chl-",
        "access denied",
        "robot check",
        "unusual traffic",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("SafeHttpClient es inmutable después de inicializar")
        object.__setattr__(self, name, value)

    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        forbidden_path_prefixes: tuple[str, ...],
        user_agent: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 0,
        retry_delay_seconds: float = 1.5,
        transport: OfflineTestTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds debe ser mayor que cero")
        if isinstance(max_retries, bool) or type(max_retries) is not int or max_retries != 0:
            raise ValueError("max_retries debe ser 0")
        if (
            isinstance(retry_delay_seconds, bool)
            or not isinstance(retry_delay_seconds, (int, float))
            or not math.isfinite(float(retry_delay_seconds))
            or retry_delay_seconds < 0
        ):
            raise ValueError("retry_delay_seconds no puede ser negativo")
        if transport is not None and type(transport) is not OfflineTestTransport:
            raise ValueError("transport requiere OfflineTestTransport explícito")
        self.allowed_hosts = frozenset(host.casefold() for host in allowed_hosts)
        self.forbidden_path_prefixes = tuple(
            prefix.casefold() for prefix in forbidden_path_prefixes
        )
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._transport = transport
        self._sleeper = sleeper
        self._last_request_monotonic: float | None = None
        self._sealed = True

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise RobotsPolicyError("Solo se permite HTTPS")
        host = (parsed.hostname or "").casefold()
        if host not in self.allowed_hosts:
            raise RobotsPolicyError(f"Host no permitido: {host}")
        path = parsed.path.casefold()
        if any(path.startswith(prefix) for prefix in self.forbidden_path_prefixes):
            raise RobotsPolicyError(f"Ruta no permitida: {parsed.path}")

    def _default_transport(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        del url, headers, timeout
        raise ExternalNetworkDeniedError(
            "El transporte externo está denegado por defecto; use una ruta live explícitamente autorizada"
        )

    def _pace(self) -> None:
        if self._last_request_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        wait = self.retry_delay_seconds - elapsed
        if wait > 0:
            self._sleeper(wait)

    def get(self, url: str, headers: Mapping[str, str] | None = None) -> HttpResponse:
        self._validate_url(url)
        request_headers = dict(headers or {})
        transport = self._transport or self._default_transport
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self._sleeper(self.retry_delay_seconds)
            self._pace()
            try:
                response = transport(url, request_headers, self.timeout_seconds)
                self._last_request_monotonic = time.monotonic()
            except (URLError, TimeoutError) as exc:
                last_error = exc
                continue

            if response.status_code == 429:
                last_error = RateLimitedError(response.status_code, url)
                continue
            if response.status_code in {401, 403}:
                raise BlockedResponseError(response.status_code, url)
            if not 200 <= response.status_code < 300:
                raise HttpStatusError(response.status_code, url)
            lowered = response.text.casefold()
            if any(marker in lowered for marker in self._BLOCK_MARKERS):
                raise BlockedResponseError(response.status_code, url)
            return response

        if last_error:
            raise last_error
        raise ScraperError("No fue posible completar la solicitud")
