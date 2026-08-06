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


def test_resultado_rechazado_con_nulls_se_normaliza_para_el_observador(tmp_path):
    node = shutil.which("node")
    assert node is not None
    script = tmp_path / "normalize.js"
    script.write_text(
        f"""
"use strict";
const fs = require("fs");
const wrapper = require({json.dumps(str(WRAPPER))});
fs.writeFileSync("dispatcher-result.json", JSON.stringify({{
  accepted: false,
  request_id: null,
  mode: null,
  workflow: null,
  pr_number: 7,
  head_sha: "1a515913a514d3b246c3445eddfff8fcb0d951b4",
  ref: "feature/la-colonia-full-crawl-validation",
  dispatch_sent: false,
  live_run_id: null,
  live_run_url: null,
  comment_published: true,
  comment_method: "rest",
  controller_run_id: "31130000000",
  controller_url: "https://example.invalid/controller",
  reason: "Solicitud rechazada.",
  warnings: []
}}, null, 2));
wrapper.normalizePersistedResult();
process.stdout.write(fs.readFileSync("dispatcher-result.json", "utf8"));
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(script)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    artifact = json.loads(completed.stdout)
    assert artifact["accepted"] is False
    assert artifact["dispatch_sent"] is False
    assert "mode" not in artifact
    assert "workflow" not in artifact
    assert artifact["controller_run_id"] == "31130000000"


def test_normalizacion_no_utiliza_internet():
    text = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.", "urllib", "httpx", "aiohttp", "socket."):
        assert forbidden not in text
