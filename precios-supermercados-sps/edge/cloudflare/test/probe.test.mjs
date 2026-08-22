import assert from "node:assert/strict";
import test from "node:test";

import {
  EdgePolicyError,
  encodeBase64Url,
  validateLaColoniaGetUrl,
  verifyReceiptSignature,
} from "../src/core.mjs";
import {
  buildControlledProbeReceiptPayload,
  buildControlledProbeRequest,
  signControlledProbeReceipt,
  validateControlledProbeOriginUrl,
  verifyControlledProbeOriginPayload,
  verifyControlledProbeReceipt,
} from "../src/probe-core.mjs";
import { createControlledProbePublicHandler } from "../src/probe-adapter.mjs";
import { createControlledProbeOidcAuthenticator } from "../src/probe-oidc.mjs";
import {
  CONTROLLED_PROBE_PURPOSE,
  CONTROLLED_PROBE_WORKER_POLICY,
} from "../src/probe-policy.mjs";
import { runControlledOriginProbe } from "../src/probe-runtime.mjs";
import { FIXED_GRAPHQL_QUERY_SHA256 } from "../src/worker-policy.mjs";

const ORIGIN_URL = "https://precios-sps-controlled-origin.example-account.workers.dev/v1/probe-origin";
const SHA = "a".repeat(40);
const NOW_MS = 2_000_000_000_000;
const NOW_SECONDS = Math.floor(NOW_MS / 1000);

function claims(overrides = {}) {
  return {
    iss: "https://token.actions.githubusercontent.com",
    aud: CONTROLLED_PROBE_WORKER_POLICY.audience,
    sub: CONTROLLED_PROBE_WORKER_POLICY.subject,
    repository: CONTROLLED_PROBE_WORKER_POLICY.repository,
    repository_id: CONTROLLED_PROBE_WORKER_POLICY.repositoryId,
    ref: CONTROLLED_PROBE_WORKER_POLICY.ref,
    workflow_ref: CONTROLLED_PROBE_WORKER_POLICY.workflowRef,
    environment: CONTROLLED_PROBE_WORKER_POLICY.environment,
    event_name: CONTROLLED_PROBE_WORKER_POLICY.eventName,
    sha: SHA,
    run_id: "32550000000",
    run_attempt: "1",
    jti: "probe-jti-001",
    iat: NOW_SECONDS - 10,
    nbf: NOW_SECONDS - 10,
    exp: NOW_SECONDS + 290,
    ...overrides,
  };
}

async function ed25519Keys() {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  return {
    privateKey: encodeBase64Url(new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey))),
    publicKey: encodeBase64Url(new Uint8Array(await crypto.subtle.exportKey("spki", pair.publicKey))),
  };
}

