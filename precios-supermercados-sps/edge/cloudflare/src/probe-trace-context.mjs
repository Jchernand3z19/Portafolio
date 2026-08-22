import { EdgePolicyError } from "./core.mjs";
import {
  CONTROLLED_PROBE_PURPOSE,
  CONTROLLED_PROBE_SPAN_NAME,
} from "./probe-policy.mjs";

export const CONTROLLED_PROBE_TRACE_CONTRACT_VERSION = "1";

function fail(code) {
  throw new EdgePolicyError(code);
}

function exactText(value, code, max = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function exactAttempt(value) {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || parsed > 100) fail("probe_trace_run_attempt_invalid");
  return String(parsed);
}

export function controlledProbeTraceAttributes(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) fail("probe_trace_input_invalid");
  return Object.freeze({
    "precios.probe_contract_version": CONTROLLED_PROBE_TRACE_CONTRACT_VERSION,
    "precios.probe_purpose": CONTROLLED_PROBE_PURPOSE,
    "precios.probe_id": exactText(input.probeId, "probe_trace_probe_id_invalid", 128),
    "precios.approved_commit_sha": exactText(
      input.approvedCommitSha,
      "probe_trace_commit_sha_invalid",
      40,
    ),
    "precios.github_run_id": exactText(input.claims?.run_id, "probe_trace_run_id_invalid", 64),
    "precios.github_run_attempt": exactAttempt(input.claims?.run_attempt),
    "precios.target_kind": "controlled_workers_dev_origin",
  });
}

export function annotateControlledProbeSpan(span, input) {
  if (!span || typeof span.setAttribute !== "function") fail("probe_trace_span_invalid");
  if (span.isTraced !== true) fail("probe_trace_not_sampled");
  const attributes = controlledProbeTraceAttributes(input);
  for (const [key, value] of Object.entries(attributes)) span.setAttribute(key, value);
  return attributes;
}

export function assertControlledProbeSpanName(value) {
  if (value !== CONTROLLED_PROBE_SPAN_NAME) fail("probe_trace_span_name_invalid");
  return value;
}
