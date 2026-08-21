import { canonicalJson, EdgePolicyError, sha256Hex } from "./core.mjs";
import {
  completeReservation,
  createAuthorizationState,
  failReservation,
  ledgerSummary,
  rejectAuthorization,
  reserveRequest,
} from "./authorization-ledger.mjs";

export const AUTHORIZATION_STATE_KEY = "authorization-state";
export const RESPONSE_KEY_PREFIX = "response:";
export const MAX_REPLAY_BODY_BYTES = 1_500_000;

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function requireStorage(storage) {
  if (!storage || typeof storage.transactionSync !== "function") {
    fail("durable_storage_transaction_sync_missing");
  }
  if (!storage.kv || typeof storage.kv.get !== "function" || typeof storage.kv.put !== "function") {
    fail("durable_storage_sync_kv_missing");
  }
  return storage;
}

function clone(value) {
  return structuredClone(value);
}

function responseKey(reservationId) {
  if (typeof reservationId !== "string" || reservationId.length === 0 || /\s/u.test(reservationId)) {
    fail("response_reservation_id_invalid");
  }
  return `${RESPONSE_KEY_PREFIX}${reservationId}`;
}

function stateConfigMatches(state, config) {
  return state.authorizationId === config.authorizationId
    && state.runId === config.runId
    && state.approvedCommitSha === config.approvedCommitSha
    && state.createdAtMs === config.createdAtMs
    && state.expiresAtMs === config.expiresAtMs
    && state.maxRequests === config.maxRequests
    && state.minStartIntervalMs === (config.minStartIntervalMs ?? 1500);
}

function validateReplayEnvelope(envelope, evidence, reservationId) {
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) {
    fail("replay_envelope_invalid");
  }
  if (envelope.reservationId !== reservationId) fail("replay_reservation_id_mismatch");
  if (!(envelope.rawBody instanceof Uint8Array)) fail("replay_raw_body_invalid");
  if (envelope.rawBody.byteLength > MAX_REPLAY_BODY_BYTES) fail("replay_body_above_limit");
  if (envelope.responseStatus !== evidence.responseStatus) fail("replay_status_mismatch");
  if (envelope.rawBody.byteLength !== evidence.responseBodyBytes) fail("replay_body_size_mismatch");
  if (typeof envelope.rawResponseSha256 !== "string" || envelope.rawResponseSha256 !== evidence.rawResponseSha256) {
    fail("replay_response_hash_mismatch");
  }
  if (!envelope.receiptPayload || typeof envelope.receiptPayload !== "object" || Array.isArray(envelope.receiptPayload)) {
    fail("replay_receipt_invalid");
  }
  if (envelope.receiptPayload.reservation_id !== reservationId) fail("replay_receipt_reservation_mismatch");
  if (envelope.receiptPayload.raw_response_sha256 !== evidence.rawResponseSha256) fail("replay_receipt_hash_mismatch");
  if (envelope.receiptPayload.response_status !== evidence.responseStatus) fail("replay_receipt_status_mismatch");
  if (envelope.receiptPayload.response_body_bytes !== evidence.responseBodyBytes) fail("replay_receipt_size_mismatch");
  if (typeof envelope.signatureB64Url !== "string" || envelope.signatureB64Url.length < 40) fail("replay_signature_invalid");
  if (typeof envelope.signingKeyId !== "string" || envelope.signingKeyId.length === 0 || /\s/u.test(envelope.signingKeyId)) {
    fail("replay_signing_key_id_invalid");
  }
  canonicalJson(envelope.receiptPayload);
}

function evidenceFromReplayEnvelope(envelope) {
  return {
    evidenceId: envelope.evidenceId,
    rawResponseSha256: envelope.rawResponseSha256,
    responseStatus: envelope.responseStatus,
    responseBodyBytes: envelope.rawBody.byteLength,
  };
}

function replayMatchesReservation(envelope, reservation) {
  if (!envelope || reservation.status !== "completed" || !reservation.evidence) return false;
  try {
    validateReplayEnvelope(envelope, reservation.evidence, reservation.reservationId);
    return envelope.evidenceId === reservation.evidence.evidenceId;
  } catch {
    return false;
  }
}

export class DurableAuthorizationStore {
  constructor(storage) {
    this.storage = requireStorage(storage);
  }

