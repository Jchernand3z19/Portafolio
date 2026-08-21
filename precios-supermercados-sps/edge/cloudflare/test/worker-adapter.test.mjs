import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError, encodeBase64Url } from "../src/core.mjs";
import {
  collectorConfiguration,
  createGitHubOidcAuthenticator,
  createPublicWorkerHandler,
  runExecuteOperation,
} from "../src/worker-adapter.mjs";
import {
  AUTHORIZATION_LIMITS,
  FIXED_GRAPHQL_QUERY_SHA256,
  GITHUB_OIDC_JWKS_URL,
  WORKER_POLICY,
} from "../src/worker-policy.mjs";

const NOW_MS = 2_000_000_000_000;
const NOW_SECONDS = Math.floor(NOW_MS / 1000);
const SHA = "a".repeat(40);

function fixedClaims(overrides = {}) {
  return {
    iss: "https://token.actions.githubusercontent.com",
    aud: WORKER_POLICY.audience,
    sub: WORKER_POLICY.subject,
    repository: WORKER_POLICY.repository,
    repository_id: WORKER_POLICY.repositoryId,
    ref: WORKER_POLICY.ref,
    workflow_ref: WORKER_POLICY.workflowRef,
    environment: WORKER_POLICY.environment,
    event_name: WORKER_POLICY.eventName,
    sha: SHA,
    run_id: "32510000000",
    run_attempt: "1",
    jti: "jti-worker-adapter-001",
    iat: NOW_SECONDS - 10,
    nbf: NOW_SECONDS - 10,
    exp: NOW_SECONDS + 290,
    ...overrides,
  };
}

function initializeBody(overrides = {}) {
  return {
    authorization: {
      authorizationId: "authorization-001",
      runId: "run-001",
      approvedCommitSha: SHA,
      createdAtMs: NOW_MS - 1000,
      expiresAtMs: NOW_MS + 10 * 60 * 1000,
      maxRequests: 25,
      ...overrides,
    },
  };
}

function executeBody(overrides = {}) {
  return {
    originUrl: "https://www.lacolonia.com/not-evaluated-by-router",
    requestContext: {
      authorizationId: "authorization-001",
      runId: "run-001",
      approvedCommitSha: SHA,
      reservationId: "reservation-001",
      requestId: "request-001",
      requestDigest: "b".repeat(64),
      nonce: "nonce-001",
      traversalRole: "primary",
      traversalId: "traversal-primary",
      partitionId: "root",
      ...overrides,
    },
  };
}

function publicRequest(path, body, token = "synthetic.jwt.token") {
  return new Request(`https://collector.example${path}`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

function namespaceHarness() {
  const calls = [];
  const stub = {
    async initialize(input) {
      calls.push(["initialize", input]);
      return { ok: true, decision: "INITIALIZED", authorization: { state: "active" } };
    },
    async execute(input) {
      calls.push(["execute", input]);
      return { ok: true, decision: "WAIT", reason: "pacing_not_elapsed" };
    },
  };
  return {
    calls,
    namespace: {
      getByName(name) {
        calls.push(["getByName", name]);
        return stub;
      },
    },
  };
}

const clock = () => new Date(NOW_MS);
const authenticate = async (_token, commitSha) => {
  assert.equal(commitSha, SHA);
  return { claims: fixedClaims() };
};

test("initialize autentica antes de seleccionar Durable Object y fuerza pacing fijo", async () => {
  const h = namespaceHarness();
  const handler = createPublicWorkerHandler({ namespace: h.namespace, authenticate, clock });
  const response = await handler(publicRequest("/v1/initialize", initializeBody()));
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.ok, true);
  assert.deepEqual(h.calls[0], ["getByName", "authorization-001"]);
  assert.equal(h.calls[1][0], "initialize");
  assert.equal(h.calls[1][1].authorization.minStartIntervalMs, 1500);
});

test("body no puede inyectar hash GraphQL ni campos de política", async () => {
  const h = namespaceHarness();
  let authCalls = 0;
  const handler = createPublicWorkerHandler({
    namespace: h.namespace,
    authenticate: async () => {
      authCalls += 1;
      return { claims: fixedClaims() };
    },
    clock,
  });
  const body = { ...executeBody(), expectedGraphqlQuerySha256: "f".repeat(64) };
  const response = await handler(publicRequest("/v1/execute", body));
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error, "execute_body_shape_invalid");
  assert.equal(authCalls, 0);
  assert.equal(h.calls.length, 0);
});

