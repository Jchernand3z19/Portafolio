from __future__ import annotations

import pytest

import precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer as module
from precios_supermercados.cloudflare_observability_verifier import (
    CloudflareObservabilityVerifierClient,
)
from test_la_colonia_verified_catalog_finalizer import (
    _collector,
    _manifest,
    _patch_collection,
    _reconciled,
    _verifier,
)


def test_observability_no_puede_sustituir_la_pagina_crypto_del_ordinal(monkeypatch) -> None:
    collector = _collector()
    _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    observations = collector.observations
    assert observations

    replacement = object()

    def wrong_page(self, page, *, bearer_token):
        return _reconciled(replacement)

    monkeypatch.setattr(
        CloudflareObservabilityVerifierClient,
        "reconcile_page",
        wrong_page,
    )
    manifest_calls = 0

    def manifest_builder(**_):
        nonlocal manifest_calls
        manifest_calls += 1
        return _manifest(collector.authenticated_plan.request_count)

    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        manifest_builder,
    )
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )

    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(collector)

    assert captured.value.code == "catalog_observability_page_identity_mismatch"
    assert manifest_calls == 0
    assert finalizer.finalized is False
