from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/precios-supermercados-sps-bigquery-first-load.yml"
BOOTSTRAP = ROOT / "precios-supermercados-sps/scripts/preparar_bigquery_gcp.sh"


def _workflow() -> dict[str, object]:
    value = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def test_bigquery_first_load_is_manual_and_hard_retired() -> None:
    workflow = _workflow()
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert set(triggers) == {"workflow_dispatch"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"retired"}
    job = jobs["retired"]
    assert job["if"] == "${{ false }}"
    assert job["timeout-minutes"] == "1"
    assert "permissions" not in job

    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "bigquery_first_load_retired_use_turso" in raw
    assert "google-github-actions/auth@" not in raw
    assert "scripts/cargar_snapshot_inicial_bigquery.py" not in raw
    assert "id-token" not in raw
    assert "secrets." not in raw
    assert "vars." not in raw
    assert "schedule:" not in raw


def test_legacy_cloud_bootstrap_remains_least_privilege_and_repo_id_bound() -> None:
    raw = BOOTSTRAP.read_text(encoding="utf-8")

    assert ': "${PROJECT_ID:?' in raw
    assert ': "${DATASET_LOCATION:?' in raw
    assert 'GITHUB_REPOSITORY_ID="1282475205"' in raw
    assert 'GITHUB_MAIN_REF="refs/heads/main"' in raw
    assert 'EXPECTED_ISSUER="https://token.actions.githubusercontent.com"' in raw
    assert "https://token.actions.githubusercontent.com/\"" not in raw
    assert "assertion.repository_id=='${GITHUB_REPOSITORY_ID}'" in raw
    assert "assertion.ref=='${GITHUB_MAIN_REF}'" in raw
    assert "attribute.repository_id=assertion.repository_id" in raw
    assert "roles/bigquery.jobUser" in raw
    assert "roles/bigquery.dataEditor" in raw
    assert "ON SCHEMA" in raw
    assert "roles/iam.workloadIdentityUser" in raw
    assert "roles/bigquery.admin" not in raw
    assert "service-accounts keys create" not in raw
    assert "credentials_json" not in raw
    assert "DATASET_LOCATION" in raw
    assert "dataset_location_mismatch" in raw


def test_legacy_cloud_bootstrap_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(BOOTSTRAP)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