test("bearer ausente o inválido nunca selecciona Durable Object", async () => {
  const h = namespaceHarness();
  const handler = createPublicWorkerHandler({ namespace: h.namespace, authenticate, clock });
  const request = new Request("https://collector.example/v1/initialize", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(initializeBody()),
  });
  const response = await handler(request);
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error, "bearer_missing");
  assert.equal(h.calls.length, 0);
});

test("fallo OIDC ocurre antes de getByName", async () => {
  const h = namespaceHarness();
  const handler = createPublicWorkerHandler({
    namespace: h.namespace,
    authenticate: async () => {
      throw new EdgePolicyError("jwt_signature_invalid");
    },
    clock,
  });
  const response = await handler(publicRequest("/v1/execute", executeBody()));
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error, "jwt_signature_invalid");
  assert.equal(h.calls.length, 0);
});

test("autorización vieja, futura o vencida falla antes de Durable Object", async () => {
  for (const overrides of [
    { createdAtMs: NOW_MS - AUTHORIZATION_LIMITS.maxLifetimeMs - 1 },
    { createdAtMs: NOW_MS + WORKER_POLICY.clockSkewSeconds * 1000 + 1, expiresAtMs: NOW_MS + 120_000 },
    { expiresAtMs: NOW_MS - WORKER_POLICY.clockSkewSeconds * 1000 - 1 },
  ]) {
    const h = namespaceHarness();
    const handler = createPublicWorkerHandler({ namespace: h.namespace, authenticate, clock });
    const response = await handler(publicRequest("/v1/initialize", initializeBody(overrides)));
    assert.equal(response.status, 400);
    assert.equal(h.calls.length, 0);
  }
});

test("request público limita ruta, query string y método", async () => {
  const h = namespaceHarness();
  const handler = createPublicWorkerHandler({ namespace: h.namespace, authenticate, clock });
  for (const request of [
    publicRequest("/v1/unknown", initializeBody()),
    publicRequest("/v1/initialize?debug=1", initializeBody()),
    new Request("https://collector.example/v1/initialize", { method: "GET" }),
  ]) {
    const response = await handler(request);
    assert.equal(response.status, 400);
  }
  assert.equal(h.calls.length, 0);
});

