import { EdgePolicyError, sha256Hex } from "./core.mjs";
import { MAX_REPLAY_BODY_BYTES } from "./durable-store.mjs";
import {
  buildStructuralReceiptPayload,
  structuralReceiptDigest,
} from "./structural-provenance.mjs";
import { validateLaColoniaStructuralGetUrl } from "./structural-request.mjs";
import { STRUCTURAL_GRAPHQL_QUERY_SHA256_BY_KIND } from "./worker-policy.mjs";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const B64URL_RE = /^[A-Za-z0-9_-]+$/u;
const REQUEST_KINDS = new Set(["root_total", "category_tree"]);
const STRUCTURAL_LEDGER_TRAVERSAL_ID = "structural-discovery";

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 1024) {
  if (
    typeof value !== "string"
    || value.length === 0
    || value.trim() !== value
    || value.length > max
    || /\s/u.test(value)
  ) fail(code);
  return value;
}

function exactContext(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    fail("structural_gateway_context_invalid");
  }
  const requestKind = exactText(input.requestKind, "structural_request_kind_invalid", 64);
  if (!REQUEST_KINDS.has(requestKind)) fail("structural_request_kind_invalid");
  const context = {
    authorizationId: exactText(input.authorizationId, "authorization_id_invalid", 128),
    runId: exactText(input.runId, "run_id_invalid", 256),
    approvedCommitSha: exactText(input.approvedCommitSha, "approved_commit_sha_invalid", 40),
    reservationId: exactText(input.reservationId, "reservation_id_invalid", 256),
    requestId: exactText(input.requestId, "request_id_invalid", 256),
    requestDigest: exactText(input.requestDigest, "request_digest_invalid", 64),
    nonce: exactText(input.nonce, "nonce_invalid", 256),
    requestKind,
  };
  if (!SHA1_RE.test(context.approvedCommitSha)) fail("approved_commit_sha_invalid");
  if (!SHA256_RE.test(context.requestDigest)) fail("request_digest_invalid");
  return Object.freeze(context);
}

function ledgerContext(context) {
  // El ledger existente comparte presupuesto/single-flight/pacing con catálogo.
  // Estos tres campos son etiquetas internas de reserva, no semántica de traversal.
  return Object.freeze({
    authorizationId: context.authorizationId,
    runId: context.runId,
    approvedCommitSha: context.approvedCommitSha,
    reservationId: context.reservationId,
    requestId: context.requestId,
    requestDigest: context.requestDigest,
    nonce: context.nonce,
    traversalRole: "primary",
    traversalId: STRUCTURAL_LEDGER_TRAVERSAL_ID,
    partitionId: `structural:${context.requestKind}`,
  });
}

function validateCollector(collector) {
  if (!collector || typeof collector !== "object" || Array.isArray(collector)) {
    fail("collector_config_invalid");
  }
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
  ]) {
    exactText(claims[key], `oidc_${key}_missing`, key === "sub" ? 1024 : 512);
  }
  const attempt = Number(claims.run_attempt);
  if (!Number.isSafeInteger(attempt) || attempt < 1 || attempt > 100) {
    fail("oidc_run_attempt_invalid");
  }
  if (`${claims.run_id}:${attempt}` !== context.runId) fail("oidc_run_context_mismatch");
  return Object.freeze({ ...claims, run_attempt: attempt });
}

function clockDate(clock, code = "structural_gateway_clock_invalid") {
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
        try {
          await reader.cancel("body_above_limit");
        } catch {
          // best effort
        }
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
  if (reservation.decision === "DENY") {
    return Object.freeze({ decision: "DENY", reason: reservation.reason });
  }
  if (reservation.decision === "REPLAY_IN_FLIGHT") {
    return Object.freeze({ decision: "WAIT", reason: "reservation_in_flight" });
  }
  if (reservation.decision === "REPLAY_FAILED") {
    return Object.freeze({ decision: "DENY", reason: "reservation_failed" });
  }
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

async function verifyReplayEnvelope(envelope, context, verifyReceipt) {
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) fail("replay_envelope_invalid");
  if (!(envelope.rawBody instanceof Uint8Array)) fail("replay_raw_body_invalid");
  if (envelope.rawBody.byteLength === 0 || envelope.rawBody.byteLength > MAX_REPLAY_BODY_BYTES) {
    fail("replay_raw_body_invalid");
  }
  const bodyHash = await sha256Hex(envelope.rawBody);
  const payload = envelope.receiptPayload;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) fail("replay_receipt_invalid");
  if (payload.request_kind !== context.requestKind) fail("replay_structural_kind_mismatch");
  if (payload.request_digest !== context.requestDigest) fail("replay_request_digest_mismatch");
  if (payload.reservation_id !== context.reservationId) fail("replay_receipt_reservation_mismatch");
  if (payload.raw_response_sha256 !== bodyHash) fail("replay_receipt_hash_mismatch");
  if (payload.response_body_bytes !== envelope.rawBody.byteLength) fail("replay_receipt_size_mismatch");
  if (payload.response_status !== envelope.responseStatus || envelope.responseStatus !== 200) {
    fail("replay_receipt_status_mismatch");
  }
  if (payload.signing_key_id !== envelope.signingKeyId) fail("replay_signing_key_mismatch");
  let valid = false;
  try {
    valid = await verifyReceipt(payload, envelope.signatureB64Url, envelope.signingKeyId);
  } catch {
    fail("replay_signature_verification_failed");
  }
  if (valid !== true) fail("replay_signature_invalid");
  const evidenceId = await structuralReceiptDigest(payload, envelope.signatureB64Url);
  if (evidenceId !== envelope.evidenceId) fail("replay_evidence_id_mismatch");
  return replayResult(envelope);
}

