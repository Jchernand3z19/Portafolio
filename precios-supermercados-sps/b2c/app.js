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

export function exactMartOffer(mart, canonicalProductId, sourceProductId) {
  const products = (mart?.products ?? []).filter((product) => product.canonical_product_id === canonicalProductId);
  if (products.length !== 1) return null;
  const offers = (products[0].offers ?? []).filter((offer) => offer.source_product_id === sourceProductId);
  return offers.length === 1 ? {product: products[0], offer: offers[0]} : null;
}

export function consumerMartContractIsCompatible(mart) {
  if (mart?.schema !== "rpi-consumer-mart/v2" || !Array.isArray(mart.products)) return false;
  const comparable = mart.comparison_status === "COMPARABLE";
  for (const product of mart.products) {
    if (!Array.isArray(product?.offers)) return false;
    for (const offer of product.offers) {
      const abs = offer?.difference_vs_best_abs;
      const pct = offer?.difference_vs_best_pct;
      if (comparable) {
        if (moneyToMinor(abs) === null || typeof pct !== "string" || !/^\d+(?:\.\d{1,2})?$/.test(pct.trim())) return false;
      } else if (abs !== null || pct !== null) {
        return false;
      }
    }
  }
  return true;
}

function offerIsUsable(offer) {
  const price = moneyToMinor(offer?.current_price);
  return price !== null && price > 0 && offer.availability !== "out_of_stock" && offer.freshness_status !== "UNAVAILABLE";
}

export function lineFromOffer(product, offer, quantity = 1) {
  const unitPriceMinor = moneyToMinor(offer.current_price);
  if (!Number.isInteger(quantity) || quantity < 1 || unitPriceMinor === null || unitPriceMinor <= 0) return null;
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
    invalid: !offerIsUsable(offer),
  };
}

export function selectOffer(lines, incoming) {
  const existing = lines.find((line) => line.canonical_product_id === incoming.canonical_product_id);
  const replacement = existing ? {...incoming, quantity: existing.quantity, checked: existing.checked} : incoming;
  return [...lines.filter((line) => line.canonical_product_id !== incoming.canonical_product_id), replacement];
}

export function detectCartUpdates(lines, mart) {
  const updates = [];
  for (const line of lines) {
    const exact = exactMartOffer(mart, line.canonical_product_id, line.source_product_id);
    if (!exact || exact.offer.supermarket_id !== line.supermarket_id || exact.offer.location_id !== line.location_id || !offerIsUsable(exact.offer)) {
      if (!line.invalid) updates.push({source_product_id: line.source_product_id, status: "unavailable", previous_price_minor: line.unit_price_minor, current_price_minor: null});
      continue;
    }
    const currentPriceMinor = moneyToMinor(exact.offer.current_price);
    if (line.invalid) {
      updates.push({source_product_id: line.source_product_id, status: "restored", previous_price_minor: line.unit_price_minor, current_price_minor: currentPriceMinor});
    } else if (currentPriceMinor !== line.unit_price_minor) {
      updates.push({source_product_id: line.source_product_id, status: "price_changed", previous_price_minor: line.unit_price_minor, current_price_minor: currentPriceMinor});
    }
  }
  return updates;
}

