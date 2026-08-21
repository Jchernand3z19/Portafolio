const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder("utf-8", { fatal: true });

export const EDGE_SCHEMA_VERSION = "2";
export const RECEIPT_SIGNATURE_DOMAIN = "precios-sps/edge-receipt-signature/v2\0";
export const GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com";
export const LA_COLONIA_HOST = "www.lacolonia.com";
export const LA_COLONIA_PATH = "/_v/segment/graphql/v1";
export const MAX_PAGE_SIZE = 50;
export const ALLOWED_ORDER_BY = Object.freeze([
  "OrderByReleaseDateDESC",
  "OrderByNameASC",
  "OrderByNameDESC",
  "OrderByPriceASC",
  "OrderByPriceDESC",
]);

const EXACT_SEARCH_KEYS = Object.freeze([
  "appsEtag",
  "domain",
  "locale",
  "maxAge",
  "operationName",
  "query",
  "variables",
  "workspace",
]);
const EXACT_VARIABLE_KEYS = Object.freeze([
  "from",
  "fullText",
  "hideUnavailableItems",
  "orderBy",
  "query",
  "selectedFacets",
  "skusFilter",
  "to",
]);
const SHA1_RE = /^[0-9a-f]{40}$/;
const SHA256_RE = /^[0-9a-f]{64}$/;
const CATEGORY_KEY_RE = /^category-[1-9][0-9]*$/;

export class EdgePolicyError extends Error {
  constructor(code, message = code) {
    super(message);
    this.name = "EdgePolicyError";
    this.code = code;
  }
}

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function normalizeCanonical(value, path = "$" ) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) fail("canonical_non_finite", `${path} no es finito`);
    if (!Number.isSafeInteger(value)) fail("canonical_non_integer", `${path} debe ser entero seguro`);
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) => normalizeCanonical(item, `${path}[${index}]`));
  }
  if (isPlainObject(value)) {
    const normalized = {};
    for (const key of Object.keys(value).sort()) {
      const item = value[key];
      if (item === undefined) fail("canonical_undefined", `${path}.${key} es undefined`);
      normalized[key] = normalizeCanonical(item, `${path}.${key}`);
    }
    return normalized;
  }
  fail("canonical_unsupported_type", `${path} contiene un tipo no soportado`);
}

export function canonicalJson(value) {
  return JSON.stringify(normalizeCanonical(value));
}

export function canonicalBytes(value) {
  return textEncoder.encode(canonicalJson(value));
}

export function bytesToHex(bytes) {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(value) {
  const bytes = typeof value === "string" ? textEncoder.encode(value) : toUint8Array(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return bytesToHex(new Uint8Array(digest));
}

function toUint8Array(value) {
  if (value instanceof Uint8Array) return value;
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  }
  fail("invalid_bytes", "Se esperaban bytes");
}

export function encodeBase64Url(value) {
  const bytes = toUint8Array(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}

export function decodeBase64Url(value, { allowEmpty = false } = {}) {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    fail("invalid_base64url", "base64url vacío o no textual");
  }
  if (value.includes("=") || !/^[A-Za-z0-9_-]*$/u.test(value)) {
    fail("invalid_base64url", "base64url no canónico");
  }
  const padded = value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4);
  let binary;
  try {
    binary = atob(padded);
  } catch {
    fail("invalid_base64url", "base64url inválido");
  }
  const result = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  if (!allowEmpty && result.byteLength === 0) fail("invalid_base64url", "base64url decodifica vacío");
  if (encodeBase64Url(result) !== value) fail("invalid_base64url", "base64url no canónico");
  return result;
}

function concatBytes(...parts) {
  const normalized = parts.map(toUint8Array);
  const total = normalized.reduce((sum, item) => sum + item.byteLength, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const item of normalized) {
    result.set(item, offset);
    offset += item.byteLength;
  }
  return result;
}

export function receiptSigningBytes(payload) {
  return concatBytes(textEncoder.encode(RECEIPT_SIGNATURE_DOMAIN), canonicalBytes(payload));
}

export async function importEd25519PrivateKeyPkcs8(privateKeyB64Url) {
  return crypto.subtle.importKey(
    "pkcs8",
    decodeBase64Url(privateKeyB64Url),
    { name: "Ed25519" },
    false,
    ["sign"],
  );
}

export async function importEd25519PublicKeySpki(publicKeyB64Url) {
  return crypto.subtle.importKey(
    "spki",
    decodeBase64Url(publicKeyB64Url),
    { name: "Ed25519" },
    false,
    ["verify"],
  );
}

