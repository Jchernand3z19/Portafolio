"""Reproduce la primera captura completa sin acceso a la red ni Turso."""
import gzip
import hashlib
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from obtener_catalogo_colonial import Download, collect
from actualizar_mvp_sqlite_la_colonia import validate_snapshot_bytes


def test_full_source_capture_reproduces_accepted_catalog_offline(tmp_path, monkeypatch):
    evidence = ROOT / "reports" / "colonial" / "2026-08-30"
    metadata = json.loads((evidence / "evidence.json").read_text())
    for name, expected in metadata["files"].items():
        assert hashlib.sha256((evidence / name).read_bytes()).hexdigest() == expected
    cache = tmp_path / "cache"
    with tarfile.open(evidence / "raw-capture.tar.gz") as archive:
        archive.extractall(cache, filter="data")
    monkeypatch.setattr("requests.Session.get", lambda *a, **k: pytest.fail("unexpected live request"))
    downloader = Download(tmp_path / "reparsed", datetime(1970, 1, 1, tzinfo=timezone.utc), [cache], 1, 1)
    downloader.offline = True
    try:
        rebuilt = collect(downloader.get)
    finally:
        downloader.session.close()
    raw = gzip.decompress((evidence / "full-catalog.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == metadata["validation"]["snapshot_sha256"]
    accepted = validate_snapshot_bytes(raw, supermarket_id="colonial")
    for field in ("products", "membership_sha256", "availability_counts", "preflight"):
        assert rebuilt[field] == accepted[field]
    assert len(accepted["products"]) == 9205
    assert downloader.metrics["total_requests"] == 0
    assert downloader.metrics["cached_resources_reused"] == 433
