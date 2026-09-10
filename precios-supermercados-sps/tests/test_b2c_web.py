from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "b2c" / "app.js"
CATALOG = ROOT / "b2c" / "catalog.js"
EXPORTS = ROOT / "b2c" / "exports.js"
HTML = ROOT / "b2c" / "index.html"
CSS = ROOT / "b2c" / "styles.css"


def run_module(tmp_path: Path, source: Path, script: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node_not_available_for_b2c_module_contract")
    module = tmp_path / f"{source.stem}.mjs"
    module.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script, module.as_uri()],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_b2c_static_contract_is_accessible_responsive_and_safe() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    js = APP.read_text(encoding="utf-8")
    catalog = CATALOG.read_text(encoding="utf-8")
    exports = EXPORTS.read_text(encoding="utf-8")

    for element_id in (
        "category-filter", "type-filter", "brand-filter", "presentation-filter",
        "product-search", "results", "batch-add", "update-confirmation",
        "cart-groups", "price-refresh", "basket-analysis", "export-csv", "export-pdf",
    ):
        assert f'id="{element_id}"' in html
    assert 'data-catalog-url="https://raw.githubusercontent.com/' in html
    assert 'type="module" src="app.js"' in html
    assert "Total estimado calculado con los precios públicos observados" in html
    assert "reported_regular_price" in js
    assert "historical_summary" in js
    assert "localStorage" in js
    assert 'input.type = "radio"' in js
    assert "Ningún escenario modifica tu lista" in html
    combined = js + catalog + exports
    assert ".innerHTML" not in combined
    assert "eval(" not in combined
    assert "* 1.15" not in combined and "*1.15" not in combined
    assert "shipping_fee" not in combined and "delivery_fee" not in combined
    assert "min-height:44px" in css
    assert ".product-cell{position:sticky" in css
    assert ".comparison-matrix tbody tr{display:grid" in css
    assert "@media(max-width:799px)" in css
    assert ".price-best" in css and ".price-highest" in css


def test_catalog_contract_filters_batch_totals_and_storage(tmp_path: Path) -> None:
    script = r'''
import assert from "node:assert/strict";
const c = await import(process.argv[1]);

const scope = c.RETAILERS.map(({supermarket_id,location_id})=>({supermarket_id,location_id}));
const manifest = {schema:"rpi-consumer-catalog-manifest/v3",catalog_schema:"rpi-consumer-catalog/v3",scope,files:[{path:"facets-sps.json",sha256:"a".repeat(64),bytes:10}],initial_payload:{request_count:2}};
assert.equal(c.manifestIsCompatible(manifest), true);
assert.equal(c.manifestIsCompatible({...manifest,scope:[...scope,{supermarket_id:"paiz",location_id:"paiz_sps"}]}), false);
assert.equal(c.manifestIsCompatible({...manifest,files:[{path:"https://evil.test/data.json",sha256:"a".repeat(64),bytes:10}]}), false);
assert.equal(c.moneyToMinor("35.50"), 3550);
assert.equal(c.moneyToMinor("35.555"), null);

const entries = [
  {row_id:"milk",product_name:"Leche Sula Entera",brand:"Sula",presentation:"1 L",partition:"catalog/a.json"},
  {row_id:"milk2",product_name:"Leche descremada",brand:"Dos Pinos",presentation:"1 L",partition:"catalog/b.json"},
  {row_id:"rice",product_name:"Arroz premium",brand:null,presentation:"5 lb",partition:"catalog/a.json"},
];
let reconciled = c.reconcileDependentFilters(entries,{query:"leche",brand:"Sula",presentation:"5 lb"});
assert.equal(reconciled.filter.presentation, "");
assert.deepEqual(reconciled.options.brands,["Dos Pinos","Sula"]);
assert.deepEqual(c.filterIndexEntries(entries,{query:"LECHE sula",brand:"",presentation:""}).map(x=>x.row_id),["milk"]);
assert.deepEqual(c.partitionPaths(entries),["catalog/a.json","catalog/b.json"]);
assert.equal(c.humanHistoricalPosition("historically_low"),"Mínimo de 90 días");

function offer(id, retailer, price, regular=null, promo=null) { return {source_product_id:id,supermarket_id:retailer,location_id:`${retailer}_sps`,current_price:price,reported_regular_price:regular,is_promotion:promo,availability:"in_stock",observed_at:"2026-09-10T00:00:00Z",freshness_status:"FRESH",relative_price_state:retailer==="walmart"?"best":"highest"}; }
const row = {row_id:"milk",canonical_product_id:"canon:milk",comparability:"comparable",category:"Lácteos",product_type:"Leche",product_name:"Leche Sula",brand:"Sula",variant:"Entera",presentation:"1 L",offers:[offer("w:1","walmart","35.50","40.00",true),offer("c:1","la_colonia","38.00",null,false)]};
assert.equal(c.relativePriceState(row,row.offers[0]),"best");
const line = c.lineFromOffer(row,row.offers[0],2,"catalog/a.json");
assert.equal(line.unit_price_minor,3550);
assert.equal(line.reported_regular_price_minor,4000);
assert.equal(line.is_promotion,true);
assert.equal(line.category,"Lácteos");
assert.equal(line.product_type,"Leche");
assert.equal(line.brand,"Sula");
assert.equal(line.presentation,"1 L");

let batch = c.prepareBatch([], [row], new Map([["milk",{source_product_id:"w:1",quantity:2,partition:"catalog/a.json"}]]));
assert.equal(batch.additions.length,1);
let cart = c.addNewLines([],batch.additions);
batch = c.prepareBatch(cart,[row],new Map([["milk",{source_product_id:"w:1",quantity:2,partition:"catalog/a.json"}]]));
assert.equal(batch.unchanged.length,1);
batch = c.prepareBatch(cart,[row],new Map([["milk",{source_product_id:"c:1",quantity:3,partition:"catalog/a.json"}]]));
assert.equal(batch.conflicts.length,1);
assert.equal(c.confirmLineUpdates(cart,batch.conflicts)[0].supermarket_id,"la_colonia");

const summary = c.cartSummary(cart);
assert.equal(summary.grand_total_minor,7100);
assert.equal(summary.retailers.get("walmart").subtotal_minor,7100);
assert.equal(summary.retailers.get("walmart").lines[0].line_total_minor,7100);
const memory = new Map();
const storage={setItem:(k,v)=>memory.set(k,v),getItem:(k)=>memory.get(k)??null};
assert.equal(c.saveCart(storage,cart),true);
assert.deepEqual(c.loadCart(storage),cart);
assert.equal(c.saveCart({setItem(){throw new Error("blocked")}},cart),false);
'''
    run_module(tmp_path, CATALOG, script)