export async function signReceiptPayload(payload, privateKeyB64Url) {
  const key = await importEd25519PrivateKeyPkcs8(privateKeyB64Url);
  const signature = await crypto.subtle.sign("Ed25519", key, receiptSigningBytes(payload));
  return encodeBase64Url(new Uint8Array(signature));
}

export async function verifyReceiptSignature(payload, signatureB64Url, publicKeyB64Url) {
  const key = await importEd25519PublicKeySpki(publicKeyB64Url);
  return crypto.subtle.verify(
    "Ed25519",
    key,
    decodeBase64Url(signatureB64Url),
    receiptSigningBytes(payload),
  );
}

function exactString(value, code, { max = 1024 } = {}) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) {
    fail(code);
  }
  return value;
}

function exactInteger(value, code, { min = 0, max = Number.MAX_SAFE_INTEGER } = {}) {
  if (!Number.isSafeInteger(value) || value < min || value > max) fail(code);
  return value;
}

function exactObjectKeys(value, expected, code) {
  if (!isPlainObject(value)) fail(code);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) fail(code);
}

function assertUniqueSearchParams(searchParams) {
  const seen = new Set();
  for (const [key] of searchParams) {
    if (seen.has(key)) fail("duplicate_query_parameter", `Parámetro repetido: ${key}`);
    seen.add(key);
  }
  const actual = [...seen].sort();
  const expected = [...EXACT_SEARCH_KEYS].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    fail("unexpected_query_parameters");
  }
}

function validateSelectedFacets(value) {
  if (!Array.isArray(value) || value.length > 8) fail("invalid_selected_facets");
  const seen = new Set();
  return value.map((facet) => {
    exactObjectKeys(facet, ["key", "value"], "invalid_selected_facet_shape");
    const key = exactString(facet.key, "invalid_selected_facet_key", { max: 32 });
    const facetValue = exactString(facet.value, "invalid_selected_facet_value", { max: 256 });
    if (!CATEGORY_KEY_RE.test(key)) fail("invalid_selected_facet_key");
    const identity = `${key}\0${facetValue}`;
    if (seen.has(identity)) fail("duplicate_selected_facet");
    seen.add(identity);
    return { key, value: facetValue };
  });
}

export async function validateLaColoniaGetUrl(rawUrl, policy) {
  const urlText = exactString(rawUrl, "invalid_origin_url", { max: 20000 });
  let url;
  try {
    url = new URL(urlText);
  } catch {
    fail("invalid_origin_url");
  }
  if (url.protocol !== "https:") fail("origin_scheme_mismatch");
  if (url.hostname !== LA_COLONIA_HOST) fail("origin_host_mismatch");
  if (url.port !== "") fail("origin_port_forbidden");
  if (url.username || url.password) fail("origin_credentials_forbidden");
  if (url.pathname !== LA_COLONIA_PATH) fail("origin_path_mismatch");
  if (url.hash !== "") fail("origin_fragment_forbidden");

  assertUniqueSearchParams(url.searchParams);
  const fixed = {
    workspace: "master",
    maxAge: "short",
    appsEtag: "remove",
    domain: "store",
    locale: "es-HN",
    operationName: "productSearchV3",
  };
  for (const [key, expected] of Object.entries(fixed)) {
    if (url.searchParams.get(key) !== expected) fail(`origin_${key}_mismatch`);
  }

  const query = url.searchParams.get("query");
  if (typeof query !== "string" || query.length === 0) fail("graphql_query_missing");
  const expectedQuerySha = exactString(policy?.expectedGraphqlQuerySha256, "query_policy_missing", { max: 64 });
  if (!SHA256_RE.test(expectedQuerySha)) fail("query_policy_invalid");
  if (await sha256Hex(query) !== expectedQuerySha) fail("graphql_query_mismatch");

  let variables;
  try {
    variables = JSON.parse(url.searchParams.get("variables"));
  } catch {
    fail("variables_invalid_json");
  }
  exactObjectKeys(variables, EXACT_VARIABLE_KEYS, "variables_shape_mismatch");

  const orderBy = exactString(variables.orderBy, "order_by_invalid", { max: 64 });
  if (!ALLOWED_ORDER_BY.includes(orderBy)) fail("order_by_not_allowed");
  const from = exactInteger(variables.from, "from_invalid");
  const to = exactInteger(variables.to, "to_invalid");
  if (to < from) fail("range_invalid");
  if (to - from + 1 > MAX_PAGE_SIZE) fail("page_size_above_limit");
  if (variables.hideUnavailableItems !== false) fail("hide_unavailable_must_be_false");
  if (variables.skusFilter !== "ALL") fail("skus_filter_must_be_all");

  const fullText = typeof variables.fullText === "string" ? variables.fullText.trim() : fail("full_text_invalid");
  const queryValue = typeof variables.query === "string" ? variables.query.trim() : fail("query_value_invalid");
  const selectedFacets = validateSelectedFacets(variables.selectedFacets);
  if (fullText) {
    if (queryValue !== "" || selectedFacets.length !== 0) fail("full_text_mode_shape_mismatch");
  } else {
    if (queryValue === "" || selectedFacets.length === 0) fail("facet_mode_shape_mismatch");
  }

  const canonicalRequest = {
    method: "GET",
    origin_url: url.toString(),
    target_host: LA_COLONIA_HOST,
    target_path: LA_COLONIA_PATH,
    variables: {
      from,
      fullText,
      hideUnavailableItems: false,
      orderBy,
      query: queryValue,
      selectedFacets,
      skusFilter: "ALL",
      to,
    },
  };

  return Object.freeze({
    url: url.toString(),
    from,
    to,
    orderBy,
    selectedFacets,
    canonicalRequest,
    canonicalRequestSha256: await sha256Hex(canonicalBytes(canonicalRequest)),
  });
}