  initialize(config) {
    return this.storage.transactionSync(() => {
      const existing = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
      if (existing !== undefined) {
        ledgerSummary(existing, config.createdAtMs);
        if (!stateConfigMatches(existing, config)) fail("authorization_initialize_conflict");
        return clone(existing);
      }
      const created = createAuthorizationState(config);
      this.storage.kv.put(AUTHORIZATION_STATE_KEY, clone(created));
      return clone(created);
    });
  }

  reserve(request, nowMs) {
    return this.storage.transactionSync(() => {
      const current = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
      if (current === undefined) fail("authorization_state_missing");
      const result = reserveRequest(current, request, nowMs);
      this.storage.kv.put(AUTHORIZATION_STATE_KEY, clone(result.state));

      if (result.decision !== "REPLAY") return clone(result);
      const reservation = result.reservation;
      if (reservation.status === "reserved") {
        return {
          decision: "REPLAY_IN_FLIGHT",
          reservation: clone(reservation),
          state: clone(result.state),
        };
      }
      if (reservation.status === "failed") {
        return {
          decision: "REPLAY_FAILED",
          reservation: clone(reservation),
          state: clone(result.state),
        };
      }

      const envelope = this.storage.kv.get(responseKey(reservation.reservationId));
      if (!replayMatchesReservation(envelope, reservation)) fail("completed_replay_evidence_missing_or_corrupt");
      return {
        decision: "REPLAY_COMPLETED",
        reservation: clone(reservation),
        replayEnvelope: clone(envelope),
        state: clone(result.state),
      };
    });
  }

  async complete(reservationId, replayEnvelope, nowMs) {
    const evidence = evidenceFromReplayEnvelope(replayEnvelope);
    if (typeof evidence.evidenceId !== "string" || evidence.evidenceId.length === 0 || /\s/u.test(evidence.evidenceId)) {
      fail("evidence_id_invalid");
    }
    validateReplayEnvelope(replayEnvelope, evidence, reservationId);
    const computedHash = await sha256Hex(replayEnvelope.rawBody);
    if (computedHash !== evidence.rawResponseSha256) fail("replay_raw_body_hash_mismatch");

    return this.storage.transactionSync(() => {
      const current = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
      if (current === undefined) fail("authorization_state_missing");
      const existingEnvelope = this.storage.kv.get(responseKey(reservationId));
      if (existingEnvelope !== undefined) {
        const reservation = current.reservations?.[reservationId];
        if (!reservation || !replayMatchesReservation(existingEnvelope, reservation)) {
          fail("existing_replay_evidence_corrupt");
        }
      }

      const completed = completeReservation(current, reservationId, evidence, nowMs);
      this.storage.kv.put(AUTHORIZATION_STATE_KEY, clone(completed));
      this.storage.kv.put(responseKey(reservationId), clone(replayEnvelope));
      return clone(completed);
    });
  }

  fail(reservationId, reason, nowMs) {
    return this.storage.transactionSync(() => {
      const current = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
      if (current === undefined) fail("authorization_state_missing");
      const failed = failReservation(current, reservationId, reason, nowMs);
      this.storage.kv.put(AUTHORIZATION_STATE_KEY, clone(failed));
      return clone(failed);
    });
  }

  reject(reason, nowMs) {
    return this.storage.transactionSync(() => {
      const current = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
      if (current === undefined) fail("authorization_state_missing");
      const rejected = rejectAuthorization(current, reason, nowMs);
      this.storage.kv.put(AUTHORIZATION_STATE_KEY, clone(rejected));
      return clone(rejected);
    });
  }

  summary(nowMs) {
    const current = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
    if (current === undefined) fail("authorization_state_missing");
    return ledgerSummary(current, nowMs);
  }

  replay(reservationId) {
    const current = this.storage.kv.get(AUTHORIZATION_STATE_KEY);
    if (current === undefined) fail("authorization_state_missing");
    ledgerSummary(current, Math.max(current.createdAtMs, 1));
    const reservation = current.reservations?.[reservationId];
    if (!reservation) fail("reservation_not_found");
    if (reservation.status !== "completed") fail("reservation_not_completed");
    const envelope = this.storage.kv.get(responseKey(reservationId));
    if (!replayMatchesReservation(envelope, reservation)) fail("completed_replay_evidence_missing_or_corrupt");
    return clone(envelope);
  }
}
