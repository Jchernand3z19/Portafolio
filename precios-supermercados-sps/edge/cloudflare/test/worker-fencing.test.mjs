import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError, encodeBase64Url } from "../src/core.mjs";
import { assertGitHubRunFence, githubRunFenceKey } from "../src/github-run-fence.mjs";
import { validateReceiptKeyPair } from "../src/receipt-key-preflight.mjs";

function expectPolicyError(error, code) {
  assert.ok(error instanceof EdgePolicyError);
  assert.equal(error.code, code);
  return true;
}

async function keyPairEnv() {
  const pair = await crypto.subtle.generateKey("Ed25519", true, ["sign", "verify"]);
  const privatePkcs8 = await crypto.subtle.exportKey("pkcs8", pair.privateKey);
  const publicSpki = await crypto.subtle.exportKey("spki", pair.publicKey);
  return {
    EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL: encodeBase64Url(new Uint8Array(privatePkcs8)),
    EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL: encodeBase64Url(new Uint8Array(publicSpki)),
  };
}

test("fence usa run_id y run_attempt exactos del OIDC", () => {
  const claims = { run_id: "32510000000", run_attempt: "2" };
  assert.equal(githubRunFenceKey(claims), "32510000000:2");
  assert.equal(assertGitHubRunFence(claims, "32510000000:2"), "32510000000:2");
});

test("otro workflow run o rerun no puede reutilizar la autorización", () => {
  assert.throws(
    () => assertGitHubRunFence({ run_id: "32510000000", run_attempt: "1" }, "32510000001:1"),
    (error) => expectPolicyError(error, "github_run_fence_mismatch"),
  );
  assert.throws(
    () => assertGitHubRunFence({ run_id: "32510000000", run_attempt: "2" }, "32510000000:1"),
    (error) => expectPolicyError(error, "github_run_fence_mismatch"),
  );
});

test("run_id OIDC malformado falla cerrado", () => {
  for (const claims of [
    { run_id: "run-1", run_attempt: "1" },
    { run_id: "0", run_attempt: "1" },
    { run_id: "32510000000", run_attempt: "0" },
    { run_id: "32510000000", run_attempt: "101" },
  ]) {
    assert.throws(() => githubRunFenceKey(claims), EdgePolicyError);
  }
});

test("par Ed25519 válido se comprueba antes de habilitar tráfico", async () => {
  const env = await keyPairEnv();
  assert.equal(await validateReceiptKeyPair(env), true);
});

test("clave pública de otro par se rechaza antes del fetch", async () => {
  const env = await keyPairEnv();
  const other = await keyPairEnv();
  await assert.rejects(
    validateReceiptKeyPair({
      ...env,
      EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL: other.EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL,
    }),
    (error) => expectPolicyError(error, "receipt_key_pair_mismatch"),
  );
});

test("clave privada malformada falla como configuración, no después de reservar", async () => {
  const env = await keyPairEnv();
  await assert.rejects(
    validateReceiptKeyPair({
      ...env,
      EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL: "invalid-private-key-material",
    }),
    (error) => expectPolicyError(error, "receipt_key_pair_invalid"),
  );
});
