import { validateLaColoniaStructuralGetUrl } from "../src/structural-request.mjs";

let input = "";
for await (const chunk of process.stdin) input += chunk;

try {
  const payload = JSON.parse(input);
  const result = await validateLaColoniaStructuralGetUrl(payload.url, {
    expectedQuerySha256ByKind: payload.expectedQuerySha256ByKind,
  });
  process.stdout.write(JSON.stringify({
    ok: true,
    requestKind: result.requestKind,
    operationName: result.operationName,
    canonicalRequestSha256: result.canonicalRequestSha256,
  }));
} catch (error) {
  process.stdout.write(JSON.stringify({
    ok: false,
    name: error?.name ?? "Error",
    code: error?.code ?? null,
    message: error?.message ?? String(error),
  }));
  process.exitCode = 1;
}
