from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "obtener_catalogo_sps_la_colonia_particionado_v4.py"
spec = importlib.util.spec_from_file_location("city_retry_runner", SCRIPT)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class FakePage:
    def __init__(self) -> None:
        self.reload_calls = 0
        self.goto_calls = 0
        self.wait_calls = 0

    def reload(self, **kwargs):
        self.reload_calls += 1

    def goto(self, *args, **kwargs):
        self.goto_calls += 1

    def wait_for_timeout(self, value):
        self.wait_calls += 1


def test_retries_target_city_not_found_exactly_once() -> None:
    calls = []

    def original(page, context, collector):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("target_city_not_found")
        return "ok"

    page = FakePage()
    wrapped = runner._single_city_reresolution_wrapper(original)
    assert wrapped(page, object(), object()) == "ok"
    assert len(calls) == 2
    assert page.reload_calls == 1
    assert page.goto_calls == 0
    assert page.wait_calls == 1


def test_does_not_retry_unrelated_error() -> None:
    page = FakePage()

    def original(page, context, collector):
        raise RuntimeError("different_failure")

    wrapped = runner._single_city_reresolution_wrapper(original)
    with pytest.raises(RuntimeError, match="different_failure"):
        wrapped(page, object(), object())
    assert page.reload_calls == 0


def test_second_city_miss_becomes_controlled_full_catalog_error() -> None:
    page = FakePage()

    def original(page, context, collector):
        raise RuntimeError("target_city_not_found")

    wrapped = runner._single_city_reresolution_wrapper(original)
    with pytest.raises(
        runner.brand.frontier.base.full.FullCatalogError,
        match="target_city_not_found_after_single_reresolution",
    ):
        wrapped(page, object(), object())
    assert page.reload_calls == 1
