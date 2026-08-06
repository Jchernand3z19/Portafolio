from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    REPO_ROOT
    / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia_observable.js"
)
WORKFLOW = (
    REPO_ROOT
    / ".github/workflows/precios-supermercados-sps-la-colonia-command.yml"
)
FACET_WORKFLOW = "precios-supermercados-sps-la-colonia-facet-discovery.yml"
DISPATCH_ENDPOINT = (
    "POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
)


def _run_scenario(tmp_path: Path, scenario: str) -> dict:
    node = shutil.which("node")
    assert node is not None, "Node.js es necesario para la prueba offline"
    runner = tmp_path / "run-observability-scenario.js"
    runner.write_text(
        f"""
"use strict";
const fs = require("fs");
const wrapper = require({json.dumps(str(WRAPPER))});
const scenario = process.argv[2];
const calls = [];
const failures = [];
let observedInitial = false;
const github = {{
  request: async (endpoint, options) => {{
    calls.push({{ endpoint, options }});
    return {{
      data: {{
        workflow_run_id: 31130000001,
        html_url: "https://example.invalid/actions/runs/31130000001",
      }},
    }};
  }},
}};
const context = {{
  repo: {{ owner: "Jchernand3z19", repo: "Portafolio" }},
  payload: {{
    action: "synchronize",
    after: "1a515913a514d3b246c3445eddfff8fcb0d951b4",
    pull_request: {{
      number: 7,
      head: {{
        sha: "1a515913a514d3b246c3445eddfff8fcb0d951b4",
        ref: "feature/la-colonia-full-crawl-validation",
      }},
    }},
  }},
  runId: 31130000000,
  serverUrl: "https://github.com",
}};
const core = {{
  setFailed: (message) => failures.push(message),
  setOutput: () => undefined,
  warning: () => undefined,
}};
const fakeController = {{
  run: async (args) => {{
    observedInitial = fs.existsSync("dispatcher-result.json");
    if (scenario === "before_dispatch") {{
      const error = new Error("private detail must not be published");
      error.status = 503;
      throw error;
    }}
    if (scenario === "after_dispatch") {{
      await args.github.request({json.dumps(DISPATCH_ENDPOINT)}, {{
        workflow_id: {json.dumps(FACET_WORKFLOW)},
        ref: "main",
        inputs: {{
          request_id: "la-colonia-facet-discovery-001",
          discovery_plan: "catalog_categories_v1",
          delay_seconds: "1.5",
        }},
      }});
      throw new Error("private post-dispatch detail");
    }}
    if (scenario === "untrusted_dispatch_shape") {{
      await args.github.request({json.dumps(DISPATCH_ENDPOINT)}, {{
        workflow_id: {json.dumps(FACET_WORKFLOW)},
        ref: "main",
        inputs: {{
          request_id: "otro-request",
          discovery_plan: "arbitrary",
          delay_seconds: "1.5",
        }},
      }});
      throw new Error("private invalid-shape detail");
    }}
    throw new Error("unknown scenario");
  }},
}};
(async () => {{
  await wrapper.runWithController({{ github, context, core }}, fakeController);
  const artifact = JSON.parse(fs.readFileSync("dispatcher-result.json", "utf8"));
  process.stdout.write(JSON.stringify({{ artifact, calls, failures, observedInitial }}));
}})().catch((error) => {{
  process.stderr.write(String(error));
  process.exitCode = 1;
}});
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(runner), scenario],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_resultado_inicial_existe_antes_de_invocar_el_controlador(tmp_path):
    result = _run_scenario(tmp_path, "before_dispatch")
    assert result["observedInitial"] is True
    assert result["artifact"]["dispatch_sent"] is False
    assert result["artifact"]["controller_run_id"] == "31130000000"
    assert result["artifact"]["head_sha"] == (
        "1a515913a514d3b246c3445eddfff8fcb0d951b4"
    )


def test_error_previo_al_dispatch_conserva_artefacto_sanitizado(tmp_path):
    result = _run_scenario(tmp_path, "before_dispatch")
    artifact = result["artifact"]
    assert artifact["accepted"] is False
    assert artifact["dispatch_sent"] is False
    assert artifact["reason"] == (
        "El controlador falló antes de confirmar workflow_dispatch."
    )
    assert artifact["warnings"] == ["Fallo interno controlado: HTTP 503."]
    assert "private detail" not in json.dumps(artifact)
    assert result["failures"] == [artifact["reason"]]


def test_error_posterior_al_dispatch_conserva_confirmacion_y_run_id(tmp_path):
    result = _run_scenario(tmp_path, "after_dispatch")
    artifact = result["artifact"]
    assert artifact["accepted"] is True
    assert artifact["request_id"] == "la-colonia-facet-discovery-001"
    assert artifact["mode"] == "facet_discovery"
    assert artifact["workflow"].endswith(
        "precios-supermercados-sps-la-colonia-facet-discovery.yml"
    )
    assert artifact["ref"] == "main"
    assert artifact["dispatch_sent"] is True
    assert artifact["live_run_id"] == "31130000001"
    assert artifact["reason"] == (
        "El controlador falló después de confirmar workflow_dispatch."
    )
    assert "private post-dispatch" not in json.dumps(artifact)


def test_wrapper_no_envia_un_segundo_dispatch(tmp_path):
    result = _run_scenario(tmp_path, "after_dispatch")
    assert len(result["calls"]) == 1
    assert result["calls"][0]["endpoint"] == DISPATCH_ENDPOINT
    assert result["calls"][0]["options"]["ref"] == "main"


def test_dispatch_con_inputs_no_confiables_no_se_marca_como_aceptado(tmp_path):
    result = _run_scenario(tmp_path, "untrusted_dispatch_shape")
    artifact = result["artifact"]
    assert artifact["accepted"] is False
    assert artifact["dispatch_sent"] is False
    assert artifact["request_id"] is None


def test_workflow_conserva_trigger_paths_y_sube_resultado_siempre():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    assert "types: [synchronize]" in text
    assert (
        "- precios-supermercados-sps/.automation/la-colonia-live-command.json"
        in text
    )
    assert "ref: main" in text
    assert "controlar_solicitud_archivo_la_colonia_observable.js" in text
    assert "if: always()" in text
    assert "if-no-files-found: error" in text
    assert "issue_comment:" not in text
    assert "schedule:" not in text
    assert "push:" not in text


def test_pruebas_de_observabilidad_no_importan_clientes_de_red():
    text = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.", "urllib", "httpx", "aiohttp", "socket."):
        assert forbidden not in text
