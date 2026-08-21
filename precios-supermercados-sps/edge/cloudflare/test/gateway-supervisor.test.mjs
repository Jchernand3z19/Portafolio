import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import { runSupervisedExecuteOperation } from "../src/gateway-supervisor.mjs";

const NOW = 2_000_000_010_000;

function execution() {
  return {
    requestContext: {
      reservationId: "reservation-001",
    },
  };
}

function storeHarness({ failThrows = false } = {}) {
  const calls = [];
  return {
    calls,
    store: {
      fail(reservationId, reason, nowMs) {
        calls.push({ reservationId, reason, nowMs });
        if (failThrows) throw new Error("storage unavailable");
      },
    },
  };
}

test("error post-fetch desconocido cierra reserva con razón terminal genérica", async () => {
  const h = storeHarness();
  const original = new Error("signer runtime failed");
  await assert.rejects(
    runSupervisedExecuteOperation(
      h.store,
      execution(),
      {},
      {},
      { clock: () => new Date(NOW) },
      async () => { throw original; },
    ),
    (error) => error === original,
  );
  assert.deepEqual(h.calls, [{
    reservationId: "reservation-001",
    reason: "gateway_execution_failed",
    nowMs: NOW,
  }]);
});

test("EdgePolicyError conserva reason al cerrar la reserva", async () => {
  const h = storeHarness();
  await assert.rejects(
    runSupervisedExecuteOperation(
      h.store,
      execution(),
      {},
      {},
      { clock: () => new Date(NOW) },
      async () => { throw new EdgePolicyError("receipt_signing_failed"); },
    ),
    (error) => {
      assert.ok(error instanceof EdgePolicyError);
      assert.equal(error.code, "receipt_signing_failed");
      return true;
    },
  );
  assert.equal(h.calls[0].reason, "receipt_signing_failed");
});

test("fallo al persistir el rechazo no provoca retry ni oculta el error original", async () => {
  const h = storeHarness({ failThrows: true });
  let executions = 0;
  const original = new Error("complete failed");
  await assert.rejects(
    runSupervisedExecuteOperation(
      h.store,
      execution(),
      {},
      {},
      { clock: () => new Date(NOW) },
      async () => {
        executions += 1;
        throw original;
      },
    ),
    (error) => error === original,
  );
  assert.equal(executions, 1);
  assert.equal(h.calls.length, 1);
});

test("éxito no toca fail y retorna exactamente el resultado supervisado", async () => {
  const h = storeHarness();
  const result = { ok: true, decision: "ORIGIN_COMPLETED" };
  const actual = await runSupervisedExecuteOperation(
    h.store,
    execution(),
    {},
    {},
    { clock: () => new Date(NOW) },
    async () => result,
  );
  assert.equal(actual, result);
  assert.equal(h.calls.length, 0);
});

test("error pre-reserve también es seguro si no existe reservation", async () => {
  const h = storeHarness({ failThrows: true });
  await assert.rejects(
    runSupervisedExecuteOperation(
      h.store,
      execution(),
      {},
      {},
      { clock: () => new Date(NOW) },
      async () => { throw new EdgePolicyError("graphql_query_mismatch"); },
    ),
    EdgePolicyError,
  );
  assert.equal(h.calls.length, 1);
});
