import { DurableObject, tracing } from "cloudflare:workers";

import { EdgePolicyError } from "./core.mjs";
import {
  controlledProbePublicErrorResponse,
  createControlledProbePublicHandler,
} from "./probe-adapter.mjs";
import { createJwksFetchGate } from "./jwks-fetch-gate.mjs";
import { createControlledProbeOidcAuthenticator } from "./probe-oidc.mjs";
import {
  CONTROLLED_PROBE_SPAN_NAME,
  CONTROLLED_PROBE_WORKER_POLICY,
} from "./probe-policy.mjs";
import { runControlledOriginProbe } from "./probe-runtime.mjs";

function fail(code) {
  throw new EdgePolicyError(code);
}

function exactProbeId(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u.test(value)) fail("probe_id_invalid");
  return value;
}

function failureCode(error) {
  return error instanceof EdgePolicyError ? error.code : "probe_execution_failed";
}

const gatedGitHubJwksFetch = createJwksFetchGate({
  fetchImpl: (...args) => fetch(...args),
});
const authenticateGitHubProbe = createControlledProbeOidcAuthenticator({
  fetchImpl: gatedGitHubJwksFetch,
});

export class ProbeLedger extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    if (!ctx.storage || typeof ctx.storage.transactionSync !== "function" || !ctx.storage.kv) {
      fail("probe_durable_storage_invalid");
    }
  }

  replayKey(probeId) {
    return `probe:${exactProbeId(probeId)}`;
  }

  assertRunFence(claims) {
    if (!claims || typeof claims !== "object" || Array.isArray(claims)) fail("probe_oidc_claims_missing");
    const runId = claims.run_id;
    const runAttempt = Number(claims.run_attempt);
    if (typeof runId !== "string" || !runId || !Number.isSafeInteger(runAttempt) || runAttempt < 1 || runAttempt > 100) {
      fail("probe_oidc_run_identity_invalid");
    }
    if (claims.environment !== CONTROLLED_PROBE_WORKER_POLICY.environment) fail("probe_oidc_environment_mismatch");
    const expectedName = `github-run:${runId}:${runAttempt}`;
    if (this.ctx.id.name !== expectedName) fail("probe_durable_object_name_mismatch");
    return expectedName;
  }

  async execute(input) {
    const probeId = exactProbeId(input?.probeId);
    const durableObjectName = this.assertRunFence(input?.claims);
    const key = this.replayKey(probeId);

    const existing = this.ctx.storage.transactionSync(() => this.ctx.storage.kv.get(key));
    if (existing?.state === "completed") {
      return Object.freeze({ ...structuredClone(existing.result), replayed: true });
    }
    if (existing?.state === "in_flight") return Object.freeze({ ok: false, error: "probe_replay_in_flight" });
    if (existing?.state === "failed") return Object.freeze({ ok: false, error: "probe_replay_failed" });
    if (existing !== undefined) return Object.freeze({ ok: false, error: "probe_replay_state_invalid" });

    this.ctx.storage.transactionSync(() => {
      if (this.ctx.storage.kv.get(key) !== undefined) fail("probe_replay_race_detected");
      this.ctx.storage.kv.put(key, { state: "in_flight" });
    });

    try {
      const result = await tracing.enterSpan(CONTROLLED_PROBE_SPAN_NAME, async (span) => {
        span.setAttribute("precios_sps.probe_id", probeId);
        span.setAttribute("precios_sps.github_run_id", input.claims.run_id);
        span.setAttribute("precios_sps.github_run_attempt", Number(input.claims.run_attempt));
        span.setAttribute("precios_sps.target_kind", "controlled_workers_dev_origin");
        return runControlledOriginProbe(
          {
            probeId,
            approvedCommitSha: input.approvedCommitSha,
            claims: input.claims,
            durableObjectName,
          },
          this.env,
          {
            fetchOrigin: (...args) => fetch(...args),
            clock: () => new Date(),
            randomUUID: () => crypto.randomUUID(),
          },
        );
      });
      this.ctx.storage.transactionSync(() => {
        const current = this.ctx.storage.kv.get(key);
        if (current?.state !== "in_flight") fail("probe_replay_state_changed");
        this.ctx.storage.kv.put(key, { state: "completed", result: structuredClone(result) });
      });
      return result;
    } catch (error) {
      try {
        this.ctx.storage.transactionSync(() => {
          const current = this.ctx.storage.kv.get(key);
          if (current?.state === "in_flight") {
            this.ctx.storage.kv.put(key, { state: "failed", error: failureCode(error) });
          }
        });
      } catch {
        // Se conserva el error primario y jamás se repite el fetch automáticamente.
      }
      throw error;
    }
  }
}

export default {
  async fetch(request, env) {
    try {
      const handler = createControlledProbePublicHandler({
        namespace: env.PROBE_LEDGER,
        authenticate: authenticateGitHubProbe,
      });
      return handler(request);
    } catch (error) {
      return controlledProbePublicErrorResponse(error);
    }
  },
};
