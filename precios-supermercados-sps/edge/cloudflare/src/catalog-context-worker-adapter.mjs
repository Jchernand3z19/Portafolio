import { EdgePolicyError } from "./core.mjs";
import { AUTHORIZATION_LIMITS, WORKER_ROUTES } from "./worker-policy.mjs";
import { jsonResponse, publicErrorResponse } from "./worker-adapter.mjs";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const AUTHORIZATION_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const LOCATION_CONTEXT_KEYS = [
  "locationId", "bindingSourceKey", "bindingEvidence", "contextFingerprint",
  "placement", "wireKey", "valuePath", "wireRequestFingerprint", "rawValue",
];

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactObject(value, expectedKeys, code) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  const actual = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) fail(code);
  return value;
}

function exactText(value, code, max = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function authorizationId(value) {
  const text = exactText(value, "authorization_id_invalid", 128);
  if (!AUTHORIZATION_ID_RE.test(text)) fail("authorization_id_invalid");
  return text;
}

function approvedCommitSha(value) {
  const text = exactText(value, "approved_commit_sha_invalid", 40);
  if (!SHA1_RE.test(text)) fail("approved_commit_sha_invalid");
  return text;
}

function requestDigest(value) {
  const text = exactText(value, "request_digest_invalid", 64);
  if (!SHA256_RE.test(text)) fail("request_digest_invalid");
  return text;
}

function bearerToken(request) {
  const header = request.headers.get("authorization");
  if (typeof header !== "string" || !header.startsWith("Bearer ")) fail("bearer_missing");
  const token = header.slice("Bearer ".length);
  if (!token || token.trim() !== token || /\s/u.test(token) || token.length > 20_000) fail("bearer_invalid");
  return token;
}

async function readBoundedRequestJson(request) {
  const declared = request.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0) fail("request_content_length_invalid");
    if (parsed > AUTHORIZATION_LIMITS.maxRequestBodyBytes) fail("request_body_above_limit");
  }
  if (!request.body || typeof request.body.getReader !== "function") fail("request_body_missing");
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) fail("request_body_chunk_invalid");
      total += value.byteLength;
      if (total > AUTHORIZATION_LIMITS.maxRequestBodyBytes) {
        try { await reader.cancel("body_above_limit"); } catch { /* best effort */ }
        fail("request_body_above_limit");
      }
      chunks.push(value);
    }
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail("request_body_read_failed");
  }
  if (total === 0) fail("request_body_empty");
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { fail("request_body_utf8_invalid"); }
  try { return JSON.parse(text); } catch { fail("request_body_json_invalid"); }
}

function parseCatalogContextBody(body) {
  const source = exactObject(body, ["locationContext", "originUrl", "requestContext"], "catalog_execute_body_shape_invalid");
  const context = exactObject(
    source.requestContext,
    [
      "authorizationId", "runId", "approvedCommitSha", "reservationId",
      "requestId", "requestDigest", "nonce", "traversalRole", "traversalId",
      "partitionId",
    ],
    "catalog_execute_context_shape_invalid",
  );
  if (!new Set(["primary", "reconciliation"]).has(context.traversalRole)) fail("traversal_role_invalid");
  const rawLocation = exactObject(source.locationContext, LOCATION_CONTEXT_KEYS, "catalog_location_context_shape_invalid");
  return Object.freeze({
    originUrl: exactText(source.originUrl, "origin_url_invalid", 20_000),
    requestContext: Object.freeze({
      authorizationId: authorizationId(context.authorizationId),
      runId: exactText(context.runId, "run_id_invalid", 256),
      approvedCommitSha: approvedCommitSha(context.approvedCommitSha),
      reservationId: exactText(context.reservationId, "reservation_id_invalid", 256),
      requestId: exactText(context.requestId, "request_id_invalid", 256),
      requestDigest: requestDigest(context.requestDigest),
      nonce: exactText(context.nonce, "nonce_invalid", 256),
      traversalRole: context.traversalRole,
      traversalId: exactText(context.traversalId, "traversal_id_invalid", 256),
      partitionId: exactText(context.partitionId, "partition_id_invalid", 256),
    }),
    locationContext: Object.freeze({ ...rawLocation }),
  });
}

export async function parseAndAuthenticateCatalogContextRequest(request, authenticate) {
  if (!(request instanceof Request)) fail("request_invalid");
  if (request.method !== "POST") fail("request_method_not_allowed");
  const url = new URL(request.url);
  if (url.pathname !== WORKER_ROUTES.catalogExecute) fail("request_route_not_found");
  if (url.search !== "") fail("request_query_forbidden");
  const mediaType = (request.headers.get("content-type") ?? "").split(";", 1)[0].trim().toLowerCase();
  if (mediaType !== "application/json") fail("request_content_type_invalid");
  const token = bearerToken(request);
  const execution = parseCatalogContextBody(await readBoundedRequestJson(request));
  if (typeof authenticate !== "function") fail("worker_authenticator_missing");
  const identity = await authenticate(token, execution.requestContext.approvedCommitSha);
  const claims = identity?.claims;
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("oidc_claims_missing");
  return Object.freeze({
    route: "catalogExecute",
    authorizationId: execution.requestContext.authorizationId,
    execution,
    claims,
  });
}

export function createCatalogContextPublicWorkerHandler({ namespace, authenticate }) {
  if (!namespace || typeof namespace.getByName !== "function") fail("durable_namespace_missing");
  return async function handle(request) {
    try {
      const parsed = await parseAndAuthenticateCatalogContextRequest(request, authenticate);
      const stub = namespace.getByName(parsed.authorizationId);
      if (!stub || typeof stub.catalogExecute !== "function") fail("durable_catalog_execute_rpc_missing");
      const result = await stub.catalogExecute({ execution: parsed.execution, claims: parsed.claims });
      if (!result || typeof result !== "object" || Array.isArray(result) || typeof result.ok !== "boolean") fail("durable_rpc_result_invalid");
      return jsonResponse(result, result.ok ? 200 : 400);
    } catch (error) {
      return publicErrorResponse(error);
    }
  };
}
