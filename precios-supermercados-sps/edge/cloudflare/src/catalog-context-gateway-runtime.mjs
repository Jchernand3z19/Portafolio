import {
  buildReceiptPayload,
  canonicalJson,
  EdgePolicyError,
  sha256Hex,
  validateLaColoniaGetUrl,
} from "./core.mjs";
import { canonicalEdgeTimestamp } from "./canonical-time.mjs";
import { MAX_REPLAY_BODY_BYTES } from "./durable-store.mjs";
import { validateAndApplyCatalogLocationContext } from "./catalog-location-context.mjs";
import { buildContextBoundCatalogReceiptPayload } from "./catalog-context-provenance.mjs";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const B64URL_RE = /^[A-Za-z0-9_-]+$/u;
const ROLE_SET = new Set(["primary", "reconciliation"]);

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 1024) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function exactContext(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) fail("catalog_gateway_context_invalid");
  const context = {
    authorizationId: exactText(input.authorizationId, "authorization_id_invalid", 256),
    runId: exactText(input.runId, "run_id_invalid", 256),
    approvedCommitSha: exactText(input.approvedCommitSha, "approved_commit_sha_invalid", 40),
    reservationId: exactText(input.reservationId, "reservation_id_invalid", 256),
    requestId: exactText(input.requestId, "request_id_invalid", 256),
    requestDigest: exactText(input.requestDigest, "request_digest_invalid", 64),
    nonce: exactText(input.nonce, "nonce_invalid", 256),
    traversalRole: input.traversalRole,
    traversalId: exactText(input.traversalId, "traversal_id_invalid", 256),
    partitionId: exactText(input.partitionId, "partition_id_invalid", 256),
  };
  if (!SHA1_RE.test(context.approvedCommitSha)) fail("approved_commit_sha_invalid");
  if (!SHA256_RE.test(context.requestDigest)) fail("request_digest_invalid");
  if (!ROLE_SET.has(context.traversalRole)) fail("traversal_role_invalid");
  return Object.freeze(context);
}

function validateCollector(collector) {
  if (!collector || typeof collector !== "object" || Array.isArray(collector)) fail("collector_config_invalid");
  const normalized = {
    principal: exactText(collector.principal, "collector_principal_invalid", 256),
    releaseId: exactText(collector.releaseId, "collector_release_id_invalid", 256),
    codeSha256: exactText(collector.codeSha256, "collector_code_sha_invalid", 64),
    signingKeyId: exactText(collector.signingKeyId, "collector_signing_key_id_invalid", 256),
  };
  if (!SHA256_RE.test(normalized.codeSha256)) fail("collector_code_sha_invalid");
  return Object.freeze(normalized);
}

function validateClaims(claims, context) {
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("oidc_claims_missing");
  if (claims.sha !== context.approvedCommitSha) fail("oidc_commit_context_mismatch");
  for (const key of [
    "repository",
    "repository_id",
    "ref",
    "workflow_ref",
    "environment",
    "run_id",
    "sub",
    "jti",
  ]) exactText(claims[key], `oidc_${key}_missing`, key === "sub" ? 1024 : 512);
  const attempt = Number(claims.run_attempt);
  if (!Number.isSafeInteger(attempt) || attempt < 1 || attempt > 100) fail("oidc_run_attempt_invalid");
  if (`${claims.run_id}:${attempt}` !== context.runId) fail("oidc_run_context_mismatch");
  return Object.freeze({ ...claims, run_attempt: attempt });
}

function clockDate(clock, code = "catalog_gateway_clock_invalid") {
  const value = clock();
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) fail(code);
  return value;
}

async function readBodyLimited(response, maxBytes) {
  if (!response.body || typeof response.body.getReader !== "function") fail("origin_body_missing");
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0) fail("origin_content_length_invalid");
    if (parsed > maxBytes) fail("origin_body_above_limit");
  }
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) fail("origin_body_chunk_invalid");
      total += value.byteLength;
      if (total > maxBytes) {
        try { await reader.cancel("body_above_limit"); } catch { /* best effort */ }
        fail("origin_body_above_limit");
      }
      chunks.push(value);
    }
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail("origin_body_read_failed");
  }
  if (total === 0) fail("origin_body_empty");
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

function noFetchResult(reservation) {
  if (reservation.decision === "WAIT") {
    return Object.freeze({
      decision: "WAIT",
      reason: reservation.reason,
      notBeforeMs: reservation.notBeforeMs ?? null,
      inFlightReservationId: reservation.inFlightReservationId ?? null,
    });
  }
  if (reservation.decision === "DENY") return Object.freeze({ decision: "DENY", reason: reservation.reason });
  if (reservation.decision === "REPLAY_IN_FLIGHT") return Object.freeze({ decision: "WAIT", reason: "reservation_in_flight" });
  if (reservation.decision === "REPLAY_FAILED") return Object.freeze({ decision: "DENY", reason: "reservation_failed" });
  fail("reservation_decision_unexpected");
}

