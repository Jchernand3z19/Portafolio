#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { TextDecoder } = require("util");

const EXPECTED_REPOSITORY = "Jchernand3z19/Portafolio";
const COMMAND_PATH = "precios-supermercados-sps/.automation/la-colonia-live-command.json";
const LIVE_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-live.yml";
const DIAGNOSTIC_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-diagnostic.yml";
const FACET_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-facet-discovery.yml";
const API_VERSION = "2026-03-10";

const WORKFLOWS = new Map([
  [LIVE_WORKFLOW, "precios-supermercados-sps-la-colonia-live.yml"],
  [DIAGNOSTIC_WORKFLOW, "precios-supermercados-sps-la-colonia-diagnostic.yml"],
  [FACET_WORKFLOW, "precios-supermercados-sps-la-colonia-facet-discovery.yml"],
]);
const MODES = new Map([
  [LIVE_WORKFLOW, new Set(["smoke", "staged"])],
  [DIAGNOSTIC_WORKFLOW, new Set(["diagnostic_overlap"])],
  [FACET_WORKFLOW, new Set(["facet_discovery"])],
]);

function writeJson(filename, value) {
  fs.writeFileSync(filename, JSON.stringify(value, null, 2), "utf8");
}

function exactKeys(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return actual.length === wanted.length && actual.every((key, index) => key === wanted[index]);
}

function normalizedInputsAreTrusted(decision) {
  if (decision.mode === "facet_discovery") {
    return exactKeys(decision.inputs, ["request_id", "discovery_plan", "delay_seconds"])
      && decision.inputs.request_id === "la-colonia-facet-discovery-001"
      && decision.inputs.discovery_plan === "catalog_categories_v1"
      && decision.inputs.delay_seconds === "1.5";
  }
  return decision.inputs && typeof decision.inputs === "object" && !Array.isArray(decision.inputs);
}

async function publishComment({ github, owner, repo, prNumber, body, warnings }) {
  let pullNodeId = null;
  try {
    const { data: pull } = await github.rest.pulls.get({ owner, repo, pull_number: prNumber });
    pullNodeId = pull.node_id || null;
  } catch (error) {
    warnings.push(`No fue posible resolver el nodo del PR: HTTP ${error.status || "desconocido"}.`);
  }

  if (pullNodeId) {
    try {
      await github.graphql(
        `mutation($subjectId: ID!, $body: String!) {
          addComment(input: {subjectId: $subjectId, body: $body}) {
            commentEdge { node { id } }
          }
        }`,
        { subjectId: pullNodeId, body },
      );
      return { published: true, method: "graphql" };
    } catch (error) {
      warnings.push(`GraphQL addComment rechazó la escritura: HTTP ${error.status || "desconocido"}.`);
    }
  }

  try {
    await github.rest.issues.createComment({ owner, repo, issue_number: prNumber, body });
    return { published: true, method: "rest" };
  } catch (error) {
    warnings.push(`REST createComment rechazó la escritura: HTTP ${error.status || "desconocido"}.`);
    return { published: false, method: null };
  }
}

