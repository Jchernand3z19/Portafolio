#!/usr/bin/env python3
"""Obtiene una muestra SPS mediante Intelligent Search API v1 con contexto explícito.

VTEX v1 permite trasladar directamente ``segment.regionId`` y ``segment.channel``
a query params. Este runner conserva ambos únicamente en memoria, exige que el
regionId coincida con el fingerprint SPS canónico observado en el mismo run y hace
como máximo una consulta pública de productos. Ningún valor de contexto raw se
persiste en el artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import probar_muestra_sps_la_colonia as passive  # noqa: E402
import probar_muestra_sps_la_colonia_bound as bound  # noqa: E402
import probar_muestra_sps_la_colonia_resilient as resilient  # noqa: E402
from precios_supermercados.diagnostics.la_colonia_sps_context_diagnostic import (  # noqa: E402
    DiagnosticSafetyError,
    launch_compatible_chromium,
)
from precios_supermercados.diagnostics.location_binding_dom_controls import (  # noqa: E402
    LocationControlResolutionError,
    open_location_selector,
    resolve_exact_city_control,
)
from precios_supermercados.scrapers.base import StructureChangedError  # noqa: E402
from precios_supermercados.scrapers.la_colonia import LaColoniaExtractor  # noqa: E402

INTELLIGENT_SEARCH_V1_ENDPOINT = (
    "https://www.lacolonia.com/api/intelligent-search/v1/product-search"
)
EXPLICIT_REQUEST_TIMEOUT_MS = 15_000
PASSIVE_OBSERVE_SECONDS = 3.0
_CHANNEL_KEYS = frozenset({"sc", "saleschannel", "channel"})


def _canonical_key(value: str) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _is_channel_key(value: str) -> bool:
    return _canonical_key(value) in _CHANNEL_KEYS


def _normalize_channel(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 < value <= 9999:
        return str(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.isdigit() and 0 < int(cleaned) <= 9999:
            return str(int(cleaned))
    return None


def _mapping_region_values(value: Any) -> list[Any]:
    return bound._nested_region_values(value)


def _mapping_channel_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _is_channel_key(str(key)):
                normalized = _normalize_channel(nested)
                if normalized is not None:
                    found.append(normalized)
            found.extend(_mapping_channel_values(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            found.extend(_mapping_channel_values(nested))
    return found


class ExplicitV1ContextTracker:
    """Conserva sólo el regionId SPS raw y sales channel efímeros del mismo run."""

    def __init__(self, *, expected_fingerprint: str = bound.SPS_REGION_FINGERPRINT) -> None:
        self.expected_fingerprint = expected_fingerprint
        self.active = False
        self.fingerprint_verified = False
        self._ephemeral_region_id: str | None = None
        self._channels_before_activation: list[str] = []
        self._channels_after_activation: list[str] = []

    def __repr__(self) -> str:
        return (
            "ExplicitV1ContextTracker("
            f"active={self.active}, fingerprint_verified={self.fingerprint_verified}, "
            f"channel_candidates={len(self._all_channels())}, "
            f"region_available={self._ephemeral_region_id is not None})"
        )

    def reset_and_enable(self) -> None:
        self.active = True
        self.fingerprint_verified = False
        self._ephemeral_region_id = None
        self._channels_after_activation.clear()

    def _remember_channel(self, value: Any) -> None:
        normalized = _normalize_channel(value)
        if normalized is None:
            return
        target = (
            self._channels_after_activation if self.active else self._channels_before_activation
        )
        if normalized not in target:
            target.append(normalized)

    def _remember_region(self, value: Any) -> None:
        if not self.active or not isinstance(value, str):
            return
        if bound._stable_fingerprint(value) != self.expected_fingerprint:
            return
        self.fingerprint_verified = True
        self._ephemeral_region_id = value

    def observe_request(self, request: Any) -> None:
        try:
            for key, value in parse_qsl(
                urlsplit(str(request.url)).query,
                keep_blank_values=True,
            ):
                if _is_channel_key(key):
                    self._remember_channel(value)
                if bound._is_region_key(key):
                    self._remember_region(value)
        except Exception:
            pass

        try:
            headers = request.headers
        except Exception:
            headers = {}
        if isinstance(headers, Mapping):
            for key, value in headers.items():
                if _is_channel_key(str(key)):
                    self._remember_channel(value)
                if bound._is_region_key(str(key)):
                    self._remember_region(value)

        try:
            payload = request.post_data_json
        except Exception:
            payload = None
        for value in _mapping_region_values(payload):
            self._remember_region(value)
        for value in _mapping_channel_values(payload):
            self._remember_channel(value)

    def _all_channels(self) -> tuple[str, ...]:
        values: list[str] = []
        for candidate in (
            *self._channels_after_activation,
            *self._channels_before_activation,
        ):
            if candidate not in values:
                values.append(candidate)
        return tuple(values)

    @property
    def channel_observed(self) -> bool:
        return bool(self._all_channels())

    def explicit_context(self) -> tuple[str, str]:
        if not self.fingerprint_verified or self._ephemeral_region_id is None:
            raise passive.MvpSampleError("sps_region_binding_not_observed_same_run")
        channels = self._all_channels()
        if not channels:
            raise passive.MvpSampleError("sales_channel_not_observed_same_run")
        if len(channels) > 1:
            raise passive.MvpSampleError("sales_channel_ambiguous_same_run")
        return self._ephemeral_region_id, channels[0]


def _build_v1_url(*, region_id: str, sales_channel: str, sample_size: int) -> str:
    params = {
        "count": str(sample_size),
        "page": "1",
        "locale": "es-HN",
        "hideUnavailableItems": "false",
        "sc": sales_channel,
        "regionId": region_id,
    }
    return f"{INTELLIGENT_SEARCH_V1_ENDPOINT}?{urlencode(params)}"


def _v1_product_payload(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    products = value.get("products")
    return (
        isinstance(products, Sequence)
        and not isinstance(products, (str, bytes))
        and any(isinstance(product, Mapping) for product in products)
    )


def _parse_v1_payload(payload: Mapping[str, Any], *, sample_size: int) -> Any:
    products = payload.get("products")
    if not isinstance(products, Sequence) or isinstance(products, (str, bytes)) or not products:
        raise passive.MvpSampleError("intelligent_v1_sample_without_products")
    total_raw = payload.get("recordsFiltered", payload.get("total", len(products)))
    try:
        total = max(int(total_raw), len(products))
    except (TypeError, ValueError):
        total = len(products)
    wrapped = {
        "data": {
            "productSearch": {
                "recordsFiltered": total,
                "products": list(products),
            }
        }
    }
    extractor = LaColoniaExtractor()
    try:
        return extractor.parse_payload(
            wrapped,
            scrape_run_id="mvp_intelligent_v1_sample",
            source_url=INTELLIGENT_SEARCH_V1_ENDPOINT,
            page_size=max(1, min(sample_size, len(products))),
        )
    except StructureChangedError as exc:
        raise passive.MvpSampleError("intelligent_v1_payload_not_parseable") from exc


def _failure_artifact(reason: str, diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    artifact = passive.build_failure_artifact(reason=reason, diagnostic=diagnostic)
    artifact.update(
        {
            "capture_strategy": "explicit_region_intelligent_search_v1",
            "region_binding_fingerprint_verified": bool(
                diagnostic.get("region_binding_fingerprint_verified", False)
            ),
            "sales_channel_observed_same_run": bool(
                diagnostic.get("sales_channel_observed_same_run", False)
            ),
            "explicit_product_data_requests": int(
                diagnostic.get("explicit_product_data_requests", 0)
            ),
        }
    )
    passive._validate_artifact_shape(artifact)
    return artifact


def _success_artifact(*, extraction_result: Any, sample_size: int) -> dict[str, Any]:
    artifact = passive.build_sample_artifact(
        extraction_result=extraction_result,
        sample_size=sample_size,
        observed_at_utc=passive._utc_now(),
        location_verified_same_run=True,
    )
    artifact.update(
        {
            "capture_strategy": "explicit_region_intelligent_search_v1",
            "capture_mode": "single_explicit_intelligent_search_v1",
            "region_binding_fingerprint_verified": True,
            "sales_channel_observed_same_run": True,
            "explicit_product_data_requests": 1,
        }
    )
    passive._validate_artifact_shape(artifact)
    return artifact


def _run_live_v1_sample(*, sample_size: int) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise passive.MvpSampleError("playwright_not_installed") from exc

    diagnostic: dict[str, Any] = {
        "location_verified_same_run": False,
        "graphql_responses_seen": 0,
        "product_search_payloads_seen": 0,
        "catalog_candidates_seen": 0,
        "blocked_http_status_observed": None,
        "region_binding_fingerprint_verified": False,
        "sales_channel_observed_same_run": False,
        "explicit_product_data_requests": 0,
    }
    tracker = ExplicitV1ContextTracker()

    with sync_playwright() as pw:
        browser, _ = launch_compatible_chromium(pw)
        try:
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            page.on("request", tracker.observe_request)

            home_response = page.goto(
                passive.TARGET_HOME,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if home_response is not None and home_response.status in {403, 429}:
                diagnostic["blocked_http_status_observed"] = int(home_response.status)
                raise passive.MvpSampleError(
                    f"http_{home_response.status}", diagnostic=diagnostic
                )
            if passive._blocked_surface(page):
                raise passive.MvpSampleError(
                    "blocked_or_login_surface", diagnostic=diagnostic
                )

            open_location_selector(page)
            control = resolve_exact_city_control(page, passive.TARGET_CITY)
            tracker.reset_and_enable()
            resilient.activate_city_control_resilient(
                control,
                passive.TARGET_CITY,
                activate_fn=bound.activate_city_control,
                resolve_fn=resolve_exact_city_control,
                wait_for_city_fn=passive._wait_for_city,
            )
            passive._wait_for_city(page)
            diagnostic["location_verified_same_run"] = True
            page.wait_for_timeout(passive.MINIMUM_ACTION_DELAY_MS)

            catalog_response = page.goto(
                passive.CATALOG_URL,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if catalog_response is not None and catalog_response.status in {403, 429}:
                diagnostic["blocked_http_status_observed"] = int(catalog_response.status)
                raise passive.MvpSampleError(
                    f"http_{catalog_response.status}", diagnostic=diagnostic
                )

            deadline = time.monotonic() + PASSIVE_OBSERVE_SECONDS
            while time.monotonic() < deadline:
                if passive._blocked_surface(page):
                    raise passive.MvpSampleError(
                        "blocked_or_login_surface", diagnostic=diagnostic
                    )
                page.wait_for_timeout(250)

            passive._wait_for_city(page)
            region_id, sales_channel = tracker.explicit_context()
            diagnostic["region_binding_fingerprint_verified"] = True
            diagnostic["sales_channel_observed_same_run"] = True

            request_url = _build_v1_url(
                region_id=region_id,
                sales_channel=sales_channel,
                sample_size=sample_size,
            )
            diagnostic["explicit_product_data_requests"] = 1
            response = context.request.get(
                request_url,
                timeout=EXPLICIT_REQUEST_TIMEOUT_MS,
                fail_on_status_code=False,
            )
            status = int(response.status)
            if status in {403, 429}:
                diagnostic["blocked_http_status_observed"] = status
                raise passive.MvpSampleError(f"http_{status}", diagnostic=diagnostic)
            if status != 200:
                raise passive.MvpSampleError(
                    f"intelligent_v1_http_{status}", diagnostic=diagnostic
                )
            try:
                payload = response.json()
            except Exception as exc:
                raise passive.MvpSampleError(
                    "intelligent_v1_not_json", diagnostic=diagnostic
                ) from exc
            if not _v1_product_payload(payload):
                raise passive.MvpSampleError(
                    "intelligent_v1_product_payload_not_observed", diagnostic=diagnostic
                )
            result = _parse_v1_payload(payload, sample_size=sample_size)
            return _success_artifact(extraction_result=result, sample_size=sample_size)
        except passive.MvpSampleError as exc:
            if exc.diagnostic:
                raise
            raise passive.MvpSampleError(str(exc), diagnostic=diagnostic) from exc
        except (DiagnosticSafetyError, LocationControlResolutionError) as exc:
            raise passive.MvpSampleError(str(exc), diagnostic=diagnostic) from exc
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--allow-single-explicit-product-data-request", action="store_true")
    parser.add_argument(
        "--sample-size",
        type=int,
        choices=passive.ALLOWED_SAMPLE_SIZES,
        default=10,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "run-artifacts" / "mvp-intelligent-v1-sample.json",
    )
    args = parser.parse_args(argv)
    if not args.live_read_only:
        parser.error("la muestra v1 requiere --live-read-only")
    if not args.allow_single_explicit_product_data_request:
        parser.error("la muestra v1 requiere autorización para un único GET de productos")

    try:
        artifact = _run_live_v1_sample(sample_size=args.sample_size)
        passive._write_artifact(artifact, args.output)
    except passive.MvpSampleError as exc:
        diagnostic = dict(getattr(exc, "diagnostic", {}) or {})
        artifact = _failure_artifact(str(exc), diagnostic)
        passive._write_artifact(artifact, args.output)
        print(f"mvp_intelligent_v1_stopped:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 3

    print(
        json.dumps(
            {
                "location_id": artifact["location_id"],
                "sample_skus_returned": artifact["sample_skus_returned"],
                "sample_skus_with_price": artifact["sample_skus_with_price"],
                "capture_mode": artifact["capture_mode"],
                "explicit_product_data_requests": artifact[
                    "explicit_product_data_requests"
                ],
                "production_authority": False,
                "catalog_accepted": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if artifact["validation_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
