import { EdgePolicyError } from "./core.mjs";

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

export function createJwksFetchGate({
  fetchImpl,
  clock = () => new Date(),
  minRefreshMs = DEFAULT_MIN_REFRESH_MS,
}) {
  if (typeof fetchImpl !== "function") fail("jwks_fetch_missing");
  if (!Number.isSafeInteger(minRefreshMs) || minRefreshMs < 1000 || minRefreshMs > MAX_MIN_REFRESH_MS) {
    fail("jwks_min_refresh_invalid");
  }

  let cached = null;
  let inFlight = null;

  async function fetchTemplate(url, init) {
    const response = await fetchImpl(url, init);
    if (!(response instanceof Response)) fail("jwks_response_invalid");
    const template = response.clone();
    if (response.status === 200) {
      cached = {
        template,
        refreshAfterMs: nowMs(clock) + minRefreshMs,
      };
    }
    return template;
  }

  return async function gatedFetch(url, init) {
    const current = nowMs(clock);
    if (cached && current < cached.refreshAfterMs) return cached.template.clone();

    if (!inFlight) {
      inFlight = fetchTemplate(url, init);
    }
    try {
      const template = await inFlight;
      return template.clone();
    } finally {
      inFlight = null;
    }
  };
}
