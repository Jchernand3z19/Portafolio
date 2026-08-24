import { EdgePolicyError, encodeBase64Url } from "./core.mjs";
import { executeStructuralGatewayRequest } from "./structural-gateway-runtime.mjs";
import {
  signStructuralReceipt,
  verifyStructuralReceipt,
} from "./structural-provenance.mjs";
import {
  AUTHORIZATION_LIMITS,
  RECEIPT_SIGNING_KEY_ID,
  WORKER_ROUTES,
} from "./worker-policy.mjs";
import {
  collectorConfiguration,
  jsonResponse,
  publicErrorResponse,
} from "./worker-adapter.mjs";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const AUTHORIZATION_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const REQUEST_KINDS = new Set(["root_total", "category_tree"]);
const LOCATION_CONTEXT_KEYS = Object.freeze([
  "locationId", "bindingSourceKey", "bindingEvidence", "contextFingerprint",
  "placement", "wireKey", "valuePath", "wireRequestFingerprint", "rawValue",
]);

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
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max || /\s/u.test(value)) fail(code);
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

function requestKind(value) {
  const text = exactText(value, "structural_request_kind_invalid", 64);
  if (!REQUEST_KINDS.has(text)) fail("structural_request_kind_invalid");
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
  while (true) {
    let item;
    try { item = await reader.read(); } catch { fail("request_body_read_failed"); }
    if (item.done) break;
    if (!(item.value instanceof Uint8Array)) fail("request_body_chunk_invalid");
    total += item.value.byteLength;
    if (total > AUTHORIZATION_LIMITS.maxRequestBodyBytes) {
      try { await reader.cancel("body_above_limit"); } catch { /* best effort */ }
      fail("request_body_above_limit");
    }
    chunks.push(item.value);
  }
  if (total === 0) fail("request_body_empty");
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { fail("request_body_utf8_invalid"); }
  try { return JSON.parse(text); } catch { fail("request_body_json_invalid"); }
}

function parseStructuralBody(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) fail("structural_execute_body_shape_invalid");
  const bodyKeys = Object.keys(body).sort();
  const v1 = ["originUrl", "requestContext"].sort();
  const contextual = ["locationContext", "originUrl", "requestContext"].sort();
  const valid = (bodyKeys.length === v1.length && bodyKeys.every((key, index) => key === v1[index]))
    || (bodyKeys.length === contextual.length && bodyKeys.every((key, index) => key === contextual[index]));
  if (!valid) fail("structural_execute_body_shape_invalid");
  const source = exactObject(
    body.requestContext,
    ["authorizationId", "runId", "approvedCommitSha", "reservationId", "requestId", "requestDigest", "nonce", "requestKind"],
    "structural_execute_context_shape_invalid",
  );
  let locationContext = null;
  if (Object.hasOwn(body, "locationContext")) {
    if (!body.locationContext || typeof body.locationContext !== "object" || Array.isArray(body.locationContext)) {
      fail("structural_location_context_shape_invalid");
    }
    const hasSession = Object.hasOwn(body.locationContext, "sessionSignals");
    const expected = hasSession ? [...LOCATION_CONTEXT_KEYS, "sessionSignals"] : LOCATION_CONTEXT_KEYS;
    const raw = exactObject(body.locationContext, expected, "structural_location_context_shape_invalid");
    if (hasSession && (!raw.sessionSignals || typeof raw.sessionSignals !== "object" || Array.isArray(raw.sessionSignals))) {
      fail("structural_session_signals_shape_invalid");
    }
    // Fingerprints, claves exactas y raws se validan dentro del runtime antes de reservar/fetch.
    locationContext = Object.freeze({ ...raw });
  }
  return Object.freeze({
    originUrl: exactText(body.originUrl, "origin_url_invalid", 20_000),
    requestContext: Object.freeze({
      authorizationId: authorizationId(source.authorizationId),
      runId: exactText(source.runId, "run_id_invalid", 256),
      approvedCommitSha: approvedCommitSha(source.approvedCommitSha),
      reservationId: exactText(source.reservationId, "reservation_id_invalid", 256),
      requestId: exactText(source.requestId, "request_id_invalid", 256),
      requestDigest: requestDigest(source.requestDigest),
      nonce: exactText(source.nonce, "nonce_invalid", 256),
      requestKind: requestKind(source.requestKind),
    }),
    locationContext,
  });
}