test("JWKS se obtiene sólo del endpoint fijo y se cachea entre verificaciones", async () => {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  Object.assign(jwk, { kid: "worker-kid", alg: "RS256", use: "sig" });

  const toB64 = (value) => encodeBase64Url(new TextEncoder().encode(JSON.stringify(value)));
  async function token(claimOverrides = {}) {
    const header = { alg: "RS256", typ: "JWT", kid: "worker-kid" };
    const input = `${toB64(header)}.${toB64(fixedClaims(claimOverrides))}`;
    const signature = await crypto.subtle.sign(
      "RSASSA-PKCS1-v1_5",
      pair.privateKey,
      new TextEncoder().encode(input),
    );
    return `${input}.${encodeBase64Url(new Uint8Array(signature))}`;
  }

  const urls = [];
  const oidc = createGitHubOidcAuthenticator({
    clock,
    fetchImpl: async (url, init) => {
      urls.push([url, init]);
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
  assert.equal((await oidc(await token(), SHA)).claims.repository, WORKER_POLICY.repository);
  assert.equal((await oidc(await token({ jti: "jti-worker-adapter-002" }), SHA)).claims.sha, SHA);
  assert.equal(urls.length, 1);
  assert.equal(urls[0][0], GITHUB_OIDC_JWKS_URL);
  assert.equal(urls[0][1].redirect, "error");
});

test("OIDC con repositorio distinto se rechaza aun con firma RSA válida", async () => {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  Object.assign(jwk, { kid: "worker-kid-2", alg: "RS256", use: "sig" });
  const toB64 = (value) => encodeBase64Url(new TextEncoder().encode(JSON.stringify(value)));
  const header = { alg: "RS256", typ: "JWT", kid: "worker-kid-2" };
  const input = `${toB64(header)}.${toB64(fixedClaims({ repository: "attacker/repo" }))}`;
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", pair.privateKey, new TextEncoder().encode(input));
  const jwt = `${input}.${encodeBase64Url(new Uint8Array(signature))}`;
  const oidc = createGitHubOidcAuthenticator({
    clock,
    fetchImpl: async () => new Response(JSON.stringify({ keys: [jwk] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  });
  await assert.rejects(oidc(jwt, SHA), (error) => {
    assert.ok(error instanceof EdgePolicyError);
    assert.equal(error.code, "jwt_repository_mismatch");
    return true;
  });
});

test("collector toma release/code/key del entorno y no del caller", () => {
  const config = collectorConfiguration({
    EDGE_COLLECTOR_CODE_SHA256: "c".repeat(64),
    CF_VERSION_METADATA: { id: "cf-version-001" },
  });
  assert.equal(config.releaseId, "cf-version-001");
  assert.equal(config.codeSha256, "c".repeat(64));
  assert.equal(config.signingKeyId, "cloudflare-ed25519-v1");
  assert.equal(config.principal, "cloudflare-worker:precios-sps-provenance");
});

test("query GraphQL alterada falla por hash fijo antes de reserve o fetch", async () => {
  const tamperedQuery = "query productSearchV3 { productSearch { recordsFiltered } }";
  assert.notEqual(FIXED_GRAPHQL_QUERY_SHA256, await crypto.subtle.digest("SHA-256", new TextEncoder().encode(tamperedQuery)).then((buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("")));
  const variables = {
    query: "supermercado",
    fullText: "",
    selectedFacets: [{ key: "category-1", value: "supermercado" }],
    orderBy: "OrderByNameASC",
    from: 0,
    to: 9,
    hideUnavailableItems: false,
    skusFilter: "ALL",
  };
  const params = new URLSearchParams({
    workspace: "master",
    maxAge: "short",
    appsEtag: "remove",
    domain: "store",
    locale: "es-HN",
    operationName: "productSearchV3",
    query: tamperedQuery,
    variables: JSON.stringify(variables),
  });
  const execution = {
    originUrl: `https://www.lacolonia.com/_v/segment/graphql/v1?${params.toString()}`,
    requestContext: executeBody().requestContext,
  };
  let reserveCalls = 0;
  let fetchCalls = 0;
  const fakeStore = {
    reserve() { reserveCalls += 1; throw new Error("reserve should not run"); },
    complete() {},
    fail() {},
  };
  await assert.rejects(
    runExecuteOperation(
      fakeStore,
      execution,
      fixedClaims(),
      {
        EDGE_COLLECTOR_CODE_SHA256: "c".repeat(64),
        EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL: "synthetic-private-key",
        EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL: "synthetic-public-key",
        CF_VERSION_METADATA: { id: "cf-version-test" },
      },
      {
        clock,
        fetchOrigin: async () => { fetchCalls += 1; return new Response("{}"); },
        randomUUID: () => "execution-test",
      },
    ),
    (error) => {
      assert.ok(error instanceof EdgePolicyError);
      assert.equal(error.code, "graphql_query_mismatch");
      return true;
    },
  );
  assert.equal(reserveCalls, 0);
  assert.equal(fetchCalls, 0);
});
