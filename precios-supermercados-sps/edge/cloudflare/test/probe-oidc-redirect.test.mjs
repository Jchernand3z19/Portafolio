import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import { createControlledProbeOidcAuthenticator } from "../src/probe-oidc.mjs";
import { GITHUB_OIDC_JWKS_URL } from "../src/worker-policy.mjs";

const SHA = "a".repeat(40);

test("OIDC de sonda usa redirect manual compatible con Cloudflare y no sigue redirects", async () => {
  const seen = [];
  const authenticate = createControlledProbeOidcAuthenticator({
    fetchImpl: async (url, init) => {
      seen.push([url, init]);
      throw new TypeError("synthetic transport stop");
    },
  });

  await assert.rejects(
    authenticate("synthetic.jwt.token", SHA),
    (error) => error instanceof EdgePolicyError && error.code === "jwks_transport_error",
  );

  assert.equal(seen.length, 1);
  assert.equal(seen[0][0], GITHUB_OIDC_JWKS_URL);
  assert.equal(seen[0][1].method, "GET");
  assert.equal(seen[0][1].redirect, "manual");
});
