import {
  CONTROLLED_PROBE_ORIGIN_PATH,
  CONTROLLED_PROBE_PURPOSE,
} from "./probe-policy.mjs";

const JSON_HEADERS = Object.freeze({
  "cache-control": "no-store",
  "content-type": "application/json; charset=utf-8",
  "x-content-type-options": "nosniff",
});
const CHALLENGE_RE = /^[A-Za-z0-9._:-]{8,256}$/u;

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: JSON_HEADERS });
}

export default {
  async fetch(request) {
    if (!(request instanceof Request)) return json({ ok: false, error: "request_invalid" }, 400);
    if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);

    const url = new URL(request.url);
    if (url.pathname !== CONTROLLED_PROBE_ORIGIN_PATH || url.search !== "" || url.hash !== "") {
      return json({ ok: false, error: "route_not_found" }, 404);
    }

    const challenge = request.headers.get("x-precios-sps-probe-challenge");
    if (typeof challenge !== "string" || !CHALLENGE_RE.test(challenge)) {
      return json({ ok: false, error: "challenge_invalid" }, 400);
    }

    return json({
      ok: true,
      purpose: CONTROLLED_PROBE_PURPOSE,
      challenge,
    });
  },
};
