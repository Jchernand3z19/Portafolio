import { EdgePolicyError } from "./core.mjs";
import { AUTHORIZATION_LIMITS, WORKER_ROUTES } from "./worker-policy.mjs";

function fail(code) {
  throw new EdgePolicyError(code);
}

export function assertPublicFrontDoor(request) {
  if (!(request instanceof Request)) fail("request_invalid");
  if (request.method !== "POST") fail("request_method_not_allowed");

  const url = new URL(request.url);
  if (url.search !== "") fail("request_query_forbidden");
  if (!Object.values(WORKER_ROUTES).includes(url.pathname)) fail("request_route_not_found");

  const authorization = request.headers.get("authorization");
  if (typeof authorization !== "string" || !authorization.startsWith("Bearer ")) fail("bearer_missing");
  const token = authorization.slice("Bearer ".length);
  if (!token || token.trim() !== token || /\s/u.test(token) || token.length > 20_000) fail("bearer_invalid");

  const rawContentType = request.headers.get("content-type") ?? "";
  const mediaType = rawContentType.split(";", 1)[0].trim().toLowerCase();
  if (mediaType !== "application/json") fail("request_content_type_invalid");

  const declared = request.headers.get("content-length");
  if (declared !== null) {
    const parsed = Number(declared);
    if (!Number.isSafeInteger(parsed) || parsed < 0) fail("request_content_length_invalid");
    if (parsed > AUTHORIZATION_LIMITS.maxRequestBodyBytes) fail("request_body_above_limit");
  }
  return true;
}
