#!/usr/bin/env python3
"""Obtiene una muestra SPS reutilizando exactamente la radiografía ya probada.

La captura de ubicación usa el mismo RequestContextCollector, los mismos stages y
el mismo análisis que produjo la evidencia canónica de San Pedro Sula. Una vez
verificado el fingerprint fuerte de regionId, y sin cerrar ni reemplazar el
BrowserContext, se hace un único GET productSearchV3 ya validado previamente.
El regionId raw sólo vive en memoria y nunca se persiste.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import probar_muestra_sps_la_colonia as passive  # noqa: E402
import probar_muestra_sps_la_colonia_bound as bound  # noqa: E402
from precios_supermercados.diagnostics import la_colonia_location_binding_capture as radiography  # noqa: E402
from precios_supermercados.diagnostics.la_colonia_sps_context_diagnostic import (  # noqa: E402
    DiagnosticSafetyError,
    launch_compatible_chromium,
)
from precios_supermercados.diagnostics.location_binding_dom_controls import (  # noqa: E402
    LocationControlResolutionError,
)
from precios_supermercados.location_binding_radiography import (  # noqa: E402
    analyze_location_binding,
    report_dict,
)
from precios_supermercados.scrapers.la_colonia_graphql import (  # noqa: E402
    GRAPHQL_ENDPOINT,
    build_product_search_url,
)

EXPLICIT_REQUEST_TIMEOUT_MS = 15_000
EXPECTED_SOURCE_KEY = (
    "request:regionid:sha256:"
    "d7732eccc99c8530a6d29cce4244920e65e85c1d5492facb05469dc3589cb8b7"
)


def _matching_region(value: Any) -> str | None:
    """Devuelve sólo el valor raw cuyo fingerprint coincide con SPS."""

    if isinstance(value, str):
        return value if bound._stable_fingerprint(value) == bound.SPS_REGION_FINGERPRINT else None
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if bound._is_region_key(str(key)):
                match = _matching_region(nested)
                if match is not None:
                    return match
            match = _matching_region(nested)
            if match is not None:
                return match
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            match = _matching_region(nested)
            if match is not None:
                return match
    return None


def _failure_artifact(reason: str, diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    artifact = passive.build_failure_artifact(reason=reason, diagnostic=diagnostic)
    artifact.update(
        {
            "capture_strategy": "radiography_then_same_context_productSearchV3",
            "radiography_binding_reused": True,
            "region_binding_fingerprint_verified": bool(
                diagnostic.get("region_binding_fingerprint_verified", False)
            ),
            "binding_source_key_verified": bool(
                diagnostic.get("binding_source_key_verified", False)
            ),
            "explicit_product_search_requests": int(
                diagnostic.get("explicit_product_search_requests", 0)
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
            "capture_strategy": "radiography_then_same_context_productSearchV3",
            "capture_mode": "single_explicit_graphql_after_radiography",
            "radiography_binding_reused": True,
            "region_binding_fingerprint_verified": True,
            "binding_source_key_verified": True,
            "explicit_product_search_requests": 1,
        }
    )
    passive._validate_artifact_shape(artifact)
    return artifact


def _run_live_sample(*, sample_size: int) -> dict[str, Any]:
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
        "binding_source_key_verified": False,
        "explicit_product_search_requests": 0,
    }

    with sync_playwright() as pw:
        browser, _ = launch_compatible_chromium(pw)
        try:
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            collector = radiography.RequestContextCollector()
            page.on("request", collector.observe_request)

            home_response = page.goto(
                radiography.TARGET_URL,
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            if home_response is not None and home_response.status in {403, 429}:
                diagnostic["blocked_http_status_observed"] = int(home_response.status)
                raise passive.MvpSampleError(f"http_{home_response.status}", diagnostic=diagnostic)
            if passive._blocked_surface(page):
                raise passive.MvpSampleError("blocked_or_login_surface", diagnostic=diagnostic)
            page.wait_for_timeout(250)
            before = radiography._stage(page, context, collector, "before")

            radiography._open_location_selector(page)
            page.wait_for_timeout(150)
            city_control, cities = radiography._city_select_and_options(page, passive.TARGET_CITY)

            collector.reset()
            city_action_performed = False
            if city_control.state != radiography.CITY_STATE_SELECTED:
                city_action_performed = radiography.activate_city_control(
                    city_control, passive.TARGET_CITY
                )
            if city_action_performed:
                page.wait_for_timeout(500)
            elif city_control.state == radiography.CITY_STATE_SELECTED:
                page.wait_for_timeout(100)

            if city_control.state is not None:
                radiography._verify_structural_city_selection(page, passive.TARGET_CITY)
            diagnostic["location_verified_same_run"] = True

            after_city = radiography._stage(page, context, collector, "after_city")
            store_option, stores = radiography._discover_store_options(page, cities)
            after_store = None
            selected_store = None
            store_selection_observed = False
            if store_option is not None:
                store_selection_observed = True
                selected_store = stores[0]
                collector.reset()
                radiography._activate_option(store_option, selected_store)
                page.wait_for_timeout(500)
                after_store = radiography._stage(page, context, collector, "after_store")

            analysis = analyze_location_binding(
                city_name=passive.TARGET_CITY,
                before=before,
                after_city=after_city,
                store_selection_observed=store_selection_observed,
                after_store=after_store,
                store_name=selected_store,
            )
            binding = report_dict(analysis)
            source_key = str(binding.get("source_location_key_candidate") or "")
            if source_key != EXPECTED_SOURCE_KEY:
                raise passive.MvpSampleError("radiography_sps_binding_not_verified", diagnostic=diagnostic)
            diagnostic["binding_source_key_verified"] = True

            # Recuperar el mismo raw regionId que originó el fingerprint, sólo en memoria.
            request_channel = after_city.channels.get("request", {})
            ephemeral_region = _matching_region(request_channel)
            if ephemeral_region is None and after_store is not None:
                ephemeral_region = _matching_region(after_store.channels.get("request", {}))
            if ephemeral_region is None:
                raise passive.MvpSampleError("radiography_region_raw_not_recovered", diagnostic=diagnostic)
            diagnostic["region_binding_fingerprint_verified"] = True

            # La consulta conocida funciona. No se altera la sesión ni se inventa contexto:
            # BrowserContext.request comparte el jar de cookies del navegador activo.
            request_url = build_product_search_url(page=1, page_size=sample_size)
            diagnostic["explicit_product_search_requests"] = 1
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
                raise passive.MvpSampleError(f"graphql_http_{status}", diagnostic=diagnostic)
            try:
                payload = response.json()
            except Exception as exc:
                raise passive.MvpSampleError("graphql_not_json", diagnostic=diagnostic) from exc
            if not passive._is_product_search_payload(payload):
                raise passive.MvpSampleError("graphql_product_search_not_observed", diagnostic=diagnostic)

            result = bound._parse_payload(payload, sample_size=sample_size)
            return _success_artifact(extraction_result=result, sample_size=sample_size)
        except passive.MvpSampleError:
            raise
        except (DiagnosticSafetyError, LocationControlResolutionError, radiography.LocationBindingCaptureError) as exc:
            raise passive.MvpSampleError(str(exc), diagnostic=diagnostic) from exc
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--allow-single-explicit-product-data-request", action="store_true")
    parser.add_argument("--sample-size", type=int, choices=passive.ALLOWED_SAMPLE_SIZES, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "run-artifacts" / "mvp-radiography-sample.json",
    )
    args = parser.parse_args(argv)
    if not args.live_read_only:
        parser.error("la muestra requiere --live-read-only")
    if not args.allow_single_explicit_product_data_request:
        parser.error("la muestra requiere autorización para un único GET de productos")

    try:
        artifact = _run_live_sample(sample_size=args.sample_size)
        passive._write_artifact(artifact, args.output)
    except passive.MvpSampleError as exc:
        diagnostic = dict(getattr(exc, "diagnostic", {}) or {})
        artifact = _failure_artifact(str(exc), diagnostic)
        passive._write_artifact(artifact, args.output)
        print(f"mvp_radiography_stopped:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 3

    print(
        json.dumps(
            {
                "location_id": artifact["location_id"],
                "sample_skus_returned": artifact["sample_skus_returned"],
                "sample_skus_with_price": artifact["sample_skus_with_price"],
                "capture_mode": artifact["capture_mode"],
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
