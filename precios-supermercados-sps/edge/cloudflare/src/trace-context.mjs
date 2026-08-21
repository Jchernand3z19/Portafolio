import { EdgePolicyError } from "./core.mjs";

export const ORIGIN_EXECUTION_SPAN_NAME = "precios_sps_origin_execution";
export const TRACE_CONTRACT_VERSION = "1";

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

export function executionTraceAttributes(execution) {
  const context = execution?.requestContext;
  if (!context || typeof context !== "object" || Array.isArray(context)) fail("trace_request_context_invalid");
  return Object.freeze({
    "precios.trace_contract_version": TRACE_CONTRACT_VERSION,
    "precios.collector_provider": "cloudflare_workers",
    "precios.authorization_id": exactText(context.authorizationId, "trace_authorization_id_invalid", 256),
    "precios.run_id": exactText(context.runId, "trace_run_id_invalid", 256),
    "precios.approved_commit_sha": exactText(context.approvedCommitSha, "trace_commit_sha_invalid", 40),
    "precios.reservation_id": exactText(context.reservationId, "trace_reservation_id_invalid", 256),
    "precios.request_id": exactText(context.requestId, "trace_request_id_invalid", 256),
    "precios.request_digest": exactText(context.requestDigest, "trace_request_digest_invalid", 64),
    "precios.traversal_role": exactText(context.traversalRole, "trace_traversal_role_invalid", 32),
    "precios.traversal_id": exactText(context.traversalId, "trace_traversal_id_invalid", 256),
    "precios.partition_id": exactText(context.partitionId, "trace_partition_id_invalid", 256),
  });
}

export function annotateExecutionSpan(span, execution) {
  if (!span || typeof span.setAttribute !== "function") fail("trace_span_invalid");
  if (span.isTraced !== true) fail("origin_trace_not_sampled");
  const attributes = executionTraceAttributes(execution);
  for (const [key, value] of Object.entries(attributes)) span.setAttribute(key, value);
  return attributes;
}
