from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "b2c" / "app.js"
HTML = ROOT / "b2c" / "index.html"
CSS = ROOT / "b2c" / "styles.css"


def test_basket_analysis_surface_is_responsive_and_does_not_auto_apply() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    js = APP.read_text(encoding="utf-8")

    assert 'id="basket-analysis"' in html
    assert 'id="basket-analysis-content"' in html
    assert "Ningún escenario modifica tu lista" in html
    assert ".scenario-grid" in css
    assert ".optimized-scenario" in css
    assert "Requiere visitar" in js
    assert "no se imputa cero" in js
    assert "Mínimo 30d" in js
    assert "Máximo 30d" in js
    assert "applyOptimized" not in js
    assert "innerHTML" not in js


def test_basket_analysis_uses_only_python_recommendations_and_preserves_missing_as_incomplete(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node_not_available_for_b2c_basket_contract")

    module = tmp_path / "app.mjs"
    module.write_text(APP.read_text(encoding="utf-8"), encoding="utf-8")
    script = r'''
import assert from "node:assert/strict";
const app = await import(process.argv[1]);

function offer(id, retailer, productName, price, {best=false, delta="1.00", pct="10.00"}={}) {
  return {
    source_product_id:id,
    supermarket_id:retailer,
    location_id:`${retailer}_sps`,
    category:"Canasta",
    product_type:"Producto",
    product_name:productName,
    brand:"Marca",
    variant:null,
    presentation:"1 u",
    current_price:price,
    reported_regular_price:null,
    is_promotion:false,
    availability:"in_stock",
    observed_at:"2026-09-08T12:00:00Z",
    freshness_status:"FRESH",
    rank:best ? 1 : 2,
    is_best_price:best,
    difference_vs_best_abs:best ? "0.00" : delta,
    difference_vs_best_pct:best ? "0.00" : pct,
    historical_summary:null,
  };
}

const milk = {
  canonical_product_id:"milk",
  recommended_source_product_ids:["b:milk"],
  offers:[
    offer("a:milk", "a", "Leche", "10.00", {delta:"1.00", pct:"11.11"}),
    offer("b:milk", "b", "Leche", "9.00", {best:true}),
  ],
};
const bread = {
  canonical_product_id:"bread",
  recommended_source_product_ids:["a:bread"],
  offers:[
    offer("a:bread", "a", "Pan", "18.00", {best:true}),
    offer("b:bread", "b", "Pan", "20.00", {delta:"2.00", pct:"11.11"}),
  ],
};
const mart = {
  schema:"rpi-consumer-mart/v2",
  comparison_status:"COMPARABLE",
  products:[milk, bread],
};
assert.equal(app.consumerMartContractIsCompatible(mart), true);

const cart = [
  app.lineFromOffer(milk, milk.offers[0], 2),
  app.lineFromOffer(bread, bread.offers[1], 1),
];
const analysis = app.analyzeBasketOptions(cart, mart);
assert.equal(analysis.status, "AVAILABLE");
assert.equal(analysis.manual.grand_total_minor, 4000);
assert.equal(analysis.optimized.status, "COMPLETE");
assert.equal(analysis.optimized.total_minor, 3600);
assert.equal(analysis.optimized.savings_vs_manual_minor, 400);
assert.equal(analysis.optimized.retailer_count, 2);
assert.deepEqual(
  analysis.optimized.selected.map((line)=>line.source_product_id).sort(),
  ["a:bread", "b:milk"],
); // only IDs published by Python as recommended are eligible.
const byRetailer = Object.fromEntries(analysis.single_retailer.map((row)=>[row.supermarket_id,row]));
assert.equal(byRetailer.a.status, "COMPLETE");
assert.equal(byRetailer.a.total_minor, 3800);
assert.equal(byRetailer.b.status, "COMPLETE");
assert.equal(byRetailer.b.total_minor, 3800);

const tieMart = structuredClone(mart);
tieMart.products[0].offers[0].current_price = "9.00";
tieMart.products[0].offers[0].is_best_price = true;
tieMart.products[0].offers[0].rank = 1;
tieMart.products[0].offers[0].difference_vs_best_abs = "0.00";
tieMart.products[0].offers[0].difference_vs_best_pct = "0.00";
tieMart.products[0].recommended_source_product_ids = ["a:milk", "b:milk"];
const tieCart = [
  app.lineFromOffer(tieMart.products[0], tieMart.products[0].offers[0], 2),
  app.lineFromOffer(tieMart.products[1], tieMart.products[1].offers[1], 1),
];
const tieAnalysis = app.analyzeBasketOptions(tieCart, tieMart);
assert.equal(tieAnalysis.optimized.tie_product_count, 1);
assert.equal(tieAnalysis.optimized.selected.find((line)=>line.canonical_product_id === "milk").source_product_id, "a:milk");
assert.deepEqual(
  tieAnalysis.optimized.selected.find((line)=>line.canonical_product_id === "milk").tied_source_product_ids,
  ["a:milk", "b:milk"],
); // deterministic estimate, tie remains explicit.

const missingMart = structuredClone(mart);
missingMart.products[1].offers = missingMart.products[1].offers.filter((row)=>row.source_product_id !== "b:bread");
const cartAtA = [
  app.lineFromOffer(missingMart.products[0], missingMart.products[0].offers[0], 2),
  app.lineFromOffer(missingMart.products[1], missingMart.products[1].offers[0], 1),
];
const missingAnalysis = app.analyzeBasketOptions(cartAtA, missingMart);
const bOnly = missingAnalysis.single_retailer.find((row)=>row.supermarket_id === "b");
assert.equal(bOnly.status, "INCOMPLETE");
assert.equal(bOnly.covered_count, 1);
assert.equal(bOnly.missing_count, 1);
assert.equal(bOnly.total_minor, null); // missing product is never cost zero.

const blocked = structuredClone(mart);
blocked.comparison_status = "INSUFFICIENT_FRESH_COMPARISON";
for (const product of blocked.products) {
  product.recommended_source_product_ids = [];
  for (const row of product.offers) {
    row.difference_vs_best_abs = null;
    row.difference_vs_best_pct = null;
    row.is_best_price = false;
    row.rank = null;
  }
}
assert.equal(app.consumerMartContractIsCompatible(blocked), true);
const blockedAnalysis = app.analyzeBasketOptions(cart, blocked);
assert.equal(blockedAnalysis.status, "COMPARISON_BLOCKED");
assert.equal(blockedAnalysis.optimized, null);
assert.deepEqual(blockedAnalysis.single_retailer, []);

const changedMart = structuredClone(mart);
changedMart.products[0].offers[0].current_price = "11.00";
changedMart.products[0].offers[0].difference_vs_best_abs = "2.00";
changedMart.products[0].offers[0].difference_vs_best_pct = "22.22";
const refreshGate = app.analyzeBasketOptions(cart, changedMart);
assert.equal(refreshGate.status, "REFRESH_REQUIRED"); // explicit price refresh remains mandatory.
assert.equal(refreshGate.optimized, null);
'''
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script, module.as_uri()],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
