from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/repo-run-observer.yml"
REQUEST = REPO_ROOT / ".github/repo-run-observer-request.json"
GITHUB_SCRIPT_SHA = "3a2844b7e9c422d3c10d287c895573f7108da1b3"
TARGET_SHA = "7a0df3c3971a4021862855166e527827035a3ea2"


def _load() -> dict:
    value = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def test_observer_is_one_shot_github_only_and_least_privilege() -> None:
    workflow = _load()
    assert workflow["permissions"] == {
        "actions": "read",
        "contents": "read",
        "statuses": "write",
    }
    assert workflow["on"] == {
        "push": {
            "branches": ["main"],
            "paths": [".github/repo-run-observer-request.json"],
        }
    }
    jobs = workflow["jobs"]
    assert set(jobs) == {"observe"}
    job = jobs["observe"]
    assert job["if"] == (
        "${{ github.repository == 'Jchernand3z19/Portafolio' && "
        "github.ref == 'refs/heads/main' }}"
    )
    assert job["timeout-minutes"] == "3"
    assert "environment" not in job
    steps = job["steps"]
    assert len(steps) == 1
    assert steps[0]["uses"] == f"actions/github-script@{GITHUB_SCRIPT_SHA}"

    raw = WORKFLOW.read_text(encoding="utf-8")
    assert TARGET_SHA in raw
    assert "listWorkflowRunsForRepo" in raw
    assert "createCommitStatus" in raw
    assert "head_sha: targetSha" in raw
    assert "event: 'push'" in raw
    assert "actions/checkout@" not in raw
    assert "id-token" not in raw
    assert "secrets." not in raw
    assert "vars." not in raw
    assert "schedule:" not in raw
    assert "workflow_dispatch:" not in raw
    assert "pull_request_target:" not in raw
    assert "issue_comment:" not in raw
    assert ".workers.dev" not in raw
    assert "lacolonia.com" not in raw
    assert re.search(r"targetSha = '[0-9a-f]{40}'", raw)


def test_observer_request_is_exactly_the_target_sha() -> None:
    text = REQUEST.read_text(encoding="utf-8")
    assert '"schema_version": "repo-run-observer/v1"' in text
    assert f'"target_sha": "{TARGET_SHA}"' in text