async function readUntrustedCommand({ github, context }) {
  const owner = context.repo.owner;
  const repo = context.repo.repo;
  const payloadPull = context.payload.pull_request;
  const eventHeadSha = context.payload.after || payloadPull?.head?.sha || "";
  const selected = {
    repository_owner: owner,
    repository_full_name: `${owner}/${repo}`,
    pr_number: payloadPull?.number || null,
    state: payloadPull?.state || null,
    base_repo_full_name: payloadPull?.base?.repo?.full_name || null,
    head_repo_full_name: payloadPull?.head?.repo?.full_name || null,
    head_repo_fork: Boolean(payloadPull?.head?.repo?.fork),
    head_ref: payloadPull?.head?.ref || null,
    head_sha: eventHeadSha,
    command_file_changed: false,
    command_file_status: "unverified",
  };
  writeJson("dispatcher-comments.json", []);

  if (!payloadPull?.number) {
    writeJson("dispatcher-context.json", selected);
    return;
  }

  const { data: pull } = await github.rest.pulls.get({
    owner,
    repo,
    pull_number: payloadPull.number,
  });
  selected.pr_number = pull.number;
  selected.state = pull.state;
  selected.base_repo_full_name = pull.base?.repo?.full_name || null;
  selected.head_repo_full_name = pull.head?.repo?.full_name || null;
  selected.head_repo_fork = Boolean(pull.head?.repo?.fork);
  selected.head_ref = pull.head?.ref || null;

  if (pull.head?.sha !== eventHeadSha) {
    selected.command_file_status = "superseded";
    writeJson("dispatcher-context.json", selected);
    return;
  }

  let page = 1;
  while (page <= 10 && !selected.command_file_changed) {
    const { data: commit } = await github.rest.repos.getCommit({
      owner,
      repo,
      ref: eventHeadSha,
      per_page: 100,
      page,
    });
    const files = Array.isArray(commit.files) ? commit.files : [];
    selected.command_file_changed = files.some((file) => file.filename === COMMAND_PATH);
    if (files.length < 100) break;
    page += 1;
  }

  if (!selected.command_file_changed) {
    selected.command_file_status = "not_modified";
    writeJson("dispatcher-context.json", selected);
    return;
  }

  try {
    const { data: commandFile } = await github.rest.repos.getContent({
      owner,
      repo,
      path: COMMAND_PATH,
      ref: eventHeadSha,
    });
    if (Array.isArray(commandFile) || commandFile.type !== "file" || commandFile.encoding !== "base64") {
      selected.command_file_status = "invalid_type";
    } else if (commandFile.size > 16384) {
      selected.command_file_status = "too_large";
    } else {
      try {
        const bytes = Buffer.from(commandFile.content.replace(/\n/g, ""), "base64");
        const decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        fs.writeFileSync("dispatcher-command.json", decoded, "utf8");
        selected.command_file_status = "ok";
      } catch (error) {
        selected.command_file_status = "invalid_encoding";
      }
    }
  } catch (error) {
    if (error.status === 404) selected.command_file_status = "missing";
    else throw error;
  }

  if (`${owner}/${repo}` === EXPECTED_REPOSITORY) {
    const comments = await github.paginate(github.rest.issues.listComments, {
      owner,
      repo,
      issue_number: pull.number,
      per_page: 100,
    });
    const markerPattern = /<!-- la-colonia-file-dispatch:[A-Za-z0-9._-]{1,80} -->/g;
    const markers = [];
    for (const comment of comments) {
      const body = typeof comment.body === "string" ? comment.body : "";
      const found = body.match(markerPattern);
      if (found) markers.push(...found);
    }
    writeJson("dispatcher-comments.json", markers);
  }
  writeJson("dispatcher-context.json", selected);
}

function runTrustedPython() {
  const workspace = process.env.GITHUB_WORKSPACE || process.cwd();
  const script = path.join(workspace, "precios-supermercados-sps/scripts/procesar_solicitud_archivo_la_colonia.py");
  execFileSync(
    "python",
    [
      script,
      "--context", "dispatcher-context.json",
      "--command", "dispatcher-command.json",
      "--comments", "dispatcher-comments.json",
      "--output", "dispatcher-decision.json",
    ],
    {
      stdio: "inherit",
      env: {
        ...process.env,
        PYTHONPATH: path.join(workspace, "precios-supermercados-sps/src"),
      },
    },
  );
}

