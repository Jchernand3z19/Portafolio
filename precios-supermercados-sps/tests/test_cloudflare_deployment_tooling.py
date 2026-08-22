from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDGE_ROOT = PROJECT_ROOT / "edge" / "cloudflare"
RUNBOOK = PROJECT_ROOT / "docs" / "cloudflare-controlled-probe-runbook.md"
WRANGLER_VERSION = "4.125.0"
PINNED_WRANGLER = f"npx --yes wrangler@{WRANGLER_VERSION}"


def test_wrangler_cli_is_pinned_and_no_productive_deploy_script_exists() -> None:
    package = json.loads((EDGE_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert scripts["wrangler"] == PINNED_WRANGLER
    assert scripts["deploy:probe-origin"] == (
        f"{PINNED_WRANGLER} deploy --config wrangler.probe-origin.json"
    )
    assert "deploy:probe" not in scripts
    assert "deploy:production" not in scripts
    assert all(" --config wrangler.json" not in value for value in scripts.values())


def test_probe_runbook_uses_only_the_pinned_wrangler_entrypoint() -> None:
    raw = RUNBOOK.read_text(encoding="utf-8")

    assert f"wrangler = {PINNED_WRANGLER}" in raw
    assert "npm run wrangler -- --version" in raw
    assert "npm run deploy:probe-origin" in raw
    assert (
        "npm run wrangler -- deploy --config wrangler.probe.json --secrets-file"
        in raw
    )
    assert "npx wrangler deploy" not in raw
    assert "npx wrangler@latest" not in raw
    assert "4.125.0" in raw


def test_cloudflare_local_secret_and_state_files_are_ignored() -> None:
    ignored = {
        line.strip()
        for line in (EDGE_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        "node_modules/",
        ".wrangler/",
        ".dev.vars",
        ".dev.vars.*",
        "*.secrets.json",
        "*.secrets.env",
        ".wrangler-secrets-*",
    }.issubset(ignored)
