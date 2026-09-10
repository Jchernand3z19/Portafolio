from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ensamblar_adquisicion_diaria.py"
SPEC = importlib.util.spec_from_file_location("ensamblar_adquisicion_diaria", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _handoff(root: Path, retailer: str, run_id: str, attempt: int, *, accepted: bool = True) -> Path:
    artifact = root / f"daily-acquisition-{retailer}-{run_id}-attempt-{attempt}" / "run-artifacts"
    artifact.mkdir(parents=True)
    marker = {
        "schema": module.HANDOFF_SCHEMA,
        "retailer": retailer,
        "run_id": run_id,
        "run_attempt": attempt,
        "accepted": accepted,
    }
    (artifact / module.HANDOFF_FILE).write_text(json.dumps(marker), encoding="utf-8")
    for relative in module.EXPECTED[retailer]:
        path = artifact / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{retailer}:{attempt}:{relative}", encoding="utf-8")
    return artifact


def _complete_root(tmp_path: Path, run_id: str = "34500000000") -> Path:
    root = tmp_path / "handoffs"
    for retailer in module.EXPECTED:
        _handoff(root, retailer, run_id, 1)
    return root


def test_selects_latest_accepted_attempt_per_retailer(tmp_path: Path) -> None:
    run_id = "34500000000"
    root = _complete_root(tmp_path, run_id)
    _handoff(root, "los_andes", run_id, 2)

    selected = module.select_handoffs(root, run_id=run_id)

    assert selected["la_colonia"][0] == 1
    assert selected["los_andes"][0] == 2


def test_failed_attempt_without_acceptance_marker_is_not_reused(tmp_path: Path) -> None:
    run_id = "34500000000"
    root = _complete_root(tmp_path, run_id)
    failed = root / f"daily-acquisition-los_andes-{run_id}-attempt-2" / "run-artifacts"
    failed.mkdir(parents=True)
    for relative in module.EXPECTED["los_andes"]:
        path = failed / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("invalid but complete-looking", encoding="utf-8")

    selected = module.select_handoffs(root, run_id=run_id)

    assert selected["los_andes"][0] == 1


def test_marker_mismatch_fails_closed(tmp_path: Path) -> None:
    run_id = "34500000000"
    root = _complete_root(tmp_path, run_id)
    artifact = _handoff(root, "los_andes", run_id, 2)
    marker_path = artifact / module.HANDOFF_FILE
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["run_id"] = "999"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    with pytest.raises(module.AssemblyError, match="retailer_handoff_marker_mismatch:los_andes:2"):
        module.select_handoffs(root, run_id=run_id)


def test_assemble_reconstructs_all_expected_trees_and_records_attempts(tmp_path: Path) -> None:
    run_id = "34500000000"
    root = _complete_root(tmp_path, run_id)
    _handoff(root, "walmart", run_id, 3)
    output = tmp_path / "assembled"

    evidence = module.assemble(root, output, run_id=run_id)

    assert evidence["run_id"] == run_id
    assert evidence["retailers"]["walmart"]["run_attempt"] == 3
    assert evidence["retailers"]["pricesmart"]["run_attempt"] == 1
    for required in module.EXPECTED.values():
        for relative in required:
            assert (output / relative).is_file()


def test_missing_retailer_and_invalid_run_id_fail_closed(tmp_path: Path) -> None:
    run_id = "34500000000"
    root = _complete_root(tmp_path, run_id)
    target = root / f"daily-acquisition-paiz-{run_id}-attempt-1"
    for child in sorted(target.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    target.rmdir()

    with pytest.raises(module.AssemblyError, match="accepted_retailer_handoff_missing:paiz"):
        module.select_handoffs(root, run_id=run_id)
    with pytest.raises(module.AssemblyError, match="daily_acquisition_run_id_invalid"):
        module.select_handoffs(root, run_id="not-a-run")
