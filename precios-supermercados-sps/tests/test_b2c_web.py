from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "b2c" / "app.js"
HTML = ROOT / "b2c" / "index.html"
CSS = ROOT / "b2c" / "styles.css"


def test_b2c_static_contract_is_mobile_first_and_safe() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    js = APP.read_text(encoding="utf-8")

    assert 'name="viewport"' in html
    assert 'id="product-search"' in html
    assert 'id="cart-panel"' in html
    assert 'type="module" src="app.js"' in html
    assert "rpi-consumer-mart/v2" in js
    assert "localStorage" in js
    assert ".textContent" in js
    assert ".innerHTML" not in js
    assert "eval(" not in js
    assert "* 1.15" not in js and "*1.15" not in js
    assert "min-height:44px" in css
    assert "@media(min-width:700px)" in css
    assert "@media(min-width:1020px)" in css


def test_b2c_core_logic_uses_authoritative_offers_integer_money_and_local_persistence(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node_not_available_for_b2c_module_contract")

    module = tmp_path / "app.mjs"
    module.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")
    script = r'''
import assert from "node:assert/strict";
const app = await import(process.argv[1]);

assert.equal(app.moneyToMinor("35.50"), 3550);
assert.equal(app.moneyToMinor("35.5"), 3550);
assert.equal(app.moneyToMinor("35.555"), null);
assert.equal(app.moneyToMinor(35.5), null);

const p1 = {
  canonical_product_id: "milk",
  recommended_source_product_ids: ["w:1", "c:1"],
  offers: [
    {source_product_id:"w:1", supermarket_id:"walmart", location_id:"walmart_sps", product_name:"Leche Sula Entera", category:"Lácteos", product_type:"Leche", brand:"Sula", presentation:"1 L", current_price:"35.50", reported_regular_price:"40.00", is_promotion:true, availability:"in_stock", observed_at:"2026-09-08T10:00:00Z", freshness_status:"FRESH"},
    {source_product_id:"c:1", supermarket_id:"la_colonia", location_id:"la_colonia_sps", product_name:"Leche Sula Entera", category:"Lácteos", product_type:"Leche", brand:"Sula", presentation:"1 L", current_price:"35.50", reported_regular_price:null, is_promotion:false, availability:"in_stock", observed_at:"2026-09-08T10:00:00Z", freshness_status:"FRESH"},
  ],
};
const p2 = {canonical_product_id:"rice", recommended_source_product_ids:["c:2"], offers:[{source_product_id:"c:2", supermarket_id:"la_colonia", location_id:"la_colonia_sps", product_name:"Arroz Premium", category:"Granos", product_type:"Arroz", brand:"Marca X", presentation:"5 lb", current_price:"118.00", reported_regular_price:null, is_promotion:false, availability:"in_stock", observed_at:"2026-09-08T09:00:00Z", freshness_status:"STALE"}]};

assert.deepEqual(app.searchProducts([p1,p2], "LECHE sula"), [p1]);
assert.deepEqual(app.searchProducts([p1,p2], "arroz 5 lb"), [p2]);
assert.deepEqual([...app.recommendedIds(p1, "COMPARABLE")].sort(), ["c:1","w:1"]);
assert.equal(app.recommendedIds(p1, "INSUFFICIENT_FRESH_COMPARISON").size, 0);

const milk = app.lineFromOffer(p1, p1.offers[0], 2);
assert.equal(milk.unit_price_minor, 3550);
assert.equal(milk.reported_regular_price_minor, 4000);
assert.equal(milk.is_promotion, true);
const rice = app.lineFromOffer(p2, p2.offers[0], 1);
let cart = app.selectOffer([], milk);
cart = app.selectOffer(cart, rice);
let summary = app.cartSummary(cart);
assert.equal(summary.products, 2);
assert.equal(summary.units, 3);
assert.equal(summary.retailer_count, 2);
assert.equal(summary.stale, 1);
assert.equal(summary.grand_total_minor, 18900); // 2*35.50 + 118.00; no inferred tax, regular price ignored.
assert.equal(summary.retailers.get("walmart").subtotal_minor, 7100);
assert.equal(summary.retailers.get("la_colonia").subtotal_minor, 11800);

const alternateMilk = app.lineFromOffer(p1, p1.offers[1], 1);
cart = app.selectOffer(cart, alternateMilk); // explicit user selection changes retailer, never background optimization.
const selected = cart.find((line) => line.canonical_product_id === "milk");
assert.equal(selected.source_product_id, "c:1");
assert.equal(selected.quantity, 2);

const memory = new Map();
const storage = {setItem:(k,v)=>memory.set(k,v), getItem:(k)=>memory.get(k) ?? null};
app.saveCart(storage, cart);
const restored = app.loadCart(storage);
assert.deepEqual(restored, cart);
restored[0].invalid = true;
summary = app.cartSummary(restored);
assert.equal(summary.incomplete, 1);
assert.equal(summary.grand_total_minor, null);
'''
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script, module.as_uri()],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
