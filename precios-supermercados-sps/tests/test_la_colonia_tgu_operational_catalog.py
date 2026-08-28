from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo as operational  # noqa: E402
import obtener_catalogo_sps_la_colonia_operativo_v2 as recovery  # noqa: E402
import obtener_catalogo_tgu_la_colonia_operativo as tgu  # noqa: E402


def test_tgu_wrapper_reuses_operational_runner_and_restores_patches(monkeypatch) -> None:
    city_calls: list[tuple[str, int]] = []
    captured: dict[str, object] = {}

    def fake_ensure_city(page, city_name="San Pedro Sula", *, max_dom_reresolutions=1):
        city_calls.append((city_name, max_dom_reresolutions))
        return city_name

    def fake_run_catalog(*, page_size: int, delay_seconds: float):
        assert operational.ensure_operational_city(object(), max_dom_reresolutions=1) == "Tegucigalpa"
        return {
            "catalog_type": "la_colonia_sps_full_read_only",
            "location_id": "la_colonia_sps",
            "city": "San Pedro Sula",
            "page_size": page_size,
            "delay_seconds": delay_seconds,
        }

    def fake_recovery_main(argv):
        captured.update(operational._run_catalog(page_size=50, delay_seconds=1.5))
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(operational, "ensure_operational_city", fake_ensure_city)
    monkeypatch.setattr(operational, "_run_catalog", fake_run_catalog)
    monkeypatch.setattr(recovery, "main", fake_recovery_main)

    assert tgu.main(["--live-read-only", "--allow-full-catalog"]) == 0
    assert city_calls == [("Tegucigalpa", 1)]
    assert captured["catalog_type"] == "la_colonia_tgu_full_read_only"
    assert captured["location_id"] == "la_colonia_tgu"
    assert captured["city"] == "Tegucigalpa"
    assert captured["argv"] == ["--live-read-only", "--allow-full-catalog"]
    assert operational.ensure_operational_city is fake_ensure_city
    assert operational._run_catalog is fake_run_catalog
