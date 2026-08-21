import { EdgePolicyError } from "./core.mjs";

const RUN_ID_RE = /^[1-9][0-9]{0,63}$/u;

function fail(code) {
  throw new EdgePolicyError(code);
}

export function githubRunFenceKey(claims) {
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("oidc_claims_missing");
  if (typeof claims.run_id !== "string" || !RUN_ID_RE.test(claims.run_id)) fail("jwt_run_id_invalid");
  const attempt = Number(claims.run_attempt);
  if (!Number.isSafeInteger(attempt) || attempt < 1 || attempt > 100) fail("jwt_run_attempt_invalid");
  return `${claims.run_id}:${attempt}`;
}

export function assertGitHubRunFence(claims, logicalRunId) {
  if (typeof logicalRunId !== "string" || logicalRunId !== githubRunFenceKey(claims)) {
    fail("github_run_fence_mismatch");
  }
  return logicalRunId;
}
