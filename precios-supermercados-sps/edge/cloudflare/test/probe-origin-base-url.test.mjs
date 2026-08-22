import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import { validateControlledProbeOriginUrl } from "../src/probe-core.mjs";

const BASE = "https://precios-sps-controlled-origin.example-account.workers.dev";
const ROUTE = `${BASE}/v1/probe-origin`;

test("binding de origen acepta URL base y deriva únicamente la ruta canónica", () => {
  const fromBase = validateControlledProbeOriginUrl(BASE);
  assert.equal(fromBase.url, ROUTE);
  assert.equal(fromBase.targetHost, "precios-sps-controlled-origin.example-account.workers.dev");
  assert.equal(fromBase.targetPath, "/v1/probe-origin");

  const fromCanonicalRoute = validateControlledProbeOriginUrl(ROUTE);
  assert.deepEqual(fromCanonicalRoute, fromBase);
});

test("binding de origen rechaza rutas distintas, query, fragment y hosts no workers.dev", () => {
  for (const value of [
    `${BASE}/otra-ruta`,
    `${BASE}/v1/probe-origin/extra`,
    `${BASE}?x=1`,
    `${BASE}#fragment`,
    "https://example.com",
    "http://precios-sps-controlled-origin.example-account.workers.dev",
    "https://www.lacolonia.com",
  ]) {
    assert.throws(
      () => validateControlledProbeOriginUrl(value),
      (error) => error instanceof EdgePolicyError,
    );
  }
});
