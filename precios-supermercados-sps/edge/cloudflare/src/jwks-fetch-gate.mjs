import { EdgePolicyError } from "./core.mjs";
import { AUTHORIZATION_LIMITS } from "./worker-policy.mjs";

const DEFAULT_MIN_REFRESH_MS = 60_000;
const MAX_MIN_REFRESH_MS = 5 * 60 * 1000;

function fail(code) {
  throw new EdgePolicyError(code);
}

function nowMs(clock) {
  const value = clock();
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) fail("jwks_gate_clock_invalid");
  return value.getTime();
}

async function readBoundedBody(response, maxBodyBytes) {
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > maxBodyBytes) {
      fail("jwks_gate_content_length_invalid");
    }
  }
  if (!response.body || typeof response.body.getReader !== "function") fail("jwks_gate_body_missing");

  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) fail("jwks_gate_body_chunk_invalid");
      total += value.byteLength;
      if (total > maxBodyBytes) {
        try {
          await reader.cancel("body_above_limit");
        } catch {
          // best effort
        }
        fail("jwks_gate_body_above_limit");
      }
      chunks.push(value);
    }
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail("jwks_gate_body_read_failed");
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

function responseFromSnapshot(snapshot) {
  return new Response(new Uint8Array(snapshot.bodyBytes), {
    status: snapshot.status,
    statusText: snapshot.statusText,
    headers: snapshot.headers,
  });
}

async function snapshotSuccessfulResponse(response, maxBodyBytes) {
  const bodyBytes = await readBoundedBody(response, maxBodyBytes);
  return Object.freeze({
    status: response.status,
    statusText: response.statusText,
    headers: Object.freeze([...response.headers.entries()].map(([key, value]) => Object.freeze([key, value]))),
    bodyBytes,
  });
}

export function createJwksFetchGate({
  fetchImpl,
  clock = () => new Date(),
  minRefreshMs = DEFAULT_MIN_REFRESH_MS,
  maxBodyBytes = AUTHORIZATION_LIMITS.maxJwksBodyBytes,
}) {
  if (typeof fetchImpl !== "function") fail("jwks_fetch_missing");
  if (!Number.isSafeInteger(minRefreshMs) || minRefreshMs < 1000 || minRefreshMs > MAX_MIN_REFRESH_MS) {
    fail("jwks_min_refresh_invalid");
  }
  if (!Number.isSafeInteger(maxBodyBytes) || maxBodyBytes < 1 || maxBodyBytes > AUTHORIZATION_LIMITS.maxJwksBodyBytes) {
    fail("jwks_gate_body_limit_invalid");
  }

  // Cloudflare Workers reuses isolates across requests. Only plain data may be
  // retained here; request-scoped Response/Request/stream/Promise objects must
  // never escape into module-level state.
  let cached = null;

  return async function gatedFetch(url, init) {
    const current = nowMs(clock);
    if (cached && current < cached.refreshAfterMs) return responseFromSnapshot(cached.snapshot);

    const response = await fetchImpl(url, init);
    if (!(response instanceof Response)) fail("jwks_response_invalid");
    if (response.status !== 200) return response;

    const snapshot = await snapshotSuccessfulResponse(response, maxBodyBytes);
    cached = Object.freeze({
      snapshot,
      refreshAfterMs: current + minRefreshMs,
    });
    return responseFromSnapshot(snapshot);
  };
}
