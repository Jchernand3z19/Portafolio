import {
  canonicalJson,
  decodeBase64Url,
  EdgePolicyError,
  encodeBase64Url,
  sha256Hex,
} from "./core.mjs";
import {
  CONTROLLED_PROBE_ORIGIN_PATH,
  CONTROLLED_PROBE_PURPOSE,
  CONTROLLED_PROBE_RECEIPT_SIGNATURE_DOMAIN,
  CONTROLLED_PROBE_SCHEMA_VERSION,
} from "./probe-policy.mjs";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const WORKERS_DEV_HOST_RE = /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.workers\.dev$/u;
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder("utf-8", { fatal: true });

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 1024) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function exactInteger(value, code, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
  return value;
}

function exactObject(value, expectedKeys, code) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  const actual = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) fail(code);
  return value;
}

function receiptSigningBytes(payload) {
  return textEncoder.encode(`${CONTROLLED_PROBE_RECEIPT_SIGNATURE_DOMAIN}${canonicalJson(payload)}`);
}

export function validateControlledProbeOriginUrl(rawUrl) {
  const value = exactText(rawUrl, "probe_origin_url_invalid", 4096);
  let baseUrl;
  try {
    baseUrl = new URL(value);
  } catch {
    fail("probe_origin_url_invalid");
  }
  if (baseUrl.protocol !== "https:") fail("probe_origin_scheme_invalid");
  if (baseUrl.port !== "") fail("probe_origin_port_forbidden");
  if (baseUrl.username || baseUrl.password) fail("probe_origin_credentials_forbidden");
  if (baseUrl.search !== "") fail("probe_origin_query_forbidden");
  if (baseUrl.hash !== "") fail("probe_origin_fragment_forbidden");
  if (baseUrl.pathname !== "/" && baseUrl.pathname !== CONTROLLED_PROBE_ORIGIN_PATH) {
    fail("probe_origin_path_invalid");
  }
  if (!WORKERS_DEV_HOST_RE.test(baseUrl.hostname)) fail("probe_origin_host_not_workers_dev");
  if (baseUrl.hostname === "www.lacolonia.com" || baseUrl.hostname.endsWith(".lacolonia.com")) {
    fail("probe_origin_lacolonia_forbidden");
  }
  const requestUrl = new URL(CONTROLLED_PROBE_ORIGIN_PATH, baseUrl.origin);
  return Object.freeze({
    url: requestUrl.toString(),
    targetHost: baseUrl.hostname,
    targetPath: CONTROLLED_PROBE_ORIGIN_PATH,
  });
}

export async function buildControlledProbeRequest({ originUrl, probeId, challenge }) {
  const origin = validateControlledProbeOriginUrl(originUrl);
  const normalizedProbeId = exactText(probeId, "probe_id_invalid", 128);
  const normalizedChallenge = exactText(challenge, "probe_challenge_invalid", 256);
  const canonicalRequest = Object.freeze({
    challenge: normalizedChallenge,
    method: "GET",
    probe_id: normalizedProbeId,
    purpose: CONTROLLED_PROBE_PURPOSE,
    target_host: origin.targetHost,
    target_path: origin.targetPath,
    target_scheme: "https",
  });
  return Object.freeze({
    origin,
    probeId: normalizedProbeId,
    challenge: normalizedChallenge,
    canonicalRequest,
    canonicalRequestSha256: await sha256Hex(canonicalJson(canonicalRequest)),
  });
}

export function verifyControlledProbeOriginPayload(rawBody, expectedChallenge) {
  if (!(rawBody instanceof Uint8Array) || rawBody.byteLength === 0) fail("probe_origin_body_invalid");
  let parsed;
  try {
    parsed = JSON.parse(textDecoder.decode(rawBody));
  } catch {
    fail("probe_origin_json_invalid");
  }
  exactObject(parsed, ["challenge", "ok", "purpose"], "probe_origin_payload_shape_invalid");
  if (parsed.ok !== true) fail("probe_origin_not_ok");
  if (parsed.purpose !== CONTROLLED_PROBE_PURPOSE) fail("probe_origin_purpose_mismatch");
  if (parsed.challenge !== exactText(expectedChallenge, "probe_challenge_invalid", 256)) {
    fail("probe_origin_challenge_mismatch");
  }
  return Object.freeze({ ...parsed });
}

