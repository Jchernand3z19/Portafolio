from __future__ import annotations

import contextlib
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


def wait_for_portfolio(page: Page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#portfolio-language-switcher")
    page.wait_for_selector("#proyectos .mw-card")
    page.wait_for_selector("#proyectos .price-card")


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


def desktop_flow(browser: Browser) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    local_only(context)
    page = context.new_page()
    page_errors, bad_local_responses = attach_runtime_guards(page)
    wait_for_portfolio(page)

    assert page.locator("html").get_attribute("lang") == "es"
    assert page.locator("#nav-links").get_by_text("Inicio", exact=True).count() == 1
    assert page.locator("#proyectos .projects-grid > [data-portfolio-project]").count() == 2
    assert "Precios de Supermercados" in page.locator("#proyectos .price-card h3").inner_text()
    assert_no_global_overflow(page)

    page.locator('[data-locale="en"]').click()
    assert page.locator("html").get_attribute("lang") == "en"
    assert page.locator("#nav-links").get_by_text("Home", exact=True).count() == 1
    assert page.evaluate("localStorage.getItem('portfolio.locale.v1')") == "en"
    assert "Grocery Price Data" in page.locator("#proyectos .price-card h3").inner_text()
    assert "World Cup 2026" in page.locator("#proyectos .mw-card h3").inner_text()

    opener = page.locator("#proyectos .price-card [data-price-open]").last
    opener.click()
    dialog = page.locator("#price-project-view")
    assert dialog.evaluate("element => element.open") is True
    assert dialog.locator("#price-title").inner_text() == "From scattered prices to useful information"
    sample_text = dialog.locator(".price-table tbody").inner_text()
    assert "Context 01" in sample_text
    assert "Contexto" not in sample_text
    assert page.locator(":focus").get_attribute("data-price-close") is not None
    page.keyboard.press("Escape")
    assert dialog.evaluate("element => element.open") is False
    assert page.locator(":focus").get_attribute("data-price-open") is not None

    page.locator("#mw-open").click()
    mundial = page.locator("#mw-view")
    assert mundial.is_visible()
    assert "World Cup 2026" in mundial.locator("#mw-title").inner_text()
    page.keyboard.press("Escape")
    assert mundial.is_hidden()

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#proyectos .price-card")
    assert page.locator("html").get_attribute("lang") == "en"
    assert page.locator("#nav-links").get_by_text("Home", exact=True).count() == 1

    page.locator('[data-locale="es"]').click()
    assert page.locator("html").get_attribute("lang") == "es"
    assert page.locator("#nav-links").get_by_text("Inicio", exact=True).count() == 1

    page.evaluate("localStorage.setItem('portfolio.locale.v1', 'invalid-locale')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#portfolio-language-switcher")
    assert page.locator("html").get_attribute("lang") == "es"

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
        page.keyboard.press("Escape")
    else:
        cards = page.locator("#proyectos .projects-grid > [data-portfolio-project]")
        assert cards.count() == 2
        first = cards.nth(0).bounding_box()
        second = cards.nth(1).bounding_box()
        assert first is not None and second is not None
        assert abs(first["x"] - second["x"]) < 8, (first, second)
        assert abs(first["width"] - second["width"]) < 8, (first, second)
        assert second["y"] >= first["y"] + first["height"], (first, second)

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
