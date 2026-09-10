export const CART_KEY = "rpi-mi-compra/v2";
export const LEGACY_CART_KEY = "rpi-mi-compra/v1";
export const RETAILERS = Object.freeze([
  {supermarket_id: "la_colonia", location_id: "la_colonia_sps", name: "La Colonia"},
  {supermarket_id: "colonial", location_id: "colonial_sps", name: "Colonial"},
  {supermarket_id: "walmart", location_id: "walmart_sps", name: "Walmart"},
  {supermarket_id: "pricesmart", location_id: "pricesmart_sps", name: "PriceSmart"},
  {supermarket_id: "comisariato_los_andes", location_id: "comisariato_los_andes_sps", name: "Los Andes"},
]);

export function moneyToMinor(value) {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,2})?$/.test(value.trim())) return null;
  const [whole, decimals = ""] = value.trim().split(".");
  const minor = Number(whole) * 100 + Number((decimals + "00").slice(0, 2));
  return Number.isSafeInteger(minor) && minor >= 0 ? minor : null;
}

export function formatHnl(minor) {
  if (!Number.isSafeInteger(minor)) return "—";
  return `L ${(minor / 100).toLocaleString("es-HN", {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}

export function normalizeText(value) {
  return String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es").trim();
}

export function manifestIsCompatible(manifest) {
  if (manifest?.schema !== "rpi-consumer-catalog-manifest/v3" || manifest.catalog_schema !== "rpi-consumer-catalog/v3") return false;
  if (!Array.isArray(manifest.scope) || manifest.scope.length !== RETAILERS.length || !Array.isArray(manifest.files) || manifest.initial_payload?.request_count !== 2) return false;
  const paths = new Set();
  if (!manifest.files.every((file) => {
    const valid = typeof file?.path === "string"
      && /^[a-z0-9/_-]+\.json$/.test(file.path)
      && /^[a-f0-9]{64}$/.test(file.sha256)
      && Number.isSafeInteger(file.bytes) && file.bytes >= 0
      && !paths.has(file.path);
    paths.add(file?.path);
    return valid;
  }) || !paths.has("facets-sps.json")) return false;
  return RETAILERS.every((retailer, index) => {
    const scope = manifest.scope[index];
    return scope?.supermarket_id === retailer.supermarket_id && scope?.location_id === retailer.location_id;
  });
}

export function facetsAreCompatible(facets, manifest) {
  return facets?.schema === "rpi-consumer-facets/v3"
    && Array.isArray(facets.categories)
    && facets.row_count === manifest?.visible_rows
    && facets.categories.every((category) => (
      typeof category?.row_count === "number"
      && ((category.navigation === "facets" && Array.isArray(category.product_types))
        || (category.navigation === "search" && Array.isArray(category.search_indexes)))
    ));
}

function uniqueValues(rows, field) {
  const values = new Map();
  for (const row of rows) {
    const value = row?.[field];
    const key = value === null || value === undefined || value === "" ? "__unknown__" : String(value);
    if (!values.has(key)) values.set(key, value ?? null);
  }
  return [...values.values()].sort((left, right) => {
    if (left === null) return 1;
    if (right === null) return -1;
    return String(left).localeCompare(String(right), "es", {sensitivity: "base"});
  });
}

function matchesQuery(row, query) {
  const terms = normalizeText(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const searchable = normalizeText([row.product_name, row.brand, row.presentation].filter(Boolean).join(" "));
  return terms.every((term) => searchable.includes(term));
}

export function filterIndexEntries(entries, filter) {
  return (entries ?? []).filter((row) => (
    (!filter.brand || (filter.brand === "__unknown__" ? !row.brand : String(row.brand) === filter.brand))
    && (!filter.presentation || (filter.presentation === "__unknown__" ? !row.presentation : String(row.presentation) === filter.presentation))
    && matchesQuery(row, filter.query)
  ));
}

export function reconcileDependentFilters(entries, filter) {
  const next = {...filter};
  const queryRows = (entries ?? []).filter((row) => matchesQuery(row, next.query));
  const brands = uniqueValues(queryRows, "brand");
  if (next.brand && !brands.some((value) => (value === null ? "__unknown__" : String(value)) === next.brand)) next.brand = "";
  const brandRows = queryRows.filter((row) => !next.brand || (next.brand === "__unknown__" ? !row.brand : String(row.brand) === next.brand));
  const presentations = uniqueValues(brandRows, "presentation");
  if (next.presentation && !presentations.some((value) => (value === null ? "__unknown__" : String(value)) === next.presentation)) next.presentation = "";
  return {filter: next, options: {brands, presentations}};
}

export function clearDependentFilters(filter, changedField, value) {
  const next = {...filter, [changedField]: value};
  const order = ["category", "product_type", "brand", "presentation"];
  const index = order.indexOf(changedField);
  if (index < 0) return next;
  for (const field of order.slice(index + 1)) next[field] = "";
  return next;
}

export function searchIndexForPrefix(category, query) {
  const prefix = normalizeText(query).replace(/[^a-z0-9]+/g, "").slice(0, 2) || "__";
  if (prefix.length < 2) return null;
  return category?.search_indexes?.find((entry) => entry.prefix === prefix) ?? null;
}

export function indexPathForType(category, productType) {
  return category?.product_types?.find((entry) => String(entry.value ?? "") === String(productType ?? ""))?.index_path ?? null;
}

export function partitionPaths(entries) {
  return [...new Set((entries ?? []).map((row) => row.partition).filter((value) => typeof value === "string"))];
}

export function quantityValue(value, fallback = 1) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 999 ? parsed : fallback;
}

export function offerIsUsable(offer) {
  const price = moneyToMinor(offer?.current_price);
  return price !== null && price > 0 && offer.availability !== "out_of_stock" && offer.freshness_status !== "UNAVAILABLE";
}

export function relativePriceState(row, offer) {
  const states = new Set(["best", "intermediate", "highest", "equivalent"]);
  if (row?.comparability !== "comparable" || !offerIsUsable(offer) || offer.freshness_status !== "FRESH") return "neutral";
  return states.has(offer.relative_price_state) ? offer.relative_price_state : "neutral";
}

export function humanHistoricalPosition(value) {
  return {
    historically_low: "Mínimo de 90 días",
    below_recent_average: "Debajo del promedio de 90 días",
    normal_range: "En el promedio de 90 días",
    above_recent_average: "Sobre el promedio de 90 días",
    insufficient_history: "Historial insuficiente",
  }[value] ?? "Historial insuficiente";
}

export function offersByRetailer(row) {
  const grouped = new Map(RETAILERS.map((retailer) => [retailer.supermarket_id, []]));
  for (const offer of row?.offers ?? []) {
    if (grouped.has(offer.supermarket_id)) grouped.get(offer.supermarket_id).push(offer);
  }
  return new Map([...grouped].map(([retailer, offers]) => [retailer, offers.length === 1 ? offers[0] : null]));
}

export function cartIdentity(line) {
  return String(line?.row_id || line?.canonical_product_id || line?.source_product_id || "");
}

export function lineFromOffer(product, offer, quantity = 1, partition = null) {
  const unitPriceMinor = moneyToMinor(offer?.current_price);
  const safeQuantity = quantityValue(quantity, 0);
  if (!safeQuantity || unitPriceMinor === null || unitPriceMinor <= 0) return null;
  return {
    row_id: product.row_id ?? product.canonical_product_id ?? offer.source_product_id,
    canonical_product_id: product.canonical_product_id ?? null,
    source_product_id: offer.source_product_id,
    supermarket_id: offer.supermarket_id,
    location_id: offer.location_id,
    catalog_partition: partition,
    category: product.category ?? offer.category ?? null,
    product_type: product.product_type ?? offer.product_type ?? null,
    product_name: product.product_name ?? offer.product_name,
    brand: product.brand ?? offer.brand ?? null,
    variant: product.variant ?? offer.variant ?? null,
    presentation: product.presentation ?? offer.presentation ?? null,
    quantity: safeQuantity,
    unit_price_minor: unitPriceMinor,
    reported_regular_price_minor: moneyToMinor(offer.reported_regular_price),
    is_promotion: offer.is_promotion === true ? true : offer.is_promotion === false ? false : null,
    availability: offer.availability,
    observed_at: offer.observed_at,
    freshness_status: offer.freshness_status,
    checked: false,
    invalid: !offerIsUsable(offer),
  };
}

export function prepareBatch(cart, rows, staging) {
  const existing = new Map((cart ?? []).map((line) => [cartIdentity(line), line]));
  const additions = [], conflicts = [], unchanged = [], skipped = [];
  for (const row of rows ?? []) {
    const staged = staging instanceof Map ? staging.get(row.row_id) : staging?.[row.row_id];
    if (!staged?.source_product_id) continue;
    const matches = (row.offers ?? []).filter((offer) => offer.source_product_id === staged.source_product_id);
    const line = matches.length === 1 ? lineFromOffer(row, matches[0], staged.quantity, staged.partition) : null;
    if (!line || line.invalid) { skipped.push(row.row_id); continue; }
    const current = existing.get(cartIdentity(line));
    if (!current) additions.push(line);
    else if (current.source_product_id !== line.source_product_id || current.quantity !== line.quantity) conflicts.push({...line, checked: current.checked});
    else unchanged.push(line);
  }
  return {additions, conflicts, unchanged, skipped};
}

export function addNewLines(cart, additions) {
  const identities = new Set((cart ?? []).map(cartIdentity));
  return [...(cart ?? []), ...(additions ?? []).filter((line) => !identities.has(cartIdentity(line)))];
}

export function confirmLineUpdates(cart, updates) {
  const replacements = new Map((updates ?? []).map((line) => [cartIdentity(line), line]));
  return (cart ?? []).map((line) => replacements.get(cartIdentity(line)) ?? line);
}

export function selectOffer(lines, incoming) {
  const identity = cartIdentity(incoming);
  const existing = (lines ?? []).find((line) => cartIdentity(line) === identity);
  const replacement = existing ? {...incoming, quantity: existing.quantity, checked: existing.checked} : incoming;
  return [...(lines ?? []).filter((line) => cartIdentity(line) !== identity), replacement];
}

export function cartSummary(lines) {
  const retailers = new Map();
  let units = 0, incomplete = 0, stale = 0, grandTotalMinor = 0;
  for (const line of lines ?? []) {
    units += Number.isInteger(line.quantity) ? line.quantity : 0;
    if (line.freshness_status === "STALE") stale += 1;
    const valid = !line.invalid && Number.isSafeInteger(line.unit_price_minor) && Number.isInteger(line.quantity) && line.quantity > 0;
    const total = valid && Number.isSafeInteger(line.unit_price_minor * line.quantity) ? line.unit_price_minor * line.quantity : null;
    if (total === null || !Number.isSafeInteger(grandTotalMinor + total)) incomplete += 1;
    else grandTotalMinor += total;
    const group = retailers.get(line.supermarket_id) ?? {subtotal_minor: 0, incomplete: 0, lines: []};
    if (total === null || !Number.isSafeInteger(group.subtotal_minor + total)) group.incomplete += 1;
    else group.subtotal_minor += total;
    group.lines.push({...line, line_total_minor: total});
    retailers.set(line.supermarket_id, group);
  }
  return {products: (lines ?? []).length, units, retailer_count: retailers.size, incomplete, stale, grand_total_minor: incomplete ? null : grandTotalMinor, retailers};
}

export function loadCart(storage) {
  try {
    const raw = storage.getItem(CART_KEY) ?? storage.getItem(LEGACY_CART_KEY) ?? "[]";
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((line) => line && typeof line.source_product_id === "string").map((line) => ({...line, row_id: cartIdentity(line)}));
  } catch { return []; }
}

export function saveCart(storage, lines) {
  try { storage.setItem(CART_KEY, JSON.stringify(lines)); return true; } catch { return false; }
}

function exactOffer(rows, line) {
  const row = rows instanceof Map ? rows.get(cartIdentity(line)) : (rows ?? []).find((item) => item.row_id === cartIdentity(line));
  if (!row) return null;
  const offers = (row.offers ?? []).filter((offer) => offer.source_product_id === line.source_product_id);
  return offers.length === 1 ? {row, offer: offers[0]} : null;
}

export function detectCartUpdates(lines, rows) {
  const updates = [];
  for (const line of lines ?? []) {
    const exact = exactOffer(rows, line);
    if (!exact || exact.offer.supermarket_id !== line.supermarket_id || exact.offer.location_id !== line.location_id || !offerIsUsable(exact.offer)) {
      if (!line.invalid) updates.push({row_id: cartIdentity(line), status: "unavailable", previous_price_minor: line.unit_price_minor, current_price_minor: null});
      continue;
    }
    const current = moneyToMinor(exact.offer.current_price);
    if (line.invalid) updates.push({row_id: cartIdentity(line), status: "restored", previous_price_minor: line.unit_price_minor, current_price_minor: current});
    else if (current !== line.unit_price_minor) updates.push({row_id: cartIdentity(line), status: "price_changed", previous_price_minor: line.unit_price_minor, current_price_minor: current});
  }
  return updates;
}

export function refreshCartPrices(lines, rows) {
  return (lines ?? []).map((line) => {
    const exact = exactOffer(rows, line);
    if (!exact || exact.offer.supermarket_id !== line.supermarket_id || exact.offer.location_id !== line.location_id || !offerIsUsable(exact.offer)) {
      return {...line, invalid: true, availability: "unavailable", freshness_status: exact?.offer?.freshness_status ?? "UNAVAILABLE"};
    }
    const refreshed = lineFromOffer(exact.row, exact.offer, line.quantity, line.catalog_partition);
    return refreshed ? {...refreshed, checked: line.checked, invalid: false} : {...line, invalid: true};
  });
}

function scenarioTotal(offer, quantity) {
  const price = moneyToMinor(offer?.current_price);
  if (!offerIsUsable(offer) || offer.freshness_status !== "FRESH" || price === null || !Number.isInteger(quantity) || quantity < 1) return null;
  const total = price * quantity;
  return Number.isSafeInteger(total) ? total : null;
}

export function analyzeBasketOptions(lines, rows) {
  const manual = cartSummary(lines);
  if (!(lines ?? []).length) return {status: "EMPTY", manual, single_retailer: [], optimized: null};
  if (detectCartUpdates(lines, rows).length) return {status: "REFRESH_REQUIRED", manual, single_retailer: [], optimized: null};
  if ((lines ?? []).some((line) => line.freshness_status !== "FRESH")) return {status: "COMPARISON_BLOCKED", manual, single_retailer: [], optimized: null};
  const resolved = (lines ?? []).map((line) => ({line, row: rows instanceof Map ? rows.get(cartIdentity(line)) : null}));
  if (resolved.some(({row}) => !row)) return {status: "CONTRACT_INVALID", manual, single_retailer: [], optimized: null};
  const singleRetailer = RETAILERS.map((retailer) => {
    let total = 0, covered = 0;
    for (const {line, row} of resolved) {
      const lineTotal = scenarioTotal(offersByRetailer(row).get(retailer.supermarket_id), line.quantity);
      if (lineTotal === null || !Number.isSafeInteger(total + lineTotal)) continue;
      total += lineTotal; covered += 1;
    }
    const complete = covered === resolved.length;
    return {
      ...retailer, requested_count: resolved.length, covered_count: covered,
      missing_count: resolved.length - covered, status: complete ? "COMPLETE" : "INCOMPLETE",
      total_minor: complete ? total : null,
      savings_vs_manual_minor: complete && Number.isSafeInteger(manual.grand_total_minor) ? manual.grand_total_minor - total : null,
    };
  });
  const selected = [];
  for (const {line, row} of resolved) {
    if (row.comparability !== "comparable") continue;
    const candidates = (row.offers ?? []).filter((offer) => (
      offerIsUsable(offer) && offer.freshness_status === "FRESH"
      && ["best", "equivalent"].includes(offer.relative_price_state)
    )).sort((left, right) => `${left.supermarket_id}\0${left.source_product_id}`.localeCompare(`${right.supermarket_id}\0${right.source_product_id}`));
    if (!candidates.length) continue;
    const lineTotal = scenarioTotal(candidates[0], line.quantity);
    if (lineTotal === null) continue;
    selected.push({row_id: row.row_id, source_product_id: candidates[0].source_product_id, supermarket_id: candidates[0].supermarket_id, quantity: line.quantity, line_total_minor: lineTotal, tie_count: candidates.length});
  }
  const complete = selected.length === resolved.length;
  const optimizedTotal = complete ? selected.reduce((total, line) => total + line.line_total_minor, 0) : null;
  return {
    status: "AVAILABLE", manual, single_retailer: singleRetailer,
    optimized: {
      status: complete ? "COMPLETE" : "INCOMPLETE", requested_count: resolved.length,
      covered_count: selected.length, missing_count: resolved.length - selected.length,
      retailer_count: new Set(selected.map((line) => line.supermarket_id)).size,
      tie_product_count: selected.filter((line) => line.tie_count > 1).length,
      total_minor: Number.isSafeInteger(optimizedTotal) ? optimizedTotal : null,
      savings_vs_manual_minor: Number.isSafeInteger(optimizedTotal) && Number.isSafeInteger(manual.grand_total_minor) ? manual.grand_total_minor - optimizedTotal : null,
      selected,
    },
  };
}

export function humanFreshness(status) {
  if (status === "STALE") return "Precio no actualizado recientemente";
  if (status === "UNAVAILABLE") return "Precio no disponible";
  return "Precio actualizado";
}
