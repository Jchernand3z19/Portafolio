from __future__ import annotations

from types import SimpleNamespace

import pytest

import precios_supermercados.authenticated_live_preflight as module
from precios_supermercados.authenticated_provenance_plan import AuthenticatedCatalogProvenancePlan
from precios_supermercados.authenticated_provenance_run import AuthenticatedProvenanceRunError
from precios_supermercados.cloudflare_live_preflight import CloudflareDeploymentEvidence


def _plan() -> AuthenticatedCatalogProvenancePlan:
    plan = object.__new__(AuthenticatedCatalogProvenancePlan)
    object.__setattr__(plan, "production_authority", False)
    return plan


def _deployment() -> CloudflareDeploymentEvidence:
    deployment = object.__new__(CloudflareDeploymentEvidence)
    object.__setattr__(deployment, "production_authority", False)
    return deployment


def test_preflight_deriva_manifest_desde_plan_autenticado(monkeypatch) -> None:
    plan = _plan()
    deployment = _deployment()
    marker = object()
    manifest = SimpleNamespace(digest="a" * 64, production_authority=False)
    assessment = SimpleNamespace(run_manifest_digest=manifest.digest, production_authority=False)
    captured: dict[str, object] = {}

    def fake_builder(*, authenticated_plan, reconciled_pages):
        captured["authenticated_plan"] = authenticated_plan
        captured["reconciled_pages"] = reconciled_pages
        return manifest

    def fake_assess(received_manifest, received_deployment):
        captured["manifest"] = received_manifest
        captured["deployment"] = received_deployment
        return assessment

    monkeypatch.setattr(module, "build_authenticated_edge_provenance_run_manifest", fake_builder)
    monkeypatch.setattr(module, "assess_cloudflare_live_preflight", fake_assess)

    result = module.assess_authenticated_cloudflare_live_preflight(
        authenticated_plan=plan,
        reconciled_pages=[marker],  # type: ignore[list-item]
        deployment=deployment,
    )

    assert result is assessment
    assert captured["authenticated_plan"] is plan
    assert captured["reconciled_pages"] == [marker]
    assert captured["manifest"] is manifest
    assert captured["deployment"] is deployment


def test_traduce_fallo_del_run_autenticado(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: (_ for _ in ()).throw(AuthenticatedProvenanceRunError("run_manifest_request_count_mismatch")),
    )

    with pytest.raises(module.AuthenticatedLivePreflightError) as captured:
        module.assess_authenticated_cloudflare_live_preflight(
            authenticated_plan=_plan(),
            reconciled_pages=[],
            deployment=_deployment(),
        )

    assert captured.value.code == "authenticated_run_run_manifest_request_count_mismatch"


def test_rechaza_assessment_ligado_a_otro_manifest(monkeypatch) -> None:
    manifest = SimpleNamespace(digest="a" * 64, production_authority=False)
    monkeypatch.setattr(module, "build_authenticated_edge_provenance_run_manifest", lambda **_: manifest)
    monkeypatch.setattr(
        module,
        "assess_cloudflare_live_preflight",
        lambda *_: SimpleNamespace(run_manifest_digest="b" * 64, production_authority=False),
    )

    with pytest.raises(module.AuthenticatedLivePreflightError) as captured:
        module.assess_authenticated_cloudflare_live_preflight(
            authenticated_plan=_plan(),
            reconciled_pages=[],
            deployment=_deployment(),
        )

    assert captured.value.code == "assessment_run_manifest_digest_mismatch"


def test_rechaza_inputs_no_autenticados() -> None:
    with pytest.raises(module.AuthenticatedLivePreflightError) as captured:
        module.assess_authenticated_cloudflare_live_preflight(
            authenticated_plan=object(),  # type: ignore[arg-type]
            reconciled_pages=[],
            deployment=_deployment(),
        )
    assert captured.value.code == "authenticated_plan_invalid"

    with pytest.raises(module.AuthenticatedLivePreflightError) as captured:
        module.assess_authenticated_cloudflare_live_preflight(
            authenticated_plan=_plan(),
            reconciled_pages=[],
            deployment=object(),  # type: ignore[arg-type]
        )
    assert captured.value.code == "deployment_evidence_invalid"