def test_exports_use_current_price_totals_and_safe_csv(tmp_path: Path) -> None:
    script = r'''
import assert from "node:assert/strict";
const e = await import(process.argv[1]);
const summary={products:2,units:3,retailer_count:1,incomplete:0,stale:0,grand_total_minor:18900,retailers:new Map([["walmart",{subtotal_minor:18900,incomplete:0,lines:[
 {product_name:"Leche Sula",brand:"Sula",presentation:"1 L",quantity:2,unit_price_minor:3550,line_total_minor:7100,invalid:false,freshness_status:"FRESH"},
 {product_name:"=2+2",brand:"Marca X",presentation:"5 lb",quantity:1,unit_price_minor:11800,line_total_minor:11800,invalid:false,freshness_status:"FRESH"},
]}]])};
const csv=e.buildCartCsv(summary);
assert.ok(csv.startsWith("\uFEFF"));
assert.ok(csv.includes('"supermercado","producto","cantidad","precio_unitario_hnl","total_linea_hnl"'));
assert.ok(csv.includes('"walmart","Leche Sula - 1 L","2","35.50","71.00"'));
assert.ok(csv.includes("\"'=2+2 - Marca X - 5 lb\""));
assert.ok(csv.includes('"walmart","SUBTOTAL","","","189.00"'));
assert.ok(csv.includes('"","TOTAL GENERAL","","","189.00"'));
assert.ok(!csv.includes("40.00"));
assert.ok(!csv.includes("1.15"));
const pdf=e.buildCartPdf(summary,new Date("2026-09-10T00:00:00Z"));
const text=new TextDecoder("latin1").decode(pdf);
assert.ok(text.startsWith("%PDF-1.4"));
assert.ok(text.includes("TOTAL ESTIMADO DE MI COMPRA: L 189.00"));
assert.ok(text.includes("Subtotal: L 189.00"));
const match=text.match(/startxref\n(\d+)\n%%EOF/); assert.ok(match); assert.equal(text.slice(Number(match[1]),Number(match[1])+4),"xref");
'''
    run_module(tmp_path, EXPORTS, script)
