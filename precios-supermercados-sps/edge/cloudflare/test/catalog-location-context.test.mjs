import assert from "node:assert/strict";
import test from "node:test";

import { canonicalBytes, sha256Hex } from "../src/core.mjs";
import { validateAndApplyCatalogLocationContext } from "../src/catalog-location-context.mjs";

const ORIGIN = "https://www.lacolonia.com/_v/segment/graphql/v1?workspace=master";
const RAW = "synthetic-sps-region-context";
const EVIDENCE = `location_binding_radiography:sha256:${"c".repeat(64)}`;

async function locationContext({
  placement = "header",
  wireKey = "X-VTEX-Region",
  rawValue = RAW,
  wireRequestFingerprint,
  valuePath = [],
} = {}) {
  const contextFingerprint = await sha256Hex(canonicalBytes(RAW));
  let url = ORIGIN;
  const headers = {};
  if (placement === "query") {
    const parsed = new URL(ORIGIN);
    parsed.searchParams.append(wireKey, RAW);
    url = parsed.toString();
  } else if (placement === "header") {
    headers[wireKey] = RAW;
  }
  const fingerprint = wireRequestFingerprint ?? await sha256Hex(canonicalBytes({
    method: "GET",
    url,
    headers,
  }));
  return {
    locationId: "la_colonia_sps",
    bindingSourceKey: `request:regionid:sha256:${contextFingerprint}`,
    bindingEvidence: EVIDENCE,
    contextFingerprint,
    placement,
    wireKey,
    valuePath,
    wireRequestFingerprint: fingerprint,
    rawValue,
  };
}

test("header aplica regionId sin incluir raw en receiptContext", async () => {
  const input = await locationContext();
  const result = await validateAndApplyCatalogLocationContext(ORIGIN, input);

  assert.equal(result.fetchUrl, ORIGIN);
  assert.deepEqual(result.fetchHeaders, { "X-VTEX-Region": RAW });
  assert.equal(result.receiptContext.locationId, "la_colonia_sps");
  assert.equal(result.receiptContext.contextFingerprint, input.contextFingerprint);
  assert.equal(result.receiptContext.contextPlacement, "header");
  assert.equal(result.receiptContext.contextWireKey, "X-VTEX-Region");
  assert.equal(result.receiptContext.wireRequestFingerprint, input.wireRequestFingerprint);
  assert.equal(JSON.stringify(result.receiptContext).includes(RAW), false);
});

test("query aplica regionId y verifica el fingerprint del wire exacto", async () => {
  const input = await locationContext({ placement: "query", wireKey: "regionId" });
  const result = await validateAndApplyCatalogLocationContext(ORIGIN, input);

  assert.equal(new URL(result.fetchUrl).searchParams.get("regionId"), RAW);
  assert.deepEqual(result.fetchHeaders, {});
  assert.equal(result.receiptContext.contextPlacement, "query");
  assert.equal(result.receiptContext.wireRequestFingerprint, input.wireRequestFingerprint);
});

test("raw alterado falla antes de producir material de fetch", async () => {
  const input = await locationContext({ rawValue: "tampered-region" });
  await assert.rejects(
    validateAndApplyCatalogLocationContext(ORIGIN, input),
    (error) => error?.code === "catalog_context_raw_fingerprint_mismatch",
  );
});

test("fingerprint de wire alterado falla cerrado", async () => {
  const input = await locationContext({ wireRequestFingerprint: "f".repeat(64) });
  await assert.rejects(
    validateAndApplyCatalogLocationContext(ORIGIN, input),
    (error) => error?.code === "catalog_wire_request_fingerprint_mismatch",
  );
});

test("placement o ruta anidada no demostrados son rechazados", async () => {
  const body = await locationContext({ placement: "body" });
  await assert.rejects(
    validateAndApplyCatalogLocationContext(ORIGIN, body),
    (error) => error?.code === "catalog_context_placement_invalid",
  );

  const nested = await locationContext({ valuePath: ["variables", "regionId"] });
  await assert.rejects(
    validateAndApplyCatalogLocationContext(ORIGIN, nested),
    (error) => error?.code === "catalog_context_value_path_invalid",
  );
});
