#!/usr/bin/env python3
"""Entrypoint MVP bound con recuperación DOM y contexto de segmento compartido.

El run 32807247386 mostró un re-render real del botón de San Pedro Sula mientras
Playwright intentaba hacer click. Los runs 32809740940 y 32857812255 confirmaron
el binding SPS exacto con ``regionId`` sólo en body; el segundo mostró además que
inferir la transición de ``vtexsegment`` únicamente desde headers de requests no es
suficiente. Este wrapper tampoco inventa un header/query: observa sólo fingerprints
efímeros de ``vtexsegment`` directamente desde el cookie jar del BrowserContext y
exige una transición respecto al último estado observado antes de activar SPS.

``context.request`` comparte ese mismo cookie jar, por lo que el único GET GraphQL
puede conservar el contexto de sesión sin copiar ni persistir cookies o ``regionId``
raw. La recuperación DOM sigue limitada a una re-resolución del mismo control y la
consulta explícita sigue limitada por el runner bound original a un máximo de una.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import probar_muestra_sps_la_colonia_bound as bound  # noqa: E402

SEGMENT_COOKIE_NAME = "vtexsegment"
TARGET_COOKIE_DOMAIN = "lacolonia.com"


def _is_playwright_timeout(exc: BaseException) -> bool:
    return exc.__class__.__name__ == "TimeoutError"


def _segment_cookie_value(headers: Mapping[str, Any]) -> str | None:
    cookie_header: str | None = None
    for key, value in headers.items():
        if str(key).casefold() == "cookie":
            cookie_header = str(value)
            break
    if not cookie_header:
        return None
    for item in cookie_header.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator and name.casefold() == SEGMENT_COOKIE_NAME:
            return value or None
    return None


def _target_cookie_domain(value: Any) -> bool:
    domain = str(value or "").strip().lstrip(".").casefold()
    return domain == TARGET_COOKIE_DOMAIN or domain.endswith(f".{TARGET_COOKIE_DOMAIN}")


def _segment_cookie_fingerprint_from_context(request: Any) -> str | None:
    """Lee el cookie jar asociado a la request y devuelve sólo un fingerprint."""

    try:
        context = request.frame.page.context
        cookies = context.cookies()
    except Exception:
        return None

    for cookie in cookies:
        if not isinstance(cookie, Mapping):
            continue
        if str(cookie.get("name") or "").casefold() != SEGMENT_COOKIE_NAME:
            continue
        if not _target_cookie_domain(cookie.get("domain")):
            continue
        value = cookie.get("value")
        if isinstance(value, str) and value:
            return bound._stable_fingerprint(value)
    return None


class SharedSegmentCookieTracker(bound.RegionContextTracker):
    """Autoriza cookie-jar compartido sólo tras transición observable de segmento."""

    shared_fallback_used = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._inactive_segment_cookie_fingerprint: str | None = None
        self._active_segment_cookie_fingerprints: list[str] = []

    def reset_and_enable(self) -> None:
        super().reset_and_enable()
        self._active_segment_cookie_fingerprints.clear()
        type(self).shared_fallback_used = False

    def _observe_segment_fingerprint(self, fingerprint: str | None) -> None:
        if fingerprint is None:
            return
        if self.active:
            if fingerprint not in self._active_segment_cookie_fingerprints:
                self._active_segment_cookie_fingerprints.append(fingerprint)
        else:
            # Mientras la selección aún no se activa, conservar siempre la última
            # fotografía disponible. Sólo es un SHA256, nunca el valor de cookie.
            self._inactive_segment_cookie_fingerprint = fingerprint

    def observe_request(self, request: Any) -> None:
        # La fuente primaria es el cookie jar real del BrowserContext, no el header
        # serializado de una request concreta. El header se conserva sólo como señal
        # secundaria compatible con evidencia previa.
        self._observe_segment_fingerprint(
            _segment_cookie_fingerprint_from_context(request)
        )
        try:
            value = _segment_cookie_value(request.headers)
        except Exception:
            value = None
        if value is not None:
            self._observe_segment_fingerprint(bound._stable_fingerprint(value))
        super().observe_request(request)

    @property
    def segment_cookie_transition_observed(self) -> bool:
        baseline = self._inactive_segment_cookie_fingerprint
        if baseline is None:
            return False
        return any(
            fingerprint != baseline
            for fingerprint in self._active_segment_cookie_fingerprints
        )

    def replay_context(self) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
        try:
            return super().replay_context()
        except bound.passive.MvpSampleError as exc:
            if str(exc) != "sps_region_binding_observed_but_not_replayable":
                raise
            if not self.segment_cookie_transition_observed:
                raise bound.passive.MvpSampleError(
                    "sps_region_binding_body_only_without_segment_cookie_transition"
                ) from exc
            # No se copia ningún valor raw. El APIRequestContext asociado al
            # BrowserContext enviará por sí mismo el cookie jar de esa sesión.
            type(self).shared_fallback_used = True
            return {}, ()


def activate_city_control_resilient(
    control: Any,
    city_name: str,
    *,
    activate_fn: Callable[[Any, str], bool],
    resolve_fn: Callable[[Any, str], Any],
    wait_for_city_fn: Callable[[Any], str],
) -> bool:
    """Activa la misma ciudad con como máximo una re-resolución por detach/timeout."""

    try:
        return activate_fn(control, city_name)
    except Exception as exc:
        if not _is_playwright_timeout(exc):
            raise

        try:
            page = control.locator.page
        except Exception as page_exc:
            raise bound.passive.MvpSampleError(
                "sps_city_control_activation_timeout"
            ) from page_exc

        # El click puede haber disparado el cambio antes de que el nodo se desmontara.
        # Verificar primero evita duplicar una selección que ya ocurrió.
        try:
            wait_for_city_fn(page)
            return True
        except bound.passive.MvpSampleError:
            pass

        refreshed = resolve_fn(page, city_name)
        try:
            return activate_fn(refreshed, city_name)
        except Exception as retry_exc:
            if _is_playwright_timeout(retry_exc):
                raise bound.passive.MvpSampleError(
                    "sps_city_control_activation_timeout"
                ) from retry_exc
            raise


def main(argv: list[str] | None = None) -> int:
    original_activate = bound.activate_city_control
    original_tracker = bound.RegionContextTracker
    original_success_artifact = bound._success_artifact

    def _resilient(control: Any, city_name: str) -> bool:
        return activate_city_control_resilient(
            control,
            city_name,
            activate_fn=original_activate,
            resolve_fn=bound.resolve_exact_city_control,
            wait_for_city_fn=bound.passive._wait_for_city,
        )

    def _success_artifact(**kwargs: Any) -> dict[str, Any]:
        if (
            kwargs.get("capture_mode") == "single_explicit_bound_fallback"
            and SharedSegmentCookieTracker.shared_fallback_used
        ):
            kwargs["capture_mode"] = "single_explicit_shared_segment_cookie"
        artifact = original_success_artifact(**kwargs)
        if SharedSegmentCookieTracker.shared_fallback_used:
            artifact["segment_cookie_transition_verified"] = True
            bound.passive._validate_artifact_shape(artifact)
        return artifact

    SharedSegmentCookieTracker.shared_fallback_used = False
    bound.activate_city_control = _resilient
    bound.RegionContextTracker = SharedSegmentCookieTracker
    bound._success_artifact = _success_artifact
    try:
        return bound.main(argv)
    finally:
        bound.activate_city_control = original_activate
        bound.RegionContextTracker = original_tracker
        bound._success_artifact = original_success_artifact
        SharedSegmentCookieTracker.shared_fallback_used = False


if __name__ == "__main__":
    raise SystemExit(main())
