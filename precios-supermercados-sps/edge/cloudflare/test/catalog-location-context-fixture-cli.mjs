import { validateAndApplyCatalogLocationContext } from "../src/catalog-location-context.mjs";

let input = "";
for await (const chunk of process.stdin) input += chunk;

try {
  const payload = JSON.parse(input);
  const result = await validateAndApplyCatalogLocationContext(
    payload.originUrl,
    payload.locationContext,
  );
  process.stdout.write(JSON.stringify({
    ok: true,
    fetchUrl: result.fetchUrl,
    fetchHeaders: result.fetchHeaders,
    receiptContext: result.receiptContext,
  }));
} catch (error) {
  process.stdout.write(JSON.stringify({
    ok: false,
    error: error?.code ?? "unknown_error",
  }));
  process.exitCode = 1;
}