function parseJwtJsonPart(part, code) {
  try {
    return JSON.parse(textDecoder.decode(decodeBase64Url(part)));
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail(code);
  }
}

export function decodeJwtUnverified(token) {
  const compact = exactString(token, "jwt_missing", { max: 20000 });
  const parts = compact.split(".");
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) fail("jwt_compact_invalid");
  const header = parseJwtJsonPart(parts[0], "jwt_header_invalid");
  const claims = parseJwtJsonPart(parts[1], "jwt_claims_invalid");
  if (!isPlainObject(header) || !isPlainObject(claims)) fail("jwt_json_shape_invalid");
  return { token: compact, parts, header, claims };
}

function audienceMatches(actual, expected) {
  if (typeof actual === "string") return actual === expected;
  return Array.isArray(actual) && actual.length === 1 && actual[0] === expected;
}

function requireClaimString(claims, key, expected, code) {
  if (claims[key] !== expected) fail(code);
}

function selectRsaJwk(jwks, kid) {
  if (!isPlainObject(jwks) || !Array.isArray(jwks.keys)) fail("jwks_invalid");
  const matches = jwks.keys.filter((key) => isPlainObject(key) && key.kid === kid);
  if (matches.length !== 1) fail("jwks_kid_not_unique");
  const jwk = matches[0];
  if (jwk.kty !== "RSA") fail("jwks_kty_invalid");
  if (jwk.alg !== undefined && jwk.alg !== "RS256") fail("jwks_alg_invalid");
  if (jwk.use !== undefined && jwk.use !== "sig") fail("jwks_use_invalid");
  return jwk;
}

