import {
  EdgePolicyError,
  encodeBase64Url,
  signReceiptPayload,
  verifyReceiptSignature,
} from "./core.mjs";
import { executeContextBoundCatalogRequest } from "./catalog-context-gateway-runtime.mjs";
import {
  FIXED_GRAPHQL_QUERY_SHA256,
  RECEIPT_SIGNING_KEY_ID,
} from "./worker-policy.mjs";
import { collectorConfiguration } from "./worker-adapter.mjs";

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactText(value, code, max = 512) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) fail(code);
  return value;
}

function requiredBinding(env, key, max = 20_000) {
  return exactText(env?.[key], `binding_${key.toLowerCase()}_missing`, max);
}

function serializeCatalogResult(result) {
  if (result.decision === "ORIGIN_COMPLETED" || result.decision === "REPLAY_COMPLETED") {
    return Object.freeze({
      ok: true,
      decision: result.decision,
      replayed: result.replayed,
      responseStatus: result.status,
      rawBodyB64Url: encodeBase64Url(result.rawBody),
      receiptPayload: result.receiptPayload,
      signatureB64Url: result.signatureB64Url,
      signingKeyId: result.signingKeyId,
      evidenceId: result.evidenceId,
    });
  }
  if (result.decision === "WAIT") {
    return Object.freeze({
      ok: true,
      decision: "WAIT",
      reason: result.reason,
      notBeforeMs: result.notBeforeMs ?? null,
      inFlightReservationId: result.inFlightReservationId ?? null,
    });
  }
  if (result.decision === "DENY") return Object.freeze({ ok: true, decision: "DENY", reason: result.reason });
  fail("catalog_gateway_result_unexpected");
}

export async function runCatalogContextExecuteOperation(
  store,
  execution,
  claims,
  env,
  { fetchOrigin, clock = () => new Date(), randomUUID = () => crypto.randomUUID() },
) {
  if (typeof fetchOrigin !== "function") fail("origin_fetch_missing");
  const collector = collectorConfiguration(env);
  const signingMaterial = requiredBinding(env, "EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL");
  const verificationMaterial = requiredBinding(env, "EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL");
  const result = await executeContextBoundCatalogRequest(
    {
      authorizationToken: "verified-by-worker-router",
      originUrl: execution.originUrl,
      requestContext: execution.requestContext,
      locationContext: execution.locationContext,
      collector,
      expectedGraphqlQuerySha256: FIXED_GRAPHQL_QUERY_SHA256,
    },
    {
      store,
      authenticate: async () => ({ claims }),
      fetchOrigin,
      signReceipt: (payload) => signReceiptPayload(payload, signingMaterial),
      verifyReceipt: async (payload, signature, keyId) => (
        keyId === RECEIPT_SIGNING_KEY_ID
        && verifyReceiptSignature(payload, signature, verificationMaterial)
      ),
      clock,
      executionId: () => exactText(randomUUID(), "collector_execution_invalid", 256),
    },
  );
  return serializeCatalogResult(result);
}
