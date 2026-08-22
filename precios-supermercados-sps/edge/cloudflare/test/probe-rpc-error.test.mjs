import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import {
  CONTROLLED_PROBE_GENERIC_EXECUTION_ERROR,
  controlledProbeExecutionFailureCode,
  controlledProbeFailureEnvelope,
} from "../src/probe-rpc-error.mjs";

test("frontera RPC conserva sólo códigos de política conocidos", () => {
  const error = new EdgePolicyError("probe_origin_http_503");
  assert.equal(controlledProbeExecutionFailureCode(error), "probe_origin_http_503");
  assert.deepEqual(controlledProbeFailureEnvelope(error), {
    ok: false,
    error: "probe_origin_http_503",
  });
});

test("frontera RPC reduce excepciones desconocidas a código genérico", () => {
  const error = new TypeError("sensitive runtime detail");
  assert.equal(controlledProbeExecutionFailureCode(error), CONTROLLED_PROBE_GENERIC_EXECUTION_ERROR);
  const envelope = controlledProbeFailureEnvelope(error);
  assert.deepEqual(envelope, {
    ok: false,
    error: "probe_execution_failed",
  });
  assert.equal(JSON.stringify(envelope).includes("sensitive runtime detail"), false);
});
