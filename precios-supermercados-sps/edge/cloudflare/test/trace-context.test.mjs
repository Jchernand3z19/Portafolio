import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  annotateExecutionSpan,
  executionTraceAttributes,
  ORIGIN_EXECUTION_SPAN_NAME,
  TRACE_CONTRACT_VERSION,
} from "../src/trace-context.mjs";

function execution() {
  return {
    requestContext: {
      authorizationId: "auth-trace-001",
      runId: "32515638856:1",
      approvedCommitSha: "a".repeat(40),
      reservationId: "reservation-trace-001",
      requestId: "request-trace-001",
      requestDigest: "b".repeat(64),
      nonce: "nonce-trace-001",
      traversalRole: "primary",
      traversalId: "traversal-primary-trace-001",
      partitionId: "root",
    },
  };
}

test("trace contract fija nombre, versión y contexto completo", () => {
  const attributes = executionTraceAttributes(execution());
  assert.equal(ORIGIN_EXECUTION_SPAN_NAME, "precios_sps_origin_execution");
  assert.equal(TRACE_CONTRACT_VERSION, "1");
  assert.deepEqual(attributes, {
    "precios.trace_contract_version": "1",
    "precios.collector_provider": "cloudflare_workers",
    "precios.authorization_id": "auth-trace-001",
    "precios.run_id": "32515638856:1",
    "precios.approved_commit_sha": "a".repeat(40),
    "precios.reservation_id": "reservation-trace-001",
    "precios.request_id": "request-trace-001",
    "precios.request_digest": "b".repeat(64),
    "precios.traversal_role": "primary",
    "precios.traversal_id": "traversal-primary-trace-001",
    "precios.partition_id": "root",
  });
  assert.equal(Object.isFrozen(attributes), true);
});

test("span no muestreado falla antes del fetch físico", () => {
  const span = {
    isTraced: false,
    setAttribute() {
      assert.fail("no debe escribir atributos si la traza no fue muestreada");
    },
  };
  assert.throws(
    () => annotateExecutionSpan(span, execution()),
    (error) => error?.code === "origin_trace_not_sampled",
  );
});

test("span trazado recibe todas las claves de correlación", () => {
  const written = new Map();
  const span = {
    isTraced: true,
    setAttribute(key, value) {
      written.set(key, value);
    },
  };
  const attributes = annotateExecutionSpan(span, execution());
  assert.deepEqual(Object.fromEntries(written), attributes);
  assert.equal(written.size, 11);
});

test("contexto incompleto falla cerrado", () => {
  const broken = execution();
  delete broken.requestContext.reservationId;
  assert.throws(
    () => executionTraceAttributes(broken),
    (error) => error?.code === "trace_reservation_id_invalid",
  );
});

test("wrangler exige tracing persistido con muestreo del cien por ciento", () => {
  const config = JSON.parse(
    readFileSync(new URL("../wrangler.json", import.meta.url), "utf8"),
  );
  assert.deepEqual(config.observability?.traces, {
    enabled: true,
    head_sampling_rate: 1,
  });
});

test("entrypoint envuelve la ejecución del Durable Object en el span correlacionado", () => {
  const source = readFileSync(new URL("../src/index.mjs", import.meta.url), "utf8");
  assert.match(source, /tracing\.enterSpan\(ORIGIN_EXECUTION_SPAN_NAME/);
  assert.match(source, /annotateExecutionSpan\(span, input\.execution\)/);
  const annotateAt = source.indexOf("annotateExecutionSpan(span, input.execution)");
  const runAt = source.indexOf("runSupervisedExecuteOperation(", annotateAt);
  assert.ok(annotateAt >= 0 && runAt > annotateAt);
});
