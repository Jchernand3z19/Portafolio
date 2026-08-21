from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from precios_supermercados.scrapers.la_colonia_graphql import (
    PRODUCT_SEARCH_QUERY,
    build_product_search_url,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDGE_ROOT = PROJECT_ROOT / "edge" / "cloudflare"


def _node() -> str:
    executable = shutil.which("node")
    assert executable is not None, "Node.js es obligatorio para validar el gateway edge"
    version = subprocess.run(
        [executable, "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    major = int(version.removeprefix("v").split(".", maxsplit=1)[0])
    assert major >= 22, f"Node.js 22+ requerido; encontrado {version}"
    return executable


def test_cloudflare_node_suite() -> None:
    result = subprocess.run(
        [
            _node(),
            "--test",
            str(EDGE_ROOT / "test" / "core.test.mjs"),
            str(EDGE_ROOT / "test" / "ledger.test.mjs"),
            str(EDGE_ROOT / "test" / "authorization-ledger.test.mjs"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        "La suite Node del gateway Cloudflare falló.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_python_graphql_url_is_accepted_by_cloudflare_core() -> None:
    source_url = build_product_search_url(
        page=3,
        page_size=50,
        order_by="OrderByPriceDESC",
    )
    payload = {
        "url": source_url,
        "expectedGraphqlQuerySha256": hashlib.sha256(
            PRODUCT_SEARCH_QUERY.encode("utf-8")
        ).hexdigest(),
    }
    result = subprocess.run(
        [_node(), str(EDGE_ROOT / "test" / "fixture-cli.mjs")],
        cwd=PROJECT_ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["from"] == 100
    assert parsed["to"] == 149
    assert parsed["orderBy"] == "OrderByPriceDESC"
    assert len(parsed["canonicalRequestSha256"]) == 64
