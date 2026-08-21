import assert from "node:assert/strict";
import test from "node:test";

import {
  HARD_MAX_REQUESTS,
  MAX_AUTHORIZATION_LIFETIME_MS,
  MIN_PACING_MS,
  completeReservation,
  createAuthorizationState,
  failReservation,
  ledgerSummary,
  rejectAuthorization,
  reserveRequest,
} from "../src/ledger.mjs";
import { EdgePolicyError } from "../src/core.mjs";

const SHA = "a".repeat(40);
const DIGEST_1 = "b".repeat(64);
const DIGEST_2 = "c".repeat(64);
const RESPONSE_1 = "d".repeat(64);
const RESPONSE_2 = "e".repeat(64);
const T0 = 2_000_000_000_000;

function expectPolicyError(error, code) {
  assert.ok(error instanceof EdgePolicyError);
  assert.equal(error.code, code);
  return true;
}

function state(overrides = {}) {
  return createAuthorizationState({
    authorizationId: "auth-001",
    runId: "run-001",
    approvedCommitSha: SHA,
    createdAtMs: T0,
    expiresAtMs: T0 + 30 * 60 * 1000,
    maxRequests: 3,
    minStartIntervalMs: MIN_PACING_MS,
    ...overrides,
  });
}

function request(index = 1, overrides = {}) {
  return {
    authorizationId: "auth-001",
    runId: "run-001",
    approvedCommitSha: SHA,
    reservationId: `reservation-${index}`,
    requestId: `request-${index}`,
    requestDigest: index === 1 ? DIGEST_1 : DIGEST_2,
    nonce: `nonce-${index}`,
    traversalRole: index === 1 ? "primary" : "reconciliation",
    traversalId: index === 1 ? "traversal-primary" : "traversal-reconciliation",
    partitionId: "root",
    ...overrides,
  };
}

function evidence(index = 1, overrides = {}) {
  return {
    evidenceId: `evidence-${index}`,
    rawResponseSha256: index === 1 ? RESPONSE_1 : RESPONSE_2,
    responseStatus: 200,
    responseBodyBytes: 1234 + index,
    ...overrides,
  };
}

test("autorización fija límites duros y nace vacía", () => {
  const value = state();
  assert.equal(value.state, "active");
  assert.equal(value.requestsUsed, 0);
  assert.equal(Object.keys(value.reservations).length, 0);
  assert.ok(Object.isFrozen(value));
});

test("rechaza presupuesto, pacing o lifetime por encima de límites", () => {
  assert.throws(() => state({ maxRequests: HARD_MAX_REQUESTS + 1 }), (error) => expectPolicyError(error, "max_requests_invalid"));
  assert.throws(() => state({ minStartIntervalMs: MIN_PACING_MS - 1 }), (error) => expectPolicyError(error, "min_start_interval_invalid"));
  assert.throws(
    () => state({ expiresAtMs: T0 + MAX_AUTHORIZATION_LIFETIME_MS + 1 }),
    (error) => expectPolicyError(error, "authorization_lifetime_above_limit"),
  );
});

test("primera reserva consume exactamente un cupo y fija inicio físico", () => {
  const result = reserveRequest(state(), request(1), T0 + 100);
  assert.equal(result.decision, "RESERVED");
  assert.equal(result.state.requestsUsed, 1);
  assert.equal(result.state.lastPhysicalStartMs, T0 + 100);
  assert.equal(result.reservation.status, "reserved");
});

test("pacing devuelve WAIT sin reservar ni consumir presupuesto", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  const wait = reserveRequest(first.state, request(2), T0 + 100 + MIN_PACING_MS - 1);
  assert.equal(wait.decision, "WAIT");
  assert.equal(wait.notBeforeMs, T0 + 100 + MIN_PACING_MS);
  assert.equal(wait.state.requestsUsed, 1);
  assert.equal(Object.hasOwn(wait.state.reservations, "reservation-2"), false);

  const second = reserveRequest(wait.state, request(2), wait.notBeforeMs);
  assert.equal(second.decision, "RESERVED");
  assert.equal(second.state.requestsUsed, 2);
});

test("replay exacto de reservation_id es idempotente aunque presupuesto esté consumido", () => {
  const initial = state({ maxRequests: 1 });
  const first = reserveRequest(initial, request(1), T0 + 100);
  assert.equal(first.state.state, "consumed");
  assert.equal(first.state.requestsUsed, 1);

  const replay = reserveRequest(first.state, request(1), T0 + 100 + MIN_PACING_MS);
  assert.equal(replay.decision, "REPLAY");
  assert.equal(replay.state.requestsUsed, 1);
  assert.equal(replay.reservation.reservationId, "reservation-1");
});

test("mismo reservation_id con identidad distinta falla cerrado", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  assert.throws(
    () => reserveRequest(first.state, request(1, { nonce: "different" }), T0 + 2000),
    (error) => expectPolicyError(error, "reservation_replay_conflict"),
  );
});

test("request_id, digest y nonce no se pueden reutilizar bajo otra reserva", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  const at = T0 + 100 + MIN_PACING_MS;
  assert.throws(
    () => reserveRequest(first.state, request(2, { requestId: "request-1" }), at),
    (error) => expectPolicyError(error, "duplicate_request_id"),
  );
  assert.throws(
    () => reserveRequest(first.state, request(2, { requestDigest: DIGEST_1 }), at),
    (error) => expectPolicyError(error, "duplicate_request_digest"),
  );
  assert.throws(
    () => reserveRequest(first.state, request(2, { nonce: "nonce-1" }), at),
    (error) => expectPolicyError(error, "duplicate_nonce"),
  );
});

