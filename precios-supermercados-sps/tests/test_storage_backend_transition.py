from __future__ import annotations

from pathlib import Path

from precios_supermercados.bigquery_contract import PRECIOS_HISTORICOS
from precios_supermercados.google_bigquery_client import GoogleCloudBigQueryClient
from precios_supermercados.storage_contract import (
    ACTIVE_STORAGE_BACKEND,
    ACTIVE_STORAGE_TABLE_NAMES,
    LEGACY_BIGQUERY_TABLE_NAMES,
)
from precios_supermercados.turso_contract import TURSO_TABLE_NAMES


REPO_ROOT = Path(__file__).resolve().parents[2]
SHEETS_WORKFLOW = (
    REPO_ROOT
    / ".github"
    / "workflows"
    / "precios-supermercados-sps-google-sheets-storage.yml"
)


def test_turso_contract_is_active_and_previous_backends_are_not_productive():
    assert ACTIVE_STORAGE_BACKEND == "turso"
    assert ACTIVE_STORAGE_TABLE_NAMES == TURSO_TABLE_NAMES
    assert set(ACTIVE_STORAGE_TABLE_NAMES).isdisjoint(LEGACY_BIGQUERY_TABLE_NAMES)

    source = SHEETS_WORKFLOW.read_text(encoding="utf-8")
    assert 'handle.write("allowed=false\\n")' in source
    assert 'handle.write("allowed=true\\n")' not in source
    assert "needs.preflight.outputs.allowed == 'true'" in source
    assert "PRECIOS_SPS_GOOGLE_SERVICE_ACCOUNT_JSON" in source


def test_legacy_bigquery_real_client_guard_remains_regression_verified():
    sql = GoogleCloudBigQueryClient._immutable_guard_sql(
        spec=PRECIOS_HISTORICOS,
        target="project.dataset.precios_historicos",
        staging_ref="project.dataset._stg_precios_historicos_deadbeef",
        join="T.`price_observation_id` = S.`price_observation_id`",
    )

    assert sql.startswith("SELECT IF(COUNTIF(")
    assert "IS DISTINCT FROM" in sql
    assert "ASSERT" not in sql
    assert "immutable_conflict:precios_historicos" in sql
    assert sql.endswith(";")
