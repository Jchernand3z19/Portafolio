#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { TextDecoder } = require("util");

const COMMAND_PATH = "precios-supermercados-sps/.automation/la-colonia-live-command.json";
const GLOBAL_LIVE_BLOCKED =
  "GLOBAL LIVE BLOCKED: no existe autorización live ni evidencia productiva de GATE-17.";

function writeJson(filename, value) {
  fs.writeFileSync(filename, JSON.stringify(value, null, 2), "utf8");
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
    result.accepted = false;
    result.reason = GLOBAL_LIVE_BLOCKED;
    persistResult(result);
    core.setFailed(GLOBAL_LIVE_BLOCKED);
    return;
  }

  persistResult(result);
  core.setFailed(result.reason || GLOBAL_LIVE_BLOCKED);
}

module.exports = { run };
