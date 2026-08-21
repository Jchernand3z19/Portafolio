import { EdgePolicyError } from "./core.mjs";

export const HARD_MAX_REQUESTS = 1000;
export const MIN_PACING_MS = 1500;
export const MAX_PACING_MS = 60_000;
export const MAX_AUTHORIZATION_LIFETIME_MS = 45 * 60 * 1000;

const SHA1_RE = /^[0-9a-f]{40}$/;
const SHA256_RE = /^[0-9a-f]{64}$/;
const ID_RE = /^[^\s]{1,256}$/;
const ROLE_SET = new Set(["primary", "reconciliation"]);
const TERMINAL_STATES = new Set(["consumed", "rejected", "expired"]);

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function id(value, code) {
  if (typeof value !== "string" || !ID_RE.test(value)) fail(code);
  return value;
}

function exactInt(value, code, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
  return value;
}

function uniqueStrings(values, code) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== "string")) fail(code);
  if (new Set(values).size !== values.length) fail(code);
}

function cloneReservation(value) {
  return value ? { ...value, evidence: value.evidence ? { ...value.evidence } : null } : value;
}

function cloneState(state) {
  const reservations = {};
  for (const [key, value] of Object.entries(state.reservations ?? {})) {
    reservations[key] = cloneReservation(value);
  }
  return {
    ...state,
    reservations,
    usedRequestIds: [...(state.usedRequestIds ?? [])],
    usedRequestDigests: [...(state.usedRequestDigests ?? [])],
    usedNonces: [...(state.usedNonces ?? [])],
    usedEvidenceIds: [...(state.usedEvidenceIds ?? [])],
  };
}

function validateStateShape(state) {
  if (!state || typeof state !== "object" || Array.isArray(state)) fail("ledger_state_invalid");
  if (state.schemaVersion !== 1) fail("ledger_schema_invalid");
  id(state.authorizationId, "ledger_authorization_id_invalid");
  id(state.runId, "ledger_run_id_invalid");
  if (!SHA1_RE.test(state.approvedCommitSha ?? "")) fail("ledger_commit_sha_invalid");
  exactInt(state.createdAtMs, "ledger_created_at_invalid", 1);
  exactInt(state.expiresAtMs, "ledger_expires_at_invalid", 1);
  exactInt(state.maxRequests, "ledger_max_requests_invalid", 1, HARD_MAX_REQUESTS);
  exactInt(state.requestsUsed, "ledger_requests_used_invalid", 0, state.maxRequests);
  exactInt(state.minStartIntervalMs, "ledger_pacing_invalid", MIN_PACING_MS, MAX_PACING_MS);
  if (!["active", "consumed", "rejected", "expired"].includes(state.state)) fail("ledger_status_invalid");
  if (state.lastPhysicalStartMs !== null) exactInt(state.lastPhysicalStartMs, "ledger_last_start_invalid", state.createdAtMs);
  if (state.terminalAtMs !== null) exactInt(state.terminalAtMs, "ledger_terminal_at_invalid", state.createdAtMs);
  if (state.terminalReason !== null) id(state.terminalReason, "ledger_terminal_reason_invalid");
  if (!state.reservations || typeof state.reservations !== "object" || Array.isArray(state.reservations)) fail("ledger_reservations_invalid");
  uniqueStrings(state.usedRequestIds, "ledger_request_ids_invalid");
  uniqueStrings(state.usedRequestDigests, "ledger_request_digests_invalid");
  uniqueStrings(state.usedNonces, "ledger_nonces_invalid");
  uniqueStrings(state.usedEvidenceIds, "ledger_evidence_ids_invalid");
  if (state.requestsUsed !== Object.keys(state.reservations).length) fail("ledger_reservation_count_mismatch");
  return state;
}

export function createAuthorizationState(config) {
  const authorizationId = id(config?.authorizationId, "authorization_id_invalid");
  const runId = id(config?.runId, "run_id_invalid");
  const approvedCommitSha = config?.approvedCommitSha;
  if (!SHA1_RE.test(approvedCommitSha ?? "")) fail("approved_commit_sha_invalid");
  const createdAtMs = exactInt(config?.createdAtMs, "created_at_invalid", 1);
  const expiresAtMs = exactInt(config?.expiresAtMs, "expires_at_invalid", createdAtMs + 1);
  if (expiresAtMs - createdAtMs > MAX_AUTHORIZATION_LIFETIME_MS) fail("authorization_lifetime_above_limit");
  const maxRequests = exactInt(config?.maxRequests, "max_requests_invalid", 1, HARD_MAX_REQUESTS);
  const minStartIntervalMs = exactInt(
    config?.minStartIntervalMs ?? MIN_PACING_MS,
    "min_start_interval_invalid",
    MIN_PACING_MS,
    MAX_PACING_MS,
  );
  return Object.freeze({
    schemaVersion: 1,
    authorizationId,
    runId,
    approvedCommitSha,
    createdAtMs,
    expiresAtMs,
    maxRequests,
    minStartIntervalMs,
    requestsUsed: 0,
    lastPhysicalStartMs: null,
    state: "active",
    terminalAtMs: null,
    terminalReason: null,
    reservations: Object.freeze({}),
    usedRequestIds: Object.freeze([]),
    usedRequestDigests: Object.freeze([]),
    usedNonces: Object.freeze([]),
    usedEvidenceIds: Object.freeze([]),
  });
}

