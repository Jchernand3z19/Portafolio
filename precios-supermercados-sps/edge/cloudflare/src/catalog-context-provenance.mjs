import { canonicalJson, EdgePolicyError } from "./core.mjs";

export const CATALOG_CONTEXT_RECEIPT_SCHEMA_VERSION = "3";

const SHA256_RE = /^[0-9a-f]{64}$/u;
const SOURCE_RE = /^request:regionid:sha256:([0-9a-f]{64})$/u;
const EVIDENCE_RE = /^location_binding_radiography:sha256:[0-9a-f]{64}$/u;
const PLACEMENTS = new Set(["query", "header"]);
const REGION_KEYS = new Set(["region", "regionid", "xvtexregion"]);
const LOCATION_KEYS = [
  "locationId",
  "bindingSourceKey",
  "bindingEvidence",
  "contextFingerprint",
  "contextPlacement",
  "contextWireKey",
  "contextValuePath",
  "wireRequestFingerprint",
];

function fail(code) {
  throw new EdgePolicyError(code, code);
}

function exactObject(value, keys, code) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) fail(code);
  return value;
}

function text(value, code, maximum = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > maximum) fail(code);
  return value;
}

function canonicalRegionKey(value) {
  return value.toLowerCase().replace(/[^a-z0-9]/gu, "");
}

function validateReceiptLocationContext(value) {
  const source = exactObject(value, LOCATION_KEYS, "catalog_receipt_location_context_shape_invalid");
  if (source.locationId !== "la_colonia_sps") fail("catalog_receipt_location_id_invalid");
  const bindingSourceKey = text(source.bindingSourceKey, "catalog_receipt_binding_source_key_invalid");
  const match = SOURCE_RE.exec(bindingSourceKey);
  if (!match) fail("catalog_receipt_binding_source_key_invalid");
  const bindingEvidence = text(source.bindingEvidence, "catalog_receipt_binding_evidence_invalid");
  if (!EVIDENCE_RE.test(bindingEvidence)) fail("catalog_receipt_binding_evidence_invalid");
  const contextFingerprint = text(source.contextFingerprint, "catalog_receipt_context_fingerprint_invalid", 64);
  if (!SHA256_RE.test(contextFingerprint)) fail("catalog_receipt_context_fingerprint_invalid");
  if (match[1] !== contextFingerprint) fail("catalog_receipt_binding_fingerprint_mismatch");
  const contextPlacement = text(source.contextPlacement, "catalog_receipt_context_placement_invalid", 16);
  if (!PLACEMENTS.has(contextPlacement)) fail("catalog_receipt_context_placement_invalid");
  const contextWireKey = text(source.contextWireKey, "catalog_receipt_context_wire_key_invalid", 160);
  if (!REGION_KEYS.has(canonicalRegionKey(contextWireKey))) fail("catalog_receipt_context_wire_key_invalid");
  if (!Array.isArray(source.contextValuePath) || source.contextValuePath.length !== 0) fail("catalog_receipt_context_value_path_invalid");
  const wireRequestFingerprint = text(source.wireRequestFingerprint, "catalog_receipt_wire_request_fingerprint_invalid", 64);
  if (!SHA256_RE.test(wireRequestFingerprint)) fail("catalog_receipt_wire_request_fingerprint_invalid");
  return Object.freeze({
    locationId: "la_colonia_sps",
    bindingSourceKey,
    bindingEvidence,
    contextFingerprint,
    contextPlacement,
    contextWireKey,
    contextValuePath: Object.freeze([]),
    wireRequestFingerprint,
  });
}

export function buildContextBoundCatalogReceiptPayload(basePayload, locationContext) {
  if (!basePayload || typeof basePayload !== "object" || Array.isArray(basePayload)) fail("catalog_receipt_base_payload_invalid");
  if (basePayload.schema_version !== "2") fail("catalog_receipt_base_schema_invalid");
  const location = validateReceiptLocationContext(locationContext);
  const payload = {
    ...basePayload,
    schema_version: CATALOG_CONTEXT_RECEIPT_SCHEMA_VERSION,
    location_id: location.locationId,
    binding_source_key: location.bindingSourceKey,
    binding_evidence: location.bindingEvidence,
    context_fingerprint: location.contextFingerprint,
    context_placement: location.contextPlacement,
    context_wire_key: location.contextWireKey,
    context_value_path: [...location.contextValuePath],
    wire_request_fingerprint: location.wireRequestFingerprint,
  };
  canonicalJson(payload);
  return Object.freeze(payload);
}