function replayResult(envelope) {
  return Object.freeze({
    decision: "REPLAY_COMPLETED",
    replayed: true,
    status: envelope.responseStatus,
    rawBody: envelope.rawBody,
    receiptPayload: envelope.receiptPayload,
    signatureB64Url: envelope.signatureB64Url,
    signingKeyId: envelope.signingKeyId,
    evidenceId: envelope.evidenceId,
  });
}

function assertReceiptLocation(payload, expectedLocation) {
  if (!payload || payload.schema_version !== "3") fail("replay_catalog_location_context_missing");
  const expected = expectedLocation.receiptContext;
  const pairs = [
    ["location_id", expected.locationId],
    ["binding_source_key", expected.bindingSourceKey],
    ["binding_evidence", expected.bindingEvidence],
    ["context_fingerprint", expected.contextFingerprint],
    ["context_placement", expected.contextPlacement],
    ["context_wire_key", expected.contextWireKey],
    ["wire_request_fingerprint", expected.wireRequestFingerprint],
  ];
  for (const [key, value] of pairs) if (payload[key] !== value) fail(`replay_catalog_${key}_mismatch`);
  if (!Array.isArray(payload.context_value_path) || payload.context_value_path.length !== 0) fail("replay_catalog_context_value_path_mismatch");
}

async function verifyReplayEnvelope(envelope, context, expectedLocation, verifyReceipt) {
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) fail("replay_envelope_invalid");
  if (!(envelope.rawBody instanceof Uint8Array)) fail("replay_raw_body_invalid");
  if (envelope.rawBody.byteLength === 0 || envelope.rawBody.byteLength > MAX_REPLAY_BODY_BYTES) fail("replay_raw_body_invalid");
  const bodyHash = await sha256Hex(envelope.rawBody);
  const payload = envelope.receiptPayload;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) fail("replay_receipt_invalid");
  if (payload.request_digest !== context.requestDigest) fail("replay_request_digest_mismatch");
  if (payload.reservation_id !== context.reservationId) fail("replay_receipt_reservation_mismatch");
  if (payload.raw_response_sha256 !== bodyHash) fail("replay_receipt_hash_mismatch");
  if (payload.response_body_bytes !== envelope.rawBody.byteLength) fail("replay_receipt_size_mismatch");
  if (payload.response_status !== envelope.responseStatus || envelope.responseStatus !== 200) fail("replay_receipt_status_mismatch");
  if (payload.signing_key_id !== envelope.signingKeyId) fail("replay_signing_key_mismatch");
  assertReceiptLocation(payload, expectedLocation);
  let valid = false;
  try {
    valid = await verifyReceipt(payload, envelope.signatureB64Url, envelope.signingKeyId);
  } catch {
    fail("replay_signature_verification_failed");
  }
  if (valid !== true) fail("replay_signature_invalid");
  const evidenceId = await sha256Hex(`${canonicalJson(payload)}\0${envelope.signatureB64Url}`);
  if (evidenceId !== envelope.evidenceId) fail("replay_evidence_id_mismatch");
  return replayResult(envelope);
}