function maybeExpire(state, nowMs) {
  if (state.state === "active" && nowMs >= state.expiresAtMs) {
    const next = cloneState(state);
    next.state = "expired";
    next.terminalAtMs = nowMs;
    next.terminalReason = "authorization_expired";
    return next;
  }
  return cloneState(state);
}

function assertActiveContext(state, request) {
  if (request.authorizationId !== state.authorizationId) fail("authorization_id_mismatch");
  if (request.runId !== state.runId) fail("run_id_mismatch");
  if (request.approvedCommitSha !== state.approvedCommitSha) fail("approved_commit_sha_mismatch");
}

function validateReservationRequest(request) {
  const normalized = {
    authorizationId: id(request?.authorizationId, "request_authorization_id_invalid"),
    runId: id(request?.runId, "request_run_id_invalid"),
    approvedCommitSha: request?.approvedCommitSha,
    reservationId: id(request?.reservationId, "reservation_id_invalid"),
    requestId: id(request?.requestId, "request_id_invalid"),
    requestDigest: request?.requestDigest,
    nonce: id(request?.nonce, "nonce_invalid"),
    traversalRole: request?.traversalRole,
    traversalId: id(request?.traversalId, "traversal_id_invalid"),
    partitionId: id(request?.partitionId, "partition_id_invalid"),
  };
  if (!SHA1_RE.test(normalized.approvedCommitSha ?? "")) fail("request_commit_sha_invalid");
  if (!SHA256_RE.test(normalized.requestDigest ?? "")) fail("request_digest_invalid");
  if (!ROLE_SET.has(normalized.traversalRole)) fail("traversal_role_invalid");
  return normalized;
}

export function reserveRequest(stateInput, requestInput, nowInput) {
  validateStateShape(stateInput);
  const nowMs = exactInt(nowInput, "reserve_now_invalid", 1);
  const request = validateReservationRequest(requestInput);
  let state = maybeExpire(stateInput, nowMs);
  assertActiveContext(state, request);

  if (state.state !== "active") {
    return Object.freeze({ decision: "DENY", reason: `authorization_${state.state}`, state: freezeState(state) });
  }
  if (state.requestsUsed >= state.maxRequests) {
    state.state = "consumed";
    state.terminalAtMs = nowMs;
    state.terminalReason = "request_budget_consumed";
    return Object.freeze({ decision: "DENY", reason: "request_budget_consumed", state: freezeState(state) });
  }
  if (Object.hasOwn(state.reservations, request.reservationId)) fail("duplicate_reservation_id");
  if (state.usedRequestIds.includes(request.requestId)) fail("duplicate_request_id");
  if (state.usedRequestDigests.includes(request.requestDigest)) fail("duplicate_request_digest");
  if (state.usedNonces.includes(request.nonce)) fail("duplicate_nonce");

  if (state.lastPhysicalStartMs !== null) {
    const notBeforeMs = state.lastPhysicalStartMs + state.minStartIntervalMs;
    if (nowMs < notBeforeMs) {
      return Object.freeze({
        decision: "WAIT",
        reason: "pacing_not_elapsed",
        notBeforeMs,
        state: freezeState(state),
      });
    }
  }

  const reservation = {
    reservationId: request.reservationId,
    requestId: request.requestId,
    requestDigest: request.requestDigest,
    nonce: request.nonce,
    traversalRole: request.traversalRole,
    traversalId: request.traversalId,
    partitionId: request.partitionId,
    physicalStartMs: nowMs,
    status: "reserved",
    completedAtMs: null,
    failureReason: null,
    evidence: null,
  };
  state.reservations[request.reservationId] = reservation;
  state.usedRequestIds.push(request.requestId);
  state.usedRequestDigests.push(request.requestDigest);
  state.usedNonces.push(request.nonce);
  state.requestsUsed += 1;
  state.lastPhysicalStartMs = nowMs;
  if (state.requestsUsed === state.maxRequests) {
    state.state = "consumed";
    state.terminalAtMs = nowMs;
    state.terminalReason = "request_budget_reserved";
  }

  return Object.freeze({
    decision: "RESERVED",
    reservation: Object.freeze({ ...reservation }),
    state: freezeState(state),
  });
}

