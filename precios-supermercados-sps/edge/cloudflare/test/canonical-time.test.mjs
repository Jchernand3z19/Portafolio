import assert from "node:assert/strict";
import test from "node:test";

import { canonicalEdgeTimestamp } from "../src/canonical-time.mjs";
import { EdgePolicyError } from "../src/core.mjs";

function expectPolicyError(error, code) {
  assert.ok(error instanceof EdgePolicyError);
  assert.equal(error.code, code);
  return true;
}

test("timestamp exacto al segundo omite fracción igual que datetime.isoformat", () => {
  assert.equal(
    canonicalEdgeTimestamp(new Date("2026-08-21T16:00:00.000Z")),
    "2026-08-21T16:00:00Z",
  );
});

test("timestamp con milisegundos usa seis dígitos compatibles con Python", () => {
  assert.equal(
    canonicalEdgeTimestamp(new Date("2026-08-21T16:00:00.123Z")),
    "2026-08-21T16:00:00.123000Z",
  );
});

test("timestamp inválido falla cerrado", () => {
  assert.throws(
    () => canonicalEdgeTimestamp(new Date(Number.NaN)),
    (error) => expectPolicyError(error, "canonical_time_invalid"),
  );
});
