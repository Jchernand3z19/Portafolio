import { DurableObject, tracing } from "cloudflare:workers";

import {
  createCatalogContextPublicWorkerHandler,
} from "./catalog-context-worker-adapter.mjs";
import { runCatalogContextExecuteOperation } from "./catalog-context-operation.mjs";
import { EdgePolicyError } from "./core.mjs";
import { DurableAuthorizationStore } from "./durable-store.mjs";
import { assertPublicFrontDoor } from "./front-door.mjs";
import { assertGitHubRunFence } from "./github-run-fence.mjs";
import { runSupervisedExecuteOperation } from "./gateway-supervisor.mjs";
import { createJwksFetchGate } from "./jwks-fetch-gate.mjs";
import { validateReceiptKeyPair } from "./receipt-key-preflight.mjs";
import {
  annotateStructuralExecutionSpan,
  STRUCTURAL_EXECUTION_SPAN_NAME,
} from "./structural-trace-context.mjs";
import {
  createStructuralPublicWorkerHandler,
  runStructuralExecuteOperation,
} from "./structural-worker-adapter.mjs";
import {
  annotateExecutionSpan,
  ORIGIN_EXECUTION_SPAN_NAME,
} from "./trace-context.mjs";
import {
  createGitHubOidcAuthenticator,
  createPublicWorkerHandler,
  durableErrorEnvelope,
  publicErrorResponse,
  runInitializeOperation,
} from "./worker-adapter.mjs";
import { WORKER_ROUTES } from "./worker-policy.mjs";

const gatedGitHubJwksFetch = createJwksFetchGate({
  fetchImpl: (...args) => fetch(...args),
});
const authenticateGitHub = createGitHubOidcAuthenticator({
  fetchImpl: gatedGitHubJwksFetch,
});

export class AuthorizationGateway extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.store = new DurableAuthorizationStore(ctx.storage);
    this.keyPairReady = null;
  }

  assertNamedAuthorization(authorizationId) {
    if (this.ctx.id.name !== authorizationId) {
      throw new EdgePolicyError("durable_object_name_mismatch");
    }
  }

  async ensureKeyPairReady() {
    if (!this.keyPairReady) {
      this.keyPairReady = validateReceiptKeyPair(this.env).catch((error) => {
        this.keyPairReady = null;
        throw error;
      });
    }
    return this.keyPairReady;
  }

  async initialize(input) {
    try {
      this.assertNamedAuthorization(input?.authorization?.authorizationId);
      assertGitHubRunFence(input?.claims, input?.authorization?.runId);
      return runInitializeOperation(this.store, input.authorization, input.claims);
    } catch (error) {
      return durableErrorEnvelope(error);
    }
  }

  async execute(input) {
    try {
      this.assertNamedAuthorization(input?.execution?.requestContext?.authorizationId);
      assertGitHubRunFence(input?.claims, input?.execution?.requestContext?.runId);
      await this.ensureKeyPairReady();
      return await tracing.enterSpan(ORIGIN_EXECUTION_SPAN_NAME, async (span) => {
        annotateExecutionSpan(span, input.execution);
        return runSupervisedExecuteOperation(
          this.store,
          input.execution,
          input.claims,
          this.env,
          { fetchOrigin: (...args) => fetch(...args) },
        );
      });
    } catch (error) {
      return durableErrorEnvelope(error);
    }
  }

  async catalogExecute(input) {
    try {
      this.assertNamedAuthorization(input?.execution?.requestContext?.authorizationId);
      assertGitHubRunFence(input?.claims, input?.execution?.requestContext?.runId);
      await this.ensureKeyPairReady();
      return await tracing.enterSpan(ORIGIN_EXECUTION_SPAN_NAME, async (span) => {
        // La traza común sólo serializa requestContext seguro; nunca locationContext/rawValue.
        annotateExecutionSpan(span, input.execution);
        return runSupervisedExecuteOperation(
          this.store,
          input.execution,
          input.claims,
          this.env,
          { fetchOrigin: (...args) => fetch(...args) },
          runCatalogContextExecuteOperation,
        );
      });
    } catch (error) {
      return durableErrorEnvelope(error);
    }
  }

  async structuralExecute(input) {
    try {
      this.assertNamedAuthorization(input?.execution?.requestContext?.authorizationId);
      assertGitHubRunFence(input?.claims, input?.execution?.requestContext?.runId);
      await this.ensureKeyPairReady();
      return await tracing.enterSpan(STRUCTURAL_EXECUTION_SPAN_NAME, async (span) => {
        annotateStructuralExecutionSpan(span, input.execution);
        return runSupervisedExecuteOperation(
          this.store,
          input.execution,
          input.claims,
          this.env,
          { fetchOrigin: (...args) => fetch(...args) },
          runStructuralExecuteOperation,
        );
      });
    } catch (error) {
      return durableErrorEnvelope(error);
    }
  }
}

export default {
  async fetch(request, env) {
    try {
      assertPublicFrontDoor(request);
    } catch (error) {
      return publicErrorResponse(error);
    }
    const path = new URL(request.url).pathname;
    if (path === WORKER_ROUTES.catalogExecute) {
      const handler = createCatalogContextPublicWorkerHandler({
        namespace: env.AUTHORIZATION_GATEWAY,
        authenticate: authenticateGitHub,
      });
      return handler(request);
    }
    if (path === WORKER_ROUTES.structuralExecute) {
      const handler = createStructuralPublicWorkerHandler({
        namespace: env.AUTHORIZATION_GATEWAY,
        authenticate: authenticateGitHub,
      });
      return handler(request);
    }
    const handler = createPublicWorkerHandler({
      namespace: env.AUTHORIZATION_GATEWAY,
      authenticate: authenticateGitHub,
    });
    return handler(request);
  },
};
