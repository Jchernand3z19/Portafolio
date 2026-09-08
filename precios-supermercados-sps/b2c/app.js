const CART_KEY = "rpi-mi-compra/v1";
const RESULT_LIMIT = 30;

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

export function searchProducts(products, query, limit = RESULT_LIMIT) {
  const terms = normalizeText(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  const matches = [];
  for (const product of products ?? []) {
    const text = normalizeText((product.offers ?? []).flatMap((offer) => [
      offer.product_name, offer.category, offer.product_type, offer.brand,
      offer.variant, offer.presentation,
    ]).filter(Boolean).join(" "));
    if (terms.every((term) => text.includes(term))) matches.push(product);
    if (matches.length >= limit) break;
  }
  return matches;
}

export function recommendedIds(product, comparisonStatus) {
  if (comparisonStatus !== "COMPARABLE") return new Set();
  return new Set((product.recommended_source_product_ids ?? []).filter((value) => typeof value === "string"));
}

export function lineFromOffer(product, offer, quantity = 1) {
  const unitPriceMinor = moneyToMinor(offer.current_price);
  if (!Number.isInteger(quantity) || quantity < 1 || unitPriceMinor === null) return null;
  return {
    canonical_product_id: product.canonical_product_id,
    source_product_id: offer.source_product_id,
    supermarket_id: offer.supermarket_id,
    location_id: offer.location_id,
    category: offer.category ?? null,
    product_type: offer.product_type ?? null,
    product_name: offer.product_name,
    brand: offer.brand ?? null,
    variant: offer.variant ?? null,
    presentation: offer.presentation ?? null,
    quantity,
    unit_price_minor: unitPriceMinor,
    reported_regular_price_minor: moneyToMinor(offer.reported_regular_price),
    is_promotion: offer.is_promotion === true,
    availability: offer.availability,
    observed_at: offer.observed_at,
    freshness_status: offer.freshness_status,
    checked: false,
    invalid: false,
  };
}

export function selectOffer(lines, incoming) {
  const existing = lines.find((line) => line.canonical_product_id === incoming.canonical_product_id);
  const replacement = existing ? {...incoming, quantity: existing.quantity, checked: existing.checked} : incoming;
  return [...lines.filter((line) => line.canonical_product_id !== incoming.canonical_product_id), replacement];
}

export function cartSummary(lines) {
  const retailers = new Map();
  let units = 0;
  let incomplete = 0;
  let stale = 0;
  let grandTotalMinor = 0;
  for (const line of lines) {
    units += Number.isInteger(line.quantity) ? line.quantity : 0;
    if (line.freshness_status === "STALE") stale += 1;
    const valid = !line.invalid && Number.isSafeInteger(line.unit_price_minor) && Number.isInteger(line.quantity) && line.quantity > 0;
    const total = valid ? line.unit_price_minor * line.quantity : null;
    if (total === null || !Number.isSafeInteger(total)) incomplete += 1;
    else grandTotalMinor += total;
    const group = retailers.get(line.supermarket_id) ?? {subtotal_minor: 0, incomplete: 0, lines: []};
    if (total === null) group.incomplete += 1; else group.subtotal_minor += total;
    group.lines.push({...line, line_total_minor: total});
    retailers.set(line.supermarket_id, group);
  }
  return {products: lines.length, units, retailer_count: retailers.size, incomplete, stale, grand_total_minor: incomplete ? null : grandTotalMinor, retailers};
}

export function loadCart(storage) {
  try {
    const parsed = JSON.parse(storage.getItem(CART_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((line) => line && typeof line.source_product_id === "string") : [];
  } catch { return []; }
}

export function saveCart(storage, lines) {
  storage.setItem(CART_KEY, JSON.stringify(lines));
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function metric(label, value) {
  const row = el("div", "metric");
  row.append(el("span", "metric-label", label), el("strong", "metric-value", value));
  return row;
}

function createApp() {
  const state = {mart: null, cart: loadCart(localStorage)};
  const search = document.querySelector("#product-search");
  const results = document.querySelector("#results");
  const status = document.querySelector("#data-status");
  const cart = document.querySelector("#cart-groups");
  const cartStats = document.querySelector("#cart-stats");
  const cartTotal = document.querySelector("#cart-total");
  const cartCount = document.querySelector("#cart-count");

  function persist() { saveCart(localStorage, state.cart); renderCart(); }

  function renderCart() {
    cart.replaceChildren();
    const summary = cartSummary(state.cart);
    cartCount.textContent = String(summary.products);
    cartStats.textContent = `${summary.products} productos · ${summary.units} unidades · ${summary.retailer_count} supermercados · ${summary.incomplete} incompletos · ${summary.stale} stale`;
    cartTotal.textContent = summary.grand_total_minor === null ? "Total incompleto" : `TOTAL ESTIMADO ${formatHnl(summary.grand_total_minor)}`;
    if (!summary.products) {
      cart.append(el("p", "empty-state", "Tu lista está vacía. Busca un producto y elige dónde comprarlo."));
      return;
    }
    for (const [retailer, group] of [...summary.retailers].sort(([a], [b]) => a.localeCompare(b))) {
      const section = el("section", "retailer-group");
      section.append(el("h3", null, retailer.replaceAll("_", " ").toLocaleUpperCase("es")));
      for (const line of group.lines) {
        const stateLine = state.cart.find((item) => item.source_product_id === line.source_product_id);
        if (!stateLine) continue;
        const item = el("article", `cart-line${line.checked ? " is-checked" : ""}`);
        const check = el("button", "check-button", line.checked ? "☑" : "☐");
        check.type = "button"; check.setAttribute("aria-label", line.checked ? "Marcar pendiente" : "Marcar comprado");
        check.addEventListener("click", () => { stateLine.checked = !stateLine.checked; persist(); });
        const info = el("div", "cart-line-info");
        info.append(el("strong", null, line.product_name), el("span", "muted", [line.brand, line.presentation].filter(Boolean).join(" · ")));
        const price = line.line_total_minor === null ? "Precio no disponible" : `${line.quantity} × ${formatHnl(line.unit_price_minor)} = ${formatHnl(line.line_total_minor)}`;
        info.append(el("span", "line-price", price));
        if (line.freshness_status === "STALE") info.append(el("span", "warning", "Precio stale"));
        const controls = el("div", "quantity-controls");
        const minus = el("button", null, "−"), plus = el("button", null, "+"), remove = el("button", "danger-link", "Eliminar");
        minus.type = plus.type = remove.type = "button";
        minus.disabled = line.quantity <= 1;
        minus.addEventListener("click", () => { stateLine.quantity -= 1; persist(); });
        plus.addEventListener("click", () => { if (stateLine.quantity < 999) stateLine.quantity += 1; persist(); });
        remove.addEventListener("click", () => { state.cart = state.cart.filter((x) => x.source_product_id !== line.source_product_id); persist(); });
        controls.append(minus, el("span", "quantity", line.quantity), plus, remove);
        item.append(check, info, controls); section.append(item);
      }
      section.append(el("div", "retailer-subtotal", group.incomplete ? "Subtotal incompleto" : `Subtotal ${formatHnl(group.subtotal_minor)}`));
      cart.append(section);
    }
  }

  function renderResults() {
    results.replaceChildren();
    if (!state.mart) return;
    const products = searchProducts(state.mart.products, search.value);
    if (!search.value.trim()) { results.append(el("p", "empty-state", "Escribe un producto, marca o presentación para comenzar.")); return; }
    if (!products.length) { results.append(el("p", "empty-state", "No encontré productos seguros con esa búsqueda.")); return; }
    for (const product of products) {
      const offers = product.offers ?? [];
      if (!offers.length) continue;
      const first = offers[0];
      const card = el("article", "product-card");
      const head = el("div", "product-head");
      head.append(el("h2", null, first.product_name));
      head.append(el("p", "muted", [first.category, first.product_type, first.brand, first.variant, first.presentation].filter(Boolean).join(" · ")));
      card.append(head);
      const recs = recommendedIds(product, state.mart.comparison_status);
      if (state.mart.comparison_status !== "COMPARABLE") card.append(el("p", "safety-note", "Comparación fresca insuficiente: no se recomienda un mejor precio."));
      const offerGrid = el("div", "offer-grid");
      for (const offer of offers) {
        const offerCard = el("div", `offer-card${recs.has(offer.source_product_id) ? " best-offer" : ""}`);
        const title = el("div", "offer-title");
        title.append(el("strong", null, offer.supermarket_id.replaceAll("_", " ")));
        if (recs.has(offer.source_product_id)) title.append(el("span", "best-badge", "Mejor precio"));
        offerCard.append(title, el("div", "offer-price", formatHnl(moneyToMinor(offer.current_price))));
        if (offer.reported_regular_price) offerCard.append(el("div", "regular-price", `Regular declarado ${formatHnl(moneyToMinor(offer.reported_regular_price))}`));
        if (offer.is_promotion) offerCard.append(el("span", "promo-badge", "Promoción reportada"));
        offerCard.append(metric("Freshness", offer.freshness_status), metric("Observado", offer.observed_at ?? "—"));
        if (offer.rank !== null && offer.rank !== undefined) offerCard.append(metric("Ranking", `#${offer.rank}`));
        const history = offer.historical_summary;
        if (history) {
          const w30 = history.windows?.["30d"], w90 = history.windows?.["90d"];
          offerCard.append(metric("Promedio 30d", w30?.status === "available" ? formatHnl(moneyToMinor(w30.average)) : "Historial insuficiente"));
          offerCard.append(metric("Promedio 90d", w90?.status === "available" ? formatHnl(moneyToMinor(w90.average)) : "Historial insuficiente"));
          offerCard.append(metric("Posición histórica", history.historical_position ?? "insufficient_history"));
        }
        const add = el("button", "primary-button", "Agregar aquí"); add.type = "button";
        add.addEventListener("click", () => {
          const line = lineFromOffer(product, offer);
          if (!line) return;
          state.cart = selectOffer(state.cart, line); persist();
          document.querySelector("#cart-panel").scrollIntoView({behavior: "smooth", block: "start"});
        });
        offerCard.append(add); offerGrid.append(offerCard);
      }
      card.append(offerGrid); results.append(card);
    }
  }

  async function loadMart() {
    const url = globalThis.RPI_CONSUMER_MART_URL || document.body.dataset.martUrl;
    try {
      const response = await fetch(url, {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const mart = await response.json();
      if (mart.schema !== "rpi-consumer-mart/v2" || !Array.isArray(mart.products)) throw new Error("Contrato no compatible");
      state.mart = mart;
      status.textContent = `${mart.product_count} productos seguros · corte ${mart.as_of} · ${mart.comparison_status}`;
      renderResults();
    } catch (error) {
      status.textContent = "Datos no disponibles. Se conserva tu lista local.";
      results.replaceChildren(el("p", "safety-note", `No fue posible cargar precios públicos: ${error.message}`));
    }
  }

  search.addEventListener("input", renderResults);
  renderCart(); loadMart();
}

if (typeof document !== "undefined") createApp();
