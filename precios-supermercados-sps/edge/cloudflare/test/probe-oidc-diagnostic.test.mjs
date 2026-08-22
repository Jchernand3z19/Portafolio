import assert from "node:assert/strict";
import test from "node:test";

import { controlledProbeJwksTransportDiagnostic } from "../src/probe-oidc.mjs";

test("diagnóstico JWKS conserva sólo nombre/mensaje acotados y sin controles", () => {
  const error = new TypeError("linea-1\nlinea-2\t" + "x".repeat(400));
  const diagnostic = controlledProbeJwksTransportDiagnostic(error);

  assert.deepEqual(Object.keys(diagnostic).sort(), ["message", "name"]);
  assert.equal(diagnostic.name, "TypeError");
  assert.ok(diagnostic.message.startsWith("linea-1 linea-2 "));
  assert.ok(diagnostic.message.length <= 240);
  assert.doesNotMatch(diagnostic.message, /[\u0000-\u001f\u007f]/u);
});

test("diagnóstico JWKS no serializa objetos arbitrarios", () => {
  const diagnostic = controlledProbeJwksTransportDiagnostic({
    name: { secret: "no" },
    message: { token: "no" },
    authorization: "Bearer secret",
  });

  assert.deepEqual(diagnostic, {
    name: "UnknownError",
    message: "no_message",
  });
});
