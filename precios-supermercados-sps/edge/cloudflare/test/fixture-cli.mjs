import { validateLaColoniaGetUrl } from "../src/core.mjs";

let input = "";
for await (const chunk of process.stdin) input += chunk;

try {
  const payload = JSON.parse(input);
  const result = await validateLaColoniaGetUrl(payload.url, {
    expectedGraphqlQuerySha256: payload.expectedGraphqlQuerySha256,
  });
  process.stdout.write(JSON.stringify({
    ok: true,
    from: result.from,
    to: result.to,
    orderBy: result.orderBy,
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