export async function executeStructuralGatewayRequest(input, dependencies) {
  if (!dependencies || typeof dependencies !== "object") fail("structural_gateway_dependencies_missing");
  const store = dependencies.store;
  if (!store || typeof store.reserve !== "function" || typeof store.complete !== "function" || typeof store.fail !== "function") {
    fail("gateway_store_invalid");
  }
  for (const [name, code] of [
    ["authenticate", "gateway_authenticator_missing"],
    ["fetchOrigin", "gateway_fetch_missing"],
    ["signReceipt", "gateway_signer_missing"],
    ["verifyReceipt", "gateway_verifier_missing"],
    ["clock", "gateway_clock_missing"],
    ["executionId", "gateway_execution_id_missing"],
  ]) {
    if (typeof dependencies[name] !== "function") fail(code);
  }

  const context = exactContext(input?.requestContext);
  const collector = validateCollector(input?.collector);
  const origin = await validateLaColoniaStructuralGetUrl(input?.originUrl, {
    expectedQuerySha256ByKind: STRUCTURAL_GRAPHQL_QUERY_SHA256_BY_KIND,
  });
  if (origin.requestKind !== context.requestKind) fail("structural_request_kind_origin_mismatch");
  if (origin.canonicalRequestSha256 !== context.requestDigest) fail("request_digest_origin_mismatch");

  const identity = await dependencies.authenticate(input?.authorizationToken);
  const claims = validateClaims(identity?.claims, context);
  const reservationContext = ledgerContext(context);
  const beforeReserve = clockDate(dependencies.clock);
  const reserved = store.reserve(reservationContext, beforeReserve.getTime());
  if (reserved.decision === "REPLAY_COMPLETED") {
    return verifyReplayEnvelope(reserved.replayEnvelope, context, dependencies.verifyReceipt);
  }
  if (reserved.decision !== "RESERVED") return noFetchResult(reserved);

  const physicalStartedAt = clockDate(dependencies.clock);
  if (physicalStartedAt.getTime() < reserved.reservation.physicalStartMs) {
    try {
      store.fail(context.reservationId, "physical_clock_precedes_reservation", physicalStartedAt.getTime());
    } catch {
      // preserve primary error
    }
    fail("physical_clock_precedes_reservation");
  }

  let response;
  try {
    response = await dependencies.fetchOrigin(origin.url, {
      method: "GET",
      redirect: "manual",
      headers: Object.freeze({ accept: "application/json" }),
    });
  } catch {
    store.fail(
      context.reservationId,
      "origin_transport_error",
      Math.max(clockDate(dependencies.clock).getTime(), physicalStartedAt.getTime()),
    );
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

  const receiptPayload = buildStructuralReceiptPayload({
    runId: context.runId,
    requestKind: context.requestKind,
    requestId: context.requestId,
    reservationId: context.reservationId,
    authorizationId: context.authorizationId,
    approvedCommitSha: context.approvedCommitSha,
    requestDigest: context.requestDigest,
    canonicalRequestSha256: origin.canonicalRequestSha256,
    graphqlQuerySha256: STRUCTURAL_GRAPHQL_QUERY_SHA256_BY_KIND[context.requestKind],
    httpMethod: "GET",
    targetScheme: "https",
    targetHost: "www.lacolonia.com",
    targetPath: "/_v/segment/graphql/v1",
    rawResponseSha256,
    responseStatus: response.status,
    responseBodyBytes: rawBody.byteLength,
    physicalStartedAt,
    responseCompletedAt,
    githubRepository: claims.repository,
    githubRepositoryId: claims.repository_id,
    githubRef: claims.ref,
    githubWorkflowRef: claims.workflow_ref,
    githubEnvironment: claims.environment,
    githubRunId: claims.run_id,
    githubRunAttempt: claims.run_attempt,
    oidcSubject: claims.sub,
    oidcJti: claims.jti,
    collectorProvider: "cloudflare_workers",
    collectorPrincipal: collector.principal,
    collectorExecution: exactText(dependencies.executionId(), "collector_execution_invalid", 256),
    collectorReleaseId: collector.releaseId,
    collectorCodeSha256: collector.codeSha256,
    signingAlgorithm: "Ed25519",
    signingKeyId: collector.signingKeyId,
    nonce: context.nonce,
  });

  let signatureB64Url;
  try {
    signatureB64Url = await dependencies.signReceipt(receiptPayload);
  } catch {
    store.fail(context.reservationId, "receipt_signature_failed", responseCompletedAt.getTime());
    fail("receipt_signature_failed");
  }
  if (typeof signatureB64Url !== "string" || !B64URL_RE.test(signatureB64Url)) {
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

  const evidenceId = await structuralReceiptDigest(receiptPayload, signatureB64Url);
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
