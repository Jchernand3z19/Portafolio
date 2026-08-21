import {
  EdgePolicyError,
  encodeBase64Url,
  signReceiptPayload,
  verifyGitHubOidcToken,
  verifyReceiptSignature,
} from "./core.mjs";
import { DurableAuthorizationStore } from "./durable-store.mjs";
import { executeGatewayRequest } from "./gateway-runtime.mjs";
import {
  AUTHORIZATION_LIMITS,
  FIXED_GRAPHQL_QUERY_SHA256,
  GITHUB_OIDC_JWKS_URL,
  JWKS_CACHE_TTL_MS,
  RECEIPT_SIGNING_KEY_ID,
  WORKER_POLICY,
  WORKER_ROUTES,
} from "./worker-policy.mjs";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const AUTHORIZATION_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const JSON_HEADERS = Object.freeze({
  "cache-control": "no-store",
  "content-type": "application/json; charset=utf-8",
  "x-content-type-options": "nosniff",
});

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

function exactInteger(value, code, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
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

function clockDate(clock) {
  const value = clock();
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) fail("worker_clock_invalid");
  return value;
}

function errorStatus(code) {
  if (code.startsWith("bearer_") || code.startsWith("jwt_") || code.startsWith("oidc_")) return 401;
  if (code === "authorization_initialize_conflict" || code.endsWith("_conflict")) return 409;
  if (code.startsWith("jwks_")) return 503;
  return 400;
}

export function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: JSON_HEADERS });
}

export function publicErrorResponse(error) {
  const code = error instanceof EdgePolicyError ? error.code : "internal_error";
  return jsonResponse({ ok: false, error: code }, error instanceof EdgePolicyError ? errorStatus(code) : 500);
}

async function readBoundedBytes(stream, maxBytes, prefix) {
  if (!stream || typeof stream.getReader !== "function") fail(`${prefix}_body_missing`);
  const reader = stream.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) fail(`${prefix}_body_chunk_invalid`);
      total += value.byteLength;
      if (total > maxBytes) {
        try {
          await reader.cancel("body_above_limit");
        } catch {
          // best effort
        }
        fail(`${prefix}_body_above_limit`);
      }
      chunks.push(value);
    }
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail(`${prefix}_body_read_failed`);
  }
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

async function readJsonRequest(request) {
  const contentType = (request.headers.get("content-type") ?? "").toLowerCase();
  if (!contentType.startsWith("application/json")) fail("request_content_type_invalid");
  const declared = request.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0) fail("request_content_length_invalid");
    if (parsed > AUTHORIZATION_LIMITS.maxRequestBodyBytes) fail("request_body_above_limit");
  }
  const bytes = await readBoundedBytes(request.body, AUTHORIZATION_LIMITS.maxRequestBodyBytes, "request");
  if (bytes.byteLength === 0) fail("request_body_empty");
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    fail("request_body_utf8_invalid");
  }
  try {
    return JSON.parse(text);
  } catch {
    fail("request_body_json_invalid");
  }
}

function bearerToken(request) {
  const header = request.headers.get("authorization");
  if (typeof header !== "string" || !header.startsWith("Bearer ")) fail("bearer_missing");
  const token = header.slice("Bearer ".length);
  if (!token || token.trim() !== token || /\s/u.test(token) || token.length > 20_000) fail("bearer_invalid");
  return token;
}

function parseInitializePayload(body) {
  exactObject(body, ["authorization"], "initialize_body_shape_invalid");
  const source = exactObject(
    body.authorization,
    ["authorizationId", "runId", "approvedCommitSha", "createdAtMs", "expiresAtMs", "maxRequests"],
    "initialize_authorization_shape_invalid",
  );
  const createdAtMs = exactInteger(source.createdAtMs, "created_at_invalid", 1);
  const expiresAtMs = exactInteger(source.expiresAtMs, "expires_at_invalid", createdAtMs + 1);
  if (expiresAtMs - createdAtMs > AUTHORIZATION_LIMITS.maxLifetimeMs) fail("authorization_lifetime_above_limit");
  return Object.freeze({
    authorizationId: authorizationId(source.authorizationId),
    runId: exactText(source.runId, "run_id_invalid", 256),
    approvedCommitSha: approvedCommitSha(source.approvedCommitSha),
    createdAtMs,
    expiresAtMs,
    maxRequests: exactInteger(source.maxRequests, "max_requests_invalid", 1, AUTHORIZATION_LIMITS.maxRequests),
    minStartIntervalMs: AUTHORIZATION_LIMITS.minStartIntervalMs,
  });
}

