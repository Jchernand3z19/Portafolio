import { DurableObject } from "cloudflare:workers";

import { EdgePolicyError } from "./core.mjs";
import { DurableAuthorizationStore } from "./durable-store.mjs";
import {
  createGitHubOidcAuthenticator,
  createPublicWorkerHandler,
  durableErrorEnvelope,
  runExecuteOperation,
  runInitializeOperation,
} from "./worker-adapter.mjs";

const authenticateGitHub = createGitHubOidcAuthenticator({
  fetchImpl: (...args) => fetch(...args),
});

export class AuthorizationGateway extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.store = new DurableAuthorizationStore(ctx.storage);
  }

  assertNamedAuthorization(authorizationId) {
    if (this.ctx.id.name !== authorizationId) {
      throw new EdgePolicyError("durable_object_name_mismatch");
    }
  }

  async initialize(input) {
    try {
      this.assertNamedAuthorization(input?.authorization?.authorizationId);
      return runInitializeOperation(this.store, input.authorization, input.claims);
    } catch (error) {
      return durableErrorEnvelope(error);
    }
  }

  async execute(input) {
    try {
      this.assertNamedAuthorization(input?.execution?.requestContext?.authorizationId);
      return await runExecuteOperation(
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
    const handler = createPublicWorkerHandler({
      namespace: env.AUTHORIZATION_GATEWAY,
      authenticate: authenticateGitHub,
    });
    return handler(request);
  },
};
