import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTHORIZATION_STATE_KEY,
  DurableAuthorizationStore,
  MAX_REPLAY_BODY_BYTES,
  RESPONSE_KEY_PREFIX,
} from "../src/durable-store.mjs";
import { EdgePolicyError, sha256Hex } from "../src/core.mjs";

const SHA = "a".repeat(40);
const DIGEST = "b".repeat(64);
const T0 = 2_000_000_000_000;

function expectPolicyError(error, code) {
  assert.ok(error instanceof EdgePolicyError);
  assert.equal(error.code, code);
  return true;
}

class FakeStorage {
  constructor() {
    this.data = new Map();
    this.failNextPut = false;
    this.kv = {
      get: (key) => {
        const value = this.data.get(key);
        return value === undefined ? undefined : structuredClone(value);
      },
      put: (key, value) => {
        if (this.failNextPut) {
          this.failNextPut = false;
          throw new Error("synthetic_storage_failure");
        }
        this.data.set(key, structuredClone(value));
      },
    };
  }

  transactionSync(callback) {
    const snapshot = new Map(
      [...this.data.entries()].map(([key, value]) => [key, structuredClone(value)]),
    );
    try {
      return callback();
    } catch (error) {
      this.data = snapshot;
      throw error;
    }
  }
}

function config(overrides = {}) {
  return {
    authorizationId: "auth-001",
    runId: "run-001",
    approvedCommitSha: SHA,
    createdAtMs: T0,
    expiresAtMs: T0 + 30 * 60 * 1000,
    maxRequests: 2,
    minStartIntervalMs: 1500,
    ...overrides,
  };
}

function request(overrides = {}) {
  return {
    authorizationId: "auth-001",
    runId: "run-001",
    approvedCommitSha: SHA,
    reservationId: "reservation-1",
    requestId: "request-1",
    requestDigest: DIGEST,
    nonce: "nonce-1",
    traversalRole: "primary",
    traversalId: "traversal-primary",
    partitionId: "root",
    ...overrides,
  };
}

async function replayEnvelope(bodyText = '{"data":[]}') {
  const rawBody = new TextEncoder().encode(bodyText);
  const rawResponseSha256 = await sha256Hex(rawBody);
  return {
    reservationId: "reservation-1",
    evidenceId: "evidence-1",
    rawBody,
    rawResponseSha256,
    responseStatus: 200,
    receiptPayload: {
      reservation_id: "reservation-1",
      raw_response_sha256: rawResponseSha256,
      response_status: 200,
      response_body_bytes: rawBody.byteLength,
    },
    signatureB64Url: "s".repeat(86),
    signingKeyId: "edge-key-001",
  };
}

test("initialize es idempotente con configuración exacta y rechaza conflicto", () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  const first = store.initialize(config());
  const second = store.initialize(config());
  assert.deepEqual(second, first);
  assert.equal(storage.data.has(AUTHORIZATION_STATE_KEY), true);
  assert.throws(
    () => store.initialize(config({ maxRequests: 3 })),
    (error) => expectPolicyError(error, "authorization_initialize_conflict"),
  );
});

test("reserve persiste estado y replay en vuelo nunca crea otro request", () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  const reserved = store.reserve(request(), T0 + 100);
  assert.equal(reserved.decision, "RESERVED");
  assert.equal(storage.data.get(AUTHORIZATION_STATE_KEY).requestsUsed, 1);

  const replay = store.reserve(request(), T0 + 5000);
  assert.equal(replay.decision, "REPLAY_IN_FLIGHT");
  assert.equal(replay.state.requestsUsed, 1);
});

test("complete persiste bytes exactos y replay completed los devuelve sin refetch", async () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  store.reserve(request(), T0 + 100);
  const envelope = await replayEnvelope();
  await store.complete("reservation-1", envelope, T0 + 500);

  const replay = store.reserve(request(), T0 + 5000);
  assert.equal(replay.decision, "REPLAY_COMPLETED");
  assert.deepEqual(replay.replayEnvelope.rawBody, envelope.rawBody);
  assert.equal(replay.replayEnvelope.rawResponseSha256, envelope.rawResponseSha256);
  assert.equal(storage.data.has(`${RESPONSE_KEY_PREFIX}reservation-1`), true);
});

test("body alterado antes de complete rompe hash y no cambia el ledger", async () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  store.reserve(request(), T0 + 100);
  const envelope = await replayEnvelope();
  envelope.rawBody = new TextEncoder().encode("tampered");
  envelope.receiptPayload.response_body_bytes = envelope.rawBody.byteLength;

  await assert.rejects(
    () => store.complete("reservation-1", envelope, T0 + 500),
    (error) => expectPolicyError(error, "replay_raw_body_hash_mismatch"),
  );
  assert.equal(storage.data.get(AUTHORIZATION_STATE_KEY).reservations["reservation-1"].status, "reserved");
  assert.equal(storage.data.has(`${RESPONSE_KEY_PREFIX}reservation-1`), false);
});

test("body mayor al límite se rechaza antes de persistir evidencia", async () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  store.reserve(request(), T0 + 100);
  const rawBody = new Uint8Array(MAX_REPLAY_BODY_BYTES + 1);
  const hash = await sha256Hex(rawBody);
  const envelope = {
    reservationId: "reservation-1",
    evidenceId: "evidence-1",
    rawBody,
    rawResponseSha256: hash,
    responseStatus: 200,
    receiptPayload: {
      reservation_id: "reservation-1",
      raw_response_sha256: hash,
      response_status: 200,
      response_body_bytes: rawBody.byteLength,
    },
    signatureB64Url: "s".repeat(86),
    signingKeyId: "edge-key-001",
  };
  await assert.rejects(
    () => store.complete("reservation-1", envelope, T0 + 500),
    (error) => expectPolicyError(error, "replay_body_above_limit"),
  );
  assert.equal(storage.data.get(AUTHORIZATION_STATE_KEY).reservations["reservation-1"].status, "reserved");
});

test("corrupción de replay persistido falla cerrado", async () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  store.reserve(request(), T0 + 100);
  const envelope = await replayEnvelope();
  await store.complete("reservation-1", envelope, T0 + 500);
  const key = `${RESPONSE_KEY_PREFIX}reservation-1`;
  storage.data.get(key).rawBody = new TextEncoder().encode("corrupt");

  assert.throws(
    () => store.reserve(request(), T0 + 5000),
    (error) => expectPolicyError(error, "completed_replay_evidence_missing_or_corrupt"),
  );
});

test("fallo de storage revierte la transacción completa", () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  storage.failNextPut = true;
  assert.throws(() => store.reserve(request(), T0 + 100), /synthetic_storage_failure/u);
  const persisted = storage.data.get(AUTHORIZATION_STATE_KEY);
  assert.equal(persisted.requestsUsed, 0);
  assert.equal(Object.keys(persisted.reservations).length, 0);
});

test("fail persiste rechazo terminal y no guarda replay body", () => {
  const storage = new FakeStorage();
  const store = new DurableAuthorizationStore(storage);
  store.initialize(config());
  store.reserve(request(), T0 + 100);
  const failed = store.fail("reservation-1", "origin_http_429", T0 + 500);
  assert.equal(failed.state, "rejected");
  assert.equal(storage.data.has(`${RESPONSE_KEY_PREFIX}reservation-1`), false);
});