function persistResult(result) {
  writeJson("dispatcher-result.json", result);
  if (process.env.GITHUB_STEP_SUMMARY) {
    const summary = [
      "## Resultado del controlador de La Colonia",
      "",
      `- accepted: \`${result.accepted}\``,
      `- request_id: \`${result.request_id || ""}\``,
      `- mode: \`${result.mode || ""}\``,
      `- workflow: \`${result.workflow || ""}\``,
      `- dispatch_sent: \`${result.dispatch_sent}\``,
      `- live_run_id: \`${result.live_run_id || ""}\``,
      `- comment_published: \`${result.comment_published}\``,
      `- controller_run_id: \`${result.controller_run_id}\``,
    ].join("\n");
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${summary}\n`, "utf8");
  }
}

async function run({ github, context, core }) {
  await readUntrustedCommand({ github, context });
  runTrustedPython();

  const decision = JSON.parse(fs.readFileSync("dispatcher-decision.json", "utf8"));
  const owner = context.repo.owner;
  const repo = context.repo.repo;
  const selectedWorkflowFile = WORKFLOWS.get(decision.workflow) || null;
  const allowedModes = MODES.get(decision.workflow);
  const controllerUrl = `${context.serverUrl}/${owner}/${repo}/actions/runs/${context.runId}`;
  const warnings = [];
  const result = {
    accepted: Boolean(decision.accepted),
    request_id: decision.request_id || null,
    mode: decision.mode || null,
    workflow: decision.workflow || null,
    pr_number: decision.pr_number || null,
    head_sha: decision.head_sha || null,
    ref: decision.ref || null,
    dispatch_sent: false,
    live_run_id: null,
    live_run_url: null,
    comment_published: false,
    comment_method: null,
    controller_run_id: String(context.runId),
    controller_url: controllerUrl,
    reason: decision.accepted ? "" : decision.reason,
    warnings,
  };

  if (decision.accepted) {
    if (!selectedWorkflowFile || !allowedModes || !allowedModes.has(decision.mode)) {
      result.reason = "La decisión confiable señaló un workflow o modo inesperado.";
      persistResult(result);
      core.setFailed(result.reason);
      return;
    }
    if (!normalizedInputsAreTrusted(decision)) {
      result.reason = "La decisión confiable contiene inputs inesperados.";
      persistResult(result);
      core.setFailed(result.reason);
      return;
    }

    const marker = `<!-- la-colonia-file-dispatch:${decision.request_id} -->`;
    if (!decision.comment.includes(marker)) {
      result.reason = "El comentario confiable no contiene la marca idempotente esperada.";
      persistResult(result);
      core.setFailed(result.reason);
      return;
    }

    const dispatchRef = decision.mode === "facet_discovery" ? "main" : decision.ref;
    try {
      const dispatch = await github.request(
        "POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        {
          owner,
          repo,
          workflow_id: selectedWorkflowFile,
          ref: dispatchRef,
          inputs: decision.inputs,
          return_run_details: true,
          headers: { "X-GitHub-Api-Version": API_VERSION },
        },
      );
      result.dispatch_sent = true;
      result.live_run_id = dispatch.data?.workflow_run_id ? String(dispatch.data.workflow_run_id) : null;
      result.live_run_url = dispatch.data?.html_url || null;
      core.setOutput("live_run_id", result.live_run_id || "");
      core.setOutput("live_run_url", result.live_run_url || "");
    } catch (error) {
      result.reason = "No fue posible enviar workflow_dispatch.";
      warnings.push(`El endpoint de dispatch respondió HTTP ${error.status || "desconocido"}.`);
      const rejection = await publishComment({
        github,
        owner,
        repo,
        prNumber: decision.pr_number,
        body: "## Solicitud rechazada\n\n- Razón: no fue posible enviar workflow_dispatch.\n- Estado: **no se confirmó ninguna ejecución**",
        warnings,
      });
      result.comment_published = rejection.published;
      result.comment_method = rejection.method;
      persistResult(result);
      core.setFailed(result.reason);
      return;
    }

    const liveDetails = [
      result.live_run_id ? `- Run ID live: \`${result.live_run_id}\`` : "- Run ID live: no devuelto por la API",
      result.live_run_url ? `- Enlace live: ${result.live_run_url}` : "- Enlace live: no devuelto por la API",
    ].join("\n");
    const acceptanceBody = decision.comment.replace(`\n\n${marker}`, `\n${liveDetails}\n\n${marker}`);
    const published = await publishComment({
      github,
      owner,
      repo,
      prNumber: decision.pr_number,
      body: acceptanceBody,
      warnings,
    });
    result.comment_published = published.published;
    result.comment_method = published.method;
    if (!published.published) {
      warnings.push("El dispatch fue enviado, pero GitHub no permitió publicar el comentario con GITHUB_TOKEN.");
      core.warning("workflow_dispatch enviado; comentario pendiente de recuperación por el conector.");
    }
    persistResult(result);
    return;
  }

  if (decision.should_comment) {
    const published = await publishComment({
      github,
      owner,
      repo,
      prNumber: decision.pr_number,
      body: decision.comment,
      warnings,
    });
    result.comment_published = published.published;
    result.comment_method = published.method;
    if (!published.published) {
      persistResult(result);
      core.setFailed("La solicitud fue rechazada, pero no fue posible publicar la razón en el PR.");
      return;
    }
  }
  persistResult(result);
}

module.exports = { run };
