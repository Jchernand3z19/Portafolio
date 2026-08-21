import assert from "node:assert/strict";
import test from "node:test";

import {
  createStructuralPublicWorkerHandler,
  parseAndAuthenticateStructuralRequest,
} from "../src/structural-worker-adapter.mjs";
import { WORKER_ROUTES } from "../src/worker-policy.mjs";

function body(overrides = {}) {
  return {
    originUrl: "https://www.lacolonia.com/_v/segment/graphql/v1?fixture=only-parser",
    requestContext: {
      authorizationId: "auth-structural-public-001",
      runId: "32530000000:1",
      approvedCommitSha: "a".repeat(40),
      reservationId: "reservation-structural-public-001",
      requestId: "request-structural-public-001",
      requestDigest: "b".repeat(64),
      nonce: "nonce-structural-public-001",
      requestKind: "root_total",
      ...overrides,
    },
  };
}

function request(payload = body(), route = WORKER_ROUTES.structuralExecute) {
  return new Request(`https://collector.example${route}`, {
    method: "POST",
    headers: {
      authorization: "Bearer oidc-token",
      "content-type": "application/json; charset=utf-8",
    },
    body: JSON.stringify(payload),
  });
}

const authenticate = async (token, commitSha) => ({
  claims: {
    token_seen: token,
    sha: commitSha,
    run_id: "32530000000",
    run_attempt: "1",
  },
});

test("parser acepta sólo contrato estructural dedicado", async () => {
  const parsed = await parseAndAuthenticateStructuralRequest(request(), authenticate);
  assert.equal(parsed.route, "structuralExecute");
  assert.equal(parsed.authorizationId, "auth-structural-public-001");
  assert.equal(parsed.execution.requestContext.requestKind, "root_total");
  assert.equal(parsed.claims.token_seen, "oidc-token");
  assert.equal("traversalRole" in parsed.execution.requestContext, false);
});

test("traversal catalog-specific queda rechazado en el body estructural", async () => {
  const payload = body();
  payload.requestContext.traversalRole = "primary";
  await assert.rejects(
    () => parseAndAuthenticateStructuralRequest(request(payload), authenticate),
    (error) => error?.code === "structural_execute_context_shape_invalid",
  );
});

test("requestKind arbitrario queda rechazado antes de Durable Object", async () => {
  await assert.rejects(
    () => parseAndAuthenticateStructuralRequest(request(body({ requestKind: "other" })), authenticate),
    (error) => error?.code === "structural_request_kind_invalid",
  );
});

test("ruta distinta no puede entrar por el parser estructural", async () => {
  await assert.rejects(
    () => parseAndAuthenticateStructuralRequest(request(body(), "/v1/execute"), authenticate),
    (error) => error?.code === "request_route_not_found",
  );
});

test("handler selecciona el Durable Object por authorizationId autenticado", async () => {
  const calls = [];
  const namespace = {
    getByName(name) {
      calls.push(["name", name]);
      return {
        async structuralExecute(input) {
          calls.push(["rpc", input]);
          return { ok: true, decision: "WAIT", reason: "pacing", notBeforeMs: 123, inFlightReservationId: null };
        },
      };
    },
  };
  const handler = createStructuralPublicWorkerHandler({ namespace, authenticate });
  const response = await handler(request());
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    ok: true,
    decision: "WAIT",
    reason: "pacing",
    notBeforeMs: 123,
    inFlightReservationId: null,
  });
  assert.equal(calls[0][1], "auth-structural-public-001");
  assert.equal(calls[1][0], "rpc");
});

test("OIDC inválido no puede crear ni seleccionar Durable Object", async () => {
  let selected = false;
  const handler = createStructuralPublicWorkerHandler({
    namespace: {
      getByName() {
        selected = true;
        throw new Error("no debe ejecutarse");
      },
    },
    authenticate: async () => {
      const error = new Error("oidc_invalid");
      error.code = "oidc_invalid";
      throw error;
    },
  });
  const response = await handler(request());
  assert.equal(response.status, 500);
  assert.equal(selected, false);
});
