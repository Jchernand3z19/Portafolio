from __future__ import annotations

from types import SimpleNamespace

import pytest

import precios_supermercados.authenticated_settings_preflight as module
from precios_supermercados.authenticated_provenance_plan import AuthenticatedCatalogProvenancePlan
from precios_supermercados.authenticated_provenance_run import AuthenticatedProvenanceRunError
from precios_supermercados.cloudflare_live_preflight import CloudflareDeploymentEvidence
from precios_supermercados.cloudflare_script_settings import CloudflareScriptSettingsEvidence


def _plan() -> AuthenticatedCatalogProvenancePlan:
    value = object.__new__(AuthenticatedCatalogProvenancePlan)
    object.__setattr__(value, "production_authority", False)
    return value


def _deployment() -> CloudflareDeploymentEvidence:
    value = object.__new__(CloudflareDeploymentEvidence)
    object.__setattr__(value, "production_authority", False)
    return value


def _settings() -> CloudflareScriptSettingsEvidence:
    value = object.__new__(CloudflareScriptSettingsEvidence)
    object.__setattr__(value, "production_authority", False)
    return value


def test_deriva_manifest_antes_de_ligar_script_settings(monkeypatch) -> None:
    manifest = SimpleNamespace(production_authority=False)
    assessment = SimpleNamespace(production_authority=False)
    captured: dict[str, object] = {}

    def fake_builder(*, authenticated_plan, reconciled_pages):
        captured["authenticated_plan"] = authenticated_plan
        captured["reconciled_pages"] = reconciled_pages
        return manifest

    def fake_binding(*, manifest, deployment, settings):
        captured["manifest"] = manifest
        captured["deployment"] = deployment
        captured["settings"] = settings
        return assessment

    monkeypatch.setattr(module, "build_authenticated_edge_provenance_run_manifest", fake_builder)
    monkeypatch.setattr(module, "bind_script_settings_to_preflight", fake_binding)

    plan = _plan()
    deployment = _deployment()
    settings = _settings()
    marker = object()
    result = module.bind_authenticated_script_settings_preflight(
        authenticated_plan=plan,
        reconciled_pages=[marker],  # type: ignore[list-item]
        deployment=deployment,
        settings=settings,
    )

    assert result is assessment
    assert captured["authenticated_plan"] is plan
    assert captured["reconciled_pages"] == [marker]
    assert captured["manifest"] is manifest
    assert captured["deployment"] is deployment
    assert captured["settings"] is settings


def test_traduce_fallo_del_run_autenticado(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: (_ for _ in ()).throw(AuthenticatedProvenanceRunError("run_manifest_pages_missing")),
    )

    with pytest.raises(module.AuthenticatedSettingsPreflightError) as captured:
        module.bind_authenticated_script_settings_preflight(
            authenticated_plan=_plan(),
            reconciled_pages=[],
            deployment=_deployment(),
            settings=_settings(),
        )

    assert captured.value.code == "authenticated_run_run_manifest_pages_missing"


def test_rechaza_assessment_con_autoridad(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: SimpleNamespace(production_authority=False),
    )
    monkeypatch.setattr(
        module,
        "bind_script_settings_to_preflight",
        lambda **_: SimpleNamespace(production_authority=True),
    )

    with pytest.raises(module.AuthenticatedSettingsPreflightError) as captured:
        module.bind_authenticated_script_settings_preflight(
            authenticated_plan=_plan(),
            reconciled_pages=[],
            deployment=_deployment(),
            settings=_settings(),
        )

    assert captured.value.code == "assessment_authority_invalid"


def test_rechaza_settings_no_autenticados() -> None:
    with pytest.raises(module.AuthenticatedSettingsPreflightError) as captured:
        module.bind_authenticated_script_settings_preflight(
            authenticated_plan=_plan(),
            reconciled_pages=[],
            deployment=_deployment(),
            settings=object(),  # type: ignore[arg-type]
        )
    assert captured.value.code == "settings_evidence_invalid"
