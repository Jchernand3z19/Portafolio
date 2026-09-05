from __future__ import annotations

import contextlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}/"
SAMPLE_PATH = ROOT / "precios-supermercados-sps" / "portfolio" / "sample-data.json"
SAFE_SAMPLE_SCHEMA = "precios-sps-safe-portfolio-sample/v1"
SAFE_POLICY = "fail_closed_strong_identity_and_commercial_consistency"


def wait_for_server(timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with contextlib.closing(socket.socket()) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((HOST, PORT)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("Local portfolio server did not start")


def local_only(context: BrowserContext) -> None:
    def route_request(route):
        if route.request.url.startswith(BASE_URL):
            route.continue_()
        else:
            route.abort()

    context.route("**/*", route_request)


def attach_runtime_guards(page: Page) -> tuple[list[str], list[str]]:
    page_errors: list[str] = []
    bad_local_responses: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    def record_response(response):
        if response.url.startswith(BASE_URL) and response.status >= 400:
            bad_local_responses.append(f"{response.status} {response.url}")

    page.on("response", record_response)
    return page_errors, bad_local_responses


def load_public_sample() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def public_sample_is_published() -> bool:
    sample = load_public_sample()
    return (
        sample.get("schema") == SAFE_SAMPLE_SCHEMA
        and sample.get("comparison_policy") == SAFE_POLICY
        and isinstance(sample.get("rows"), list)
        and sample.get("row_count") == len(sample["rows"])
        and bool(sample["rows"])
    )


def wait_for_portfolio(page: Page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#portfolio-language-switcher")
    page.wait_for_selector("#proyectos .price-card")
    page.wait_for_selector("#proyectos .mw-card")
    page.wait_for_function(
        """() => Boolean(
            document.querySelector('#proyectos .price-card')?.dataset.projectPosition &&
            document.querySelector('#proyectos .mw-card')?.dataset.projectPosition
        )"""
    )


def assert_no_global_overflow(page: Page) -> None:
    metrics = page.evaluate(
        """() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            bodyWidth: document.body.scrollWidth
        })"""
    )
    assert metrics["scrollWidth"] <= metrics["clientWidth"] + 1, metrics
    assert metrics["bodyWidth"] <= metrics["clientWidth"] + 1, metrics


def assert_project_order(page: Page) -> None:
    cards = page.locator("#proyectos .projects-grid > [data-portfolio-project]")
    assert cards.count() == 2
    assert cards.nth(0).get_attribute("data-portfolio-project") == "precios-supermercados"
    assert cards.nth(1).get_attribute("data-portfolio-project") == "mundial-2026"


def assert_price_evidence(dialog) -> None:
    proof = dialog.locator(".price-proof")
    assert proof.count() == 1
    proof_text = proof.inner_text()
    assert "Comisariato Los Andes" in proof_text
    assert "6,646" in proof_text
    assert "120" in proof_text
    assert "9920279680" in proof_text
    assert proof.locator('a[href="https://comisariatolosandes.com/"]').count() == 1
    assert proof.locator('a[href*="reports/comisariato-los-andes/2026-09-04-full"]').count() == 1
    assert proof.locator('a[href*="src/precios_supermercados"]').count() == 1


def assert_comparison_state(dialog) -> None:
    section = dialog.locator("#price-sample-title").locator("xpath=../..")
    assert "strong identity" in section.locator("#price-sample-title").inner_text().lower()
    assert section.locator('[data-price-ranking-legend]').count() == 0
    note = section.locator(".price-note")
    table_wrap = section.locator(".price-table-wrap")

    if public_sample_is_published():
        sample = load_public_sample()
        table_wrap.wait_for(state="visible", timeout=5000)
        assert note.get_attribute("data-comparison-safety") == "verified-strong-identity"
        rows = table_wrap.locator("tbody tr")
        assert rows.count() == sample["row_count"]
        first = sample["rows"][0]
        table_text = table_wrap.inner_text()
        assert first["canonical_gtin"] in table_text
        assert "La Colonia" in table_text
        assert "Walmart" in table_text
        for offer in first["offers"]:
            assert offer["source_name"] in table_text
    else:
        assert table_wrap.is_hidden()
        assert note.get_attribute("data-comparison-safety") == "fail-closed"
        text = note.inner_text().lower()
        assert "fail-closed" in text
        assert "passion jaguar" in text
        assert "passion especial" in text


def desktop_flow(browser: Browser) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    local_only(context)
    page = context.new_page()
    page_errors, bad_local_responses = attach_runtime_guards(page)
    wait_for_portfolio(page)

    assert page.locator("html").get_attribute("lang") == "es"
    assert page.locator("#nav-links").get_by_text("Inicio", exact=True).count() == 1
    assert_project_order(page)
    card = page.locator("#proyectos .price-card")
    assert "Monitoreo automatizado de precios" in card.locator("h3").inner_text()
    assert "Web Scraping" in card.inner_text()
    assert "Playwright" in card.inner_text()
    assert card.get_attribute("data-project-position") == "PROYECTO PRINCIPAL · 01"
    assert page.locator("#proyectos .mw-card").get_attribute("data-project-position") == "PROYECTO · 02"
    assert page.locator("#mw-view .mw-kicker").count() == 0
    assert_no_global_overflow(page)

    page.locator('[data-locale="en"]').click()
    assert page.locator("html").get_attribute("lang") == "en"
    assert page.locator("#nav-links").get_by_text("Home", exact=True).count() == 1
    assert page.evaluate("localStorage.getItem('portfolio.locale.v1')") == "en"
    assert "Automated grocery price monitoring" in page.locator("#proyectos .price-card h3").inner_text()
    assert "Web Scraping" in page.locator("#proyectos .price-card").inner_text()
    assert "World Cup 2026" in page.locator("#proyectos .mw-card h3").inner_text()
    assert page.locator("#proyectos .price-card").get_attribute("data-project-position") == "FEATURED PROJECT · 01"
    assert page.locator("#proyectos .mw-card").get_attribute("data-project-position") == "PROJECT · 02"
    assert page.locator("#mw-view .mw-kicker").count() == 0
    assert_project_order(page)

    opener = page.locator("#proyectos .price-card [data-price-open]").last
    opener.click()
    dialog = page.locator("#price-project-view")
    assert dialog.evaluate("element => element.open") is True
    assert dialog.locator("#price-title").inner_text() == "Grocery prices collected from the web"
    assert "Web Scraping" in dialog.locator("#price-flow-title").locator("xpath=../..").inner_text()
    assert_price_evidence(dialog)
    assert_comparison_state(dialog)
    assert dialog.locator("#price-quality-title").count() == 0
    assert dialog.locator("#price-cap-title").count() == 1
    assert dialog.locator("#price-value-title").count() == 1
    assert page.locator(":focus").get_attribute("data-price-close") is not None
    page.keyboard.press("Escape")
    assert dialog.evaluate("element => element.open") is False
    assert page.locator(":focus").get_attribute("data-price-open") is not None

    page.locator("#mw-open").click()
    mundial = page.locator("#mw-view")
    assert mundial.is_visible()
    assert "World Cup 2026" in mundial.locator("#mw-title").inner_text()
    page.wait_for_function("() => document.querySelector('#mw-view .mw-kicker') === null")
    assert mundial.locator(".mw-kicker").count() == 0
    assert page.locator(":focus").get_attribute("id") == "mw-close"
    page.keyboard.press("Escape")
    assert mundial.is_hidden()
    assert page.locator(":focus").get_attribute("id") == "mw-open"

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#proyectos .price-card")
    page.wait_for_function("() => Boolean(document.querySelector('#proyectos .price-card')?.dataset.projectPosition)")
    assert page.locator("html").get_attribute("lang") == "en"
    assert page.locator("#nav-links").get_by_text("Home", exact=True).count() == 1
    assert_project_order(page)

    page.locator('[data-locale="es"]').click()
    assert page.locator("html").get_attribute("lang") == "es"
    assert page.locator("#nav-links").get_by_text("Inicio", exact=True).count() == 1

    page.evaluate("localStorage.setItem('portfolio.locale.v1', 'invalid-locale')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#portfolio-language-switcher")
    page.wait_for_function("() => Boolean(document.querySelector('#proyectos .price-card')?.dataset.projectPosition)")
    assert page.locator("html").get_attribute("lang") == "es"
    assert_project_order(page)

    assert page_errors == [], page_errors
    assert bad_local_responses == [], bad_local_responses
    context.close()


def storage_blocked_flow(browser: Browser) -> None:
    context = browser.new_context(viewport={"width": 1024, "height": 768})
    local_only(context)
    context.add_init_script(
        """
        Object.defineProperty(Storage.prototype, 'getItem', {
          configurable: true,
          value() { throw new DOMException('Storage blocked', 'SecurityError'); }
        });
        Object.defineProperty(Storage.prototype, 'setItem', {
          configurable: true,
          value() { throw new DOMException('Storage blocked', 'SecurityError'); }
        });
        """
    )
    page = context.new_page()
    page_errors, bad_local_responses = attach_runtime_guards(page)
    wait_for_portfolio(page)
    assert page.locator("html").get_attribute("lang") == "es"
    assert_project_order(page)
    page.locator('[data-locale="en"]').click()
    assert page.locator("html").get_attribute("lang") == "en"
    assert page_errors == [], page_errors
    assert bad_local_responses == [], bad_local_responses
    context.close()


def responsive_flow(browser: Browser, width: int, height: int) -> None:
    context = browser.new_context(viewport={"width": width, "height": height})
    local_only(context)
    page = context.new_page()
    page_errors, bad_local_responses = attach_runtime_guards(page)
    wait_for_portfolio(page)
    assert_project_order(page)
    assert_no_global_overflow(page)

    if width <= 767:
        toggle = page.locator("#menu-toggle")
        assert toggle.is_visible()
        toggle.click()
        assert toggle.get_attribute("aria-expanded") == "true"
        page.locator("#nav-links a").first.click()
        assert toggle.get_attribute("aria-expanded") == "false"

        page.locator('[data-locale="en"]').click()
        assert page.locator("html").get_attribute("lang") == "en"
        assert_no_global_overflow(page)

        page.locator("#proyectos .price-card [data-price-open]").first.click()
        dialog = page.locator("#price-project-view")
        assert dialog.evaluate("element => element.open") is True
        rect = dialog.bounding_box()
        assert rect is not None and rect["width"] <= width + 1, rect
        assert_comparison_state(dialog)
        assert_no_global_overflow(page)
        page.keyboard.press("Escape")
    else:
        cards = page.locator("#proyectos .projects-grid > [data-portfolio-project]")
        first = cards.nth(0).bounding_box()
        second = cards.nth(1).bounding_box()
        assert first is not None and second is not None
        assert abs(first["x"] - second["x"]) < 8, (first, second)
        assert abs(first["width"] - second["width"]) < 8, (first, second)
        assert second["y"] >= first["y"] + first["height"] + 24, (first, second)

    assert page_errors == [], page_errors
    assert bad_local_responses == [], bad_local_responses
    context.close()


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
            try:
                desktop_flow(browser)
                storage_blocked_flow(browser)
                responsive_flow(browser, 320, 720)
                responsive_flow(browser, 390, 844)
                responsive_flow(browser, 768, 900)
                responsive_flow(browser, 1024, 900)
            finally:
                browser.close()
    finally:
        server.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            server.wait(timeout=5)
        if server.poll() is None:
            server.kill()

    print("PORTFOLIO_FRONTEND_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
