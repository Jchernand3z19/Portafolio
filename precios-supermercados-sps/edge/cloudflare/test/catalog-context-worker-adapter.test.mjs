import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import { createCatalogContextPublicWorkerHandler } from "../src/catalog-context-worker-adapter.mjs";

const SHA = "a".repeat(40);

function body(overrides = {}) {
  return {
    originUrl: "https://www.lacolonia.com/_v/segment/graphql/v1?synthetic=1",
    requestContext: {
      authorizationId: "authorization-catalog-001",
      runId: "32540000000:1",
      approvedCommitSha: SHA,
      reservationId: "reservation-catalog-001",
      requestId: "request-catalog-001",
      requestDigest: "b".repeat(64),
      nonce: "nonce-catalog-001",
      traversalRole: "primary",
      traversalId: "traversal-primary",
      partitionId: "supermercado",
    },
    locationContext: {
      locationId: "la_colonia_sps",
      bindingSourceKey: `request:regionid:sha256:${"c".repeat(64)}`,
      bindingEvidence: `location_binding_radiography:sha256:${"d".repeat(64)}`,
      contextFingerprint: "c".repeat(64),
      placement: "header",
      wireKey: "X-VTEX-Region",
      valuePath: [],
      wireRequestFingerprint: "e".repeat(64),
      rawValue: "synthetic-region",
    },
    ...overrides,
  };
}

function request(payload = body(), token = "synthetic.jwt.token") {
  return new Request("https://collector.example/v1/catalog-execute", {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

function harness() {
  const calls = [];
  const stub = {
    async catalogExecute(input) {
      calls.push(["catalogExecute", input]);
      return { ok: true, decision: "WAIT", reason: "pacing_not_elapsed" };
    },
  };
  return {
    calls,
    namespace: {
      getByName(name) {
        calls.push(["getByName", name]);
        return stub;
      },
    },
  };
}

test("autentica antes de seleccionar Durable Object y reenvía contexto exacto", async () => {
  const h = harness();
  const authCalls = [];
  const handler = createCatalogContextPublicWorkerHandler({
    namespace: h.namespace,
    authenticate: async (token, commitSha) => {
      authCalls.push([token, commitSha]);
      return { claims: { sha: SHA } };
    },
  });

  const response = await handler(request());
  const payload = await response.json();

  assert.equal(response.status, 200);
  assert.equal(payload.ok, true);
  assert.deepEqual(authCalls, [["synthetic.jwt.token", SHA]]);
  assert.deepEqual(h.calls[0], ["getByName", "authorization-catalog-001"]);
  assert.equal(h.calls[1][0], "catalogExecute");
  assert.deepEqual(h.calls[1][1].execution.locationContext, body().locationContext);
});

test("campo extra o contexto incompleto falla antes de OIDC y Durable Object", async () => {
  for (const malformed of [
    { ...body(), attacker: true },
    { ...body(), locationContext: { ...body().locationContext, attacker: true } },
    { ...body(), locationContext: null },
  ]) {
    const h = harness();
    let authCalls = 0;
    const handler = createCatalogContextPublicWorkerHandler({
      namespace: h.namespace,
      authenticate: async () => {
        authCalls += 1;
        return { claims: { sha: SHA } };
      },
    });
    const response = await handler(request(malformed));
    assert.equal(response.status, 400);
    assert.equal(authCalls, 0);
    assert.equal(h.calls.length, 0);
  }
});

test("fallo OIDC ocurre antes de getByName", async () => {
  const h = harness();
  const handler = createCatalogContextPublicWorkerHandler({
    namespace: h.namespace,
    authenticate: async () => {
      throw new EdgePolicyError("jwt_signature_invalid");
    },
  });

  const response = await handler(request());
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error, "jwt_signature_invalid");
  assert.equal(h.calls.length, 0);
});

test("bearer inválido y query pública no seleccionan Durable Object", async () => {
  const h = harness();
  const handler = createCatalogContextPublicWorkerHandler({
    namespace: h.namespace,
    authenticate: async () => ({ claims: { sha: SHA } }),
  });
  const missingBearer = new Request("https://collector.example/v1/catalog-execute", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body()),
  });
  const queryRequest = new Request("https://collector.example/v1/catalog-execute?debug=1", {
    method: "POST",
    headers: {
      authorization: "Bearer synthetic.jwt.token",
      "content-type": "application/json",
    },
    body: JSON.stringify(body()),
  });

  assert.equal((await handler(missingBearer)).status, 401);
  assert.equal((await handler(queryRequest)).status, 400);
  assert.equal(h.calls.length, 0);
});
