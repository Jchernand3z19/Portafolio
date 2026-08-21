import { signReceiptPayload } from "../src/core.mjs";

let input = "";
for await (const chunk of process.stdin) input += chunk;

try {
  const payload = JSON.parse(input);
  const signatureB64Url = await signReceiptPayload(
    payload.receiptPayload,
    payload.privateKeyPkcs8B64Url,
  );
  process.stdout.write(JSON.stringify({ ok: true, signatureB64Url }));
} catch (error) {
  process.stdout.write(JSON.stringify({
    ok: false,
    name: error?.name ?? "Error",
    code: error?.code ?? null,
    message: error?.message ?? String(error),
  }));
  process.exitCode = 1;
}
