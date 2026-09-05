from __future__ import annotations

import contextlib
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8766
BASE_URL = f"http://{HOST}:{PORT}/"


def wait_for_server(timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with contextlib.closing(socket.socket()) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((HOST, PORT)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("Local portfolio server did not start")


def main() -> int:
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", HOST],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.route(
                "**/*",
                lambda route: route.continue_() if route.request.url.startswith(BASE_URL) else route.abort(),
            )
            page = context.new_page()
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_selector("#proyectos .price-card")
            page.wait_for_selector("#proyectos .mw-card")
            page.wait_for_function(
                """() => Boolean(
                    document.querySelector('#price-project-view')?.classList.contains('portfolio-detail-standard') &&
                    document.querySelector('#mw-view')?.classList.contains('portfolio-detail-standard')
                )"""
            )

            signal_values = page.locator("#proyectos .price-card .price-card__signal strong").all_inner_texts()
            assert signal_values == ["6", "11", "56K+", "108K+"], signal_values

            # Price detail uses the same full-screen secondary-page shell.
            page.locator("#proyectos .price-card [data-price-open]").first.click()
            price = page.locator("#price-project-view")
            assert price.evaluate("el => el.open") is True
            price_box = price.bounding_box()
            assert price_box is not None
            assert abs(price_box["width"] - 1440) <= 2, price_box
            assert abs(price_box["height"] - 900) <= 2, price_box
            assert price.locator(".portfolio-detail__breadcrumb").count() == 1
            assert "PROYECTO PRINCIPAL · 01" in price.locator(".portfolio-detail__meta").inner_text()
            assert price.get_by_text("Ver resultado", exact=True).count() == 1
            assert price.get_by_text("Ver código", exact=True).count() >= 1

            assert price.locator("#price-scale-title").inner_text() == "Cobertura productiva actual"
            coverage = price.locator(".price-coverage-table")
            assert coverage.count() == 1
            assert coverage.locator("tbody tr").count() == 6
            coverage_text = coverage.inner_text()
            for chain in (
                "La Colonia",
                "Supermercados Colonial",
                "Walmart",
                "PriceSmart",
                "Comisariato Los Andes",
                "Paiz",
            ):
                assert chain in coverage_text
            assert "SPS 6603 · Florencia 6602" in coverage_text
            assert "TGU Multiplaza · TGU Próceres" in coverage_text

            # Cross-source rows are withheld until they pass the strong-identity gate.
            assert price.locator("#price-sample-title").inner_text() == "Comparaciones cross-source con identidad fuerte"
            comparison_wrap = price.locator(".price-table-wrap")
            assert comparison_wrap.is_hidden()
            assert comparison_wrap.get_attribute("aria-hidden") == "true"
            assert price.locator("[data-price-ranking-legend]").count() == 0
            safety_note = price.locator("#price-sample-title").locator("xpath=../..").locator(".price-note")
            assert safety_note.get_attribute("data-comparison-safety") == "fail-closed"
            safety_text = safety_note.inner_text()
            assert "Passion Jaguar" in safety_text
            assert "Passion Especial" in safety_text

            price_shell = price.locator(".price-view__body").bounding_box()
            price_top = price.locator(".price-view__top").bounding_box()
            price_title_size = price.locator("#price-title").evaluate(
                "el => parseFloat(getComputedStyle(el).fontSize)"
            )
            price_section_size = price.locator(".price-section__head h3").first.evaluate(
                "el => parseFloat(getComputedStyle(el).fontSize)"
            )
            page.keyboard.press("Escape")

            # Mundial detail must use the same shell, rhythm and vocabulary.
            page.locator("#mw-open").click()
            mundial = page.locator("#mw-view")
            assert mundial.is_visible()
            mundial_box = mundial.bounding_box()
            assert mundial_box is not None
            assert abs(mundial_box["width"] - 1440) <= 2, mundial_box
            assert abs(mundial_box["height"] - 900) <= 2, mundial_box
            assert mundial.locator(".portfolio-detail__breadcrumb").count() == 1
            assert "PROYECTO · 02" in mundial.locator(".portfolio-detail__meta").inner_text()
            assert mundial.get_by_text("Ver resultado", exact=True).count() == 1
            assert mundial.get_by_text("Ver código", exact=True).count() == 1
            mundial_shell = mundial.locator(".mw-shell").bounding_box()
            mundial_top = mundial.locator(".mw-top").bounding_box()
            mundial_title_size = mundial.locator("#mw-title").evaluate(
                "el => parseFloat(getComputedStyle(el).fontSize)"
            )
            mundial_section_size = mundial.locator(".mw-section__head h3").first.evaluate(
                "el => parseFloat(getComputedStyle(el).fontSize)"
            )

            assert price_shell is not None and mundial_shell is not None
            assert abs(price_shell["width"] - mundial_shell["width"]) <= 2, (price_shell, mundial_shell)
            assert price_top is not None and mundial_top is not None
            assert abs(price_top["height"] - mundial_top["height"]) <= 2, (price_top, mundial_top)
            assert abs(price_title_size - mundial_title_size) <= 1, (price_title_size, mundial_title_size)
            assert abs(price_section_size - mundial_section_size) <= 1, (price_section_size, mundial_section_size)

            page.keyboard.press("Escape")
            context.close()
            browser.close()
    finally:
        server.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            server.wait(timeout=5)
        if server.poll() is None:
            server.kill()

    print("PROJECT_DETAIL_STANDARD_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())