import * as base from "./catalog.js?base=1";
export * from "./catalog.js?base=1";

export const CART_KEY = "rpi-mi-compra/tegucigalpa/v1";
export const LEGACY_CART_KEY = CART_KEY;

export const RETAILERS = Object.freeze([
  {supermarket_id: "la_colonia_tgu", source_supermarket_id: "la_colonia", location_id: "la_colonia_tgu", name: "La Colonia"},
  {supermarket_id: "walmart_tgu_ffaa", source_supermarket_id: "walmart", location_id: "walmart_tgu_ffaa", name: "Walmart FFAA"},
  {supermarket_id: "walmart_tgu_el_sauce", source_supermarket_id: "walmart", location_id: "walmart_tgu_el_sauce", name: "Walmart El Sauce"},
  {supermarket_id: "pricesmart_tgu", source_supermarket_id: "pricesmart", location_id: "pricesmart_tgu", name: "PriceSmart Florencia"},
  {supermarket_id: "paiz_tgu_multiplaza", source_supermarket_id: "paiz", location_id: "paiz_tgu_multiplaza", name: "Paiz Multiplaza"},
  {supermarket_id: "paiz_tgu_proceres", source_supermarket_id: "paiz", location_id: "paiz_tgu_proceres", name: "Paiz Próceres"},
]);

function exactRetailer(supermarketId, locationId) {
  return RETAILERS.find((item) => (
    item.source_supermarket_id === supermarketId && item.location_id === locationId
  )) ?? null;
}

export function manifestIsCompatible(manifest) {
  if (manifest?.schema !== "rpi-consumer-catalog-manifest/v3" || manifest.catalog_schema !== "rpi-consumer-catalog/v3") return false;
  if (manifest?.location?.city !== "Tegucigalpa" || manifest?.location?.country_code !== "HN") return false;
  if (!Array.isArray(manifest.scope) || manifest.scope.length !== RETAILERS.length || !Array.isArray(manifest.files) || manifest.initial_payload?.request_count !== 2) return false;
  const contexts = new Set();
  for (let index = 0; index < RETAILERS.length; index += 1) {
    const retailer = RETAILERS[index];
    const scope = manifest.scope[index];
    if (scope?.supermarket_id !== retailer.source_supermarket_id || scope?.location_id !== retailer.location_id) return false;
    const key = `${scope.supermarket_id}\0${scope.location_id}`;
    if (contexts.has(key)) return false;
    contexts.add(key);
  }
  const paths = new Set();
  if (!manifest.files.every((file) => {
    const valid = typeof file?.path === "string"
      && /^[a-z0-9/_-]+\.json$/.test(file.path)
      && /^[a-f0-9]{64}$/.test(file.sha256)
      && Number.isSafeInteger(file.bytes) && file.bytes >= 0
      && !paths.has(file.path);
    paths.add(file?.path);
    return valid;
  })) return false;
  return paths.has("facets-tgu.json") && Array.isArray(manifest.retailers)
    && manifest.retailers.length === RETAILERS.length;
}

export function offersByRetailer(row) {
  const result = new Map();
  for (const retailer of RETAILERS) {
    const offers = (row?.offers ?? []).filter((offer) => (
      offer.supermarket_id === retailer.source_supermarket_id
      && offer.location_id === retailer.location_id
    ));
    result.set(retailer.supermarket_id, offers.length === 1 ? offers[0] : null);
  }
  return result;
}