export async function parseAndAuthenticateStructuralRequest(request, authenticate) {
  if (!(request instanceof Request)) fail("request_invalid");
  if (request.method !== "POST") fail("request_method_not_allowed");
  const url = new URL(request.url);
  if (url.pathname !== WORKER_ROUTES.structuralExecute) fail("request_route_not_found");
  if (url.search !== "") fail("request_query_forbidden");
  const mediaType = (request.headers.get("content-type") ?? "").split(";", 1)[0].trim().toLowerCase();
  if (mediaType !== "application/json") fail("request_content_type_invalid");
  const token = bearerToken(request);
  const execution = parseStructuralBody(await readBoundedRequestJson(request));
  if (typeof authenticate !== "function") fail("worker_authenticator_missing");
  const identity = await authenticate(token, execution.requestContext.approvedCommitSha);
  const claims = identity?.claims;
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("oidc_claims_missing");
  return Object.freeze({ route: "structuralExecute", authorizationId: execution.requestContext.authorizationId, execution, claims });
}

function requiredBinding(env, key, max = 20_000) {
  return exactText(env?.[key], `binding_${key.toLowerCase()}_missing`, max);
}

function serializeStructuralResult(result) {
  if (result.decision === "ORIGIN_COMPLETED" || result.decision === "REPLAY_COMPLETED") {
    return Object.freeze({
      ok: true,
      decision: result.decision,
      replayed: result.replayed,
      responseStatus: result.status,
      rawBodyB64Url: encodeBase64Url(result.rawBody),
      receiptPayload: result.receiptPayload,
      signatureB64Url: result.signatureB64Url,
      signingKeyId: result.signingKeyId,
      evidenceId: result.evidenceId,
    });
  }
  if (result.decision === "WAIT") return Object.freeze({ ok: true, decision: "WAIT", reason: result.reason, notBeforeMs: result.notBeforeMs ?? null, inFlightReservationId: result.inFlightReservationId ?? null });
  if (result.decision === "DENY") return Object.freeze({ ok: true, decision: "DENY", reason: result.reason });
  fail("structural_gateway_result_unexpected");
}

export async function runStructuralExecuteOperation(
  store,
  execution,
  claims,
  env,
  { fetchOrigin, clock = () => new Date(), randomUUID = () => crypto.randomUUID() },
) {
  if (typeof fetchOrigin !== "function") fail("origin_fetch_missing");
  const collector = collectorConfiguration(env);
  const privateKey = requiredBinding(env, "EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL");
  const publicKey = requiredBinding(env, "EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL");
  const result = await executeStructuralGatewayRequest(
    {
      authorizationToken: "verified-by-worker-router",
      originUrl: execution.originUrl,
      requestContext: execution.requestContext,
      locationContext: execution.locationContext,
      collector,
    },
    {
      store,
      authenticate: async () => ({ claims }),
      fetchOrigin,
      signReceipt: (payload) => signStructuralReceipt(payload, privateKey),
      verifyReceipt: async (payload, signature, keyId) => keyId === RECEIPT_SIGNING_KEY_ID && verifyStructuralReceipt(payload, signature, publicKey),
      clock,
      executionId: () => exactText(randomUUID(), "collector_execution_invalid", 256),
    },
  );
  return serializeStructuralResult(result);
}

export function createStructuralPublicWorkerHandler({ namespace, authenticate }) {
  if (!namespace || typeof namespace.getByName !== "function") fail("durable_namespace_missing");
  return async function handle(request) {
    try {
      const parsed = await parseAndAuthenticateStructuralRequest(request, authenticate);
      const stub = namespace.getByName(parsed.authorizationId);
      if (!stub || typeof stub.structuralExecute !== "function") fail("durable_structural_execute_rpc_missing");
      const result = await stub.structuralExecute({ execution: parsed.execution, claims: parsed.claims });
      if (!result || typeof result !== "object" || Array.isArray(result) || typeof result.ok !== "boolean") fail("durable_rpc_result_invalid");
      return jsonResponse(result, result.ok ? 200 : 400);
    } catch (error) {
      return publicErrorResponse(error);
    }
  };
}
