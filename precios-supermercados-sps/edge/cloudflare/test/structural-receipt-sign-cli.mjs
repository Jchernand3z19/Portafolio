import {
  signStructuralReceipt,
  structuralReceiptDigest,
  verifyStructuralReceipt,
} from "../src/structural-provenance.mjs";

let input = "";
for await (const chunk of process.stdin) input += chunk;

try {
  const payload = JSON.parse(input);
  const signatureB64Url = await signStructuralReceipt(
    payload.receiptPayload,
    payload.privateKeyPkcs8B64Url,
  );
  const verified = await verifyStructuralReceipt(
    payload.receiptPayload,
    signatureB64Url,
    payload.publicKeySpkiB64Url,
  );
  const digest = await structuralReceiptDigest(payload.receiptPayload, signatureB64Url);
  process.stdout.write(JSON.stringify({ ok: true, signatureB64Url, verified, digest }));
} catch (error) {
  process.stdout.write(JSON.stringify({
    ok: false,
    name: error?.name ?? "Error",
    code: error?.code ?? null,
    message: error?.message ?? String(error),
  }));
  process.exitCode = 1;
}
