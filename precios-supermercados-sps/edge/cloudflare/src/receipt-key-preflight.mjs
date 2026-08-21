import {
  EdgePolicyError,
  signReceiptPayload,
  verifyReceiptSignature,
} from "./core.mjs";

const PROBE_PAYLOAD = Object.freeze({
  purpose: "precios-sps-edge-key-pair-preflight",
  schema_version: "1",
});

function fail(code) {
  throw new EdgePolicyError(code);
}

function secret(env, key) {
  const value = env?.[key];
  if (typeof value !== "string" || value.length < 16 || value.trim() !== value || /\s/u.test(value)) {
    fail(`binding_${key.toLowerCase()}_invalid`);
  }
  return value;
}

export async function validateReceiptKeyPair(env) {
  const privateKey = secret(env, "EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL");
  const publicKey = secret(env, "EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL");
  try {
    const signature = await signReceiptPayload(PROBE_PAYLOAD, privateKey);
    const valid = await verifyReceiptSignature(PROBE_PAYLOAD, signature, publicKey);
    if (valid !== true) fail("receipt_key_pair_mismatch");
  } catch (error) {
    if (error instanceof EdgePolicyError) throw error;
    fail("receipt_key_pair_invalid");
  }
  return true;
}