export async function executeContextBoundCatalogRequest(input, dependencies) {
  if (!dependencies || typeof dependencies !== "object") fail("catalog_gateway_dependencies_missing");
  const store = dependencies.store;
  if (!store || typeof store.reserve !== "function" || typeof store.complete !== "function" || typeof store.fail !== "function") fail("gateway_store_invalid");
  for (const [name, code] of [
    ["authenticate", "gateway_authenticator_missing"],
    ["fetchOrigin", "gateway_fetch_missing"],
    ["signReceipt", "gateway_signer_missing"],
    ["verifyReceipt", "gateway_verifier_missing"],
    ["clock", "gateway_clock_missing"],
    ["executionId", "gateway_execution_id_missing"],
  ]) if (typeof dependencies[name] !== "function") fail(code);

  const context = exactContext(input?.requestContext);
  const collector = validateCollector(input?.collector);
  const origin = await validateLaColoniaGetUrl(input?.originUrl, {
    expectedGraphqlQuerySha256: input?.expectedGraphqlQuerySha256,
  });
  if (context.requestDigest !== origin.canonicalRequestSha256) fail("request_digest_origin_mismatch");
  if (!input?.locationContext) fail("catalog_location_context_required");
  const appliedLocation = await validateAndApplyCatalogLocationContext(
    origin.url,
    input.locationContext,
  );

  const identity = await dependencies.authenticate(input?.authorizationToken);
  const claims = validateClaims(identity?.claims, context);
  const beforeReserve = clockDate(dependencies.clock);
  const reserved = store.reserve(context, beforeReserve.getTime());
  if (reserved.decision === "REPLAY_COMPLETED") {
    return verifyReplayEnvelope(
      reserved.replayEnvelope,
      context,
      appliedLocation,
      dependencies.verifyReceipt,
    );
  }
  if (reserved.decision !== "RESERVED") return noFetchResult(reserved);

  const physicalStartedAt = clockDate(dependencies.clock);
  if (physicalStartedAt.getTime() < reserved.reservation.physicalStartMs) {
    try {
      store.fail(context.reservationId, "physical_clock_precedes_reservation", physicalStartedAt.getTime());
    } catch { /* preserve primary error */ }
    fail("physical_clock_precedes_reservation");
  }

  const fetchHeaders = {
    accept: "application/json",
    ...appliedLocation.fetchHeaders,
  };
  let response;
  try {
    response = await dependencies.fetchOrigin(appliedLocation.fetchUrl, {
      method: "GET",
      redirect: "manual",
      headers: Object.freeze(fetchHeaders),
    });
  } catch {
    store.fail(context.reservationId, "origin_transport_error", Math.max(clockDate(dependencies.clock).getTime(), physicalStartedAt.getTime()));
    fail("origin_transport_error");
  }
  if (!(response instanceof Response)) {
    store.fail(context.reservationId, "origin_response_invalid", physicalStartedAt.getTime());
    fail("origin_response_invalid");
  }
  if (response.redirected || (response.status >= 300 && response.status <= 399) || response.headers.has("location")) {
    store.fail(context.reservationId, "origin_redirect", Math.max(clockDate(dependencies.clock).getTime(), physicalStartedAt.getTime()));
    fail("origin_redirect");
  }
  if (response.status !== 200) {
    const reason = `origin_http_${response.status}`;
    store.fail(context.reservationId, reason, Math.max(clockDate(dependencies.clock).getTime(), physicalStartedAt.getTime()));
    fail(reason);
  }
  const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
  if (!contentType.includes("application/json")) {
    store.fail(context.reservationId, "origin_content_type_invalid", Math.max(clockDate(dependencies.clock).getTime(), physicalStartedAt.getTime()));
    fail("origin_content_type_invalid");
  }

  let rawBody;
  try {
    rawBody = await readBodyLimited(response, MAX_REPLAY_BODY_BYTES);
  } catch (error) {
    const reason = error instanceof EdgePolicyError ? error.code : "origin_body_read_failed";
    store.fail(context.reservationId, reason, Math.max(clockDate(dependencies.clock).getTime(), physicalStartedAt.getTime()));
    throw error;
  }
  const rawResponseSha256 = await sha256Hex(rawBody);
  const responseCompletedAt = clockDate(dependencies.clock);
  if (responseCompletedAt.getTime() < physicalStartedAt.getTime()) {
    store.fail(context.reservationId, "response_clock_precedes_start", physicalStartedAt.getTime());
    fail("response_clock_precedes_start");
  }

  const baseReceipt = buildReceiptPayload({
    requestContext: context,
    origin,
    response,
    oidcClaims: claims,
    collector: {
      ...collector,
      execution: exactText(dependencies.executionId(), "collector_execution_invalid", 256),
    },
    physicalStartedAt: canonicalEdgeTimestamp(physicalStartedAt),
    responseCompletedAt: canonicalEdgeTimestamp(responseCompletedAt),
    rawResponseSha256,
    responseBodyBytes: rawBody.byteLength,
  });
  const receiptPayload = buildContextBoundCatalogReceiptPayload(
    baseReceipt,
    appliedLocation.receiptContext,
  );

  let signatureB64Url;
  try {
    signatureB64Url = await dependencies.signReceipt(receiptPayload);
  } catch {
    store.fail(context.reservationId, "receipt_signature_failed", responseCompletedAt.getTime());
    fail("receipt_signature_failed");
  }
  if (typeof signatureB64Url !== "string" || signatureB64Url.length < 40 || !B64URL_RE.test(signatureB64Url)) {
    store.fail(context.reservationId, "receipt_signature_invalid", responseCompletedAt.getTime());
    fail("receipt_signature_invalid");
  }
  let signatureValid = false;
  try {
    signatureValid = await dependencies.verifyReceipt(
      receiptPayload,
      signatureB64Url,
      collector.signingKeyId,
    );
  } catch {
    store.fail(context.reservationId, "receipt_signature_verification_failed", responseCompletedAt.getTime());
    fail("receipt_signature_verification_failed");
  }
  if (signatureValid !== true) {
    store.fail(context.reservationId, "receipt_signature_verification_failed", responseCompletedAt.getTime());
    fail("receipt_signature_verification_failed");
  }

  const evidenceId = await sha256Hex(`${canonicalJson(receiptPayload)}\0${signatureB64Url}`);
  const replayEnvelope = {
    reservationId: context.reservationId,
    evidenceId,
    rawBody,
    rawResponseSha256,
    responseStatus: response.status,
    receiptPayload,
    signatureB64Url,
    signingKeyId: collector.signingKeyId,
  };
  await store.complete(context.reservationId, replayEnvelope, responseCompletedAt.getTime());
  return Object.freeze({
    decision: "ORIGIN_COMPLETED",
    replayed: false,
    status: response.status,
    rawBody,
    receiptPayload,
    signatureB64Url,
    signingKeyId: collector.signingKeyId,
    evidenceId,
  });
}
