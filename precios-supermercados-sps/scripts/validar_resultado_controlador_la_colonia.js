#!/usr/bin/env node
"use strict";

const fs = require("fs");

const RESULT_PATH = process.env.RESULT_PATH || "";
const SOURCE_RUN_ID = String(process.env.SOURCE_RUN_ID || "");
const SUMMARY_PATH = process.env.GITHUB_STEP_SUMMARY || "";

const NUMERIC_ID = /^[0-9]+$/;
const REQUEST_ID = /^[a-z0-9](?:[a-z0-9._-]{0,78}[a-z0-9])?$/;
const LIVE_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-live.yml";
const DIAGNOSTIC_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml";
const FACET_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml";
const MODE_TO_WORKFLOW = new Map([
  ["smoke", LIVE_WORKFLOW],
  ["staged", LIVE_WORKFLOW],
  ["diagnostic_overlap", DIAGNOSTIC_WORKFLOW],
  ["facet_discovery", FACET_WORKFLOW],
]);
const ALLOWED_WORKFLOWS = new Set([
  LIVE_WORKFLOW,
  DIAGNOSTIC_WORKFLOW,
  FACET_WORKFLOW,
]);
const ALLOWED_KEYS = new Set([
  "accepted",
  "request_id",
  "mode",
  "workflow",
  "pr_number",
  "head_sha",
  "ref",
  "dispatch_sent",
  "live_run_id",
  "live_run_url",
  "comment_published",
  "comment_method",
  "controller_run_id",
  "controller_url",
  "reason",
  "warnings",
]);

function fail(message) {
  process.stderr.write(`::error::${message}\n`);
  process.exitCode = 1;
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function writeSummary(lines) {
  const text = `${lines.join("\n")}\n`;
  if (SUMMARY_PATH) {
    fs.appendFileSync(SUMMARY_PATH, text, "utf8");
  } else {
    process.stdout.write(text);
  }
}

function main() {
  if (!NUMERIC_ID.test(SOURCE_RUN_ID)) {
    fail("El run de origen no tiene un identificador válido.");
    return;
  }
  if (!RESULT_PATH || !fs.existsSync(RESULT_PATH)) {
    fail("No existe el resultado operacional del controlador.");
    return;
  }

  let result;
  try {
    result = JSON.parse(fs.readFileSync(RESULT_PATH, "utf8"));
  } catch (error) {
    fail("El resultado operacional no contiene JSON válido.");
    return;
  }

  if (!result || typeof result !== "object" || Array.isArray(result)) {
    fail("El resultado operacional debe ser un objeto.");
    return;
  }
  if (Object.keys(result).some((key) => !ALLOWED_KEYS.has(key))) {
    fail("El resultado operacional contiene campos inesperados.");
    return;
  }
  if (String(result.controller_run_id || "") !== SOURCE_RUN_ID) {
    fail("El resultado no corresponde al run controlador observado.");
    return;
  }

  const hasMode = hasOwn(result, "mode");
  const hasWorkflow = hasOwn(result, "workflow");
  if (hasMode !== hasWorkflow) {
    fail("mode y workflow deben estar ambos presentes o ambos ausentes.");
    return;
  }

  let safeMode = "";
  let safeWorkflow = "";
  let legacyArtifact = true;
  if (hasMode && hasWorkflow) {
    legacyArtifact = false;
    if (typeof result.mode !== "string" || typeof result.workflow !== "string") {
      fail("mode y workflow deben ser strings.");
      return;
    }
    const expectedWorkflow = MODE_TO_WORKFLOW.get(result.mode);
    if (!expectedWorkflow) {
      fail("El modo del controlador no está permitido.");
      return;
    }
    if (!ALLOWED_WORKFLOWS.has(result.workflow)) {
      fail("El workflow del controlador no está permitido.");
      return;
    }
    if (result.workflow !== expectedWorkflow) {
      fail("La relación mode/workflow del controlador no está permitida.");
      return;
    }
    safeMode = result.mode;
    safeWorkflow = result.workflow;
  }

  const accepted = result.accepted === true;
  const dispatchSent = result.dispatch_sent === true;
  const commentPublished = result.comment_published === true;
  const safeRequestId =
    typeof result.request_id === "string" && REQUEST_ID.test(result.request_id)
      ? result.request_id
      : "";
  const liveRunId =
    typeof result.live_run_id === "string" && NUMERIC_ID.test(result.live_run_id)
      ? result.live_run_id
      : "";

  writeSummary([
    "## Recuperación del controlador de La Colonia",
    "",
    `- controller_run_id: \`${SOURCE_RUN_ID}\``,
    `- request_id: \`${safeRequestId}\``,
    `- mode: \`${safeMode}\``,
    `- workflow: \`${safeWorkflow}\``,
    `- legacy_artifact: \`${legacyArtifact}\``,
    `- accepted: \`${accepted}\``,
    `- dispatch_sent: \`${dispatchSent}\``,
    `- live_run_id: \`${liveRunId}\``,
    `- comment_published: \`${commentPublished}\``,
  ]);

  if (accepted && dispatchSent && !commentPublished) {
    if (!safeRequestId || !liveRunId) {
      fail("El dispatch requiere recuperación, pero faltan identificadores válidos.");
      return;
    }
    process.stderr.write(
      `::error::RECOVERY_REQUIRED request_id=${safeRequestId} controller_run_id=${SOURCE_RUN_ID} live_run_id=${liveRunId}\n`,
    );
    fail("El dispatch fue enviado, pero el comentario requiere recuperación controlada.");
  }
}

main();
