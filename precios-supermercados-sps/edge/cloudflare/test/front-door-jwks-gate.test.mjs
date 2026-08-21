import assert from "node:assert/strict";
import test from "node:test";

import { EdgePolicyError } from "../src/core.mjs";
import { assertPublicFrontDoor } from "../src/front-door.mjs";
import { createJwksFetchGate } from "../src/jwks-fetch-gate.mjs";

function expectPolicyError(error, code) {
  assert.ok(error instanceof EdgePolicyError);
  assert.equal(error.code, code);
  return true;
}

function request({
  path = "/v1/execute",
  method = "POST",
  authorization = "Bearer a.b.c",
  contentType = "application/json",
  body = "{}",
  contentLength,
} = {}) {
  const headers = {};
  if (authorization !== null) headers.authorization = authorization;
  if (contentType !== null) headers["content-type"] = contentType;
  if (contentLength !== undefined) headers["content-length"] = String(contentLength);
  return new Request(`https://collector.example${path}`, {
    method,
    headers,
    body: method === "GET" ? undefined : body,
  });
}

test("front door acepta JSON exacto con parámetros MIME permitidos", () => {
  assert.equal(assertPublicFrontDoor(request({ contentType: "application/json; charset=utf-8" })), true);
});

test("front door rechaza JSONP, bearer ausente, query y body declarado excesivo antes del router", () => {
  const cases = [
    [request({ contentType: "application/jsonp" }), "request_content_type_invalid"],
    [request({ authorization: null }), "bearer_missing"],
    [request({ path: "/v1/execute?debug=1" }), "request_query_forbidden"],
    [request({ contentLength: 70_000 }), "request_body_above_limit"],
  ];
  for (const [value, code] of cases) {
    assert.throws(() => assertPublicFrontDoor(value), (error) => expectPolicyError(error, code));
  }
});

test("front door rechaza rutas y métodos fuera de allowlist", () => {
  assert.throws(
    () => assertPublicFrontDoor(request({ path: "/v1/other" })),
    (error) => expectPolicyError(error, "request_route_not_found"),
  );
  assert.throws(
    () => assertPublicFrontDoor(request({ method: "GET" })),
    (error) => expectPolicyError(error, "request_method_not_allowed"),
  );
});

test("JWKS gate coalesce requests concurrentes en un único fetch físico", async () => {
  let now = 2_000_000_000_000;
  let fetchCalls = 0;
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const gate = createJwksFetchGate({
    clock: () => new Date(now),
    fetchImpl: async () => {
      fetchCalls += 1;
      await blocked;
      return new Response('{"keys":[]}', {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  const first = gate("https://token.actions.githubusercontent.com/.well-known/jwks", {});
  const second = gate("https://token.actions.githubusercontent.com/.well-known/jwks", {});
  release();
  const [a, b] = await Promise.all([first, second]);
  assert.equal(fetchCalls, 1);
  assert.equal(await a.text(), '{"keys":[]}');
  assert.equal(await b.text(), '{"keys":[]}');
});

test("JWKS gate impide refresh físico repetido por kid desconocido dentro de ventana", async () => {
  let now = 2_000_000_000_000;
  let fetchCalls = 0;
  const gate = createJwksFetchGate({
    clock: () => new Date(now),
    minRefreshMs: 60_000,
    fetchImpl: async () => {
      fetchCalls += 1;
      return new Response(`{"keys":[{"kid":"k-${fetchCalls}"}]}`, {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  const first = await gate("https://token.actions.githubusercontent.com/.well-known/jwks", {});
  assert.match(await first.text(), /k-1/u);
  for (let index = 0; index < 20; index += 1) {
    now += 1000;
    const replay = await gate("https://token.actions.githubusercontent.com/.well-known/jwks", {});
    assert.match(await replay.text(), /k-1/u);
  }
  assert.equal(fetchCalls, 1);

  now += 60_000;
  const refreshed = await gate("https://token.actions.githubusercontent.com/.well-known/jwks", {});
  assert.match(await refreshed.text(), /k-2/u);
  assert.equal(fetchCalls, 2);
});

test("JWKS gate no cachea respuestas HTTP fallidas", async () => {
  let fetchCalls = 0;
  const gate = createJwksFetchGate({
    clock: () => new Date(2_000_000_000_000),
    fetchImpl: async () => {
      fetchCalls += 1;
      return new Response("failure", { status: 503 });
    },
  });
  assert.equal((await gate("https://example.invalid", {})).status, 503);
  assert.equal((await gate("https://example.invalid", {})).status, 503);
  assert.equal(fetchCalls, 2);
});