export async function verifyGitHubOidcToken(token, jwks, policy, nowSeconds = Math.floor(Date.now() / 1000)) {
  const decoded = decodeJwtUnverified(token);
  const { header, claims, parts } = decoded;
  if (header.alg !== "RS256") fail("jwt_alg_invalid");
  const kid = exactString(header.kid, "jwt_kid_missing", { max: 256 });
  const jwk = selectRsaJwk(jwks, kid);
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const signedBytes = textEncoder.encode(`${parts[0]}.${parts[1]}`);
  const validSignature = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    decodeBase64Url(parts[2]),
    signedBytes,
  );
  if (!validSignature) fail("jwt_signature_invalid");

  const now = exactInteger(nowSeconds, "now_invalid", { min: 1 });
  const skew = exactInteger(policy?.clockSkewSeconds ?? 30, "clock_skew_invalid", { min: 0, max: 120 });
  const maxAge = exactInteger(policy?.maxTokenAgeSeconds ?? 600, "max_token_age_invalid", { min: 60, max: 900 });
  const exp = exactInteger(claims.exp, "jwt_exp_invalid", { min: 1 });
  const nbf = exactInteger(claims.nbf, "jwt_nbf_invalid", { min: 1 });
  const iat = exactInteger(claims.iat, "jwt_iat_invalid", { min: 1 });
  if (exp < now - skew) fail("jwt_expired");
  if (nbf > now + skew) fail("jwt_not_yet_valid");
  if (iat > now + skew) fail("jwt_issued_in_future");
  if (now - iat > maxAge + skew) fail("jwt_too_old");
  if (exp <= iat || exp - iat > maxAge + skew) fail("jwt_lifetime_invalid");

  const expectedAudience = exactString(policy?.audience, "oidc_audience_policy_missing", { max: 256 });
  if (!audienceMatches(claims.aud, expectedAudience)) fail("jwt_audience_mismatch");
  requireClaimString(claims, "iss", GITHUB_OIDC_ISSUER, "jwt_issuer_mismatch");
  requireClaimString(claims, "repository", policy.repository, "jwt_repository_mismatch");
  requireClaimString(claims, "repository_id", policy.repositoryId, "jwt_repository_id_mismatch");
  requireClaimString(claims, "ref", policy.ref, "jwt_ref_mismatch");
  requireClaimString(claims, "workflow_ref", policy.workflowRef, "jwt_workflow_ref_mismatch");
  requireClaimString(claims, "environment", policy.environment, "jwt_environment_mismatch");
  requireClaimString(claims, "event_name", policy.eventName ?? "workflow_dispatch", "jwt_event_mismatch");
  if (policy.sha !== undefined) {
    const expectedSha = exactString(policy.sha, "oidc_sha_policy_invalid", { max: 40 });
    if (!SHA1_RE.test(expectedSha)) fail("oidc_sha_policy_invalid");
    requireClaimString(claims, "sha", expectedSha, "jwt_sha_mismatch");
  } else if (!SHA1_RE.test(claims.sha ?? "")) {
    fail("jwt_sha_invalid");
  }
  if (policy.subject !== undefined) {
    requireClaimString(claims, "sub", policy.subject, "jwt_subject_mismatch");
  } else {
    exactString(claims.sub, "jwt_subject_missing", { max: 1024 });
  }
  exactString(claims.jti, "jwt_jti_missing", { max: 256 });
  exactString(claims.run_id, "jwt_run_id_missing", { max: 64 });
  exactInteger(Number(claims.run_attempt), "jwt_run_attempt_invalid", { min: 1, max: 100 });

  return Object.freeze({ header, claims });
}

export function buildReceiptPayload({
  requestContext,
  origin,
  response,
  oidcClaims,
  collector,
  physicalStartedAt,
  responseCompletedAt,
  rawResponseSha256,
  responseBodyBytes,
}) {
  const payload = {
    approved_commit_sha: oidcClaims.sha,
    authorization_id: requestContext.authorizationId,
    canonical_request_sha256: origin.canonicalRequestSha256,
    collector_code_sha256: collector.codeSha256,
    collector_execution: collector.execution,
    collector_principal: collector.principal,
    collector_provider: "cloudflare_workers",
    collector_release_id: collector.releaseId,
    from_index: origin.from,
    github_environment: oidcClaims.environment,
    github_ref: oidcClaims.ref,
    github_repository: oidcClaims.repository,
    github_repository_id: oidcClaims.repository_id,
    github_run_attempt: Number(oidcClaims.run_attempt),
    github_run_id: oidcClaims.run_id,
    github_workflow_ref: oidcClaims.workflow_ref,
    http_method: "GET",
    nonce: requestContext.nonce,
    oidc_jti: oidcClaims.jti,
    oidc_subject: oidcClaims.sub,
    order_by: origin.orderBy,
    partition_id: requestContext.partitionId,
    physical_started_at_utc: physicalStartedAt,
    raw_response_sha256: rawResponseSha256,
    request_digest: requestContext.requestDigest,
    request_id: requestContext.requestId,
    reservation_id: requestContext.reservationId,
    response_body_bytes: responseBodyBytes,
    response_completed_at_utc: responseCompletedAt,
    response_status: response.status,
    run_id: requestContext.runId,
    schema_version: EDGE_SCHEMA_VERSION,
    signing_algorithm: "Ed25519",
    signing_key_id: collector.signingKeyId,
    target_host: LA_COLONIA_HOST,
    target_path: LA_COLONIA_PATH,
    target_scheme: "https",
    to_index: origin.to,
    traversal_id: requestContext.traversalId,
    traversal_role: requestContext.traversalRole,
  };
  canonicalJson(payload);
  return Object.freeze(payload);
}
