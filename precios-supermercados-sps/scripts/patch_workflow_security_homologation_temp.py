#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "precios-supermercados-sps" / "tests" / "test_workflow_security_audit.py"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"security_patch_contract_failed:{count}:{old[:100]}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'BIGQUERY_FIRST_LOAD_WORKFLOW = "precios-supermercados-sps-bigquery-first-load.yml"\n',
        'BIGQUERY_FIRST_LOAD_WORKFLOW = "precios-supermercados-sps-bigquery-first-load.yml"\n'
        'HOMOLOGATION_REFRESH_WORKFLOW = "precios-supermercados-sps-homologation-refresh.yml"\n',
    )
    text = replace_once(
        text,
        '    BIGQUERY_FIRST_LOAD_WORKFLOW: {"actions": "read", "contents": "read"},\n    TEST_WORKFLOW: {"contents": "read"},\n',
        '    BIGQUERY_FIRST_LOAD_WORKFLOW: {"actions": "read", "contents": "read"},\n'
        '    HOMOLOGATION_REFRESH_WORKFLOW: {"contents": "read"},\n'
        '    TEST_WORKFLOW: {"contents": "read"},\n',
    )
    text = replace_once(
        text,
        '    BIGQUERY_FIRST_LOAD_WORKFLOW: {"workflow_dispatch"},\n    TEST_WORKFLOW: {"workflow_dispatch", "pull_request", "push"},\n',
        '    BIGQUERY_FIRST_LOAD_WORKFLOW: {"workflow_dispatch"},\n'
        '    HOMOLOGATION_REFRESH_WORKFLOW: {"workflow_dispatch", "workflow_run"},\n'
        '    TEST_WORKFLOW: {"workflow_dispatch", "pull_request", "push"},\n',
    )
    text = replace_once(
        text,
        '    MVP_UPDATE_WORKFLOW: {TURSO_DATABASE_URL_SECRET, TURSO_AUTH_TOKEN_SECRET},\n}\n',
        '    MVP_UPDATE_WORKFLOW: {TURSO_DATABASE_URL_SECRET, TURSO_AUTH_TOKEN_SECRET},\n'
        '    HOMOLOGATION_REFRESH_WORKFLOW: {TURSO_DATABASE_URL_SECRET, TURSO_AUTH_TOKEN_SECRET},\n'
        '}\n',
    )
    marker = '''        expected_ref = (\n            "${{ github.workflow_sha }}"\n            if path.name in {COMMAND_WORKFLOW, RECOVERY_WORKFLOW}\n            else "${{ github.sha }}"\n        )\n'''
    special = '''        if path.name == HOMOLOGATION_REFRESH_WORKFLOW:\n            assert len(checkout_steps) == 1\n            assert checkout_steps[0]["with"] == {\n                "ref": "${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}",\n                "persist-credentials": "false",\n            }\n            continue\n\n'''
    text = replace_once(text, marker, special + marker)
    TARGET.write_text(text, encoding="utf-8")
    print("WORKFLOW_SECURITY_HOMOLOGATION_PATCH_OK=1")


if __name__ == "__main__":
    main()
