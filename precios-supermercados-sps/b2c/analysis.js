const EXPECTED_RETAILERS = Object.freeze([
  "la_colonia", "colonial", "walmart", "pricesmart", "comisariato_los_andes",
]);

function node(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined && text !== null) value.textContent = String(text);
  return value;
}

function hnl(value) {
  return typeof value === "string" && /^\d+(?:\.\d{2})$/.test(value) ? `L ${value}` : "—";
}

function percent(value) {
  return typeof value === "string" && /^-?\d+(?:\.\d{2})$/.test(value) ? `${value}%` : "—";
}

export function analysisIsCompatible(value, manifest) {
  if (value?.schema !== "rpi-consumer-analysis/v1" || value.as_of !== manifest?.as_of) return false;
  if (!value.summary || !Array.isArray(value.retailers) || !Array.isArray(value.categories)) return false;
  if (!value.opportunities || !["price_drops", "price_increases", "promotions", "recent_lows"].every((key) => Array.isArray(value.opportunities[key]))) return false;
  return value.retailers.length === EXPECTED_RETAILERS.length
    && value.retailers.every((retailer, index) => retailer?.supermarket_id === EXPECTED_RETAILERS[index]);
}

function metric(label, value, note) {
  const card = node("article", "metric-card");
  card.append(node("span", null, label), node("strong", null, value), node("small", null, note));
  return card;
}

function opportunityList(title, rows, mode) {
  const card = node("article", "opportunity-card");
  card.append(node("h4", null, title));
  const list = node("ol");
  for (const item of rows.slice(0, 6)) {
    const entry = node("li");
    const copy = node("div");
    copy.append(node("strong", null, item.product_name), node("small", null, [item.brand, item.presentation, item.retailer_name].filter(Boolean).join(" · ")));
    const price = node("div", "opportunity-price");
    price.append(node("strong", null, hnl(item.current_price)));
    if (mode === "movement") price.append(node("small", item.change_pct?.startsWith("-") ? "trend-down" : "trend-up", percent(item.change_pct)));
    if (mode === "promotion" && item.discount_pct) price.append(node("small", "trend-down", `${percent(item.discount_pct)} menos`));
    entry.append(copy, price); list.append(entry);
  }
  if (!rows.length) list.append(node("li", "empty-inline", "Aún no hay evidencia suficiente en este corte."));
  card.append(list);
  return card;
}

export function renderConsumerAnalysis(targets, analysis) {
  const summary = analysis.summary;
  targets.summary.replaceChildren(
    metric("Productos visibles", Number(summary.visible_products).toLocaleString("es-HN"), "con al menos una oferta pública"),
    metric("Comparables seguros", Number(summary.comparable_products).toLocaleString("es-HN"), "identidad ready y precio fresco"),
    metric("Promociones activas", Number(summary.active_promotions).toLocaleString("es-HN"), "reportadas por los comercios"),
    metric("Ahorro unitario observado", hnl(summary.observed_unit_savings), "suma de brechas; no es una canasta"),
    metric("Bajaron / subieron", `${Number(summary.price_movements.decreased).toLocaleString("es-HN")} / ${Number(summary.price_movements.increased).toLocaleString("es-HN")}`, "contra la observación aceptada anterior"),
    metric("En mínimo reciente", Number(summary.recent_low_opportunities).toLocaleString("es-HN"), "según hasta 90 días de historia"),
  );

  targets.retailers.replaceChildren(...analysis.retailers.map((retailer) => {
    const card = node("article", "retailer-analysis-card");
    card.append(node("h4", null, retailer.name));
    const values = node("dl");
    for (const [label, value] of [
      ["Ofertas visibles", Number(retailer.visible_offers).toLocaleString("es-HN")],
      ["Mejores precios", Number(retailer.best_price_wins).toLocaleString("es-HN")],
      ["Cobertura comparable", Number(retailer.comparable_products).toLocaleString("es-HN")],
      ["Promociones", `${Number(retailer.active_promotions).toLocaleString("es-HN")} · ${percent(retailer.promotion_rate_pct)}`],
    ]) {
      values.append(node("dt", null, label), node("dd", null, value));
    }
    card.append(values);
    return card;
  }));

  targets.opportunities.replaceChildren(
    opportunityList("Bajaron de precio", analysis.opportunities.price_drops, "movement"),
    opportunityList("En promoción", analysis.opportunities.promotions, "promotion"),
    opportunityList("En mínimo reciente", analysis.opportunities.recent_lows, "low"),
    opportunityList("Subieron de precio", analysis.opportunities.price_increases, "movement"),
  );

  const table = node("table", "analysis-table");
  const head = node("tr");
  for (const label of ["Categoría", "Productos comparables", "Líder(es) en mejores precios", "Brecha unitaria observable"]) head.append(node("th", null, label));
  const thead = node("thead"); thead.append(head);
  const body = node("tbody");
  for (const category of analysis.categories.slice(0, 12)) {
    const row = node("tr");
    row.append(
      node("th", null, category.category),
      node("td", null, Number(category.comparable_products).toLocaleString("es-HN")),
      node("td", null, category.best_price_leaders.join(" · ") || "Empate sin líder"),
      node("td", null, hnl(category.unit_savings)),
    );
    body.append(row);
  }
  if (!analysis.categories.length) {
    const row = node("tr"); const cell = node("td", "empty-inline", "Aún no hay categorías con comparación segura."); cell.colSpan = 4; row.append(cell); body.append(row);
  }
  table.append(thead, body); targets.categories.replaceChildren(table);
}
