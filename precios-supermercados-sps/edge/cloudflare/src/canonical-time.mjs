import { EdgePolicyError } from "./core.mjs";

export function canonicalEdgeTimestamp(value) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
    throw new EdgePolicyError("canonical_time_invalid");
  }
  const iso = value.toISOString();
  if (iso.endsWith(".000Z")) return `${iso.slice(0, -5)}Z`;
  return iso.replace(/\.(\d{3})Z$/u, ".$1000Z");
}
