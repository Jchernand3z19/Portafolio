import assert from "node:assert/strict";
import test from "node:test";

import {
  completeReservation,
  createAuthorizationState,
  reserveRequest,
} from "../src/authorization-ledger.mjs";

const SHA = "a".repeat(40);
const DIGEST_1 = "b".repeat(64);
const DIGEST_2 = "c".repeat(64);
const RESPONSE_1 = "d".repeat(64);
const T0 = 2_000_000_000_000;

function state() {
  return createAuthorizationState({
    authorizationId: "auth-001",
    runId: "run-001",
    approvedCommitSha: SHA,
    createdAtMs: T0,
    expiresAtMs: T0 + 30 * 60 * 1000,
    maxRequests: 3,
    minStartIntervalMs: 1500,
  });
}

function request(index) {
  return {
    authorizationId: "auth-001",
    runId: "run-001",
    approvedCommitSha: SHA,
    reservationId: `reservation-${index}`,
    requestId: `request-${index}`,
    requestDigest: index === 1 ? DIGEST_1 : DIGEST_2,
    nonce: `nonce-${index}`,
    traversalRole: index === 1 ? "primary" : "reconciliation",
    traversalId: `traversal-${index}`,
    partitionId: "root",
  };
}

test("un request distinto espera mientras existe uno físicamente en vuelo", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  assert.equal(first.decision, "RESERVED");

  const second = reserveRequest(first.state, request(2), T0 + 5000);
  assert.equal(second.decision, "WAIT");
  assert.equal(second.reason, "physical_request_in_flight");
  assert.equal(second.inFlightReservationId, "reservation-1");
  assert.equal(second.state.requestsUsed, 1);
  assert.equal(Object.hasOwn(second.state.reservations, "reservation-2"), false);
});

test("replay exacto del request en vuelo sigue siendo idempotente", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  const replay = reserveRequest(first.state, request(1), T0 + 5000);
  assert.equal(replay.decision, "REPLAY");
  assert.equal(replay.reservation.status, "reserved");
  assert.equal(replay.state.requestsUsed, 1);
});

test("después de completar el request anterior puede reservar el siguiente", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  const completed = completeReservation(
    first.state,
    "reservation-1",
    {
      evidenceId: "evidence-1",
      rawResponseSha256: RESPONSE_1,
      responseStatus: 200,
      responseBodyBytes: 1234,
    },
    T0 + 1000,
  );
  const second = reserveRequest(completed, request(2), T0 + 100 + 1500);
  assert.equal(second.decision, "RESERVED");
  assert.equal(second.state.requestsUsed, 2);
});
