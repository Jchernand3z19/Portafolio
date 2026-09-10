import {manifestIsCompatible} from "./catalog.js";

const HN_TIME_ZONE = "America/Tegucigalpa";

function partsFor(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: HN_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

function dayKey(value) {
  const parts = partsFor(value);
  return parts ? `${parts.year}-${parts.month}-${parts.day}` : null;
}

function humanDateTime(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("es-HN", {
    timeZone: HN_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function datasetStatus(manifest, now = new Date()) {
  if (!manifestIsCompatible(manifest)) return {state: "invalid", text: "⚠️ No se pudo validar el corte público de precios."};
  const asOf = new Date(manifest.as_of);
  if (Number.isNaN(asOf.getTime())) return {state: "invalid", text: "⚠️ El corte publicado no tiene una fecha válida."};
  const label = humanDateTime(asOf) ?? manifest.as_of;
  const today = dayKey(now);
  const accepted = dayKey(asOf);
  if (today && accepted === today) return {state: "current", text: `✅ Datos actualizados hoy · último corte aceptado ${label}.`};
  return {state: "stale", text: `⚠️ Último corte aceptado ${label}. Todavía no hay una actualización aceptada de hoy.`};
}

async function installStatus() {
  const node = document.getElementById("dataset-status");
  const manifestUrl = document.body.dataset.catalogUrl;
  if (!node || !manifestUrl) return;
  try {
    const response = await fetch(manifestUrl, {cache: "no-store"});
    if (!response.ok) throw new Error(`manifest_http_${response.status}`);
    const manifest = await response.json();
    const status = datasetStatus(manifest);
    node.dataset.state = status.state;
    node.textContent = status.text;
  } catch {
    node.dataset.state = "unavailable";
    node.textContent = "⚠️ No fue posible comprobar la fecha del último corte. Tu lista guardada sigue disponible.";
  }
}

if (typeof document !== "undefined") void installStatus();
