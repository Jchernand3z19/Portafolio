from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import obtener_catalogo_comisariato_los_andes_operativo as runner  # noqa: E402


def test_operational_capture_rejects_unsafe_budgets(tmp_path: Path) -> None:
    common = {
        "output": tmp_path / "snapshot.json",
        "raw_directory": tmp_path / "raw",
        "evidence_output": tmp_path / "evidence.json",
    }
    with pytest.raises(runner.LiveCaptureError, match="delay_below_operational_floor"):
        runner.capture_catalog(**common, delay_seconds=0.49)
    with pytest.raises(runner.LiveCaptureError, match="retry_budget_invalid"):
        runner.capture_catalog(**common, max_retries=runner.MAX_RETRIES + 1)
    with pytest.raises(runner.LiveCaptureError, match="timeout_invalid"):
        runner.capture_catalog(**common, timeout_seconds=61)


def test_operational_capture_builds_complete_offsets_and_final_recheck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(*, url, body, output, **kwargs):
        calls.append((url, output.name))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}", encoding="utf-8")
        if output.name == "store-evidence.json":
            payload = [{"id": 1}]
        else:
            skip = int(url.split("skip=")[1].split("&")[0])
            payload = {
                "totalItems": 205,
                "totalPages": 3,
                "itemPerPage": 100,
                "currentPage": skip // 100 + 1,
                "data": [],
            }
        return payload, {
            "status": 201,
            "retries": 0,
            "url": url,
            "request_body": body,
            "response_file": output.name,
            "response_sha256": "0" * 64,
            "response_bytes": 2,
            "observed_at_utc": "2026-09-04T01:44:36Z",
        }

    def fake_reconcile(directory):
        ledger = json.loads((Path(directory) / "ledger.json").read_text(encoding="utf-8"))
        assert [page["skip"] for page in ledger["pages"]] == [0, 100, 200]
        assert ledger["final_recheck"]["skip"] == 0
        return {
            "store_id": 1,
            "store_name": "COMISARIATO LOS ANDES",
            "office_code": "00",
            "location_one_code": "COR",
            "location_two_code": "501",
            "catalog_products_reported": 205,
            "unique_products_extracted": 205,
            "skus_with_price": 205,
            "availability_counts": {"unknown": 205},
            "promotion_counts": {"promotion": 0, "not_promotion": 205, "unknown": 0},
            "membership_sha256": "1" * 64,
        }

    monkeypatch.setattr(runner, "_request_json", fake_request_json)
    monkeypatch.setattr(runner, "reconcile_capture", fake_reconcile)
    evidence = runner.capture_catalog(
        output=tmp_path / "snapshot.json",
        raw_directory=tmp_path / "raw",
        evidence_output=tmp_path / "evidence.json",
    )
    assert [name for _, name in calls] == [
        "store-evidence.json",
        "page-00000.json",
        "page-00100.json",
        "page-00200.json",
        "final-recheck.json",
    ]
    assert evidence["catalog_products_reported"] == 205
    assert (tmp_path / "snapshot.json").is_file()
    assert json.loads((tmp_path / "evidence.json").read_text())["result"] == "success"


def test_operational_capture_stops_when_catalog_exceeds_hard_request_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_request_json(*, url, body, output, **kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}", encoding="utf-8")
        if output.name == "store-evidence.json":
            payload = [{"id": 1}]
        else:
            payload = {
                "totalItems": runner.PAGE_SIZE * runner.MAX_REQUESTS,
                "totalPages": runner.MAX_REQUESTS,
                "itemPerPage": runner.PAGE_SIZE,
                "currentPage": 1,
                "data": [],
            }
        return payload, {
            "status": 201,
            "retries": 0,
            "url": url,
            "request_body": body,
            "response_file": output.name,
            "response_sha256": "0" * 64,
            "response_bytes": 2,
            "observed_at_utc": "2026-09-04T01:44:36Z",
        }

    monkeypatch.setattr(runner, "_request_json", fake_request_json)
    with pytest.raises(runner.LiveCaptureError, match="catalog_exceeds_request_budget"):
        runner.capture_catalog(
            output=tmp_path / "snapshot.json",
            raw_directory=tmp_path / "raw",
            evidence_output=tmp_path / "evidence.json",
        )
