import { canonicalBytes, EdgePolicyError, sha256Hex } from "./core.mjs";
import { STRUCTURAL_SPS_CONTEXT_POLICY } from "./worker-policy.mjs";

const SHA256_RE = /^[0-9a-f]{64}$/u;
const SOURCE_RE = /^request:regionid:sha256:([0-9a-f]{64})$/u;
const EVIDENCE_RE = /^location_binding_radiography:sha256:[0-9a-f]{64}$/u;
const PLACEMENTS = new Set(["query", "header"]);
const REGION_KEYS = new Set(["region", "regionid", "xvtexregion"]);
const BASE_KEYS = Object.freeze([
  "locationId",
  "bindingSourceKey",
  "bindingEvidence",
  "contextFingerprint",
  "placement",
  "wireKey",
  "valuePath",
  "wireRequestFingerprint",
  "rawValue",
]);
const SESSION_KEYS = Object.freeze(["vtexsegment", "vtexsession"]);
const SESSION_SIGNAL_KEYS = Object.freeze(["fingerprint", "rawValue"]);

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

function cookieValue(value, code) {
  const raw = text(value, code, 8192);
  if (raw.includes("\r") || raw.includes("\n") || raw.includes(";")) fail(code);
  return raw;
}

function canonicalRegionKey(value) {
  return value.toLowerCase().replace(/[^a-z0-9]/gu, "");
}

function validatePolicy(policy) {
  if (!policy || typeof policy !== "object" || Array.isArray(policy)) fail("structural_sps_context_policy_invalid");
  const evidence = text(policy.bindingEvidence, "structural_sps_context_policy_evidence_invalid", 512);
  if (!EVIDENCE_RE.test(evidence)) fail("structural_sps_context_policy_evidence_invalid");
  const regionFingerprint = text(policy.regionFingerprint, "structural_sps_region_policy_invalid", 64);
  if (!SHA256_RE.test(regionFingerprint)) fail("structural_sps_region_policy_invalid");
  const sourceLocationKey = text(policy.sourceLocationKey, "structural_sps_source_policy_invalid", 512);
  const sourceMatch = SOURCE_RE.exec(sourceLocationKey);
  if (!sourceMatch || sourceMatch[1] !== regionFingerprint) fail("structural_sps_source_policy_invalid");
  const fingerprints = exactObject(
    policy.expectedSessionFingerprints,
    SESSION_KEYS,
    "structural_sps_session_policy_shape_invalid",
  );
  for (const key of SESSION_KEYS) {
    const value = text(fingerprints[key], `structural_sps_${key}_policy_invalid`, 64);
    if (!SHA256_RE.test(value)) fail(`structural_sps_${key}_policy_invalid`);
  }
  return Object.freeze({
    bindingEvidence: evidence,
    regionFingerprint,
    sourceLocationKey,
    expectedSessionFingerprints: fingerprints,
  });
}

async function validateSessionSignals(source, bindingEvidence, bindingSourceKey, contextFingerprint, policy) {
  if (!Object.hasOwn(source, "sessionSignals")) return null;
  if (bindingEvidence !== policy.bindingEvidence) fail("structural_session_binding_evidence_mismatch");
  if (bindingSourceKey !== policy.sourceLocationKey) fail("structural_session_source_location_key_mismatch");
  if (contextFingerprint !== policy.regionFingerprint) fail("structural_session_region_fingerprint_mismatch");
  const signals = exactObject(
    source.sessionSignals,
    SESSION_KEYS,
    "structural_session_signals_shape_invalid",
  );
  const rawValues = {};
  const fingerprints = {};
  for (const key of SESSION_KEYS) {
    const item = exactObject(
      signals[key],
      SESSION_SIGNAL_KEYS,
      `structural_session_${key}_shape_invalid`,
    );
    const expected = text(item.fingerprint, `structural_session_${key}_fingerprint_invalid`, 64);
    if (!SHA256_RE.test(expected)) fail(`structural_session_${key}_fingerprint_invalid`);
    if (expected !== policy.expectedSessionFingerprints[key]) fail(`structural_session_${key}_fingerprint_policy_mismatch`);
    const raw = cookieValue(item.rawValue, `structural_session_${key}_raw_invalid`);
    const observed = await sha256Hex(canonicalBytes(raw));
    if (observed !== expected) fail(`structural_session_${key}_raw_fingerprint_mismatch`);
    rawValues[key] = raw;
    fingerprints[key] = expected;
  }
  return Object.freeze({
    cookieHeader: SESSION_KEYS.map((key) => `${key}=${rawValues[key]}`).join("; "),
    fingerprints: Object.freeze(fingerprints),
  });
}

