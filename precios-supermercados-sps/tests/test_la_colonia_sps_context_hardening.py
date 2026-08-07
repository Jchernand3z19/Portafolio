from __future__ import annotations

import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

import precios_supermercados.diagnostics.la_colonia_sps_context_diagnostic as diag

SYNTHETIC_ID = "SPS-context-and-root-facets-777"
DOM = Path(__file__).parent / "fixtures/la_colonia_sps_context_diagnostic.html"


def _live_html(*, city=True, stores=1, fetch_script="") -> str:
    city_html = '<select aria-label="Ciudad"><option role="option" aria-label="San Pedro Sula">San Pedro Sula</option></select>' if city else '<select aria-label="Ciudad"><option>Tegucigalpa</option></select>'
    store_html = "".join('<button role="option" aria-label="Plaza Pedregal">Plaza Pedregal</button>' for _ in range(stores))
    return f'''<!doctype html><html><body>
    <button role="button" aria-label="Selecciona tu tienda">Selecciona tu tienda</button>
    {city_html}<div role="listbox">{store_html}</div>{fetch_script}</body></html>'''


@pytest.fixture
def local_site():
    state = {"home": "<html><body>empty</body></html>", "catalog": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = state["catalog"] if self.path.startswith("/supermercado") and state["catalog"] is not None else state["home"]
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture
def browser_runtime():
    with sync_playwright() as pw:
        browser, executable = diag.launch_compatible_chromium(pw)
        context = browser.new_context()
        events: list[dict] = []
        diag.install_local_network_guard(context, events=events)
        page = context.new_page()
        try:
            yield browser, context, page, events, executable
        finally:
            context.close()
            browser.close()


def test_active_allow_list_is_empty():
    assert diag.ACTIVE_AUTHORIZATION_IDS == frozenset()


@pytest.mark.parametrize("value, message", [
    ("SPS-context-and-root-facets-001", "consumido"),
    ("SPS-context-and-root-facets-002", "no autorizado"),
    ("SPS-context-and-root-facets-999", "no autorizado"),
    ("invalid", "formato"),
])
def test_authorization_rejections(value: str, message: str):
    with pytest.raises(diag.DiagnosticSafetyError, match=message):
        diag.validate_live_authorization(live=True, authorization_id=value)


def test_allow_list_functionality_uses_only_injected_synthetic_id():
    assert diag.validate_live_authorization(
        live=True, authorization_id=SYNTHETIC_ID, active_ids={SYNTHETIC_ID}
    ) == "live"


def test_live_without_authorization_is_rejected():
    with pytest.raises(diag.DiagnosticSafetyError):
        diag.validate_live_authorization(live=True, authorization_id=None)


def test_offline_with_authorization_is_rejected():
    with pytest.raises(diag.DiagnosticSafetyError):
        diag.validate_live_authorization(live=False, authorization_id=SYNTHETIC_ID)


def test_error_sanitizer_removes_sensitive_values():
    error = RuntimeError(
        "Authorization: Bearer abcdefghijkl Cookie=secret token=opaque123 "
        "orderFormId=order-123 address=Street42 coordinates=15.50000,-88.00000 "
        "https://synthetic.invalid/x?token=secret&operationName=facets"
    )
    text = diag.sanitize_error(error)
    for secret in ("abcdefghijkl", "secret", "opaque123", "order-123", "Street42", "15.50000", "-88.00000"):
        assert secret not in text
    assert "redacted" in text
    assert "operationName=facets" in text


def test_browser_runtime_is_real(browser_runtime):
    browser, context, page, events, executable = browser_runtime
    assert browser.is_connected()
    assert Path(executable).exists()
    assert context is not None


def test_browser_can_close_cleanly():
    with sync_playwright() as pw:
        browser, _ = diag.launch_compatible_chromium(pw)
        assert browser.is_connected()
        browser.close()
        assert browser.is_connected() is False


def test_page_set_content_and_role_locator(browser_runtime):
    _, _, page, _, _ = browser_runtime
    page.set_content(DOM.read_text(encoding="utf-8"))
    assert page.get_by_role("button", name=re.compile("Selecciona tu tienda", re.I)).count() == 1
    locator = diag._pw_unique(page, diag.store_selector_plan(), "Selecciona tu tienda")
    diag._pw_activate(locator, "Selecciona tu tienda")


def test_real_select_option_and_store_button(browser_runtime):
    _, _, page, _, _ = browser_runtime
    page.set_content(DOM.read_text(encoding="utf-8"))
    city = diag._pw_unique(page, diag.city_selector_plan(), "San Pedro Sula")
    diag._pw_activate(city, "San Pedro Sula")
    assert page.locator("select#city").input_value() == "San Pedro Sula"
    store = diag._pw_unique(page, diag.store_option_plan(), "Plaza Pedregal")
    diag._pw_activate(store, "Plaza Pedregal")


def test_real_browser_missing_and_ambiguous_targets(browser_runtime):
    _, _, page, _, _ = browser_runtime
    page.set_content("<button>Otro</button>")
    with pytest.raises(diag.DomTargetNotFound):
        diag._pw_unique(page, diag.city_selector_plan(), "San Pedro Sula")
    page.set_content('<button role="option" aria-label="Plaza Pedregal">A</button><button role="option" aria-label="Plaza Pedregal">B</button>')
    with pytest.raises(diag.AmbiguousDomTarget):
        diag._pw_unique(page, diag.store_option_plan(), "Plaza Pedregal")


@pytest.mark.skipif(os.environ.get("CI") != "true", reason="loopback navigation is validated on GitHub runner")
def test_storage_and_cookie_observation_is_local(browser_runtime, local_site):
    _, context, page, _, _ = browser_runtime
    _, base_url = local_site
    page.goto(base_url)
    page.evaluate("localStorage.setItem('regionId','synthetic-region'); sessionStorage.setItem('orderFormId','synthetic-order')")
    context.add_cookies([{"name":"vtex_session","value":"synthetic-session","url":base_url}])
    local, session = diag._storage(page)
    cookies = diag._cookies(context)
    assert local["regionId"] == "synthetic-region"
    assert session["orderFormId"] == "synthetic-order"
    assert cookies["vtex_session"] == "synthetic-session"


def test_network_interception_fulfills_synthetic_and_blocks_external(browser_runtime):
    _, _, page, events, _ = browser_runtime
    page.set_content("<html><body>network guard</body></html>")
    result = page.evaluate("fetch('https://synthetic.invalid/api').then(r => r.json())")
    assert result == {"synthetic": True}
    blocked = page.evaluate("fetch('https://www.lacolonia.com/forbidden').then(() => false).catch(() => true)")
    assert blocked is True
    assert any(e["action"] == "fulfilled_locally" and "synthetic.invalid" in e["url"] for e in events)
    assert any(e["action"] == "blocked_before_network" and "lacolonia.com" in e["url"] for e in events)


def test_custom_combobox_path_with_real_browser(browser_runtime):
    _, _, page, _, _ = browser_runtime
    page.set_content('<div role="combobox" aria-label="Plaza Pedregal">Plaza Pedregal</div>')
    plan = ({"kind":"combobox", "name":"Plaza Pedregal"},)
    locator = diag._pw_unique(page, plan, "Plaza Pedregal")
    assert locator.count() == 1


@pytest.mark.skipif(os.environ.get("CI") != "true", reason="run_live local scenario is validated on GitHub runner")
@pytest.mark.parametrize(
    "html,budget,expected",
    [
        ("<html><body>missing</body></html>", diag.DiagnosticBudget(), "dom_target_not_found"),
        (_live_html(city=False), diag.DiagnosticBudget(), "dom_target_not_found"),
        (_live_html(stores=2), diag.DiagnosticBudget(), "ambiguous_dom_target"),
        (_live_html(), diag.DiagnosticBudget(), "product_search_not_observed"),
        (_live_html(), diag.DiagnosticBudget(max_logical_requests=1), "logical_request_budget_exceeded"),
    ],
)
def test_failure_artifact_is_persisted(monkeypatch, tmp_path: Path, local_site, html: str, budget, expected: str):
    state, base_url = local_site
    state["home"] = html
    state["catalog"] = html
    monkeypatch.setattr(diag, "TARGET_URL", base_url)
    output = tmp_path / f"{expected}.json"
    report = diag.run_live(
        authorization_id=SYNTHETIC_ID,
        active_ids={SYNTHETIC_ID},
        output_path=output,
        budget=budget,
        _network_policy="local_only",
    )
    assert report.completed_at
    assert report.stop_reason == expected
    assert report.errors
    assert report.logical_requests >= 0
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["stop_reason"] == expected
    assert persisted["completed_at"]
    assert persisted["errors"]
    serialized = json.dumps(persisted)
    assert "Bearer " not in serialized
    assert "synthetic-session" not in serialized


@pytest.mark.skipif(os.environ.get("CI") != "true", reason="run_live local scenario is validated on GitHub runner")
def test_facets_not_observed_failure_artifact(monkeypatch, tmp_path: Path, local_site):
    script = '''<script>
      fetch("https://synthetic.invalid/graphql?operationName=productSearchV3", {
        method:"POST", headers:{"content-type":"application/json"},
        body:JSON.stringify({operationName:"productSearchV3", query:"query productSearchV3 { productSearch { products { productId } } }", variables:{from:0,to:4}})
      }).catch(()=>{});
    </script>'''
    html = _live_html(fetch_script=script)
    state, base_url = local_site
    state["home"] = _live_html()
    state["catalog"] = html
    monkeypatch.setattr(diag, "TARGET_URL", base_url)
    output = tmp_path / "facets.json"
    report = diag.run_live(
        authorization_id=SYNTHETIC_ID, active_ids={SYNTHETIC_ID}, output_path=output,
        _network_policy="local_only",
    )
    assert report.stop_reason == "facets_not_observed"
    assert report.completed_at
    assert output.exists()


def test_failure_before_target_navigation_is_not_consumption_eligible(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(diag, "launch_compatible_chromium", lambda pw: (_ for _ in ()).throw(diag.DiagnosticSafetyError("launch failed")))
    report = diag.run_live(
        authorization_id=SYNTHETIC_ID, active_ids={SYNTHETIC_ID}, output_path=tmp_path / "before.json"
    )
    assert report.authorization_checked is True
    assert report.target_navigation_started is False
    assert report.authorization_consumption_eligible is False


@pytest.mark.skipif(os.environ.get("CI") != "true", reason="run_live local scenario is validated on GitHub runner")
def test_failure_after_target_navigation_is_consumption_eligible(monkeypatch, tmp_path: Path, local_site):
    state, base_url = local_site
    state["home"] = "<html>missing selector</html>"
    monkeypatch.setattr(diag, "TARGET_URL", base_url)
    report = diag.run_live(
        authorization_id=SYNTHETIC_ID, active_ids={SYNTHETIC_ID}, output_path=tmp_path / "after.json",
        _network_policy="local_only",
    )
    assert report.target_navigation_started is True
    assert report.authorization_consumption_eligible is True
    assert report.target_navigation_completed is True


def test_default_live_allow_list_empty_never_starts_browser(tmp_path: Path):
    output = tmp_path / "inactive.json"
    report = diag.run_live(authorization_id="SPS-context-and-root-facets-002", output_path=output)
    assert report.authorization_checked is True
    assert report.browser_started is False
    assert report.target_navigation_started is False
    assert report.stop_reason == "authorization_rejected"
    assert "no autorizado" in report.errors[0]
    assert output.exists()


def test_safe_replay_headers_do_not_invent_context_headers():
    headers = {
        "accept":"application/json", "content-type":"application/json", "x-vtex-locale":"es-HN",
        "cookie":"vtex_session=secret", "authorization":"Bearer secret",
        "binding":"unknown", "salesChannel":"99", "regionId":"opaque",
    }
    safe = diag._safe_replay_headers(headers)
    assert safe == {"accept":"application/json", "content-type":"application/json", "x-vtex-locale":"es-HN"}
