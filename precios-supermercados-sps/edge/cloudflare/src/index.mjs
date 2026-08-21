import { DurableObject } from "cloudflare:workers";

import { EdgePolicyError } from "./core.mjs";
import { DurableAuthorizationStore } from "./durable-store.mjs";
import { assertPublicFrontDoor } from "./front-door.mjs";
import { assertGitHubRunFence } from "./github-run-fence.mjs";
import { runSupervisedExecuteOperation } from "./gateway-supervisor.mjs";
import { createJwksFetchGate } from "./jwks-fetch-gate.mjs";
import { validateReceiptKeyPair } from "./receipt-key-preflight.mjs";
import {
  createGitHubOidcAuthenticator,
  createPublicWorkerHandler,
  durableErrorEnvelope,
  publicErrorResponse,
  runInitializeOperation,
} from "./worker-adapter.mjs";

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
      return await runSupervisedExecuteOperation(
        this.store,
        input.execution,
        input.claims,
        this.env,
        { fetchOrigin: (...args) => fetch(...args) },
      );
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
    const handler = createPublicWorkerHandler({
      namespace: env.AUTHORIZATION_GATEWAY,
      authenticate: authenticateGitHub,
    });
    return handler(request);
  },
};