function parseExecutePayload(body) {
  exactObject(body, ["originUrl", "requestContext"], "execute_body_shape_invalid");
  const source = exactObject(
    body.requestContext,
    [
      "authorizationId",
      "runId",
      "approvedCommitSha",
      "reservationId",
      "requestId",
      "requestDigest",
      "nonce",
      "traversalRole",
      "traversalId",
      "partitionId",
    ],
    "execute_context_shape_invalid",
  );
  const digest = exactText(source.requestDigest, "request_digest_invalid", 64);
  if (!SHA256_RE.test(digest)) fail("request_digest_invalid");
  if (!new Set(["primary", "reconciliation"]).has(source.traversalRole)) fail("traversal_role_invalid");
  return Object.freeze({
    originUrl: exactText(body.originUrl, "origin_url_invalid", 20_000),
    requestContext: Object.freeze({
      authorizationId: authorizationId(source.authorizationId),
      runId: exactText(source.runId, "run_id_invalid", 256),
      approvedCommitSha: approvedCommitSha(source.approvedCommitSha),
      reservationId: exactText(source.reservationId, "reservation_id_invalid", 256),
      requestId: exactText(source.requestId, "request_id_invalid", 256),
      requestDigest: digest,
      nonce: exactText(source.nonce, "nonce_invalid", 256),
      traversalRole: source.traversalRole,
      traversalId: exactText(source.traversalId, "traversal_id_invalid", 256),
      partitionId: exactText(source.partitionId, "partition_id_invalid", 256),
    }),
  });
}

async function readJwksResponse(response) {
  if (!(response instanceof Response)) fail("jwks_response_invalid");
  if (response.redirected || response.status !== 200) fail("jwks_http_invalid");
  const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
  if (!contentType.includes("application/json")) fail("jwks_content_type_invalid");
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > AUTHORIZATION_LIMITS.maxJwksBodyBytes) {
      fail("jwks_content_length_invalid");
    }
  }
  const bytes = await readBoundedBytes(response.body, AUTHORIZATION_LIMITS.maxJwksBodyBytes, "jwks");
  let jwks;
  try {
    jwks = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    fail("jwks_json_invalid");
  }
  if (!jwks || typeof jwks !== "object" || Array.isArray(jwks) || !Array.isArray(jwks.keys)) fail("jwks_invalid");
  return jwks;
}

export function createGitHubOidcAuthenticator({ fetchImpl, clock = () => new Date(), cacheTtlMs = JWKS_CACHE_TTL_MS }) {
  if (typeof fetchImpl !== "function") fail("jwks_fetch_missing");
  exactInteger(cacheTtlMs, "jwks_cache_ttl_invalid", 1, 30 * 60 * 1000);
  let cache = null;

  async function loadJwks(force = false) {
    const now = clockDate(clock).getTime();
    if (!force && cache && now < cache.expiresAtMs) return cache.jwks;
    let response;
    try {
      response = await fetchImpl(GITHUB_OIDC_JWKS_URL, {
        method: "GET",
        redirect: "error",
        headers: Object.freeze({ accept: "application/json" }),
      });
    } catch {
      fail("jwks_transport_error");
    }
    const jwks = await readJwksResponse(response);
    cache = { jwks, expiresAtMs: now + cacheTtlMs };
    return jwks;
  }

  return async function authenticate(token, commitSha) {
    const sha = approvedCommitSha(commitSha);
    const nowSeconds = Math.floor(clockDate(clock).getTime() / 1000);
    let jwks = await loadJwks(false);
    try {
      return await verifyGitHubOidcToken(token, jwks, { ...WORKER_POLICY, sha }, nowSeconds);
    } catch (error) {
      if (!(error instanceof EdgePolicyError) || error.code !== "jwks_kid_not_unique") throw error;
      jwks = await loadJwks(true);
      return verifyGitHubOidcToken(token, jwks, { ...WORKER_POLICY, sha }, nowSeconds);
    }
  };
}

function validateInitializationTiming(config, claims, nowMs) {
  const skewMs = WORKER_POLICY.clockSkewSeconds * 1000;
  const tokenIatMs = exactInteger(claims.iat, "jwt_iat_invalid", 1) * 1000;
  if (config.createdAtMs > nowMs + skewMs) fail("authorization_created_in_future");
  if (config.createdAtMs < nowMs - AUTHORIZATION_LIMITS.maxLifetimeMs) fail("authorization_created_too_old");
  if (config.expiresAtMs <= nowMs - skewMs) fail("authorization_already_expired");
  if (tokenIatMs > nowMs + skewMs) fail("jwt_issued_in_future");
}

export async function parseAndAuthenticatePublicRequest(request, authenticate, clock = () => new Date()) {
  if (!(request instanceof Request)) fail("request_invalid");
  if (request.method !== "POST") fail("request_method_not_allowed");
  const url = new URL(request.url);
  if (url.search !== "") fail("request_query_forbidden");
  if (!Object.values(WORKER_ROUTES).includes(url.pathname)) fail("request_route_not_found");

  const body = await readJsonRequest(request);
  const token = bearerToken(request);
  if (typeof authenticate !== "function") fail("worker_authenticator_missing");

  if (url.pathname === WORKER_ROUTES.initialize) {
    const authorization = parseInitializePayload(body);
    const identity = await authenticate(token, authorization.approvedCommitSha);
    const claims = identity?.claims;
    if (!claims) fail("oidc_claims_missing");
    const nowMs = clockDate(clock).getTime();
    validateInitializationTiming(authorization, claims, nowMs);
    return Object.freeze({ route: "initialize", authorizationId: authorization.authorizationId, authorization, claims });
  }

  const execution = parseExecutePayload(body);
  const identity = await authenticate(token, execution.requestContext.approvedCommitSha);
  const claims = identity?.claims;
  if (!claims) fail("oidc_claims_missing");
  return Object.freeze({
    route: "execute",
    authorizationId: execution.requestContext.authorizationId,
    execution,
    claims,
  });
}

