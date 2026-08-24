import { canonicalBytes, EdgePolicyError, sha256Hex } from "./core.mjs";

const SHA256_RE = /^[0-9a-f]{64}$/u;
const SOURCE_RE = /^request:regionid:sha256:([0-9a-f]{64})$/u;
const EVIDENCE_RE = /^location_binding_radiography:sha256:[0-9a-f]{64}$/u;
const PLACEMENTS = new Set(["query", "header"]);
const REGION_KEYS = new Set(["region", "regionid", "xvtexregion"]);
const EXACT_KEYS = [
  "locationId",
  "bindingSourceKey",
  "bindingEvidence",
  "contextFingerprint",
  "placement",
  "wireKey",
  "valuePath",
  "wireRequestFingerprint",
  "rawValue",
];

function fail(code) {
  throw new EdgePolicyError(code, code);
}

function exactObject(value, expected, code) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) fail(code);
  return value;
}

function text(value, code, maximum = 4096) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > maximum) fail(code);
  return value;
}

function canonicalRegionKey(value) {
  return value.toLowerCase().replace(/[^a-z0-9]/gu, "");
}

export async function validateAndApplyCatalogLocationContext(originUrl, input) {
  const source = exactObject(input, EXACT_KEYS, "catalog_location_context_shape_invalid");
  if (source.locationId !== "la_colonia_sps") fail("catalog_location_id_invalid");
  const bindingSourceKey = text(source.bindingSourceKey, "catalog_binding_source_key_invalid", 512);
  const sourceMatch = SOURCE_RE.exec(bindingSourceKey);
  if (!sourceMatch) fail("catalog_binding_source_key_invalid");
  const bindingEvidence = text(source.bindingEvidence, "catalog_binding_evidence_invalid", 512);
  if (!EVIDENCE_RE.test(bindingEvidence)) fail("catalog_binding_evidence_invalid");
  const contextFingerprint = text(source.contextFingerprint, "catalog_context_fingerprint_invalid", 64);
  if (!SHA256_RE.test(contextFingerprint)) fail("catalog_context_fingerprint_invalid");
  if (sourceMatch[1] !== contextFingerprint) fail("catalog_binding_context_fingerprint_mismatch");
  const placement = text(source.placement, "catalog_context_placement_invalid", 16);
  if (!PLACEMENTS.has(placement)) fail("catalog_context_placement_invalid");
  const wireKey = text(source.wireKey, "catalog_context_wire_key_invalid", 160);
  if (!REGION_KEYS.has(canonicalRegionKey(wireKey))) fail("catalog_context_wire_key_not_region");
  if (!Array.isArray(source.valuePath) || source.valuePath.length !== 0) fail("catalog_context_value_path_invalid");
  const wireRequestFingerprint = text(source.wireRequestFingerprint, "catalog_wire_request_fingerprint_invalid", 64);
  if (!SHA256_RE.test(wireRequestFingerprint)) fail("catalog_wire_request_fingerprint_invalid");
  const rawValue = text(source.rawValue, "catalog_context_raw_value_invalid", 4096);
  const observedFingerprint = await sha256Hex(canonicalBytes(rawValue));
  if (observedFingerprint !== contextFingerprint) fail("catalog_context_raw_fingerprint_mismatch");

  let url = originUrl;
  const headers = {};
  if (placement === "query") {
    const parsed = new URL(originUrl);
    for (const key of parsed.searchParams.keys()) {
      if (key.toLowerCase() === wireKey.toLowerCase()) fail("catalog_context_query_key_already_present");
    }
    parsed.searchParams.append(wireKey, rawValue);
    url = parsed.toString();
  } else {
    headers[wireKey] = rawValue;
  }

  const computedWireFingerprint = await sha256Hex(canonicalBytes({
    method: "GET",
    url,
    headers,
  }));
  if (computedWireFingerprint !== wireRequestFingerprint) fail("catalog_wire_request_fingerprint_mismatch");

  return Object.freeze({
    fetchUrl: url,
    fetchHeaders: Object.freeze(headers),
    receiptContext: Object.freeze({
      locationId: "la_colonia_sps",
      bindingSourceKey,
      bindingEvidence,
      contextFingerprint,
      contextPlacement: placement,
      contextWireKey: wireKey,
      contextValuePath: Object.freeze([]),
      wireRequestFingerprint,
    }),
  });
}
