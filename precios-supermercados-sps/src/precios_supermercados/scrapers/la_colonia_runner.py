"""Orquestación segura y validación global del catálogo público de La Colonia.

Este módulo no persiste productos ni implementa historial. Mantiene el catálogo en
memoria y delega el parsing de cada página al ``LaColoniaExtractor`` existente.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from precios_supermercados.models import RawProduct

from .base import (
    BlockedResponseError,
    EmptyResponseError,
    HttpStatusError,
    RateLimitedError,
    ScraperError,
    StructureChangedError,
)
from .la_colonia import LaColoniaExtractor, decode_search_variables
from .la_colonia_graphql import (
    ALLOWED_ORDER_BY,
    MAX_CATALOG_PAGE_SIZE,
    build_product_search_url,
)


class AcceptanceProfile(str, Enum):
    """Etapa usada para evaluar anomalías observacionales."""

    BASELINE = "baseline"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True)
class CrawlConfig:
    """Configuración conservadora de un recorrido secuencial."""

    page_size: int = 10
    max_pages: int | None = 2
    max_products: int | None = None
    delay_seconds: float = 1.5
    max_retries: int = 2
    stop_on_error: bool = True
    order_by: str = "OrderByNameASC"
    max_duration_seconds: float = 1_800.0

    def __post_init__(self) -> None:
        if not 1 <= self.page_size <= MAX_CATALOG_PAGE_SIZE:
            raise ValueError(
                f"page_size debe estar entre 1 y {MAX_CATALOG_PAGE_SIZE}"
            )
        if self.max_pages is not None and self.max_pages <= 0:
            raise ValueError("max_pages debe ser mayor que cero")
        if self.max_products is not None:
            if self.max_products <= 0:
                raise ValueError("max_products debe ser mayor que cero")
            if self.max_products % self.page_size != 0:
                raise ValueError(
                    "max_products debe ser múltiplo de page_size para conservar "
                    "un tamaño de página constante"
                )
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds no puede ser negativo")
        if not 0 <= self.max_retries <= 3:
            raise ValueError("max_retries debe estar entre 0 y 3")
        if self.order_by not in ALLOWED_ORDER_BY:
            raise ValueError(f"order_by no permitido: {self.order_by}")
        if self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds debe ser mayor que cero")


@dataclass(frozen=True, slots=True)
class AcceptanceThresholds:
    """Umbrales observacionales; no se activan automáticamente."""

    max_missing_price_ratio: float | None = None
    max_duplicate_sku_ratio: float | None = None
    max_duplicate_product_ratio: float | None = None
    max_total_change_ratio: float | None = None

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} debe estar entre 0 y 1")

    @property
    def complete(self) -> bool:
        return all(value is not None for value in asdict(self).values())


@dataclass(frozen=True, slots=True)
class PageSummary:
    """Resumen no comercial de una página solicitada."""

    page: int
    from_index: int
    to_index: int
    order_by: str
    total_reported: int
    products_expected: int
    products_returned: int
    skus_returned: int
    skus_extracted: int
    response_bytes: int
    duration_seconds: float
    accepted: bool
    signature: str
    quality_events: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["quality_events"] = list(self.quality_events)
        return value


@dataclass(slots=True)
class CatalogRunMetrics:
    """Métricas globales separadas de páginas, productos y SKU."""

    run_id: str
    started_at_utc: str
    finished_at_utc: str | None = None
    duration_seconds: float = 0.0
    page_size: int = 0
    order_by: str = ""
    products_reported_initial: int = 0
    products_reported_final: int = 0
    catalog_pages_reported: int = 0
    pages_expected: int = 0
    pages_attempted: int = 0
    pages_completed: int = 0
    page_coverage: float = 0.0
    products_returned: int = 0
    products_processed: int = 0
    skus_returned: int = 0
    skus_extracted: int = 0
    skus_with_price: int = 0
    skus_without_price: int = 0
    skus_pending_review: int = 0
    weighted_skus: int = 0
    promotional_skus: int = 0
    duplicate_skus: int = 0
    duplicate_products: int = 0
    errors: int = 0
    structural_events: int = 0
    http_403: int = 0
    http_429: int = 0
    persistent_http_429: int = 0
    http_5xx: int = 0
    retries: int = 0
    response_bytes: int = 0
    average_response_seconds: float = 0.0
    average_response_bytes: float = 0.0
    delay_seconds_applied: float = 0.0
    total_change_absolute: int = 0
    total_change_ratio: float = 0.0
    missing_price_ratio: float = 0.0
    duplicate_sku_ratio: float = 0.0
    duplicate_product_ratio: float = 0.0
    accepted: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality_events: list[str] = field(default_factory=list)
    proposed_thresholds: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CatalogRunResult:
    """Resultado en memoria de un recorrido controlado."""

    products: tuple[RawProduct, ...]
    pages: tuple[PageSummary, ...]
    metrics: CatalogRunMetrics

    def sanitized_summary(self) -> dict[str, Any]:
        """Devuelve métricas y hashes limitados, nunca el catálogo completo."""

        sample_hashes = [
            hashlib.sha256(
                f"{product.source_key_type.value}:{product.source_key}".encode("utf-8")
            ).hexdigest()[:16]
            for product in self.products[:5]
        ]
        return {
            "metrics": self.metrics.as_dict(),
            "pages": [page.as_dict() for page in self.pages],
            "sample_source_key_hashes": sample_hashes,
        }


class LaColoniaCatalogRunner:
    """Recorre páginas consecutivas con concurrencia fija de una solicitud."""

    concurrency = 1

    def __init__(
        self,
        extractor: LaColoniaExtractor | None = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.extractor = extractor or LaColoniaExtractor()
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def run(
        self,
        config: CrawlConfig,
        *,
        run_id: str | None = None,
        profile: AcceptanceProfile = AcceptanceProfile.BASELINE,
        thresholds: AcceptanceThresholds | None = None,
    ) -> CatalogRunResult:
        """Ejecuta un recorrido secuencial y detiene la primera página crítica."""

        started_at = _utc(self.clock())
        run_id = run_id or started_at.strftime("la_colonia_%Y%m%dT%H%M%SZ")
        metrics = CatalogRunMetrics(
            run_id=run_id,
            started_at_utc=started_at.isoformat(),
            page_size=config.page_size,
            order_by=config.order_by,
        )
        thresholds = thresholds or AcceptanceThresholds()
        pages: list[PageSummary] = []
        accumulated: list[RawProduct] = []
        seen_skus: set[tuple[str, str]] = set()
        seen_products: set[str] = set()
        seen_page_signatures: set[str] = set()
        previous_to: int | None = None
        expected_order_by: str | None = None
        total_duration = 0.0
        run_started_monotonic = self.monotonic()

        client = self.extractor.client
        original_transport = getattr(client, "transport", None)
        original_max_retries = getattr(client, "max_retries", None)
        attempts_total = 0
        transport_instrumented = callable(original_transport)

        if transport_instrumented:

            def observed_transport(url: str, headers: Mapping[str, str], timeout: float):
                nonlocal attempts_total
                attempts_total += 1
                response = original_transport(url, headers, timeout)
                if response.status_code == 403:
                    metrics.http_403 += 1
                elif response.status_code == 429:
                    metrics.http_429 += 1
                elif 500 <= response.status_code <= 599:
                    metrics.http_5xx += 1
                return response

            client.transport = observed_transport
        if original_max_retries is not None:
            client.max_retries = config.max_retries

        try:
            page = 1
            while metrics.pages_expected == 0 or page <= metrics.pages_expected:
                if self.monotonic() - run_started_monotonic > config.max_duration_seconds:
                    self._critical(
                        metrics,
                        "maximum_duration_exceeded",
                        structural=False,
                    )
                    break

                metrics.pages_attempted += 1
                source_url = build_product_search_url(
                    page=page,
                    page_size=config.page_size,
                    order_by=config.order_by,
                )
                try:
                    variables = decode_search_variables(source_url)
                    from_index = int(variables["from"])
                    to_index = int(variables["to"])
                    order_by = str(variables["orderBy"])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self._critical(metrics, "invalid_pagination_variables", structural=True)
                    break

                continuity_error = _continuity_error(
                    page=page,
                    from_index=from_index,
                    to_index=to_index,
                    page_size=config.page_size,
                    previous_to=previous_to,
                    order_by=order_by,
                    expected_order_by=expected_order_by,
                )
                if continuity_error:
                    self._critical(metrics, continuity_error, structural=True)
                    break

                page_attempts_before = attempts_total
                page_started = self.monotonic()
                try:
                    response = client.get(source_url)
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    response_bytes = len(response.body)
                    metrics.response_bytes += response_bytes
                    payload = response.json()
                    raw_products, total_reported = _read_raw_page(payload)
                    result = self.extractor.parse_payload(
                        payload,
                        scrape_run_id=run_id,
                        source_url=source_url,
                        page_size=config.page_size,
                    )
                except BlockedResponseError as exc:
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    if not transport_instrumented and exc.status_code == 403:
                        metrics.http_403 += 1
                    self._critical(metrics, "http_403_or_captcha", structural=False)
                    break
                except RateLimitedError:
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    if not transport_instrumented:
                        metrics.http_429 += 1
                    metrics.persistent_http_429 += 1
                    self._critical(metrics, "persistent_http_429", structural=False)
                    break
                except HttpStatusError as exc:
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    if not transport_instrumented and 500 <= exc.status_code <= 599:
                        metrics.http_5xx += 1
                    self._critical(metrics, f"http_status_{exc.status_code}", structural=False)
                    break
                except EmptyResponseError:
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    self._critical(metrics, "unexpected_empty_page", structural=True)
                    break
                except StructureChangedError:
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    self._critical(metrics, "structure_changed", structural=True)
                    break
                except ScraperError:
                    elapsed = self.monotonic() - page_started
                    total_duration += elapsed
                    self._critical(metrics, "scraper_error", structural=False)
                    break

                page_attempts = max(attempts_total - page_attempts_before, 1)
                metrics.retries += max(page_attempts - 1, 0)

                if metrics.products_reported_initial == 0:
                    metrics.products_reported_initial = total_reported
                    metrics.catalog_pages_reported = math.ceil(
                        total_reported / config.page_size
                    )
                    metrics.pages_expected = _planned_pages(total_reported, config)
                metrics.products_reported_final = total_reported

                expected_products = min(
                    config.page_size,
                    max(metrics.products_reported_initial - from_index, 0),
                )
                page_product_keys = _page_product_keys(raw_products)
                page_signature = _page_signature(page_product_keys)
                page_events = list(result.quality_events)

                metrics.products_returned += result.metrics.products_returned
                metrics.skus_returned += result.metrics.skus_returned
                metrics.errors += result.metrics.errors
                metrics.structural_events += result.metrics.structural_events
                metrics.duplicate_skus += result.metrics.duplicate_skus

                page_valid = True
                if len(raw_products) < expected_products:
                    page_events.append("quality:partial_product_page_global")
                    self._critical(
                        metrics,
                        "partial_product_page",
                        structural=True,
                        increment=False,
                    )
                    page_valid = False
                elif len(raw_products) > expected_products:
                    page_events.append("structure:more_products_than_expected")
                    self._critical(
                        metrics,
                        "more_products_than_expected",
                        structural=True,
                        increment=False,
                    )
                    page_valid = False
                if page_signature in seen_page_signatures:
                    page_events.append("structure:repeated_page")
                    self._critical(
                        metrics,
                        "repeated_page",
                        structural=True,
                    )
                    page_valid = False
                if not result.accepted:
                    reason = (
                        "page_without_prices"
                        if result.metrics.skus_with_price == 0
                        else "page_rejected_by_extractor"
                    )
                    self._critical(
                        metrics,
                        reason,
                        structural=False,
                        increment=result.metrics.errors == 0,
                    )
                    page_valid = False

                page_summary = PageSummary(
                    page=page,
                    from_index=from_index,
                    to_index=to_index,
                    order_by=order_by,
                    total_reported=total_reported,
                    products_expected=expected_products,
                    products_returned=len(raw_products),
                    skus_returned=result.metrics.skus_returned,
                    skus_extracted=result.metrics.skus_extracted,
                    response_bytes=response_bytes,
                    duration_seconds=round(elapsed, 6),
                    accepted=page_valid,
                    signature=page_signature,
                    quality_events=tuple(dict.fromkeys(page_events)),
                )
                pages.append(page_summary)

                if not page_valid:
                    if config.stop_on_error:
                        break
                else:
                    metrics.pages_completed += 1
                    seen_page_signatures.add(page_signature)
                    duplicate_products = _count_duplicate_products(
                        page_product_keys, seen_products
                    )
                    metrics.duplicate_products += duplicate_products
                    seen_products.update(page_product_keys)

                    for product in result.products:
                        identity = (
                            product.source_key_type.value,
                            product.source_key,
                        )
                        if identity in seen_skus:
                            metrics.duplicate_skus += 1
                            continue
                        seen_skus.add(identity)
                        accumulated.append(product)

                    previous_to = to_index
                    expected_order_by = order_by

                if page >= metrics.pages_expected:
                    break
                if config.delay_seconds:
                    self.sleeper(config.delay_seconds)
                    metrics.delay_seconds_applied += config.delay_seconds
                page += 1
        finally:
            if transport_instrumented:
                client.transport = original_transport
            if original_max_retries is not None:
                client.max_retries = original_max_retries

        self._finish_metrics(
            metrics,
            accumulated,
            seen_products=seen_products,
            total_duration=total_duration,
            run_started_monotonic=run_started_monotonic,
            profile=profile,
            thresholds=thresholds,
        )
        return CatalogRunResult(
            products=tuple(accumulated),
            pages=tuple(pages),
            metrics=metrics,
        )

    def _finish_metrics(
        self,
        metrics: CatalogRunMetrics,
        products: Sequence[RawProduct],
        *,
        seen_products: set[str],
        total_duration: float,
        run_started_monotonic: float,
        profile: AcceptanceProfile,
        thresholds: AcceptanceThresholds,
    ) -> None:
        metrics.products_processed = len(seen_products)
        metrics.skus_extracted = len(products)
        metrics.skus_with_price = sum(
            1 for product in products if product.raw_values.get("current_price") is not None
        )
        metrics.skus_without_price = metrics.skus_extracted - metrics.skus_with_price
        metrics.skus_pending_review = sum(
            1
            for product in products
            if any(
                product.raw_values.get(name) is None
                for name in ("current_price", "brand", "category", "presentation")
            )
            or product.raw_values.get("availability") == "unknown"
        )
        metrics.weighted_skus = sum(
            1 for product in products if product.raw_values.get("weighted_product")
        )
        metrics.promotional_skus = sum(
            1 for product in products if product.raw_values.get("is_promotion")
        )
        metrics.page_coverage = (
            metrics.pages_completed / metrics.pages_expected
            if metrics.pages_expected
            else 0.0
        )
        metrics.average_response_seconds = (
            total_duration / metrics.pages_attempted if metrics.pages_attempted else 0.0
        )
        metrics.average_response_bytes = (
            metrics.response_bytes / metrics.pages_attempted
            if metrics.pages_attempted
            else 0.0
        )
        metrics.total_change_absolute = (
            metrics.products_reported_final - metrics.products_reported_initial
        )
        metrics.total_change_ratio = _ratio(
            abs(metrics.total_change_absolute), metrics.products_reported_initial
        )
        metrics.missing_price_ratio = _ratio(
            metrics.skus_without_price, metrics.skus_extracted
        )
        metrics.duplicate_sku_ratio = _ratio(
            metrics.duplicate_skus, metrics.skus_returned
        )
        metrics.duplicate_product_ratio = _ratio(
            metrics.duplicate_products, metrics.products_returned
        )

        if metrics.products_reported_initial != metrics.products_reported_final:
            _append_unique(metrics.warnings, "catalog_total_changed_during_run")
        if metrics.http_429 and not metrics.persistent_http_429:
            _append_unique(metrics.warnings, "transient_http_429_recovered")
        if metrics.http_5xx and metrics.errors == 0:
            _append_unique(metrics.warnings, "transient_http_5xx_recovered")
        _append_unique(metrics.warnings, "ordering_is_not_strictly_unique")

        mandatory = {
            "pages_incomplete": metrics.pages_completed != metrics.pages_expected,
            "page_coverage_below_100_percent": not math.isclose(
                metrics.page_coverage, 1.0
            ),
            "errors_present": metrics.errors != 0,
            "structural_events_present": metrics.structural_events != 0,
            "http_403_present": metrics.http_403 != 0,
            "persistent_http_429_present": metrics.persistent_http_429 != 0,
            "no_skus_extracted": metrics.skus_extracted <= 0,
            "no_skus_with_price": metrics.skus_with_price <= 0,
        }
        for reason, failed in mandatory.items():
            if failed:
                _append_unique(metrics.rejection_reasons, reason)

        if metrics.skus_extracted >= 100 and metrics.pages_completed >= 2:
            metrics.proposed_thresholds = {
                "max_missing_price_ratio": _proposed_limit(
                    metrics.missing_price_ratio, minimum_margin=0.01
                ),
                "max_duplicate_sku_ratio": _proposed_limit(
                    metrics.duplicate_sku_ratio, minimum_margin=0.005
                ),
                "max_duplicate_product_ratio": _proposed_limit(
                    metrics.duplicate_product_ratio, minimum_margin=0.005
                ),
                "max_total_change_ratio": _proposed_limit(
                    metrics.total_change_ratio, minimum_margin=0.002
                ),
            }
        else:
            _append_unique(metrics.warnings, "baseline_too_small_for_thresholds")

        if profile is AcceptanceProfile.VALIDATION:
            if not thresholds.complete:
                _append_unique(metrics.rejection_reasons, "validation_thresholds_missing")
            else:
                checks = {
                    "missing_price_ratio_above_threshold": (
                        metrics.missing_price_ratio
                        > float(thresholds.max_missing_price_ratio)
                    ),
                    "duplicate_sku_ratio_above_threshold": (
                        metrics.duplicate_sku_ratio
                        > float(thresholds.max_duplicate_sku_ratio)
                    ),
                    "duplicate_product_ratio_above_threshold": (
                        metrics.duplicate_product_ratio
                        > float(thresholds.max_duplicate_product_ratio)
                    ),
                    "catalog_total_change_above_threshold": (
                        metrics.total_change_ratio
                        > float(thresholds.max_total_change_ratio)
                    ),
                }
                for reason, failed in checks.items():
                    if failed:
                        _append_unique(metrics.rejection_reasons, reason)

        metrics.accepted = not metrics.rejection_reasons
        finished_at = _utc(self.clock())
        metrics.finished_at_utc = finished_at.isoformat()
        metrics.duration_seconds = round(
            max(self.monotonic() - run_started_monotonic, 0.0), 6
        )
        metrics.quality_events = list(dict.fromkeys(metrics.quality_events))

    @staticmethod
    def _critical(
        metrics: CatalogRunMetrics,
        reason: str,
        *,
        structural: bool,
        increment: bool = True,
    ) -> None:
        _append_unique(metrics.rejection_reasons, reason)
        _append_unique(metrics.quality_events, reason)
        if increment:
            if structural:
                metrics.structural_events += 1
            else:
                metrics.errors += 1


def _read_raw_page(payload: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], int]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise StructureChangedError("Falta data en la respuesta GraphQL")
    product_search = data.get("productSearch")
    if not isinstance(product_search, Mapping):
        raise StructureChangedError("Falta data.productSearch")
    products = product_search.get("products")
    if not isinstance(products, Sequence) or isinstance(products, (str, bytes)):
        raise StructureChangedError("Falta data.productSearch.products")
    mapped_products = [product for product in products if isinstance(product, Mapping)]
    if len(mapped_products) != len(products):
        raise StructureChangedError("La página contiene productos inválidos")
    try:
        total = int(product_search["recordsFiltered"])
    except (KeyError, TypeError, ValueError) as exc:
        raise StructureChangedError("recordsFiltered es inválido") from exc
    if total <= 0:
        raise StructureChangedError("recordsFiltered debe ser mayor que cero")
    if total < len(mapped_products):
        raise StructureChangedError("recordsFiltered es menor que la página devuelta")
    if not mapped_products:
        raise EmptyResponseError("La página no devolvió productos")
    return mapped_products, total


def _planned_pages(total_products: int, config: CrawlConfig) -> int:
    catalog_pages = math.ceil(total_products / config.page_size)
    planned = catalog_pages
    if config.max_pages is not None:
        planned = min(planned, config.max_pages)
    if config.max_products is not None:
        planned = min(planned, config.max_products // config.page_size)
    return max(planned, 1)


def _continuity_error(
    *,
    page: int,
    from_index: int,
    to_index: int,
    page_size: int,
    previous_to: int | None,
    order_by: str,
    expected_order_by: str | None,
) -> str | None:
    if page == 1 and from_index != 0:
        return "first_page_does_not_start_at_zero"
    if to_index - from_index + 1 != page_size:
        return "page_size_changed"
    if previous_to is not None:
        if from_index <= previous_to:
            return "overlapping_page_ranges"
        if from_index != previous_to + 1:
            return "page_range_gap"
    if expected_order_by is not None and order_by != expected_order_by:
        return "ordering_changed_during_run"
    return None


def _page_product_keys(products: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: list[str] = []
    for index, product in enumerate(products):
        product_id = _clean(product.get("productId"))
        reference = _clean(product.get("productReference"))
        link_text = _clean(product.get("linkText"))
        name = _clean(product.get("productName"))
        key = product_id or reference or link_text or name
        keys.append(key or f"missing-product-key:{index}")
    return keys


def _count_duplicate_products(page_keys: Sequence[str], seen: set[str]) -> int:
    local_seen: set[str] = set()
    duplicates = 0
    for key in page_keys:
        if key in local_seen or key in seen:
            duplicates += 1
        local_seen.add(key)
    return duplicates


def _page_signature(product_keys: Sequence[str]) -> str:
    encoded = json.dumps(list(product_keys), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _proposed_limit(observed: float, *, minimum_margin: float) -> float:
    """Propone un límite reproducible sin activarlo automáticamente."""

    return round(min(1.0, max(observed * 1.25, observed + minimum_margin)), 6)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock debe devolver una fecha con zona horaria")
    return value.astimezone(timezone.utc)