function publicRequest(body, token = "synthetic.jwt.token") {
  return new Request("https://probe.example/v1/probe", {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

test("sonda acepta únicamente origen workers.dev exacto y nunca La Colonia", async () => {
  const accepted = validateControlledProbeOriginUrl(ORIGIN_URL);
  assert.equal(accepted.targetHost, "precios-sps-controlled-origin.example-account.workers.dev");
  assert.equal(accepted.targetPath, "/v1/probe-origin");

  for (const value of [
    "https://www.lacolonia.com/v1/probe-origin",
    "https://precios-sps-controlled-origin.example-account.workers.dev/v1/probe-origin?target=lacolonia",
    "https://example.com/v1/probe-origin",
    "http://precios-sps-controlled-origin.example-account.workers.dev/v1/probe-origin",
  ]) {
    assert.throws(() => validateControlledProbeOriginUrl(value), EdgePolicyError);
  }

  await assert.rejects(
    validateLaColoniaGetUrl(ORIGIN_URL, { expectedGraphqlQuerySha256: FIXED_GRAPHQL_QUERY_SHA256 }),
    (error) => error instanceof EdgePolicyError && error.code === "origin_host_mismatch",
  );
});

test("payload del origen debe ecoar exactamente propósito y challenge", () => {
  const challenge = "probe-challenge-001";
  const raw = new TextEncoder().encode(JSON.stringify({ ok: true, purpose: CONTROLLED_PROBE_PURPOSE, challenge }));
  assert.equal(verifyControlledProbeOriginPayload(raw, challenge).challenge, challenge);
  const tampered = new TextEncoder().encode(JSON.stringify({ ok: true, purpose: CONTROLLED_PROBE_PURPOSE, challenge: "other" }));
  assert.throws(
    () => verifyControlledProbeOriginPayload(tampered, challenge),
    (error) => error instanceof EdgePolicyError && error.code === "probe_origin_challenge_mismatch",
  );
});

test("firma de sonda usa dominio criptográfico distinto al recibo productivo", async () => {
  const keys = await ed25519Keys();
  const probeRequest = await buildControlledProbeRequest({
    originUrl: ORIGIN_URL,
    probeId: "probe-001",
    challenge: "probe-challenge-001",
  });
  const payload = buildControlledProbeReceiptPayload({
    probeRequest,
    claims: claims(),
    collectorReleaseId: "cf-probe-version-001",
    durableObjectName: "github-run:32550000000:1",
    physicalStartedAt: "2033-05-18T03:33:20.000Z",
    responseCompletedAt: "2033-05-18T03:33:21.000Z",
    responseStatus: 200,
    rawResponseSha256: "b".repeat(64),
    responseBodyBytes: 64,
    signingKeyId: "cloudflare-probe-ed25519-v1",
  });
  const signature = await signControlledProbeReceipt(payload, keys.privateKey);
  assert.equal(await verifyControlledProbeReceipt(payload, signature, keys.publicKey), true);
  assert.equal(await verifyReceiptSignature(payload, signature, keys.publicKey), false);
  assert.equal(payload.schema_version, "probe-1");
  assert.equal(payload.purpose, CONTROLLED_PROBE_PURPOSE);
  assert.notEqual(payload.target_host, "www.lacolonia.com");
});

test("runtime obtiene el destino sólo del binding y cierra evidencia completa", async () => {
  const keys = await ed25519Keys();
  const seen = [];
  const times = [new Date(NOW_MS), new Date(NOW_MS + 125)];
  const result = await runControlledOriginProbe(
    {
      probeId: "probe-runtime-001",
      approvedCommitSha: SHA,
      claims: claims(),
      durableObjectName: "github-run:32550000000:1",
    },
    {
      PROBE_ORIGIN_URL: ORIGIN_URL,
      PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL: keys.privateKey,
      PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL: keys.publicKey,
      CF_VERSION_METADATA: { id: "cf-probe-version-runtime" },
    },
    {
      randomUUID: () => "runtime-challenge-001",
      clock: () => times.shift() ?? new Date(NOW_MS + 125),
      fetchOrigin: async (url, init) => {
        seen.push([url, init]);
        return new Response(JSON.stringify({
          ok: true,
          purpose: CONTROLLED_PROBE_PURPOSE,
          challenge: init.headers["x-precios-sps-probe-challenge"],
        }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    },
  );
  assert.equal(result.ok, true);
  assert.equal(result.decision, "PROBE_COMPLETED");
  assert.equal(result.replayed, false);
  assert.equal(result.receiptPayload.collector_release_id, "cf-probe-version-runtime");
  assert.equal(result.receiptPayload.target_host, "precios-sps-controlled-origin.example-account.workers.dev");
  assert.equal(seen.length, 1);
  assert.equal(seen[0][0], ORIGIN_URL);
  assert.equal(seen[0][1].redirect, "manual");
});

test("runtime jamás hace fetch si el binding intenta apuntar a La Colonia", async () => {
  const keys = await ed25519Keys();
  let fetchCalls = 0;
  await assert.rejects(
    runControlledOriginProbe(
      {
        probeId: "probe-runtime-deny",
        approvedCommitSha: SHA,
        claims: claims(),
        durableObjectName: "github-run:32550000000:1",
      },
      {
        PROBE_ORIGIN_URL: "https://www.lacolonia.com/v1/probe-origin",
        PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL: keys.privateKey,
        PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL: keys.publicKey,
        CF_VERSION_METADATA: { id: "cf-probe-version-runtime" },
      },
      {
        randomUUID: () => "runtime-challenge-deny",
        clock: () => new Date(NOW_MS),
        fetchOrigin: async () => {
          fetchCalls += 1;
          throw new Error("fetch must not run");
        },
      },
    ),
    EdgePolicyError,
  );
  assert.equal(fetchCalls, 0);
});

test("front door no permite que caller inyecte originUrl ni nombre de Durable Object", async () => {
  const calls = [];
  let authCalls = 0;
  const namespace = {
    getByName(name) {
      calls.push(["getByName", name]);
      return {
        async execute(input) {
          calls.push(["execute", input]);
          return { ok: true, decision: "PROBE_COMPLETED", replayed: false };
        },
      };
    },
  };
  const authenticate = async (_token, commitSha) => {
    authCalls += 1;
    assert.equal(commitSha, SHA);
    return { claims: claims() };
  };
  const handler = createControlledProbePublicHandler({ namespace, authenticate });

  const injected = await handler(publicRequest({
    probeId: "probe-adapter-injected",
    approvedCommitSha: SHA,
    originUrl: "https://www.lacolonia.com/",
  }));
  assert.equal(injected.status, 400);
  assert.equal((await injected.json()).error, "probe_body_shape_invalid");
  assert.equal(authCalls, 0);
  assert.equal(calls.length, 0);

  const ok = await handler(publicRequest({ probeId: "probe-adapter-ok", approvedCommitSha: SHA }));
  assert.equal(ok.status, 200);
  assert.equal(authCalls, 1);
  assert.deepEqual(calls[0], ["getByName", "github-run:32550000000:1"]);
  assert.equal(calls[1][0], "execute");
  assert.deepEqual(Object.keys(calls[1][1]).sort(), ["approvedCommitSha", "claims", "probeId"]);
});

test("OIDC de sonda acepta sólo workflow/environment/audience de sonda", async () => {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  Object.assign(jwk, { kid: "probe-kid", alg: "RS256", use: "sig" });
  const b64Json = (value) => encodeBase64Url(new TextEncoder().encode(JSON.stringify(value)));
  async function makeToken(claimOverrides = {}) {
    const header = { alg: "RS256", typ: "JWT", kid: "probe-kid" };
    const input = `${b64Json(header)}.${b64Json(claims(claimOverrides))}`;
    const signature = await crypto.subtle.sign(
      "RSASSA-PKCS1-v1_5",
      pair.privateKey,
      new TextEncoder().encode(input),
    );
    return `${input}.${encodeBase64Url(new Uint8Array(signature))}`;
  }

  let fetchCalls = 0;
  const authenticate = createControlledProbeOidcAuthenticator({
    clock: () => new Date(NOW_MS),
    fetchImpl: async () => {
      fetchCalls += 1;
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
  assert.equal((await authenticate(await makeToken(), SHA)).claims.environment, "cloudflare-probe");
  await assert.rejects(
    authenticate(await makeToken({ environment: "la-colonia-live" }), SHA),
    (error) => error instanceof EdgePolicyError && error.code === "jwt_environment_mismatch",
  );
  assert.equal(fetchCalls, 1);
});
