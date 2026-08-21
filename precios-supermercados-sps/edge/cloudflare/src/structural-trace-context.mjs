import { EdgePolicyError } from "./core.mjs";

export const STRUCTURAL_EXECUTION_SPAN_NAME = "precios_sps_structural_execution";
export const STRUCTURAL_TRACE_CONTRACT_VERSION = "1";

const SHA1_RE = /^[0-9a-f]{40}$/u;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const REQUEST_KINDS = new Set(["root_total", "category_tree"]);

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 512) {
  if (
    typeof value !== "string"
    || value.length === 0
    || value.trim() !== value
    || value.length > max
    || /\s/u.test(value)
  ) fail(code);
  return value;
}

function sha1(value, code) {
  const text = exactText(value, code, 40);
  if (!SHA1_RE.test(text)) fail(code);
  return text;
}

function sha256(value, code) {
  const text = exactText(value, code, 64);
  if (!SHA256_RE.test(text)) fail(code);
  return text;
}

function requestKind(value) {
  const text = exactText(value, "structural_trace_request_kind_invalid", 64);
  if (!REQUEST_KINDS.has(text)) fail("structural_trace_request_kind_invalid");
  return text;
}

export function structuralExecutionTraceAttributes(execution) {
  const context = execution?.requestContext;
  if (!context || typeof context !== "object" || Array.isArray(context)) {
    fail("structural_trace_request_context_invalid");
  }
  return Object.freeze({
    "precios.trace_contract_version": STRUCTURAL_TRACE_CONTRACT_VERSION,
    "precios.collector_provider": "cloudflare_workers",
    "precios.authorization_id": exactText(
      context.authorizationId,
      "structural_trace_authorization_id_invalid",
      128,
    ),
    "precios.run_id": exactText(context.runId, "structural_trace_run_id_invalid", 256),
    "precios.approved_commit_sha": sha1(
      context.approvedCommitSha,
      "structural_trace_commit_sha_invalid",
    ),
    "precios.reservation_id": exactText(
      context.reservationId,
      "structural_trace_reservation_id_invalid",
      256,
    ),
    "precios.request_id": exactText(
      context.requestId,
      "structural_trace_request_id_invalid",
      256,
    ),
    "precios.request_digest": sha256(
      context.requestDigest,
      "structural_trace_request_digest_invalid",
    ),
    "precios.request_kind": requestKind(context.requestKind),
  });
}

export function annotateStructuralExecutionSpan(span, execution) {
  if (!span || typeof span.setAttribute !== "function") {
    fail("structural_trace_span_invalid");
  }
  if (span.isTraced !== true) fail("structural_origin_trace_not_sampled");
  const attributes = structuralExecutionTraceAttributes(execution);
  for (const [key, value] of Object.entries(attributes)) span.setAttribute(key, value);
  return attributes;
}
