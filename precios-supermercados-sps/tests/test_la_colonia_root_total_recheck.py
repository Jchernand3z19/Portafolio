from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo as operational  # noqa: E402


class _Request:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        return self.payload


class _Context:
    def __init__(self, payload):
        self.request = _Request(payload)


def _diagnostic(total: int) -> dict[str, int]:
    return {
        "partition_quantity_estimate_sum": total,
        "partition_observed_total_sum": total,
        "product_requests_completed": 10,
        "catalog_products_reported": 0,
    }


def _patch_shape(monkeypatch):
    monkeypatch.setattr(
        operational.core,
        "_read_json_response",
        lambda response, *_args, **_kwargs: response,
    )
    monkeypatch.setattr(
        operational.core,
        "_read_shape",
        lambda payload: (payload["total"], 0),
    )


def test_no_recheck_when_initial_total_matches(monkeypatch):
    _patch_shape(monkeypatch)
    context = _Context({"total": 999})
    diagnostic = _diagnostic(9469)
    result = operational._resolve_root_total_after_partitions(
        context=context,
        root_url="root",
        initial_total=9469,
        unique_product_count=9469,
        diagnostic=diagnostic,
    )
    assert result == 9469
    assert context.request.calls == 0


def test_single_recheck_accepts_only_exact_coherent_total(monkeypatch):
    _patch_shape(monkeypatch)
    context = _Context({"total": 9469})
    diagnostic = _diagnostic(9469)
    result = operational._resolve_root_total_after_partitions(
        context=context,
        root_url="root",
        initial_total=9493,
        unique_product_count=9469,
        diagnostic=diagnostic,
    )
    assert result == 9469
    assert context.request.calls == 1
    assert diagnostic["product_requests_completed"] == 11
    assert diagnostic["catalog_products_reported"] == 9469


def test_recheck_stays_fail_closed_when_root_still_disagrees(monkeypatch):
    _patch_shape(monkeypatch)
    context = _Context({"total": 9493})
    diagnostic = _diagnostic(9469)
    with pytest.raises(operational.full.FullCatalogError) as exc:
        operational._resolve_root_total_after_partitions(
            context=context,
            root_url="root",
            initial_total=9493,
            unique_product_count=9469,
            diagnostic=diagnostic,
        )
    assert exc.value.reason == "unique_product_coverage_mismatch"
    assert context.request.calls == 1


def test_recheck_not_attempted_when_partition_signals_disagree(monkeypatch):
    _patch_shape(monkeypatch)
    context = _Context({"total": 9469})
    diagnostic = _diagnostic(9469)
    diagnostic["partition_observed_total_sum"] = 9468
    with pytest.raises(operational.full.FullCatalogError):
        operational._resolve_root_total_after_partitions(
            context=context,
            root_url="root",
            initial_total=9493,
            unique_product_count=9469,
            diagnostic=diagnostic,
        )
    assert context.request.calls == 0
