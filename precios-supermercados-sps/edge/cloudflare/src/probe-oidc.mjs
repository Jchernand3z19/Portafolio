import {
  EdgePolicyError,
  verifyGitHubOidcToken,
} from "./core.mjs";
import {
  AUTHORIZATION_LIMITS,
  GITHUB_OIDC_JWKS_URL,
  JWKS_CACHE_TTL_MS,
} from "./worker-policy.mjs";
import { CONTROLLED_PROBE_WORKER_POLICY } from "./probe-policy.mjs";

function fail(code) {
  throw new EdgePolicyError(code);
}

function clockDate(clock) {
  const value = clock();
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) fail("probe_oidc_clock_invalid");
  return value;
}

function safeDiagnosticText(value, fallback) {
  const text = typeof value === "string" && value ? value : fallback;
  return text.replace(/[\u0000-\u001f\u007f]+/gu, " ").slice(0, 240);
}

export function controlledProbeJwksTransportDiagnostic(error) {
  return Object.freeze({
    name: safeDiagnosticText(error?.name, "UnknownError"),
    message: safeDiagnosticText(error?.message, "no_message"),
  });
}

async function readBoundedJwks(response) {
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

  if (!response.body || typeof response.body.getReader !== "function") fail("jwks_body_missing");
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    let item;
    try {
      item = await reader.read();
    } catch {
      fail("jwks_body_read_failed");
    }
    if (item.done) break;
    if (!(item.value instanceof Uint8Array)) fail("jwks_body_chunk_invalid");
    total += item.value.byteLength;
    if (total > AUTHORIZATION_LIMITS.maxJwksBodyBytes) {
      try {
        await reader.cancel("body_above_limit");
      } catch {
        // best effort
      }
      fail("jwks_body_above_limit");
    }
    chunks.push(item.value);
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  let jwks;
  try {
    jwks = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    fail("jwks_json_invalid");
  }
  if (!jwks || typeof jwks !== "object" || Array.isArray(jwks) || !Array.isArray(jwks.keys)) fail("jwks_invalid");
  return jwks;
}

export function createControlledProbeOidcAuthenticator({
  fetchImpl,
  clock = () => new Date(),
  cacheTtlMs = JWKS_CACHE_TTL_MS,
}) {
  if (typeof fetchImpl !== "function") fail("jwks_fetch_missing");
  if (!Number.isSafeInteger(cacheTtlMs) || cacheTtlMs < 1 || cacheTtlMs > 30 * 60 * 1000) {
    fail("jwks_cache_ttl_invalid");
  }
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
    } catch (error) {
      console.error(
        "controlled_probe_jwks_transport_error",
        JSON.stringify(controlledProbeJwksTransportDiagnostic(error)),
      );
      fail("jwks_transport_error");
    }
    const jwks = await readBoundedJwks(response);
    cache = { jwks, expiresAtMs: now + cacheTtlMs };
    return jwks;
  }

  return async function authenticate(token, commitSha) {
    if (typeof commitSha !== "string" || !/^[0-9a-f]{40}$/u.test(commitSha)) fail("approved_commit_sha_invalid");
    const nowSeconds = Math.floor(clockDate(clock).getTime() / 1000);
    let jwks = await loadJwks(false);
    try {
      return await verifyGitHubOidcToken(
        token,
        jwks,
        { ...CONTROLLED_PROBE_WORKER_POLICY, sha: commitSha },
        nowSeconds,
      );
    } catch (error) {
      if (!(error instanceof EdgePolicyError) || error.code !== "jwks_kid_not_unique") throw error;
      jwks = await loadJwks(true);
      return verifyGitHubOidcToken(
        token,
        jwks,
        { ...CONTROLLED_PROBE_WORKER_POLICY, sha: commitSha },
        nowSeconds,
      );
    }
  };
}
