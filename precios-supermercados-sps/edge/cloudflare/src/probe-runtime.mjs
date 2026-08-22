import {
  canonicalJson,
  EdgePolicyError,
  encodeBase64Url,
  sha256Hex,
} from "./core.mjs";
import { canonicalEdgeTimestamp } from "./canonical-time.mjs";
import {
  buildControlledProbeReceiptPayload,
  buildControlledProbeRequest,
  signControlledProbeReceipt,
  verifyControlledProbeOriginPayload,
  verifyControlledProbeReceipt,
} from "./probe-core.mjs";
import {
  CONTROLLED_PROBE_MAX_BODY_BYTES,
  CONTROLLED_PROBE_PURPOSE,
  CONTROLLED_PROBE_RECEIPT_SIGNATURE_DOMAIN,
  CONTROLLED_PROBE_SIGNING_KEY_ID,
  CONTROLLED_PROBE_WORKER_POLICY,
} from "./probe-policy.mjs";

const B64URL_RE = /^[A-Za-z0-9_-]+$/u;

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 1024) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function requiredBinding(env, key, max = 20_000) {
  return exactText(env?.[key], `binding_${key.toLowerCase()}_missing`, max);
}

function clockDate(clock) {
  const value = clock();
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) fail("probe_clock_invalid");
  return value;
}

function validateClaims(claims, approvedCommitSha) {
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("probe_oidc_claims_missing");
  const expected = {
    repository: CONTROLLED_PROBE_WORKER_POLICY.repository,
    repository_id: CONTROLLED_PROBE_WORKER_POLICY.repositoryId,
    ref: CONTROLLED_PROBE_WORKER_POLICY.ref,
    workflow_ref: CONTROLLED_PROBE_WORKER_POLICY.workflowRef,
    environment: CONTROLLED_PROBE_WORKER_POLICY.environment,
    event_name: CONTROLLED_PROBE_WORKER_POLICY.eventName,
    sub: CONTROLLED_PROBE_WORKER_POLICY.subject,
    sha: approvedCommitSha,
  };
  for (const [key, value] of Object.entries(expected)) {
    if (claims[key] !== value) fail(`probe_oidc_${key}_mismatch`);
  }
  exactText(claims.run_id, "probe_oidc_run_id_invalid", 64);
  exactText(claims.jti, "probe_oidc_jti_invalid", 256);
  const attempt = Number(claims.run_attempt);
  if (!Number.isSafeInteger(attempt) || attempt < 1 || attempt > 100) fail("probe_oidc_run_attempt_invalid");
  return claims;
}

async function readBodyLimited(response) {
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0) fail("probe_origin_content_length_invalid");
    if (parsed > CONTROLLED_PROBE_MAX_BODY_BYTES) fail("probe_origin_body_above_limit");
  }
  if (!response.body || typeof response.body.getReader !== "function") fail("probe_origin_body_missing");
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) fail("probe_origin_body_chunk_invalid");
      total += value.byteLength;
      if (total > CONTROLLED_PROBE_MAX_BODY_BYTES) {
        try {
          await reader.cancel("body_above_limit");
        } catch {
          // best effort
        }
        fail("probe_origin_body_above_limit");
      }
      chunks.push(value);
    }
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail("probe_origin_body_read_failed");
  }
  if (total === 0) fail("probe_origin_body_empty");
  const rawBody = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    rawBody.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return rawBody;
}

export async function runControlledOriginProbe(input, env, dependencies) {
  if (!input || typeof input !== "object" || Array.isArray(input)) fail("probe_input_invalid");
  if (!dependencies || typeof dependencies !== "object" || Array.isArray(dependencies)) fail("probe_dependencies_invalid");
  if (typeof dependencies.fetchOrigin !== "function") fail("probe_fetch_missing");
  if (typeof dependencies.clock !== "function") fail("probe_clock_missing");
  if (typeof dependencies.randomUUID !== "function") fail("probe_random_uuid_missing");

  const probeId = exactText(input.probeId, "probe_id_invalid", 128);
  const approvedCommitSha = exactText(input.approvedCommitSha, "approved_commit_sha_invalid", 40);
  if (!/^[0-9a-f]{40}$/u.test(approvedCommitSha)) fail("approved_commit_sha_invalid");
  const claims = validateClaims(input.claims, approvedCommitSha);
  const durableObjectName = exactText(input.durableObjectName, "probe_durable_object_name_invalid", 256);

  const originUrl = requiredBinding(env, "PROBE_ORIGIN_URL", 4096);
  const privateKey = requiredBinding(env, "PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL");
  const publicKey = requiredBinding(env, "PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL");
  const collectorReleaseId = exactText(env?.CF_VERSION_METADATA?.id, "binding_cf_version_metadata_missing", 256);
  const challenge = exactText(dependencies.randomUUID(), "probe_challenge_invalid", 256);
  const probeRequest = await buildControlledProbeRequest({ originUrl, probeId, challenge });

  const physicalStartedAt = clockDate(dependencies.clock);
  let response;
  try {
    response = await dependencies.fetchOrigin(probeRequest.origin.url, {
      method: "GET",
      redirect: "manual",
      headers: Object.freeze({
        accept: "application/json",
        "x-precios-sps-probe-challenge": challenge,
      }),
    });
  } catch {
    fail("probe_origin_transport_error");
  }
  if (!(response instanceof Response)) fail("probe_origin_response_invalid");
  if (response.redirected || (response.status >= 300 && response.status <= 399) || response.headers.has("location")) {
    fail("probe_origin_redirect");
  }
  if (response.status !== 200) fail(`probe_origin_http_${response.status}`);
  const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
  if (!contentType.includes("application/json")) fail("probe_origin_content_type_invalid");

  const rawBody = await readBodyLimited(response);
  verifyControlledProbeOriginPayload(rawBody, challenge);
  const rawResponseSha256 = await sha256Hex(rawBody);
  const responseCompletedAt = clockDate(dependencies.clock);
  if (responseCompletedAt.getTime() < physicalStartedAt.getTime()) fail("probe_response_clock_precedes_start");

  const receiptPayload = buildControlledProbeReceiptPayload({
    probeRequest,
    claims,
    collectorReleaseId,
    durableObjectName,
    physicalStartedAt: canonicalEdgeTimestamp(physicalStartedAt),
    responseCompletedAt: canonicalEdgeTimestamp(responseCompletedAt),
    responseStatus: response.status,
    rawResponseSha256,
    responseBodyBytes: rawBody.byteLength,
    signingKeyId: CONTROLLED_PROBE_SIGNING_KEY_ID,
  });
  const signatureB64Url = await signControlledProbeReceipt(receiptPayload, privateKey);
  if (signatureB64Url.length < 40 || !B64URL_RE.test(signatureB64Url)) fail("probe_receipt_signature_invalid");
  if (!(await verifyControlledProbeReceipt(receiptPayload, signatureB64Url, publicKey))) {
    fail("probe_receipt_signature_verification_failed");
  }

  const evidenceId = await sha256Hex(
    `${CONTROLLED_PROBE_RECEIPT_SIGNATURE_DOMAIN}${canonicalJson(receiptPayload)}\0${signatureB64Url}`,
  );
  return Object.freeze({
    ok: true,
    decision: "PROBE_COMPLETED",
    replayed: false,
    purpose: CONTROLLED_PROBE_PURPOSE,
    rawBodyB64Url: encodeBase64Url(rawBody),
    receiptPayload,
    signatureB64Url,
    signingKeyId: CONTROLLED_PROBE_SIGNING_KEY_ID,
    evidenceId,
  });
}
