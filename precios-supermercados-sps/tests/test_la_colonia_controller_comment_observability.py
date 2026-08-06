from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    REPO_ROOT
    / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia_observable.js"
)


def _run(tmp_path: Path, scenario: str) -> dict:
    node = shutil.which("node")
    assert node is not None
    script = tmp_path / "comments.js"
    script.write_text(
        f"""
"use strict";
const fs = require("fs");
const wrapper = require({json.dumps(str(WRAPPER))});
const scenario = process.argv[2];
const calls = {{ dispatch: 0, graphql: 0, rest: 0 }};
const github = {{
  request: async () => {{
    calls.dispatch += 1;
    return {{ data: {{ workflow_run_id: 31130000001 }} }};
  }},
  graphql: async () => {{
    calls.graphql += 1;
    if (scenario !== "graphql") throw Object.assign(new Error("blocked"), {{status: 403}});
    return {{ data: {{}} }};
  }},
  rest: {{
    issues: {{
      createComment: async () => {{
        calls.rest += 1;
        if (scenario === "blocked") throw Object.assign(new Error("blocked"), {{status: 403}});
        return {{ data: {{ id: 1 }} }};
      }},
    }},
  }},
}};
const context = {{
  eventName: "pull_request_target",
  repo: {{ owner: "Jchernand3z19", repo: "Portafolio" }},
  payload: {{
    action: "synchronize",
    after: "1a515913a514d3b246c3445eddfff8fcb0d951b4",
    pull_request: {{
      number: 7,
      head: {{
        sha: "1a515913a514d3b246c3445eddfff8fcb0d951b4",
        ref: "feature/la-colonia-full-crawl-validation",
        repo: {{ full_name: "Jchernand3z19/Portafolio", fork: false }},
      }},
    }},
  }},
  runId: 31130000000,
  serverUrl: "https://github.com",
}};
const core = {{ setFailed: () => undefined }};
const fakeController = {{
  run: async (args) => {{
    await args.github.request("POST /repos/{{owner}}/{{repo}}/actions/workflows/{{workflow_id}}/dispatches", {{
      workflow_id: "precios-supermercados-sps-la-colonia-facet-discovery.yml",
      ref: "main",
      inputs: {{
        request_id: "la-colonia-facet-discovery-001",
        discovery_plan: "catalog_categories_v1",
        delay_seconds: "1.5",
      }},
    }});
    try {{
      await args.github.graphql("mutation addComment {{ addComment }}");
      return;
    }} catch (error) {{
      try {{
        await args.github.rest.issues.createComment({{}});
      }} catch (ignored) {{
        return;
      }}
    }}
  }},
}};
(async () => {{
  await wrapper.runWithController({{ github, context, core }}, fakeController);
  const artifact = JSON.parse(fs.readFileSync("dispatcher-result.json", "utf8"));
  process.stdout.write(JSON.stringify({{ artifact, calls }}));
}})();
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(script), scenario],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_comentario_graphql_exitoso_queda_registrado(tmp_path):
    result = _run(tmp_path, "graphql")
    assert result["artifact"]["comment_published"] is True
    assert result["artifact"]["comment_method"] == "graphql"
    assert result["calls"] == {"dispatch": 1, "graphql": 1, "rest": 0}


def test_fallback_rest_exitoso_queda_registrado(tmp_path):
    result = _run(tmp_path, "rest")
    assert result["artifact"]["comment_published"] is True
    assert result["artifact"]["comment_method"] == "rest"
    assert result["calls"] == {"dispatch": 1, "graphql": 1, "rest": 1}


def test_ambos_comentarios_bloqueados_conservan_dispatch_sin_repetirlo(tmp_path):
    result = _run(tmp_path, "blocked")
    assert result["artifact"]["dispatch_sent"] is True
    assert result["artifact"]["comment_published"] is False
    assert result["artifact"]["comment_method"] is None
    assert result["calls"] == {"dispatch": 1, "graphql": 1, "rest": 1}


def test_pruebas_de_comentarios_no_utilizan_internet():
    text = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.", "urllib", "httpx", "aiohttp", "socket."):
        assert forbidden not in text
