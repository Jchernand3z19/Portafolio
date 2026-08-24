import {
  canonicalBytes,
  decodeBase64Url,
  encodeBase64Url,
  importEd25519PrivateKeyPkcs8,
  importEd25519PublicKeySpki,
  sha256Hex,
} from "./core.mjs";

export const STRUCTURAL_PROVENANCE_SCHEMA_VERSION = "1";
export const STRUCTURAL_PROVENANCE_CONTEXT_SCHEMA_VERSION = "2";
export const STRUCTURAL_SIGNATURE_DOMAIN = "precios-sps/structural-receipt-signature/v1\0";
export const STRUCTURAL_DIGEST_DOMAIN = "precios-sps/structural-receipt/v1\0";
export const STRUCTURAL_CONTEXT_SIGNATURE_DOMAIN = "precios-sps/structural-receipt-signature/v2\0";
export const STRUCTURAL_CONTEXT_DIGEST_DOMAIN = "precios-sps/structural-receipt/v2\0";

const encoder = new TextEncoder();
const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const SOURCE_RE = /^request:regionid:sha256:([0-9a-f]{64})$/u;
const EVIDENCE_RE = /^location_binding_radiography:sha256:[0-9a-f]{64}$/u;
const KINDS = new Set(["root_total", "category_tree"]);
const CONTEXT_PLACEMENTS = new Set(["query", "header"]);

function fail(code) {
  const error = new Error(code);
  error.name = "StructuralProvenanceError";
  error.code = code;
  throw error;
}

function text(value, code, maximum = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > maximum || /\s/u.test(value)) {
    fail(code);
  }
  return value;
}

function sha1(value, code) {
  const result = text(value, code, 40);
  if (!SHA1_RE.test(result)) fail(code);
  return result;
}

function sha256(value, code) {
  const result = text(value, code, 64);
  if (!SHA256_RE.test(result)) fail(code);
  return result;
}

function safeInt(value, code, minimum = 0, maximum = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) fail(code);
  return value;
}

function timestamp(value, code) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) fail(code);
  return value.toISOString();
}

