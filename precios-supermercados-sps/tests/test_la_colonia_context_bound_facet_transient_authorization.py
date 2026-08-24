from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "precios-supermercados-sps/scripts/ejecutar_facets_context_bound_la_colonia_autorizado.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("transient_facet_authorization", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _trusted_push_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "Jchernand3z19/Portafolio")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv(
        "GITHUB_WORKFLOW_REF",
        "Jchernand3z19/Portafolio/.github/workflows/"
        "precios-supermercados-sps-la-colonia-live.yml@refs/heads/main",
    )
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "32780000000")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")


def test_marker_autorizado_es_contrato_cerrado(tmp_path: Path) -> None:
    module = _module()
    runtime = module._load_runtime()
    marker = tmp_path / "authorization.json"
    marker.write_text(
        json.dumps(module.EXPECTED_AUTHORIZATION, ensure_ascii=False),
        encoding="utf-8",
    )
    module._validate_authorization_file(runtime, marker)


def test_marker_con_scope_ampliado_falla_cerrado(tmp_path: Path) -> None:
    module = _module()
    runtime = module._load_runtime()
    marker = tmp_path / "authorization.json"
    payload = dict(module.EXPECTED_AUTHORIZATION)
    payload["catalog_crawl"] = True
    marker.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(runtime.FacetLiveEntrypointSafetyError) as exc:
        module._validate_authorization_file(runtime, marker)
    assert exc.value.code == "authorization_file_contract_mismatch"


def test_contexto_solo_acepta_push_main_del_workflow_exacto(monkeypatch) -> None:
    module = _module()
    runtime = module._load_runtime()
    _trusted_push_env(monkeypatch)
    assert module._trusted_push_context(runtime) == ("32780000000", 1, "a" * 40)

    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    with pytest.raises(runtime.FacetLiveEntrypointSafetyError) as exc:
        module._trusted_push_context(runtime)
    assert exc.value.code == "github_event_not_authorized_push"


def test_autorizacion_transitoria_no_cubre_crawl_ni_persistencia() -> None:
    module = _module()
    assert module.EXPECTED_AUTHORIZATION["max_requests"] == 2
    assert module.EXPECTED_AUTHORIZATION["concurrency"] == 1
    assert module.EXPECTED_AUTHORIZATION["max_retries"] == 0
    assert module.EXPECTED_AUTHORIZATION["catalog_crawl"] is False
    assert module.EXPECTED_AUTHORIZATION["commercial_persistence"] is False
    assert module.EXPECTED_AUTHORIZATION["production_authority"] is False
    assert module.EXPECTED_AUTHORIZATION["catalog_accepted"] is False
    assert module.EXPECTED_AUTHORIZATION["extraction_enabled"] is False
