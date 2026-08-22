import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import { CONTROLLED_PROBE_PURPOSE, CONTROLLED_PROBE_SPAN_NAME } from "../src/probe-policy.mjs";
import {
  CONTROLLED_PROBE_TRACE_CONTRACT_VERSION,
  annotateControlledProbeSpan,
  assertControlledProbeSpanName,
  controlledProbeTraceAttributes,
} from "../src/probe-trace-context.mjs";

const SHA = "a".repeat(40);

function input(overrides = {}) {
  return {
    probeId: "github-32550000000-1",
    approvedCommitSha: SHA,
    claims: {
      run_id: "32550000000",
      run_attempt: "1",
    },
    ...overrides,
  };
}

test("atributos de tracing de sonda quedan ligados a commit y run", () => {
  assert.deepEqual(controlledProbeTraceAttributes(input()), {
    "precios.probe_contract_version": CONTROLLED_PROBE_TRACE_CONTRACT_VERSION,
    "precios.probe_purpose": CONTROLLED_PROBE_PURPOSE,
    "precios.probe_id": "github-32550000000-1",
    "precios.approved_commit_sha": SHA,
    "precios.github_run_id": "32550000000",
    "precios.github_run_attempt": "1",
    "precios.target_kind": "controlled_workers_dev_origin",
  });
  assert.equal(assertControlledProbeSpanName(CONTROLLED_PROBE_SPAN_NAME), CONTROLLED_PROBE_SPAN_NAME);
});

test("sonda falla antes del fetch cuando Cloudflare no muestrea el span", () => {
  let writes = 0;
  const span = {
    isTraced: false,
    setAttribute() {
      writes += 1;
    },
  };
  assert.throws(
    () => annotateControlledProbeSpan(span, input()),
    (error) => error instanceof EdgePolicyError && error.code === "probe_trace_not_sampled",
  );
  assert.equal(writes, 0);
});

test("span muestreado recibe únicamente el contexto canónico", () => {
  const observed = {};
  const span = {
    isTraced: true,
    setAttribute(key, value) {
      observed[key] = value;
    },
  };
  const expected = controlledProbeTraceAttributes(input());
  assert.deepEqual(annotateControlledProbeSpan(span, input()), expected);
  assert.deepEqual(observed, expected);
});

test("run attempt o contexto inválidos fallan cerrado", () => {
  for (const bad of ["0", "101", "x", 1.5]) {
    assert.throws(
      () => controlledProbeTraceAttributes(input({ claims: { run_id: "32550000000", run_attempt: bad } })),
      EdgePolicyError,
    );
  }
  assert.throws(() => assertControlledProbeSpanName("precios_sps_origin_execution"), EdgePolicyError);
});
