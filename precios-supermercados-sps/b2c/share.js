import {CART_KEY, LEGACY_CART_KEY, RETAILERS, cartSummary, formatHnl} from "./catalog.js";

function dateTimeHn(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("es-HN", {
    timeZone: "America/Tegucigalpa",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function dateHn(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("es-HN", {
    timeZone: "America/Tegucigalpa",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

function productLabel(line) {
  const values = [line.product_name, line.brand, line.presentation].filter(Boolean);
  const seen = new Set();
  return values.filter((value) => {
    const key = String(value).trim().toLocaleLowerCase("es");
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  }).join(" · ");
}

function loadedCart(storage) {
  try {
    const raw = storage.getItem(CART_KEY) ?? storage.getItem(LEGACY_CART_KEY) ?? "[]";
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((line) => line && typeof line.source_product_id === "string") : [];
  } catch {
    return [];
  }
}

function observedDates(lines) {
  const dates = new Set();
  for (const line of lines) {
    const value = dateHn(line.observed_at);
    if (value) dates.add(value);
  }
  return [...dates];
}

export function buildWhatsAppMessage(lines, now = new Date(), city = "San Pedro Sula") {
  const summary = cartSummary(lines);
  if (!summary.products) return "";
  const prepared = dateTimeHn(now) ?? "fecha no disponible";
  const dates = observedDates(lines);
  const output = [
    "🛒 *MI LISTA DE COMPRA*",
    city,
    "",
    `Preparada: ${prepared}`,
    dates.length === 1 ? `Precios observados: ${dates[0]}` : dates.length > 1 ? `Fechas de precios: ${dates.join(", ")}` : "Precios observados: fecha no disponible",
  ];

  for (const retailer of RETAILERS) {
    const group = summary.retailers.get(retailer.supermarket_id);
    if (!group) continue;
    output.push("", `*${retailer.name.toLocaleUpperCase("es-HN")}*`);
    for (const line of group.lines) {
      const unit = Number.isSafeInteger(line.unit_price_minor) ? formatHnl(line.unit_price_minor) : "precio no disponible";
      const total = Number.isSafeInteger(line.line_total_minor) ? formatHnl(line.line_total_minor) : "incompleto";
      output.push(`• ${productLabel(line)}`);
      output.push(`  ${line.quantity} × ${unit} = ${total}`);
      if (line.is_promotion === true) {
        const regular = Number.isSafeInteger(line.reported_regular_price_minor) ? ` · regular ${formatHnl(line.reported_regular_price_minor)}` : "";
        output.push(`  🔥 Promoción${regular}`);
      }
      if (line.invalid || line.freshness_status === "UNAVAILABLE") output.push("  ⚠️ Oferta no disponible en el último corte válido");
      else if (line.freshness_status !== "FRESH") output.push("  ⚠️ Precio no actualizado recientemente");
    }
    output.push(group.incomplete ? `*Subtotal ${retailer.name}: incompleto*` : `*Subtotal ${retailer.name}: ${formatHnl(group.subtotal_minor)}*`);
  }

  output.push(
    "",
    summary.grand_total_minor === null ? "*TOTAL ESTIMADO: INCOMPLETO*" : `*TOTAL ESTIMADO: ${formatHnl(summary.grand_total_minor)}*`,
    `${summary.products} producto${summary.products === 1 ? "" : "s"} · ${summary.units} unidad${summary.units === 1 ? "" : "es"} · ${summary.retailer_count} supermercado${summary.retailer_count === 1 ? "" : "s"}`,
  );
  if (summary.incomplete) output.push(`⚠️ ${summary.incomplete} línea${summary.incomplete === 1 ? "" : "s"} con total incompleto`);
  if (summary.stale) output.push(`⚠️ ${summary.stale} precio${summary.stale === 1 ? "" : "s"} no actualizado${summary.stale === 1 ? "" : "s"} recientemente`);
  output.push("", "Precios públicos observados. Pueden cambiar en tienda.");
  return output.join("\n");
}

export function whatsAppShareUrl(message) {
  return message ? `https://wa.me/?text=${encodeURIComponent(message)}` : null;
}

function installShare() {
  const button = document.getElementById("share-whatsapp");
  const status = document.getElementById("share-status");
  const cartCount = document.getElementById("cart-count");
  if (!button || !status) return;

  const refreshButton = () => {
    button.disabled = loadedCart(localStorage).length === 0;
  };
  refreshButton();
  if (cartCount) new MutationObserver(refreshButton).observe(cartCount, {childList: true, characterData: true, subtree: true});

  button.addEventListener("click", () => {
    const lines = loadedCart(localStorage);
    const city = document.body?.dataset.cityName || "San Pedro Sula";
    const message = buildWhatsAppMessage(lines, new Date(), city);
    const url = whatsAppShareUrl(message);
    if (!url) {
      status.textContent = "Agrega productos a tu lista antes de compartirla.";
      refreshButton();
      return;
    }
    status.textContent = "Abriendo WhatsApp con tu lista preparada…";
    window.open(url, "_blank", "noopener,noreferrer");
  });
}

if (typeof document !== "undefined") installShare();
