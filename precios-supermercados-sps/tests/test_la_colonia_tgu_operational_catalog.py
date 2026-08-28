from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo as operational  # noqa: E402
import obtener_catalogo_sps_la_colonia_operativo_v2 as recovery  # noqa: E402
import obtener_catalogo_tgu_la_colonia_operativo as tgu  # noqa: E402


def test_tgu_wrapper_reuses_operational_runner_and_restores_patches(monkeypatch) -> None:
    city_calls: list[tuple[str, int]] = []
    fetch_calls: list[dict[str, object]] = []
    captured: dict[str, object] = {}
    original_location_id = operational.full.passive.MVP_LOCATION_ID
    original_target_city = operational.full.passive.TARGET_CITY

    def fake_ensure_city(page, city_name="San Pedro Sula", *, max_dom_reresolutions=1):
        city_calls.append((city_name, max_dom_reresolutions))
        return city_name

    def fake_fetch_page(**kwargs):
        fetch_calls.append(kwargs)
        return 7

    def fake_run_catalog(*, page_size: int, delay_seconds: float):
        assert operational.ensure_operational_city(
            object(), max_dom_reresolutions=1
        ) == "Tegucigalpa"
        assert operational._fetch_known_total_page(marker="page") == 7
        assert operational.full.passive.MVP_LOCATION_ID == "la_colonia_tgu"
        assert operational.full.passive.TARGET_CITY == "Tegucigalpa"
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
    monkeypatch.setattr(operational, "_fetch_known_total_page", fake_fetch_page)
    monkeypatch.setattr(operational, "_run_catalog", fake_run_catalog)
    monkeypatch.setattr(recovery, "main", fake_recovery_main)

    assert tgu.main(["--live-read-only", "--allow-full-catalog"]) == 0
    assert city_calls == [("Tegucigalpa", 1)]
    assert fetch_calls == [{"marker": "page"}]
    assert captured["catalog_type"] == "la_colonia_tgu_full_read_only"
    assert captured["location_id"] == "la_colonia_tgu"
    assert captured["city"] == "Tegucigalpa"
    assert captured["argv"] == ["--live-read-only", "--allow-full-catalog"]
    assert operational.ensure_operational_city is fake_ensure_city
    assert operational._fetch_known_total_page is fake_fetch_page
    assert operational._run_catalog is fake_run_catalog
    assert operational.full.passive.MVP_LOCATION_ID == original_location_id
    assert operational.full.passive.TARGET_CITY == original_target_city


def test_tgu_retries_only_transient_product_graphql_errors(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def fake_fetch(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise operational.full.FullCatalogError("product_search_graphql_errors")
        return 11

    monkeypatch.setattr(tgu.time, "sleep", sleeps.append)

    assert tgu._with_product_graphql_retry(fake_fetch, page=8) == 11
    assert attempts == 3
    assert sleeps == [
        tgu.GRAPHQL_RETRY_DELAY_SECONDS,
        tgu.GRAPHQL_RETRY_DELAY_SECONDS,
    ]


def test_tgu_does_not_retry_other_failures(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def fake_fetch(**kwargs):
        nonlocal attempts
        attempts += 1
        raise operational.full.FullCatalogError("product_search_http_500")

    monkeypatch.setattr(tgu.time, "sleep", sleeps.append)

    with pytest.raises(operational.full.FullCatalogError, match="product_search_http_500"):
        tgu._with_product_graphql_retry(fake_fetch, page=8)
    assert attempts == 1
    assert sleeps == []


def test_tgu_graphql_retry_exhaustion_remains_fail_closed(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def fake_fetch(**kwargs):
        nonlocal attempts
        attempts += 1
        raise operational.full.FullCatalogError("product_search_graphql_errors")

    monkeypatch.setattr(tgu.time, "sleep", sleeps.append)

    with pytest.raises(
        operational.full.FullCatalogError, match="product_search_graphql_errors"
    ):
        tgu._with_product_graphql_retry(fake_fetch, page=8)
    assert attempts == tgu.MAX_GRAPHQL_RETRIES + 1
    assert sleeps == [tgu.GRAPHQL_RETRY_DELAY_SECONDS] * tgu.MAX_GRAPHQL_RETRIES