test("contexto authorization/run/commit distinto se rechaza", () => {
  const current = state();
  assert.throws(
    () => reserveRequest(current, request(1, { authorizationId: "auth-other" }), T0 + 100),
    (error) => expectPolicyError(error, "authorization_id_mismatch"),
  );
  assert.throws(
    () => reserveRequest(current, request(1, { runId: "run-other" }), T0 + 100),
    (error) => expectPolicyError(error, "run_id_mismatch"),
  );
  assert.throws(
    () => reserveRequest(current, request(1, { approvedCommitSha: "f".repeat(40) }), T0 + 100),
    (error) => expectPolicyError(error, "approved_commit_sha_mismatch"),
  );
});

test("expiración niega requests nuevos pero no aumenta presupuesto", () => {
  const current = state({ expiresAtMs: T0 + 2000 });
  const result = reserveRequest(current, request(1), T0 + 2000);
  assert.equal(result.decision, "DENY");
  assert.equal(result.reason, "authorization_expired");
  assert.equal(result.state.requestsUsed, 0);
  assert.equal(result.state.state, "expired");
});

test("última reserva marca presupuesto consumido pero todavía puede completarse", () => {
  const reserved = reserveRequest(state({ maxRequests: 1 }), request(1), T0 + 100);
  assert.equal(reserved.state.state, "consumed");
  const completed = completeReservation(reserved.state, "reservation-1", evidence(1), T0 + 500);
  assert.equal(completed.reservations["reservation-1"].status, "completed");
  assert.equal(completed.state, "consumed");
});

test("completion replay con misma evidencia es idempotente aunque now cambie", () => {
  const reserved = reserveRequest(state(), request(1), T0 + 100);
  const completed = completeReservation(reserved.state, "reservation-1", evidence(1), T0 + 500);
  const replay = completeReservation(completed, "reservation-1", evidence(1), T0 + 900);
  assert.deepEqual(replay, completed);
});

test("completion conflict o evidence_id repetido falla cerrado", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  const completed = completeReservation(first.state, "reservation-1", evidence(1), T0 + 500);
  assert.throws(
    () => completeReservation(completed, "reservation-1", evidence(1, { responseStatus: 201 }), T0 + 900),
    (error) => expectPolicyError(error, "reservation_completion_conflict"),
  );

  const second = reserveRequest(completed, request(2), T0 + 100 + MIN_PACING_MS);
  assert.throws(
    () => completeReservation(second.state, "reservation-2", evidence(2, { evidenceId: "evidence-1" }), T0 + 2000),
    (error) => expectPolicyError(error, "duplicate_evidence_id"),
  );
});

test("fallo físico consume el cupo reservado y rechaza toda la autorización", () => {
  const reserved = reserveRequest(state(), request(1), T0 + 100);
  const failed = failReservation(reserved.state, "reservation-1", "origin_http_429", T0 + 500);
  assert.equal(failed.state, "rejected");
  assert.equal(failed.requestsUsed, 1);
  assert.equal(failed.reservations["reservation-1"].status, "failed");
  assert.equal(failed.terminalReason, "origin_http_429");

  const denied = reserveRequest(failed, request(2), T0 + 5000);
  assert.equal(denied.decision, "DENY");
  assert.equal(denied.reason, "authorization_rejected");
  assert.equal(denied.state.requestsUsed, 1);
});

test("failure replay con mismo reason es idempotente aunque now cambie", () => {
  const reserved = reserveRequest(state(), request(1), T0 + 100);
  const failed = failReservation(reserved.state, "reservation-1", "origin_redirect", T0 + 500);
  const replay = failReservation(failed, "reservation-1", "origin_redirect", T0 + 900);
  assert.deepEqual(replay, failed);
});

test("rechazo manual es terminal e idempotente por reason", () => {
  const rejected = rejectAuthorization(state(), "operator_cancelled", T0 + 100);
  assert.equal(rejected.state, "rejected");
  assert.deepEqual(rejectAuthorization(rejected, "operator_cancelled", T0 + 500), rejected);
  assert.throws(
    () => rejectAuthorization(rejected, "different_reason", T0 + 500),
    (error) => expectPolicyError(error, "authorization_rejection_conflict"),
  );
});

test("summary no revela catálogo y conserva contadores de reservations", () => {
  const first = reserveRequest(state(), request(1), T0 + 100);
  const completed = completeReservation(first.state, "reservation-1", evidence(1), T0 + 500);
  const second = reserveRequest(completed, request(2), T0 + 100 + MIN_PACING_MS);
  const summary = ledgerSummary(second.state, T0 + 3000);
  assert.deepEqual(summary.reservationCounts, { reserved: 1, completed: 1, failed: 0 });
  assert.equal(summary.requestsUsed, 2);
  assert.equal(summary.remainingRequests, 1);
  assert.equal("reservations" in summary, false);
});

test("estado persistido corrupto falla cerrado", () => {
  const reserved = reserveRequest(state(), request(1), T0 + 100).state;
  const corrupt = structuredClone(reserved);
  corrupt.requestsUsed = 0;
  assert.throws(
    () => ledgerSummary(corrupt, T0 + 500),
    (error) => expectPolicyError(error, "ledger_reservation_count_mismatch"),
  );
});