export function refreshCartPrices(lines, mart) {
  return lines.map((line) => {
    const exact = exactMartOffer(mart, line.canonical_product_id, line.source_product_id);
    if (!exact || exact.offer.supermarket_id !== line.supermarket_id || exact.offer.location_id !== line.location_id || !offerIsUsable(exact.offer)) {
      return {...line, invalid: true, availability: "unavailable", freshness_status: exact?.offer?.freshness_status ?? "UNAVAILABLE"};
    }
    const refreshed = lineFromOffer(exact.product, exact.offer, line.quantity);
    if (!refreshed) return {...line, invalid: true};
    return {...refreshed, quantity: line.quantity, checked: line.checked, invalid: false};
  });
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

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = el("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
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
  const refreshBox = document.querySelector("#price-refresh");
  const refreshMessage = document.querySelector("#price-refresh-message");
  const refreshButton = document.querySelector("#price-refresh-button");
  const exportCsvButton = document.querySelector("#export-csv");
  const exportPdfButton = document.querySelector("#export-pdf");
  const exportStatus = document.querySelector("#export-status");

  function renderRefresh() {
    if (!state.mart || !state.cart.length) {
      refreshBox.hidden = true;
      return;
    }
    const updates = detectCartUpdates(state.cart, state.mart);
    if (!updates.length) {
      refreshBox.hidden = true;
      return;
    }
    const changed = updates.filter((item) => item.status === "price_changed").length;
    const unavailable = updates.filter((item) => item.status === "unavailable").length;
    const restored = updates.filter((item) => item.status === "restored").length;
    const parts = [];
    if (changed) parts.push(`${changed} ${changed === 1 ? "precio cambió" : "precios cambiaron"} desde que guardaste esta lista.`);
    if (unavailable) parts.push(`${unavailable} ${unavailable === 1 ? "oferta ya no está disponible" : "ofertas ya no están disponibles"}.`);
    if (restored) parts.push(`${restored} ${restored === 1 ? "oferta volvió a estar disponible" : "ofertas volvieron a estar disponibles"}.`);
    refreshMessage.textContent = parts.join(" ");
    refreshBox.hidden = false;
  }

  function persist() {
    saveCart(localStorage, state.cart);
    renderCart();
    renderRefresh();
  }

  function renderCart() {
    cart.replaceChildren();
    const summary = cartSummary(state.cart);
    cartCount.textContent = String(summary.products);
    cartStats.textContent = `${summary.products} productos · ${summary.units} unidades · ${summary.retailer_count} supermercados · ${summary.incomplete} incompletos · ${summary.stale} stale`;
    cartTotal.textContent = summary.grand_total_minor === null ? "Total incompleto" : `TOTAL ESTIMADO ${formatHnl(summary.grand_total_minor)}`;
    exportCsvButton.disabled = summary.products === 0;
    exportPdfButton.disabled = summary.products === 0;
    if (!summary.products) {
      exportStatus.textContent = "";
      cart.append(el("p", "empty-state", "Tu lista está vacía. Busca un producto y elige dónde comprarlo."));
      return;
    }
    for (const [retailer, group] of [...summary.retailers].sort(([a], [b]) => a.localeCompare(b))) {
      const section = el("section", "retailer-group");
      section.append(el("h3", null, retailer.replaceAll("_", " ").toLocaleUpperCase("es")));
      for (const line of group.lines) {
        const stateLine = state.cart.find((item) => item.source_product_id === line.source_product_id);
        if (!stateLine) continue;
        const item = el("article", `cart-line${line.checked ? " is-checked" : ""}${line.invalid ? " is-invalid" : ""}`);
        const check = el("button", "check-button", line.checked ? "☑" : "☐");
        check.type = "button";
        check.setAttribute("aria-label", line.checked ? "Marcar pendiente" : "Marcar comprado");
        check.addEventListener("click", () => { stateLine.checked = !stateLine.checked; persist(); });
        const info = el("div", "cart-line-info");
        info.append(el("strong", null, line.product_name), el("span", "muted", [line.brand, line.presentation].filter(Boolean).join(" · ")));
        const price = line.line_total_minor === null ? `Último precio guardado ${formatHnl(line.unit_price_minor)} · total incompleto` : `${line.quantity} × ${formatHnl(line.unit_price_minor)} = ${formatHnl(line.line_total_minor)}`;
        info.append(el("span", "line-price", price));
        if (line.invalid) info.append(el("span", "danger-text", "Oferta no disponible. No se sustituyó por otro supermercado."));
        else if (line.freshness_status === "STALE") info.append(el("span", "warning", "Precio stale"));
        const controls = el("div", "quantity-controls");
        const minus = el("button", null, "−");
        const quantity = el("input", "quantity-input");
        const plus = el("button", null, "+");
        const remove = el("button", "danger-link", "Eliminar");
        minus.type = plus.type = remove.type = "button";
        quantity.type = "number";
        quantity.min = "1";
        quantity.max = "999";
        quantity.inputMode = "numeric";
        quantity.value = String(line.quantity);
        quantity.setAttribute("aria-label", `Cantidad de ${line.product_name}`);
        minus.disabled = line.quantity <= 1;
        minus.addEventListener("click", () => { stateLine.quantity -= 1; persist(); });
        quantity.addEventListener("change", () => {
          const value = Number(quantity.value);
          if (Number.isInteger(value) && value >= 1 && value <= 999) stateLine.quantity = value;
          else quantity.value = String(stateLine.quantity);
          persist();
        });
        plus.addEventListener("click", () => { if (stateLine.quantity < 999) stateLine.quantity += 1; persist(); });
        remove.addEventListener("click", () => { state.cart = state.cart.filter((x) => x.source_product_id !== line.source_product_id); persist(); });
        controls.append(minus, quantity, plus, remove);
        item.append(check, info, controls);
        section.append(item);
      }
      section.append(el("div", "retailer-subtotal", group.incomplete ? "Subtotal incompleto" : `Subtotal ${formatHnl(group.subtotal_minor)}`));
      cart.append(section);
    }
  }

  function renderResults() {
    results.replaceChildren();
    if (!state.mart) return;
    const products = searchProducts(state.mart.products, search.value);
    if (!search.value.trim()) {
      results.append(el("p", "empty-state", "Escribe un producto, marca o presentación para comenzar."));
      return;
    }
    if (!products.length) {
      results.append(el("p", "empty-state", "No encontré productos seguros con esa búsqueda."));
      return;
    }
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
        if (offer.difference_vs_best_abs !== null && offer.difference_vs_best_pct !== null) {
          const deltaMinor = moneyToMinor(offer.difference_vs_best_abs);
          const prefix = offer.is_best_price ? "" : "+";
          offerCard.append(metric("Vs mejor precio", `${prefix}${formatHnl(deltaMinor)} · ${prefix}${offer.difference_vs_best_pct}%`));
        }
        const history = offer.historical_summary;
        if (history) {
          const w30 = history.windows?.["30d"], w90 = history.windows?.["90d"];
          offerCard.append(metric("Promedio 30d", w30?.status === "available" ? formatHnl(moneyToMinor(w30.average)) : "Historial insuficiente"));
          offerCard.append(metric("Promedio 90d", w90?.status === "available" ? formatHnl(moneyToMinor(w90.average)) : "Historial insuficiente"));
          offerCard.append(metric("Posición histórica", history.historical_position ?? "insufficient_history"));
        }
        const add = el("button", "primary-button", "Agregar aquí");
        add.type = "button";
        add.addEventListener("click", () => {
          const line = lineFromOffer(product, offer);
          if (!line) return;
          state.cart = selectOffer(state.cart, line);
          persist();
          document.querySelector("#cart-panel").scrollIntoView({behavior: "smooth", block: "start"});
        });
        offerCard.append(add);
        offerGrid.append(offerCard);
      }
      card.append(offerGrid);
      results.append(card);
    }
  }

  async function exportCart(kind) {
    if (!state.cart.length) return;
    exportStatus.textContent = `Preparando ${kind.toUpperCase()}…`;
    try {
      const exportsModule = await import("./exports.js");
      const summary = cartSummary(state.cart);
      const generatedAt = new Date();
      const date = generatedAt.toISOString().slice(0, 10);
      if (kind === "csv") {
        const csv = exportsModule.buildCartCsv(summary);
        downloadBlob(new Blob([csv], {type: "text/csv;charset=utf-8"}), `mi-compra-${date}.csv`);
      } else {
        const pdf = exportsModule.buildCartPdf(summary, generatedAt);
        downloadBlob(new Blob([pdf], {type: "application/pdf"}), `mi-compra-${date}.pdf`);
      }
      exportStatus.textContent = `${kind.toUpperCase()} generado desde tu lista local.`;
    } catch {
      exportStatus.textContent = `No fue posible generar ${kind.toUpperCase()}.`;
    }
  }

  exportCsvButton.addEventListener("click", () => { void exportCart("csv"); });
  exportPdfButton.addEventListener("click", () => { void exportCart("pdf"); });
  refreshButton.addEventListener("click", () => {
    if (!state.mart) return;
    state.cart = refreshCartPrices(state.cart, state.mart);
    persist();
  });

  async function loadMart() {
    const url = globalThis.RPI_CONSUMER_MART_URL || document.body.dataset.martUrl;
    try {
      const response = await fetch(url, {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const mart = await response.json();
      if (!consumerMartContractIsCompatible(mart)) throw new Error("Contrato no compatible");
      state.mart = mart;
      status.textContent = `${mart.product_count} productos seguros · corte ${mart.as_of} · ${mart.comparison_status}`;
      renderResults();
      renderRefresh();
    } catch (error) {
      status.textContent = "Datos no disponibles. Se conserva tu lista local.";
      results.replaceChildren(el("p", "safety-note", `No fue posible cargar precios públicos: ${error.message}`));
      refreshBox.hidden = true;
    }
  }

  search.addEventListener("input", renderResults);
  renderCart();
  loadMart();
}

if (typeof document !== "undefined") createApp();