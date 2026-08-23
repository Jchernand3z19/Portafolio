#!/usr/bin/env python3
"""Radiografía estructural read-only del selector de ubicación de La Colonia.

La herramienta observa únicamente la portada pública y el selector de ubicación.
Conserva evidencia estructural suficiente para entender el DOM real sin persistir
secretos: clases públicas, texto visible acotado, atributos de UI, geometría,
ancestros, nombres de cookies/storage y URLs de red sin valores de query.

No recorre catálogo ni productos, no ejecuta GraphQL manual, no persiste valores de
cookies/storage y no concede autoridad comercial.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import Page, sync_playwright

from precios_supermercados.diagnostics.la_colonia_sps_context_diagnostic import (
    launch_compatible_chromium,
)
from precios_supermercados.diagnostics.location_binding_dom_controls import (
    LocationControlResolutionError,
    open_location_selector,
)


TARGET_URL = "https://www.lacolonia.com/"
TARGET_CITY = "San Pedro Sula"
OTHER_CITY = "Tegucigalpa"
DEFAULT_OUTPUT_DIR = Path(
    "precios-supermercados-sps/diagnostic-artifacts/location-radiography-v2"
)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _safe_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        query_names = sorted(
            {name for name, _ in parse_qsl(parts.query, keep_blank_values=True)}
        )
        query = urlencode([(name, "") for name in query_names])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
    except Exception:
        return "invalid-url"


def _storage(page: Page) -> dict[str, list[dict[str, str]]]:
    raw = page.evaluate(
        """
        () => {
          const read = (storage) => {
            const rows = [];
            for (let i = 0; i < storage.length; i += 1) {
              const key = storage.key(i);
              rows.push([key, storage.getItem(key)]);
            }
            return rows;
          };
          return {local: read(localStorage), session: read(sessionStorage)};
        }
        """
    ) or {"local": [], "session": []}
    result: dict[str, list[dict[str, str]]] = {"local": [], "session": []}
    for bucket in ("local", "session"):
        for key, value in raw.get(bucket, []):
            result[bucket].append(
                {
                    "key": str(key),
                    "value_fingerprint": _fingerprint("" if value is None else str(value)),
                }
            )
        result[bucket].sort(key=lambda row: row["key"].casefold())
    return result


def _cookies(page: Page) -> list[dict[str, str]]:
    rows = []
    for cookie in page.context.cookies():
        rows.append(
            {
                "name": str(cookie.get("name", "")),
                "domain": str(cookie.get("domain", "")),
                "path": str(cookie.get("path", "")),
            }
        )
    return sorted(rows, key=lambda row: (row["domain"], row["name"], row["path"]))


def _body_text(page: Page, limit: int = 10_000) -> str:
    try:
        value = page.locator("body").inner_text(timeout=5_000)
    except Exception:
        return ""
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines)[:limit]


def _dom_inventory(page: Page) -> dict[str, Any]:
    return page.evaluate(
        r"""
        ({targetCity, otherCity}) => {
          const normalize = (value) => String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
          const target = normalize(targetCity);
          const other = normalize(otherCity);
          const promptTerms = ['desde que ciudad', 'ciudad', 'ubicacion', 'tienda'];

          const text = (el) => String(el.innerText || el.textContent || '')
            .replace(/\s+/g, ' ')
            .trim();
          const ownText = (el) => Array.from(el.childNodes || [])
            .filter((node) => node.nodeType === Node.TEXT_NODE)
            .map((node) => node.textContent || '')
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
          const presented = (el) => {
            const style = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
              Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0 &&
              rect.right > 0 && rect.bottom > 0 && rect.left < innerWidth && rect.top < innerHeight;
          };
          const attributes = (el) => {
            const result = {};
            const safeNames = new Set([
              'id', 'class', 'role', 'type', 'name', 'for', 'tabindex', 'title',
              'aria-label', 'aria-selected', 'aria-checked', 'aria-expanded',
              'aria-controls', 'aria-current', 'aria-hidden', 'disabled'
            ]);
            for (const attr of Array.from(el.attributes || [])) {
              const name = attr.name.toLowerCase();
              if (safeNames.has(name)) result[name] = String(attr.value).slice(0, 240);
              if (name.startsWith('data-')) result[name] = '<present>';
            }
            if (el.hasAttribute && el.hasAttribute('onclick')) result.onclick = '<present>';
            return result;
          };
          const descriptor = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return {
              tag: String(el.tagName || '').toLowerCase(),
              text: text(el).slice(0, 240),
              own_text: ownText(el).slice(0, 180),
              attributes: attributes(el),
              presented: presented(el),
              rect: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
              },
              style: {
                display: style.display,
                visibility: style.visibility,
                opacity: style.opacity,
                position: style.position,
                z_index: style.zIndex,
                cursor: style.cursor,
                pointer_events: style.pointerEvents,
              },
            };
          };
          const ancestry = (el, maxDepth = 7) => {
            const rows = [];
            let current = el;
            for (let depth = 0; current && depth < maxDepth; depth += 1) {
              rows.push({depth, ...descriptor(current)});
              current = current.parentElement;
            }
            return rows;
          };

          const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
          const visible = all.filter(presented);
          const buttons = visible.filter((el) => el.tagName.toLowerCase() === 'button');
          const controls = visible.filter((el) => {
            const tag = el.tagName.toLowerCase();
            const role = String(el.getAttribute('role') || '').toLowerCase();
            return ['button','input','select','option','a','label'].includes(tag) ||
              ['button','radio','option','menuitem','dialog','alertdialog'].includes(role);
          });
          const exactTarget = visible.filter((el) => normalize(text(el)) === target);
          const containsTarget = visible.filter((el) => normalize(text(el)).includes(target));
          const exactOther = visible.filter((el) => normalize(text(el)) === other);
          const cityRelated = visible.filter((el) => {
            const value = normalize(text(el));
            const classValue = normalize(el.getAttribute('class') || '');
            const idValue = normalize(el.getAttribute('id') || '');
            return value.includes(target) || value.includes(other) ||
              promptTerms.some((term) => value.includes(term)) ||
              /ciudad|ubic|location|modal|selector/.test(classValue) ||
              /ciudad|ubic|location|modal|selector/.test(idValue);
          });

          const interestingClasses = {};
          for (const el of all) {
            for (const token of Array.from(el.classList || [])) {
              if (/ciudad|ubic|location|modal|selector|radio|store|tienda/i.test(token)) {
                interestingClasses[token] = (interestingClasses[token] || 0) + 1;
              }
            }
          }

          const shadowHosts = all
            .filter((el) => Boolean(el.shadowRoot))
            .map((el) => ({
              host: descriptor(el),
              child_count: el.shadowRoot ? el.shadowRoot.querySelectorAll('*').length : 0,
            }));

          return {
            viewport: {width: innerWidth, height: innerHeight},
            document: {
              title: document.title,
              ready_state: document.readyState,
              body_child_count: document.body ? document.body.children.length : 0,
              element_count: all.length,
              presented_element_count: visible.length,
            },
            class_counts: interestingClasses,
            visible_buttons: buttons.slice(0, 80).map(descriptor),
            visible_controls: controls.slice(0, 120).map(descriptor),
            target_exact: exactTarget.slice(0, 30).map((el) => ({
              descriptor: descriptor(el), ancestors: ancestry(el),
            })),
            target_contains: containsTarget.slice(0, 40).map((el) => ({
              descriptor: descriptor(el), ancestors: ancestry(el),
            })),
            other_exact: exactOther.slice(0, 30).map((el) => ({
              descriptor: descriptor(el), ancestors: ancestry(el),
            })),
            city_related: cityRelated.slice(0, 120).map((el) => ({
              descriptor: descriptor(el), ancestors: ancestry(el, 4),
            })),
            iframes: Array.from(document.querySelectorAll('iframe')).slice(0, 20).map((frame) => ({
              title: String(frame.getAttribute('title') || '').slice(0, 160),
              name: String(frame.getAttribute('name') || '').slice(0, 160),
              src_origin_path: (() => {
                try {
                  const url = new URL(frame.src, location.href);
                  return `${url.origin}${url.pathname}`;
                } catch (_) {
                  return '<invalid>';
                }
              })(),
              presented: presented(frame),
            })),
            shadow_hosts: shadowHosts.slice(0, 20),
          };
        }
        """,
        {"targetCity": TARGET_CITY, "otherCity": OTHER_CITY},
    )


def _snapshot(page: Page) -> dict[str, Any]:
    return {
        "url": _safe_url(page.url),
        "body_text": _body_text(page),
        "storage": _storage(page),
        "cookies": _cookies(page),
        "dom": _dom_inventory(page),
    }


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    requests: list[dict[str, str]] = []
    responses: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": "precios-sps-la-colonia-location-radiography/v2",
        "target_url": TARGET_URL,
        "target_city": TARGET_CITY,
        "selector_opened": False,
        "errors": [],
        "authority": False,
        "catalog_accepted": False,
        "extraction_enabled": False,
    }

    with sync_playwright() as playwright:
        browser, executable = launch_compatible_chromium(playwright)
        report["browser_executable_name"] = Path(executable).name if executable else "managed"
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="es-HN",
            service_workers="block",
        )
        page = context.new_page()
        page.on(
            "request",
            lambda request: requests.append(
                {
                    "method": request.method,
                    "resource_type": request.resource_type,
                    "url": _safe_url(request.url),
                }
            ),
        )
        page.on(
            "response",
            lambda response: responses.append(
                {"status": response.status, "url": _safe_url(response.url)},
        )
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(3_000)
            report["before_open"] = _snapshot(page)
            page.screenshot(path=str(output_dir / "01-before-open.png"), full_page=False)

            try:
                resolved = open_location_selector(page)
                report["selector_opened"] = True
                report["opener_source"] = resolved.source
                report["visible_location_before_open"] = resolved.visible_location
            except LocationControlResolutionError as exc:
                report["errors"].append(
                    {
                        "stage": "open_selector",
                        "reason": str(exc),
                        "diagnostic": dict(getattr(exc, "diagnostic", {}) or {}),
                    }
                )

            page.wait_for_timeout(3_000)
            report["after_open"] = _snapshot(page)
            page.screenshot(path=str(output_dir / "02-after-open.png"), full_page=False)
        except Exception as exc:
            report["errors"].append(
                {"stage": "runtime", "reason": f"{exc.__class__.__name__}: {str(exc)[:240]}"}
            )
        finally:
            report["network"] = {
                "requests": requests[:500],
                "responses": responses[:500],
                "request_count": len(requests),
                "response_count": len(responses),
            }
            context.close()
            browser.close()

    (output_dir / "radiography.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = run()
    after = report.get("after_open") if isinstance(report.get("after_open"), dict) else {}
    dom = after.get("dom") if isinstance(after, dict) and isinstance(after.get("dom"), dict) else {}
    summary = {
        "selector_opened": report.get("selector_opened"),
        "target_exact_count": len(dom.get("target_exact", []) or []),
        "target_contains_count": len(dom.get("target_contains", []) or []),
        "visible_button_count": len(dom.get("visible_buttons", []) or []),
        "errors": report.get("errors", []),
        "authority": False,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