function requiredSecret(env, key, max = 20_000) {
  return exactText(env?.[key], `binding_${key.toLowerCase()}_missing`, max);
}

export function collectorConfiguration(env) {
  const codeSha256 = requiredSecret(env, "EDGE_COLLECTOR_CODE_SHA256", 64);
  if (!SHA256_RE.test(codeSha256)) fail("binding_edge_collector_code_sha256_invalid");
  const releaseId = exactText(env?.CF_VERSION_METADATA?.id, "binding_cf_version_metadata_missing", 256);
  return Object.freeze({
    principal: "cloudflare-worker:precios-sps-provenance",
    releaseId,
    codeSha256,
    signingKeyId: RECEIPT_SIGNING_KEY_ID,
  });
}

function serializeGatewayResult(result) {
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
  if (result.decision === "WAIT") {
    return Object.freeze({
      ok: true,
      decision: "WAIT",
      reason: result.reason,
      notBeforeMs: result.notBeforeMs ?? null,
      inFlightReservationId: result.inFlightReservationId ?? null,
    });
  }
  if (result.decision === "DENY") {
    return Object.freeze({ ok: true, decision: "DENY", reason: result.reason });
  }
  fail("gateway_result_unexpected");
}

export function durableErrorEnvelope(error) {
  const code = error instanceof EdgePolicyError ? error.code : "internal_error";
  return Object.freeze({ ok: false, error: code });
}

export function runInitializeOperation(store, authorization, claims, clock = () => new Date()) {
  if (!(store instanceof DurableAuthorizationStore) && (!store || typeof store.initialize !== "function" || typeof store.summary !== "function")) {
    fail("durable_store_invalid");
  }
  if (!claims || claims.sha !== authorization.approvedCommitSha) fail("oidc_commit_context_mismatch");
  const nowMs = clockDate(clock).getTime();
  validateInitializationTiming(authorization, claims, nowMs);
  store.initialize(authorization);
  return Object.freeze({
    ok: true,
    decision: "INITIALIZED",
    authorization: store.summary(Math.max(nowMs, authorization.createdAtMs)),
  });
}

export async function runExecuteOperation(
  store,
  execution,
  claims,
  env,
  {
    fetchOrigin,
    clock = () => new Date(),
    randomUUID = () => crypto.randomUUID(),
  },
) {
  if (typeof fetchOrigin !== "function") fail("origin_fetch_missing");
  const collector = collectorConfiguration(env);
  const privateKey = requiredSecret(env, "EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL");
  const publicKey = requiredSecret(env, "EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL");
  const result = await executeGatewayRequest(
    {
      authorizationToken: "verified-by-worker-router",
      originUrl: execution.originUrl,
      expectedGraphqlQuerySha256: FIXED_GRAPHQL_QUERY_SHA256,
      requestContext: execution.requestContext,
      collector,
    },
    {
      store,
      authenticate: async () => ({ claims }),
      fetchOrigin,
      signReceipt: (payload) => signReceiptPayload(payload, privateKey),
      verifyReceipt: async (payload, signature, keyId) => {
        if (keyId !== RECEIPT_SIGNING_KEY_ID) return false;
        return verifyReceiptSignature(payload, signature, publicKey);
      },
      clock,
      executionId: () => exactText(randomUUID(), "collector_execution_invalid", 256),
    },
  );
  return serializeGatewayResult(result);
}

export function createPublicWorkerHandler({ namespace, authenticate, clock = () => new Date() }) {
  if (!namespace || typeof namespace.getByName !== "function") fail("durable_namespace_missing");
  return async function handle(request) {
    try {
      const parsed = await parseAndAuthenticatePublicRequest(request, authenticate, clock);
      const stub = namespace.getByName(parsed.authorizationId);
      if (!stub) fail("durable_stub_missing");
      let result;
      if (parsed.route === "initialize") {
        if (typeof stub.initialize !== "function") fail("durable_initialize_rpc_missing");
        result = await stub.initialize({ authorization: parsed.authorization, claims: parsed.claims });
      } else {
        if (typeof stub.execute !== "function") fail("durable_execute_rpc_missing");
        result = await stub.execute({ execution: parsed.execution, claims: parsed.claims });
      }
      if (!result || typeof result !== "object" || Array.isArray(result) || typeof result.ok !== "boolean") {
        fail("durable_rpc_result_invalid");
      }
      return jsonResponse(result, result.ok ? 200 : errorStatus(result.error ?? "internal_error"));
    } catch (error) {
      return publicErrorResponse(error);
    }
  };
}
