import { EdgePolicyError } from "./core.mjs";
import {
  CONTROLLED_PROBE_MAX_REQUEST_BODY_BYTES,
  CONTROLLED_PROBE_ROUTE,
} from "./probe-policy.mjs";
import { CONTROLLED_PROBE_GENERIC_EXECUTION_ERROR } from "./probe-rpc-error.mjs";

const JSON_HEADERS = Object.freeze({
  "cache-control": "no-store",
  "content-type": "application/json; charset=utf-8",
  "x-content-type-options": "nosniff",
});
const PROBE_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const SHA1_RE = /^[0-9a-f]{40}$/u;

function fail(code) {
  throw new EdgePolicyError(code);
}

function exactText(value, code, max = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: JSON_HEADERS });
}

function errorStatus(code) {
  if (code.startsWith("bearer_") || code.startsWith("jwt_") || code.startsWith("oidc_") || code.startsWith("probe_oidc_")) {
    return 401;
  }
  if (code === "probe_replay_in_flight" || code === "probe_replay_failed") return 409;
  if (code.startsWith("jwks_")) return 503;
  if (code === CONTROLLED_PROBE_GENERIC_EXECUTION_ERROR) return 500;
  return 400;
}

export function controlledProbePublicErrorResponse(error) {
  const code = error instanceof EdgePolicyError ? error.code : "internal_error";
  return jsonResponse({ ok: false, error: code }, error instanceof EdgePolicyError ? errorStatus(code) : 500);
}

function bearerToken(request) {
  const header = request.headers.get("authorization");
  if (typeof header !== "string" || !header.startsWith("Bearer ")) fail("bearer_missing");
  const token = header.slice("Bearer ".length);
  if (!token || token.trim() !== token || /\s/u.test(token) || token.length > 20_000) fail("bearer_invalid");
  return token;
}

async function readBoundedJson(request) {
  const rawContentType = request.headers.get("content-type") ?? "";
  const mediaType = rawContentType.split(";", 1)[0].trim().toLowerCase();
  if (mediaType !== "application/json") fail("request_content_type_invalid");
  const declared = request.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0) fail("request_content_length_invalid");
    if (parsed > CONTROLLED_PROBE_MAX_REQUEST_BODY_BYTES) fail("request_body_above_limit");
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
      if (total > CONTROLLED_PROBE_MAX_REQUEST_BODY_BYTES) {
        try {
          await reader.cancel("body_above_limit");
        } catch {
          // best effort
        }
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
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  let body;
  try {
    body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    fail("request_body_json_invalid");
  }
  return body;
}

function parseProbeBody(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) fail("probe_body_shape_invalid");
  const keys = Object.keys(body).sort();
  if (keys.length !== 2 || keys[0] !== "approvedCommitSha" || keys[1] !== "probeId") fail("probe_body_shape_invalid");
  const probeId = exactText(body.probeId, "probe_id_invalid", 128);
  if (!PROBE_ID_RE.test(probeId)) fail("probe_id_invalid");
  const approvedCommitSha = exactText(body.approvedCommitSha, "approved_commit_sha_invalid", 40);
  if (!SHA1_RE.test(approvedCommitSha)) fail("approved_commit_sha_invalid");
  return Object.freeze({ probeId, approvedCommitSha });
}

function validateClaims(claims, approvedCommitSha) {
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("probe_oidc_claims_missing");
  if (claims.sha !== approvedCommitSha) fail("probe_oidc_commit_context_mismatch");
  const runId = exactText(claims.run_id, "probe_oidc_run_id_invalid", 64);
  const runAttempt = Number(claims.run_attempt);
  if (!Number.isSafeInteger(runAttempt) || runAttempt < 1 || runAttempt > 100) fail("probe_oidc_run_attempt_invalid");
  return Object.freeze({ runId, runAttempt });
}

export function createControlledProbePublicHandler({ namespace, authenticate }) {
  if (!namespace || typeof namespace.getByName !== "function") fail("probe_durable_namespace_missing");
  if (typeof authenticate !== "function") fail("probe_authenticator_missing");

  return async function handle(request) {
    try {
      if (!(request instanceof Request)) fail("request_invalid");
      if (request.method !== "POST") fail("request_method_not_allowed");
      const url = new URL(request.url);
      if (url.pathname !== CONTROLLED_PROBE_ROUTE) fail("request_route_not_found");
      if (url.search !== "" || url.hash !== "") fail("request_query_forbidden");

      const token = bearerToken(request);
      const parsed = parseProbeBody(await readBoundedJson(request));
      const identity = await authenticate(token, parsed.approvedCommitSha);
      const run = validateClaims(identity?.claims, parsed.approvedCommitSha);
      const durableObjectName = `github-run:${run.runId}:${run.runAttempt}`;
      const stub = namespace.getByName(durableObjectName);
      if (!stub || typeof stub.execute !== "function") fail("probe_durable_execute_rpc_missing");
      const result = await stub.execute({
        probeId: parsed.probeId,
        approvedCommitSha: parsed.approvedCommitSha,
        claims: identity.claims,
      });
      if (!result || typeof result !== "object" || Array.isArray(result) || typeof result.ok !== "boolean") {
        fail("probe_durable_rpc_result_invalid");
      }
      return jsonResponse(result, result.ok ? 200 : errorStatus(result.error ?? "internal_error"));
    } catch (error) {
      return controlledProbePublicErrorResponse(error);
    }
  };
}