export function loadCart(storage) {
  try {
    const parsed = JSON.parse(storage.getItem(CART_KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((line) => (
      line && typeof line.source_product_id === "string"
      && exactRetailer(line.supermarket_id, line.location_id)
    )).map((line) => ({...line, row_id: base.cartIdentity(line)}));
  } catch {
    return [];
  }
}

export function saveCart(storage, lines) {
  try {
    const safe = (lines ?? []).filter((line) => exactRetailer(line.supermarket_id, line.location_id));
    storage.setItem(CART_KEY, JSON.stringify(safe));
    return true;
  } catch {
    return false;
  }
}

export function cartSummary(lines) {
  const retailers = new Map();
  let products = 0, units = 0, incomplete = 0, stale = 0, grandTotalMinor = 0;
  for (const line of lines ?? []) {
    const retailer = exactRetailer(line.supermarket_id, line.location_id);
    if (!retailer) continue;
    products += 1;
    units += Number.isInteger(line.quantity) ? line.quantity : 0;
    if (line.freshness_status === "STALE") stale += 1;
    const valid = !line.invalid && Number.isSafeInteger(line.unit_price_minor)
      && Number.isInteger(line.quantity) && line.quantity > 0;
    const total = valid && Number.isSafeInteger(line.unit_price_minor * line.quantity)
      ? line.unit_price_minor * line.quantity : null;
    if (total === null || !Number.isSafeInteger(grandTotalMinor + total)) incomplete += 1;
    else grandTotalMinor += total;
    const key = retailer.supermarket_id;
    const group = retailers.get(key) ?? {subtotal_minor: 0, incomplete: 0, lines: []};
    if (total === null || !Number.isSafeInteger(group.subtotal_minor + total)) group.incomplete += 1;
    else group.subtotal_minor += total;
    group.lines.push({...line, line_total_minor: total});
    retailers.set(key, group);
  }
  return {
    products, units, retailer_count: retailers.size, incomplete, stale,
    grand_total_minor: incomplete ? null : grandTotalMinor, retailers,
  };
}

function scenarioTotal(offer, quantity) {
  const price = base.moneyToMinor(offer?.current_price);
  if (!base.offerIsUsable(offer) || offer.freshness_status !== "FRESH" || price === null || !Number.isInteger(quantity) || quantity < 1) return null;
  const total = price * quantity;
  return Number.isSafeInteger(total) ? total : null;
}

export function analyzeBasketOptions(lines, rows) {
  const scopedLines = (lines ?? []).filter((line) => exactRetailer(line.supermarket_id, line.location_id));
  const manual = cartSummary(scopedLines);
  if (!scopedLines.length) return {status: "EMPTY", manual, single_retailer: [], optimized: null};
  if (base.detectCartUpdates(scopedLines, rows).length) return {status: "REFRESH_REQUIRED", manual, single_retailer: [], optimized: null};
  if (scopedLines.some((line) => line.freshness_status !== "FRESH")) return {status: "COMPARISON_BLOCKED", manual, single_retailer: [], optimized: null};
  const resolved = scopedLines.map((line) => ({line, row: rows instanceof Map ? rows.get(base.cartIdentity(line)) : null}));
  if (resolved.some(({row}) => !row)) return {status: "CONTRACT_INVALID", manual, single_retailer: [], optimized: null};

  const singleRetailer = RETAILERS.map((retailer) => {
    let total = 0, covered = 0;
    for (const {line, row} of resolved) {
      const lineTotal = scenarioTotal(offersByRetailer(row).get(retailer.supermarket_id), line.quantity);
      if (lineTotal === null || !Number.isSafeInteger(total + lineTotal)) continue;
      total += lineTotal;
      covered += 1;
    }
    const complete = covered === resolved.length;
    return {
      ...retailer,
      requested_count: resolved.length,
      covered_count: covered,
      missing_count: resolved.length - covered,
      status: complete ? "COMPLETE" : "INCOMPLETE",
      total_minor: complete ? total : null,
      savings_vs_manual_minor: complete && Number.isSafeInteger(manual.grand_total_minor)
        ? manual.grand_total_minor - total : null,
    };
  });

  const selected = [];
  for (const {line, row} of resolved) {
    if (row.comparability !== "comparable") continue;
    const candidates = (row.offers ?? []).filter((offer) => (
      exactRetailer(offer.supermarket_id, offer.location_id)
      && base.offerIsUsable(offer)
      && offer.freshness_status === "FRESH"
      && ["best", "equivalent"].includes(offer.relative_price_state)
    )).sort((left, right) => (
      `${left.supermarket_id}\0${left.location_id}\0${left.source_product_id}`
        .localeCompare(`${right.supermarket_id}\0${right.location_id}\0${right.source_product_id}`)
    ));
    if (!candidates.length) continue;
    const lineTotal = scenarioTotal(candidates[0], line.quantity);
    if (lineTotal === null) continue;
    selected.push({
      row_id: row.row_id,
      source_product_id: candidates[0].source_product_id,
      supermarket_id: candidates[0].supermarket_id,
      location_id: candidates[0].location_id,
      quantity: line.quantity,
      line_total_minor: lineTotal,
      tie_count: candidates.length,
    });
  }
  const complete = selected.length === resolved.length;
  const optimizedTotal = complete ? selected.reduce((total, line) => total + line.line_total_minor, 0) : null;
  return {
    status: "AVAILABLE",
    manual,
    single_retailer: singleRetailer,
    optimized: {
      status: complete ? "COMPLETE" : "INCOMPLETE",
      requested_count: resolved.length,
      covered_count: selected.length,
      missing_count: resolved.length - selected.length,
      retailer_count: new Set(selected.map((line) => `${line.supermarket_id}\0${line.location_id}`)).size,
      tie_product_count: selected.filter((line) => line.tie_count > 1).length,
      total_minor: Number.isSafeInteger(optimizedTotal) ? optimizedTotal : null,
      savings_vs_manual_minor: Number.isSafeInteger(optimizedTotal) && Number.isSafeInteger(manual.grand_total_minor)
        ? manual.grand_total_minor - optimizedTotal : null,
      selected,
    },
  };
}
