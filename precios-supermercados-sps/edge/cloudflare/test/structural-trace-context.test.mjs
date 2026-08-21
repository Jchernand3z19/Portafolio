import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import {
  STRUCTURAL_EXECUTION_SPAN_NAME,
  STRUCTURAL_TRACE_CONTRACT_VERSION,
  annotateStructuralExecutionSpan,
  structuralExecutionTraceAttributes,
} from "../src/structural-trace-context.mjs";

const SHA = "a".repeat(40);
const DIGEST = "b".repeat(64);

function execution(overrides = {}) {
  return {
    requestContext: {
      authorizationId: "authorization-structural-001",
      runId: "32526000000:1",
      approvedCommitSha: SHA,
      reservationId: "reservation-root-total-001",
      requestId: "request-root-total-001",
      requestDigest: DIGEST,
      requestKind: "root_total",
      ...overrides,
    },
  };
}

function expectPolicyError(error, code) {
  assert.ok(error instanceof EdgePolicyError);
  assert.equal(error.code, code);
  return true;
}

test("emite exactamente los atributos estructurales esperados", () => {
  const attributes = structuralExecutionTraceAttributes(execution());
  assert.deepEqual(attributes, {
    "precios.trace_contract_version": STRUCTURAL_TRACE_CONTRACT_VERSION,
    "precios.collector_provider": "cloudflare_workers",
    "precios.authorization_id": "authorization-structural-001",
    "precios.run_id": "32526000000:1",
    "precios.approved_commit_sha": SHA,
    "precios.reservation_id": "reservation-root-total-001",
    "precios.request_id": "request-root-total-001",
    "precios.request_digest": DIGEST,
    "precios.request_kind": "root_total",
  });
  assert.equal(STRUCTURAL_EXECUTION_SPAN_NAME, "precios_sps_structural_execution");
  assert.equal(Object.isFrozen(attributes), true);
});

test("category_tree usa el mismo contrato sin campos de traversal", () => {
  const attributes = structuralExecutionTraceAttributes(
    execution({ requestKind: "category_tree", requestId: "request-tree-001" }),
  );
  assert.equal(attributes["precios.request_kind"], "category_tree");
  assert.equal(attributes["precios.request_id"], "request-tree-001");
  assert.equal("precios.traversal_role" in attributes, false);
  assert.equal("precios.traversal_id" in attributes, false);
  assert.equal("precios.partition_id" in attributes, false);
});

test("rechaza kinds ajenos y digests o commits no canonicos", () => {
  assert.throws(
    () => structuralExecutionTraceAttributes(execution({ requestKind: "primary" })),
    (error) => expectPolicyError(error, "structural_trace_request_kind_invalid"),
  );
  assert.throws(
    () => structuralExecutionTraceAttributes(execution({ requestDigest: "b".repeat(63) })),
    (error) => expectPolicyError(error, "structural_trace_request_digest_invalid"),
  );
  assert.throws(
    () => structuralExecutionTraceAttributes(execution({ approvedCommitSha: "A".repeat(40) })),
    (error) => expectPolicyError(error, "structural_trace_commit_sha_invalid"),
  );
});

test("rechaza contexto ausente, whitespace y ids vacios", () => {
  assert.throws(
    () => structuralExecutionTraceAttributes({}),
    (error) => expectPolicyError(error, "structural_trace_request_context_invalid"),
  );
  assert.throws(
    () => structuralExecutionTraceAttributes(execution({ authorizationId: " auth" })),
    (error) => expectPolicyError(error, "structural_trace_authorization_id_invalid"),
  );
  assert.throws(
    () => structuralExecutionTraceAttributes(execution({ reservationId: "" })),
    (error) => expectPolicyError(error, "structural_trace_reservation_id_invalid"),
  );
});

test("anota sólo spans muestreados y devuelve los mismos atributos", () => {
  const observed = new Map();
  const span = {
    isTraced: true,
    setAttribute: (key, value) => observed.set(key, value),
  };
  const attributes = annotateStructuralExecutionSpan(span, execution());
  assert.deepEqual(Object.fromEntries(observed), attributes);
});

test("falla cerrado si tracing no fue muestreado o el span es invalido", () => {
  assert.throws(
    () => annotateStructuralExecutionSpan({ isTraced: false, setAttribute() {} }, execution()),
    (error) => expectPolicyError(error, "structural_origin_trace_not_sampled"),
  );
  assert.throws(
    () => annotateStructuralExecutionSpan({}, execution()),
    (error) => expectPolicyError(error, "structural_trace_span_invalid"),
  );
});
