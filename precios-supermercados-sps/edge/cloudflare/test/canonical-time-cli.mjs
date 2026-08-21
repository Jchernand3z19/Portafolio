import { canonicalEdgeTimestamp } from "../src/canonical-time.mjs";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const payload = JSON.parse(input);
const value = canonicalEdgeTimestamp(new Date(payload.epochMs));
process.stdout.write(JSON.stringify({ value }));
