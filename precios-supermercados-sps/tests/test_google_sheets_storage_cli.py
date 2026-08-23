from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inicializar_google_sheets.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("storage_cli_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_error_code_rejects_values_that_could_leak_or_inject() -> None:
    module = load_module()

    class SafeError(Exception):
        code = "missing_precios_sps_google_service_account_json"

    class UnsafeError(Exception):
        code = "access denied: secret=abc\nother=value"

    assert module._safe_error_code(SafeError()) == (
        "missing_precios_sps_google_service_account_json"
    )
    assert module._safe_error_code(UnsafeError()) == (
        "storage_bootstrap_unexpected_error"
    )


def test_github_outputs_are_closed_sanitized_values(tmp_path, monkeypatch) -> None:
    module = load_module()
    output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    assert module._write_github_outputs(
        result="error",
        error_code="managed_sheet_header_mismatch",
        wrote=None,
    ) is True

    assert output.read_text(encoding="utf-8") == (
        "result=error\n"
        "error_code=managed_sheet_header_mismatch\n"
        "wrote=unknown\n"
    )
    assert module._write_github_outputs(
        result="error",
        error_code="unsafe\nvalue",
        wrote=None,
    ) is False


def test_github_output_channel_failure_does_not_replace_cli_result(tmp_path, monkeypatch) -> None:
    module = load_module()
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "missing" / "output.txt"))

    assert module._write_github_outputs(
        result="error",
        error_code="storage_job_failed",
        wrote=None,
    ) is False
    assert module._report_error("storage_job_failed", exit_code=2) == 2
