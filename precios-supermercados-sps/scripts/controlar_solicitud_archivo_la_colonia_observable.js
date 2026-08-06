#!/usr/bin/env node
"use strict";

const fs = require("fs");
const controller = require("./controlar_solicitud_archivo_la_colonia.js");

const DISPATCH_ENDPOINT =
  "POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches";
const LIVE_WORKFLOW_FILE = "precios-supermercados-sps-la-colonia-live.yml";
const DIAGNOSTIC_WORKFLOW_FILE =
  "precios-supermercados-sps-la-colonia-diagnostic.yml";
const FACET_WORKFLOW_FILE =
  "precios-supermercados-sps-la-colonia-facet-discovery.yml";
const LIVE_WORKFLOW =
  ".github/workflows/precios-supermercados-sps-la-colonia-live.yml";
const DIAGNOSTIC_WORKFLOW =
  ".github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml";
const FACET_WORKFLOW =
  ".github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml";
const REQUEST_ID = /^[a-z0-9](?:[a-z0-9._-]{0,78}[a-z0-9])?$/;
const NUMERIC_ID = /^[0-9]+$/;

function writeResult(result) {
  fs.writeFileSync(
    "dispatcher-result.json",
    JSON.stringify(result, null, 2),
    "utf8",
  );
}

function initialResult(context) {
  const pull = context.payload?.pull_request || {};
  const owner = context.repo?.owner || "";
  const repo = context.repo?.repo || "";
  const runId = String(context.runId || "");
  return {
    accepted: false,
    request_id: null,
    pr_number: Number.isInteger(pull.number) ? pull.number : null,
    head_sha: context.payload?.after || pull.head?.sha || null,
    ref: pull.head?.ref || null,
    dispatch_sent: false,
    live_run_id: null,
    live_run_url: null,
    comment_published: false,
    comment_method: null,
    controller_run_id: runId,
    controller_url:
      context.serverUrl && owner && repo && runId
        ? `${context.serverUrl}/${owner}/${repo}/actions/runs/${runId}`
        : null,
    reason: "El controlador todavía no produjo un resultado final.",
    warnings: [
      "Resultado inicial de observabilidad; debe ser reemplazado al completar el controlador.",
    ],
  };
}

function trustedDispatchDetails(workflowId, ref, inputs) {
  if (!inputs || typeof inputs !== "object" || Array.isArray(inputs)) return null;
  const requestId = inputs.request_id;
  if (typeof requestId !== "string" || !REQUEST_ID.test(requestId)) return null;

  if (
    workflowId === FACET_WORKFLOW_FILE &&
    ref === "main" &&
    requestId === "la-colonia-facet-discovery-001" &&
    inputs.discovery_plan === "catalog_categories_v1" &&
    inputs.delay_seconds === "1.5"
  ) {
    return {
      request_id: requestId,
      mode: "facet_discovery",
      workflow: FACET_WORKFLOW,
    };
  }
  if (
    workflowId === DIAGNOSTIC_WORKFLOW_FILE &&
    inputs.diagnostic_plan === "frontier_380_399_v1" &&
    inputs.delay_seconds === "1.5"
  ) {
    return {
      request_id: requestId,
      mode: "diagnostic_overlap",
      workflow: DIAGNOSTIC_WORKFLOW,
    };
  }
  if (
    workflowId === LIVE_WORKFLOW_FILE &&
    (inputs.mode === "smoke" || inputs.mode === "staged")
  ) {
    return {
      request_id: requestId,
      mode: inputs.mode,
      workflow: LIVE_WORKFLOW,
    };
  }
  return null;
}

function checkpointDispatch(result, endpoint, options, response) {
  if (endpoint !== DISPATCH_ENDPOINT) return;
  const details = trustedDispatchDetails(
    options?.workflow_id,
    options?.ref,
    options?.inputs,
  );
  if (!details) return;

  const runId = response?.data?.workflow_run_id
    ? String(response.data.workflow_run_id)
    : "";
  result.accepted = true;
  result.request_id = details.request_id;
  result.mode = details.mode;
  result.workflow = details.workflow;
  result.ref = typeof options.ref === "string" ? options.ref : result.ref;
  result.dispatch_sent = true;
  result.live_run_id = NUMERIC_ID.test(runId) ? runId : null;
  result.live_run_url =
    typeof response?.data?.html_url === "string" ? response.data.html_url : null;
  result.reason = "workflow_dispatch confirmado; resultado final pendiente.";
  result.warnings = [];
  writeResult(result);
}

async function runWithController(args, controllerModule) {
  const { github, context, core } = args;
  const result = initialResult(context);
  writeResult(result);

  const observableGithub = new Proxy(github, {
    get(target, property, receiver) {
      if (property !== "request") {
        return Reflect.get(target, property, receiver);
      }
      return async (endpoint, options) => {
        const response = await target.request(endpoint, options);
        checkpointDispatch(result, endpoint, options, response);
        return response;
      };
    },
  });

  try {
    await controllerModule.run({ github: observableGithub, context, core });
  } catch (error) {
    result.reason = result.dispatch_sent
      ? "El controlador falló después de confirmar workflow_dispatch."
      : "El controlador falló antes de confirmar workflow_dispatch.";
    result.warnings = [
      error && Number.isInteger(error.status)
        ? `Fallo interno controlado: HTTP ${error.status}.`
        : "Fallo interno controlado sin detalles públicos.",
    ];
    writeResult(result);
    core.setFailed(result.reason);
  }
}

async function run(args) {
  return runWithController(args, controller);
}

module.exports = { run, runWithController };