export function buildControlledProbeReceiptPayload({
  probeRequest,
  claims,
  collectorReleaseId,
  durableObjectName,
  physicalStartedAt,
  responseCompletedAt,
  responseStatus,
  rawResponseSha256,
  responseBodyBytes,
  signingKeyId,
}) {
  if (!probeRequest || typeof probeRequest !== "object") fail("probe_request_missing");
  if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("probe_oidc_claims_missing");
  const approvedCommitSha = exactText(claims.sha, "probe_oidc_sha_invalid", 40);
  if (!SHA1_RE.test(approvedCommitSha)) fail("probe_oidc_sha_invalid");
  const rawHash = exactText(rawResponseSha256, "probe_raw_response_sha256_invalid", 64);
  if (!SHA256_RE.test(rawHash)) fail("probe_raw_response_sha256_invalid");

  const payload = {
    approved_commit_sha: approvedCommitSha,
    canonical_request_sha256: exactText(
      probeRequest.canonicalRequestSha256,
      "probe_request_digest_invalid",
      64,
    ),
    collector_provider: "cloudflare_workers",
    collector_principal: "cloudflare-worker:precios-sps-controlled-probe",
    collector_release_id: exactText(collectorReleaseId, "probe_collector_release_id_invalid", 256),
    durable_object_name: exactText(durableObjectName, "probe_durable_object_name_invalid", 256),
    github_environment: exactText(claims.environment, "probe_oidc_environment_invalid", 256),
    github_ref: exactText(claims.ref, "probe_oidc_ref_invalid", 512),
    github_repository: exactText(claims.repository, "probe_oidc_repository_invalid", 512),
    github_repository_id: exactText(claims.repository_id, "probe_oidc_repository_id_invalid", 64),
    github_run_attempt: exactInteger(Number(claims.run_attempt), "probe_oidc_run_attempt_invalid", 1, 100),
    github_run_id: exactText(claims.run_id, "probe_oidc_run_id_invalid", 64),
    github_workflow_ref: exactText(claims.workflow_ref, "probe_oidc_workflow_ref_invalid", 1024),
    oidc_jti: exactText(claims.jti, "probe_oidc_jti_invalid", 256),
    oidc_subject: exactText(claims.sub, "probe_oidc_subject_invalid", 1024),
    physical_started_at_utc: exactText(physicalStartedAt, "probe_physical_started_at_invalid", 64),
    probe_id: exactText(probeRequest.probeId, "probe_id_invalid", 128),
    purpose: CONTROLLED_PROBE_PURPOSE,
    raw_response_sha256: rawHash,
    response_body_bytes: exactInteger(responseBodyBytes, "probe_response_body_bytes_invalid", 1),
    response_completed_at_utc: exactText(responseCompletedAt, "probe_response_completed_at_invalid", 64),
    response_status: exactInteger(responseStatus, "probe_response_status_invalid", 100, 599),
    schema_version: CONTROLLED_PROBE_SCHEMA_VERSION,
    signing_algorithm: "Ed25519",
    signing_key_id: exactText(signingKeyId, "probe_signing_key_id_invalid", 256),
    target_host: exactText(probeRequest.origin?.targetHost, "probe_target_host_invalid", 512),
    target_path: exactText(probeRequest.origin?.targetPath, "probe_target_path_invalid", 1024),
    target_scheme: "https",
  };
  canonicalJson(payload);
  return Object.freeze(payload);
}

export async function signControlledProbeReceipt(payload, privateKeyPkcs8B64Url) {
  const key = await crypto.subtle.importKey(
    "pkcs8",
    decodeBase64Url(privateKeyPkcs8B64Url),
    { name: "Ed25519" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("Ed25519", key, receiptSigningBytes(payload));
  return encodeBase64Url(new Uint8Array(signature));
}

export async function verifyControlledProbeReceipt(payload, signatureB64Url, publicKeySpkiB64Url) {
  const key = await crypto.subtle.importKey(
    "spki",
    decodeBase64Url(publicKeySpkiB64Url),
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  return crypto.subtle.verify(
    "Ed25519",
    key,
    decodeBase64Url(signatureB64Url),
    receiptSigningBytes(payload),
  );
}
