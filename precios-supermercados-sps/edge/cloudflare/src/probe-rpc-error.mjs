import { EdgePolicyError } from "./core.mjs";

export const CONTROLLED_PROBE_GENERIC_EXECUTION_ERROR = "probe_execution_failed";

export function controlledProbeExecutionFailureCode(error) {
  return error instanceof EdgePolicyError ? error.code : CONTROLLED_PROBE_GENERIC_EXECUTION_ERROR;
}

export function controlledProbeFailureEnvelope(error) {
  return Object.freeze({
    ok: false,
    error: controlledProbeExecutionFailureCode(error),
  });
}
