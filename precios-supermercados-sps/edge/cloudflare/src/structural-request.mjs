import {
  canonicalBytes,
  EdgePolicyError,
  LA_COLONIA_HOST,
  LA_COLONIA_PATH,
  sha256Hex,
} from "./core.mjs";

const SEARCH_KEYS = Object.freeze([
  "workspace",
  "maxAge",
  "appsEtag",
  "domain",
  "locale",
  "operationName",
  "query",
  "variables",
]);
const VARIABLE_KEYS = Object.freeze(["query", "fullText", "selectedFacets", "from", "to"]);
const FIXED_SEARCH = Object.freeze({
  workspace: "master",
  maxAge: "short",
  appsEtag: "remove",
  domain: "store",
  locale: "es-HN",
});
const FIXED_VARIABLES = Object.freeze({
  query: "",
  fullText: "",
  selectedFacets: Object.freeze([]),
  from: 0,
  to: 0,
});
const OPERATION_KIND = Object.freeze({
  FacetDiscoveryRootTotal: "root_total",
  FacetDiscoveryCategoryTree: "category_tree",
});
const SHA256_RE = /^[0-9a-f]{64}$/u;

function fail(code, message = code) {
  throw new EdgePolicyError(code, message);
}

function exactString(value, code, max = 20_000) {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value || value.length > max) {
    fail(code);
  }
  return value;
}

function exactKeys(value, expected, code) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  const actual = Object.keys(value);
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) fail(code);
}

function exactSearchParams(searchParams) {
  const pairs = [...searchParams.entries()];
  const keys = pairs.map(([key]) => key);
  if (new Set(keys).size !== keys.length) fail("structural_origin_query_parameter_duplicate");
  if (keys.length !== SEARCH_KEYS.length || keys.some((key, index) => key !== SEARCH_KEYS[index])) {
    fail("structural_origin_query_parameter_order_or_set_invalid");
  }
  return Object.fromEntries(pairs);
}

function policyHash(policy, requestKind) {
  const hashes = policy?.expectedQuerySha256ByKind;
  if (!hashes || typeof hashes !== "object" || Array.isArray(hashes)) fail("structural_query_policy_missing");
  const value = hashes[requestKind];
  if (typeof value !== "string" || !SHA256_RE.test(value)) fail("structural_query_policy_invalid");
  return value;
}

export async function validateLaColoniaStructuralGetUrl(rawUrl, policy) {
  const text = exactString(rawUrl, "structural_origin_url_invalid");
  let url;
  try {
    url = new URL(text);
  } catch {
    fail("structural_origin_url_invalid");
  }
  if (url.protocol !== "https:") fail("structural_origin_scheme_mismatch");
  if (url.hostname !== LA_COLONIA_HOST) fail("structural_origin_host_mismatch");
  if (url.port !== "" || url.username || url.password) fail("structural_origin_authority_invalid");
  if (url.pathname !== LA_COLONIA_PATH || url.hash !== "") fail("structural_origin_path_invalid");
  if (url.toString() !== text) fail("structural_origin_url_noncanonical");

  const params = exactSearchParams(url.searchParams);
  for (const [key, expected] of Object.entries(FIXED_SEARCH)) {
    if (params[key] !== expected) fail(`structural_origin_${key}_mismatch`);
  }

  const requestKind = OPERATION_KIND[params.operationName];
  if (!requestKind) fail("structural_operation_name_invalid");
  const expectedQuerySha = policyHash(policy, requestKind);
  if (await sha256Hex(params.query) !== expectedQuerySha) fail("structural_graphql_query_mismatch");

  let variables;
  try {
    variables = JSON.parse(params.variables);
  } catch {
    fail("structural_variables_json_invalid");
  }
  exactKeys(variables, VARIABLE_KEYS, "structural_variables_shape_or_order_invalid");
  if (
    variables.query !== ""
    || variables.fullText !== ""
    || !Array.isArray(variables.selectedFacets)
    || variables.selectedFacets.length !== 0
    || variables.from !== 0
    || variables.to !== 0
  ) {
    fail("structural_variables_values_invalid");
  }
  const canonicalVariables = JSON.stringify(FIXED_VARIABLES);
  if (params.variables !== canonicalVariables) fail("structural_variables_json_noncanonical");

  const canonicalRequest = {
    method: "GET",
    operation_name: params.operationName,
    origin_url: text,
    target_host: LA_COLONIA_HOST,
    target_path: LA_COLONIA_PATH,
    variables: {
      query: "",
      fullText: "",
      selectedFacets: [],
      from: 0,
      to: 0,
    },
  };

  return Object.freeze({
    requestKind,
    operationName: params.operationName,
    url: text,
    canonicalRequest,
    canonicalRequestSha256: await sha256Hex(canonicalBytes(canonicalRequest)),
  });
}