export async function validateAndApplyStructuralLocationContext(
  originUrl,
  input,
  policyInput = STRUCTURAL_SPS_CONTEXT_POLICY,
) {
  if (!input || typeof input !== "object" || Array.isArray(input)) fail("structural_location_context_shape_invalid");
  const hasSession = Object.hasOwn(input, "sessionSignals");
  const source = exactObject(
    input,
    hasSession ? [...BASE_KEYS, "sessionSignals"] : BASE_KEYS,
    "structural_location_context_shape_invalid",
  );
  const policy = validatePolicy(policyInput);
  if (source.locationId !== "la_colonia_sps") fail("structural_location_id_invalid");
  const bindingSourceKey = text(source.bindingSourceKey, "structural_binding_source_key_invalid", 512);
  const sourceMatch = SOURCE_RE.exec(bindingSourceKey);
  if (!sourceMatch) fail("structural_binding_source_key_invalid");
  const bindingEvidence = text(source.bindingEvidence, "structural_binding_evidence_invalid", 512);
  if (!EVIDENCE_RE.test(bindingEvidence)) fail("structural_binding_evidence_invalid");
  const contextFingerprint = text(source.contextFingerprint, "structural_context_fingerprint_invalid", 64);
  if (!SHA256_RE.test(contextFingerprint)) fail("structural_context_fingerprint_invalid");
  if (sourceMatch[1] !== contextFingerprint) fail("structural_binding_context_fingerprint_mismatch");
  const placement = text(source.placement, "structural_context_placement_invalid", 16);
  if (!PLACEMENTS.has(placement)) fail("structural_context_placement_invalid");
  const wireKey = text(source.wireKey, "structural_context_wire_key_invalid", 160);
  if (!REGION_KEYS.has(canonicalRegionKey(wireKey))) fail("structural_context_wire_key_not_region");
  if (!Array.isArray(source.valuePath) || source.valuePath.length !== 0) fail("structural_context_value_path_invalid");
  const wireRequestFingerprint = text(source.wireRequestFingerprint, "structural_wire_request_fingerprint_invalid", 64);
  if (!SHA256_RE.test(wireRequestFingerprint)) fail("structural_wire_request_fingerprint_invalid");
  const rawValue = text(source.rawValue, "structural_context_raw_value_invalid", 4096);
  const observedFingerprint = await sha256Hex(canonicalBytes(rawValue));
  if (observedFingerprint !== contextFingerprint) fail("structural_context_raw_fingerprint_mismatch");
  const session = await validateSessionSignals(
    source,
    bindingEvidence,
    bindingSourceKey,
    contextFingerprint,
    policy,
  );

  let url = originUrl;
  const headers = {};
  if (placement === "query") {
    const parsed = new URL(originUrl);
    for (const key of parsed.searchParams.keys()) {
      if (key.toLowerCase() === wireKey.toLowerCase()) fail("structural_context_query_key_already_present");
    }
    parsed.searchParams.append(wireKey, rawValue);
    url = parsed.toString();
  } else {
    headers[wireKey] = rawValue;
  }
  if (session) headers.cookie = session.cookieHeader;

  const computedWireFingerprint = await sha256Hex(canonicalBytes({ method: "GET", url, headers }));
  if (computedWireFingerprint !== wireRequestFingerprint) fail("structural_wire_request_fingerprint_mismatch");

  const receiptContext = {
    locationId: "la_colonia_sps",
    bindingSourceKey,
    bindingEvidence,
    contextFingerprint,
    contextPlacement: placement,
    contextWireKey: wireKey,
    contextValuePath: Object.freeze([]),
    wireRequestFingerprint,
  };
  if (session) {
    Object.assign(receiptContext, {
      sessionContextComplete: true,
      vtexsegmentFingerprint: session.fingerprints.vtexsegment,
      vtexsessionFingerprint: session.fingerprints.vtexsession,
    });
  }

  return Object.freeze({
    fetchUrl: url,
    fetchHeaders: Object.freeze(headers),
    receiptContext: Object.freeze(receiptContext),
  });
}