function validateEvidence(evidence) {
  const normalized = {
    evidenceId: id(evidence?.evidenceId, "evidence_id_invalid"),
    rawResponseSha256: evidence?.rawResponseSha256,
    responseStatus: exactInt(evidence?.responseStatus, "response_status_invalid", 100, 599),
    responseBodyBytes: exactInt(evidence?.responseBodyBytes, "response_body_bytes_invalid", 0),
  };
  if (!SHA256_RE.test(normalized.rawResponseSha256 ?? "")) fail("raw_response_sha256_invalid");
  return normalized;
}

function evidenceEquals(left, right) {
  return left?.evidenceId === right.evidenceId
    && left?.rawResponseSha256 === right.rawResponseSha256
    && left?.responseStatus === right.responseStatus
    && left?.responseBodyBytes === right.responseBodyBytes;
}

export function completeReservation(stateInput, reservationIdInput, evidenceInput, nowInput) {
  validateStateShape(stateInput);
  const reservationId = id(reservationIdInput, "complete_reservation_id_invalid");
  const nowMs = exactInt(nowInput, "complete_now_invalid", 1);
  const evidence = validateEvidence(evidenceInput);
  const state = cloneState(stateInput);
  const reservation = state.reservations[reservationId];
  if (!reservation) fail("reservation_not_found");
  if (nowMs < reservation.physicalStartMs) fail("completion_precedes_start");

  if (reservation.status === "completed") {
    if (!evidenceEquals(reservation.evidence, evidence) || reservation.completedAtMs !== nowMs) {
      fail("reservation_completion_conflict");
    }
    return freezeState(state);
  }
  if (reservation.status !== "reserved") fail("reservation_not_completable");
  if (state.usedEvidenceIds.includes(evidence.evidenceId)) fail("duplicate_evidence_id");

  reservation.status = "completed";
  reservation.completedAtMs = nowMs;
  reservation.evidence = evidence;
  state.usedEvidenceIds.push(evidence.evidenceId);
  return freezeState(state);
}

export function failReservation(stateInput, reservationIdInput, reasonInput, nowInput) {
  validateStateShape(stateInput);
  const reservationId = id(reservationIdInput, "fail_reservation_id_invalid");
  const reason = id(reasonInput, "failure_reason_invalid");
  const nowMs = exactInt(nowInput, "failure_now_invalid", 1);
  const state = cloneState(stateInput);
  const reservation = state.reservations[reservationId];
  if (!reservation) fail("reservation_not_found");
  if (nowMs < reservation.physicalStartMs) fail("failure_precedes_start");
  if (reservation.status === "failed") {
    if (reservation.failureReason !== reason || reservation.completedAtMs !== nowMs) {
      fail("reservation_failure_conflict");
    }
    return freezeState(state);
  }
  if (reservation.status !== "reserved") fail("reservation_not_failable");

  reservation.status = "failed";
  reservation.failureReason = reason;
  reservation.completedAtMs = nowMs;
  state.state = "rejected";
  state.terminalAtMs = nowMs;
  state.terminalReason = reason;
  return freezeState(state);
}

export function rejectAuthorization(stateInput, reasonInput, nowInput) {
  validateStateShape(stateInput);
  const reason = id(reasonInput, "reject_reason_invalid");
  const nowMs = exactInt(nowInput, "reject_now_invalid", 1);
  const state = maybeExpire(stateInput, nowMs);
  if (state.state === "rejected") {
    if (state.terminalReason !== reason || state.terminalAtMs !== nowMs) fail("authorization_rejection_conflict");
    return freezeState(state);
  }
  if (TERMINAL_STATES.has(state.state)) fail("authorization_already_terminal");
  state.state = "rejected";
  state.terminalAtMs = nowMs;
  state.terminalReason = reason;
  return freezeState(state);
}

export function ledgerSummary(stateInput, nowInput) {
  validateStateShape(stateInput);
  const nowMs = exactInt(nowInput, "summary_now_invalid", 1);
  const state = maybeExpire(stateInput, nowMs);
  const reservations = Object.values(state.reservations);
  const counts = { reserved: 0, completed: 0, failed: 0 };
  for (const reservation of reservations) counts[reservation.status] += 1;
  return Object.freeze({
    authorizationId: state.authorizationId,
    runId: state.runId,
    state: state.state,
    maxRequests: state.maxRequests,
    requestsUsed: state.requestsUsed,
    remainingRequests: state.maxRequests - state.requestsUsed,
    minStartIntervalMs: state.minStartIntervalMs,
    lastPhysicalStartMs: state.lastPhysicalStartMs,
    terminalAtMs: state.terminalAtMs,
    terminalReason: state.terminalReason,
    reservationCounts: Object.freeze(counts),
  });
}

function freezeState(state) {
  for (const reservation of Object.values(state.reservations)) {
    if (reservation.evidence) Object.freeze(reservation.evidence);
    Object.freeze(reservation);
  }
  Object.freeze(state.reservations);
  Object.freeze(state.usedRequestIds);
  Object.freeze(state.usedRequestDigests);
  Object.freeze(state.usedNonces);
  Object.freeze(state.usedEvidenceIds);
  return Object.freeze(state);
}