function concat(...parts) {
  const length = parts.reduce((total, item) => total + item.byteLength, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  for (const item of parts) {
    result.set(item, offset);
    offset += item.byteLength;
  }
  return result;
}

function normalizeLocationContext(value) {
  if (value === undefined || value === null) return null;
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("structural_receipt_location_context_invalid");
  if (value.locationId !== "la_colonia_sps") fail("structural_receipt_location_id_invalid");
  const bindingSourceKey = text(value.bindingSourceKey, "structural_receipt_binding_source_key_invalid");
  const match = SOURCE_RE.exec(bindingSourceKey);
  if (!match) fail("structural_receipt_binding_source_key_invalid");
  const bindingEvidence = text(value.bindingEvidence, "structural_receipt_binding_evidence_invalid");
  if (!EVIDENCE_RE.test(bindingEvidence)) fail("structural_receipt_binding_evidence_invalid");
  const contextFingerprint = sha256(value.contextFingerprint, "structural_receipt_context_fingerprint_invalid");
  if (match[1] !== contextFingerprint) fail("structural_receipt_binding_context_fingerprint_mismatch");
  const contextPlacement = text(value.contextPlacement, "structural_receipt_context_placement_invalid", 16);
  if (!CONTEXT_PLACEMENTS.has(contextPlacement)) fail("structural_receipt_context_placement_invalid");
  const contextWireKey = text(value.contextWireKey, "structural_receipt_context_wire_key_invalid", 160);
  if (!Array.isArray(value.contextValuePath) || value.contextValuePath.length !== 0) {
    fail("structural_receipt_context_value_path_invalid");
  }
  return Object.freeze({
    binding_evidence: bindingEvidence,
    binding_source_key: bindingSourceKey,
    context_fingerprint: contextFingerprint,
    context_placement: contextPlacement,
    context_value_path: Object.freeze([]),
    context_wire_key: contextWireKey,
    location_id: "la_colonia_sps",
    wire_request_fingerprint: sha256(value.wireRequestFingerprint, "structural_receipt_wire_request_fingerprint_invalid"),
  });
}

export function buildStructuralReceiptPayload(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) fail("structural_receipt_input_invalid");
  const requestKind = input.requestKind;
  if (!KINDS.has(requestKind)) fail("structural_receipt_request_kind_invalid");
  const requestDigest = sha256(input.requestDigest, "structural_receipt_request_digest_invalid");
  const canonicalRequestSha256 = sha256(input.canonicalRequestSha256, "structural_receipt_canonical_request_sha256_invalid");
  if (requestDigest !== canonicalRequestSha256) fail("structural_receipt_request_digest_mismatch");
  const started = input.physicalStartedAt;
  const completed = input.responseCompletedAt;
  const startedText = timestamp(started, "structural_receipt_physical_started_at_invalid");
  const completedText = timestamp(completed, "structural_receipt_response_completed_at_invalid");
  if (completed.getTime() < started.getTime()) fail("structural_receipt_time_order_invalid");
  if (input.httpMethod !== "GET") fail("structural_receipt_http_method_invalid");
  if (input.targetScheme !== "https") fail("structural_receipt_target_scheme_invalid");
  if (input.targetHost !== "www.lacolonia.com") fail("structural_receipt_target_host_invalid");
  if (input.targetPath !== "/_v/segment/graphql/v1") fail("structural_receipt_target_path_invalid");
  if (input.responseStatus !== 200) fail("structural_receipt_response_status_invalid");
  if (input.collectorProvider !== "cloudflare_workers") fail("structural_receipt_collector_provider_invalid");
  if (input.signingAlgorithm !== "Ed25519") fail("structural_receipt_signing_algorithm_invalid");
  const locationContext = normalizeLocationContext(input.locationContext);

  const result = {
    approved_commit_sha: sha1(input.approvedCommitSha, "structural_receipt_approved_commit_sha_invalid"),
    authorization_id: text(input.authorizationId, "structural_receipt_authorization_id_invalid"),
    canonical_request_sha256: canonicalRequestSha256,
    collector_code_sha256: sha256(input.collectorCodeSha256, "structural_receipt_collector_code_sha256_invalid"),
    collector_execution: text(input.collectorExecution, "structural_receipt_collector_execution_invalid"),
    collector_principal: text(input.collectorPrincipal, "structural_receipt_collector_principal_invalid"),
    collector_provider: input.collectorProvider,
    collector_release_id: text(input.collectorReleaseId, "structural_receipt_collector_release_id_invalid"),
    github_environment: text(input.githubEnvironment, "structural_receipt_github_environment_invalid"),
    github_ref: text(input.githubRef, "structural_receipt_github_ref_invalid"),
    github_repository: text(input.githubRepository, "structural_receipt_github_repository_invalid"),
    github_repository_id: text(input.githubRepositoryId, "structural_receipt_github_repository_id_invalid"),
    github_run_attempt: safeInt(input.githubRunAttempt, "structural_receipt_github_run_attempt_invalid", 1, 100),
    github_run_id: text(input.githubRunId, "structural_receipt_github_run_id_invalid"),
    github_workflow_ref: text(input.githubWorkflowRef, "structural_receipt_github_workflow_ref_invalid"),
    graphql_query_sha256: sha256(input.graphqlQuerySha256, "structural_receipt_graphql_query_sha256_invalid"),
    http_method: input.httpMethod,
    nonce: text(input.nonce, "structural_receipt_nonce_invalid"),
    oidc_jti: text(input.oidcJti, "structural_receipt_oidc_jti_invalid"),
    oidc_subject: text(input.oidcSubject, "structural_receipt_oidc_subject_invalid"),
    physical_started_at_utc: startedText,
    raw_response_sha256: sha256(input.rawResponseSha256, "structural_receipt_raw_response_sha256_invalid"),
    request_digest: requestDigest,
    request_id: text(input.requestId, "structural_receipt_request_id_invalid"),
    request_kind: requestKind,
    reservation_id: text(input.reservationId, "structural_receipt_reservation_id_invalid"),
    response_body_bytes: safeInt(input.responseBodyBytes, "structural_receipt_response_body_bytes_invalid", 1),
    response_completed_at_utc: completedText,
    response_status: input.responseStatus,
    run_id: text(input.runId, "structural_receipt_run_id_invalid"),
    schema_version: locationContext ? STRUCTURAL_PROVENANCE_CONTEXT_SCHEMA_VERSION : STRUCTURAL_PROVENANCE_SCHEMA_VERSION,
    signing_algorithm: input.signingAlgorithm,
    signing_key_id: text(input.signingKeyId, "structural_receipt_signing_key_id_invalid"),
    target_host: input.targetHost,
    target_path: input.targetPath,
    target_scheme: input.targetScheme,
  };
  if (locationContext) Object.assign(result, locationContext);
  return Object.freeze(result);
}

function domains(payload) {
  if (payload?.schema_version === STRUCTURAL_PROVENANCE_CONTEXT_SCHEMA_VERSION) {
    return [STRUCTURAL_CONTEXT_SIGNATURE_DOMAIN, STRUCTURAL_CONTEXT_DIGEST_DOMAIN];
  }
  if (payload?.schema_version === STRUCTURAL_PROVENANCE_SCHEMA_VERSION) {
    return [STRUCTURAL_SIGNATURE_DOMAIN, STRUCTURAL_DIGEST_DOMAIN];
  }
  fail("structural_receipt_schema_version_invalid");
}

export function structuralReceiptSigningBytes(payload) {
  const [signatureDomain] = domains(payload);
  return concat(encoder.encode(signatureDomain), canonicalBytes(payload));
}

export async function signStructuralReceipt(payload, privateKeyPkcs8B64Url) {
  const key = await importEd25519PrivateKeyPkcs8(privateKeyPkcs8B64Url);
  const signature = await crypto.subtle.sign("Ed25519", key, structuralReceiptSigningBytes(payload));
  return encodeBase64Url(new Uint8Array(signature));
}

export async function verifyStructuralReceipt(payload, signatureB64Url, publicKeySpkiB64Url) {
  const signature = decodeBase64Url(signatureB64Url);
  if (signature.byteLength !== 64) return false;
  const key = await importEd25519PublicKeySpki(publicKeySpkiB64Url);
  return crypto.subtle.verify("Ed25519", key, signature, structuralReceiptSigningBytes(payload));
}

export async function structuralReceiptDigest(payload, signatureB64Url) {
  const signature = decodeBase64Url(signatureB64Url);
  if (signature.byteLength !== 64) fail("structural_receipt_signature_length_invalid");
  const [, digestDomain] = domains(payload);
  return sha256Hex(concat(encoder.encode(digestDomain), canonicalBytes(payload), new Uint8Array([0]), signature));
}
