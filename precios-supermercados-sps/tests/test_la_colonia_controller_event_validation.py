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
VALID_SHA = "1a515913a514d3b246c3445eddfff8fcb0d951b4"


def _validate(tmp_path: Path, **overrides):
    node = shutil.which("node")
    assert node is not None
    context = {
        "eventName": "pull_request_target",
        "payload": {
            "action": "synchronize",
            "after": VALID_SHA,
            "pull_request": {
                "number": 7,
                "head": {
                    "sha": VALID_SHA,
                    "ref": "feature/la-colonia-full-crawl-validation",
                    "repo": {
                        "full_name": "Jchernand3z19/Portafolio",
                        "fork": False,
                    },
                },
            },
        },
    }
    for dotted, value in overrides.items():
        if dotted == "event_name":
            context["eventName"] = value
        elif dotted == "action":
            context["payload"]["action"] = value
        elif dotted == "pr_number":
            context["payload"]["pull_request"]["number"] = value
        elif dotted == "head_sha":
            context["payload"]["after"] = value
            context["payload"]["pull_request"]["head"]["sha"] = value
        elif dotted == "fork":
            context["payload"]["pull_request"]["head"]["repo"]["fork"] = value
        elif dotted == "head_repo":
            context["payload"]["pull_request"]["head"]["repo"]["full_name"] = value
        else:
            raise AssertionError(dotted)

    script = tmp_path / "validate-event.js"
    script.write_text(
        "\n".join(
            [
                '"use strict";',
                f"const wrapper = require({json.dumps(str(WRAPPER))});",
                f"const context = {json.dumps(context)};",
                "const result = wrapper.validateExpectedEvent(context);",
                "process.stdout.write(JSON.stringify(result));",
            ]
        ),
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
    return json.loads(completed.stdout)


def test_evento_pull_request_target_synchronize_de_pr_7_es_valido(tmp_path):
    assert _validate(tmp_path) is None


def test_accion_distinta_es_rechazada(tmp_path):
    assert "acción" in _validate(tmp_path, action="opened")


def test_evento_distinto_es_rechazado(tmp_path):
    assert "evento" in _validate(tmp_path, event_name="pull_request")


def test_pr_distinto_es_rechazado(tmp_path):
    assert "Pull Request" in _validate(tmp_path, pr_number=8)


def test_fork_es_rechazado(tmp_path):
    assert "forks" in _validate(tmp_path, fork=True, head_repo="other/Portafolio")


def test_head_sha_invalido_es_rechazado(tmp_path):
    assert "SHA" in _validate(tmp_path, head_sha="invalid")


def test_validacion_de_evento_no_utiliza_internet():
    text = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.", "urllib", "httpx", "aiohttp", "socket."):
        assert forbidden not in text
