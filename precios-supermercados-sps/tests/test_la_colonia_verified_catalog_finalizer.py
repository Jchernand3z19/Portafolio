from __future__ import annotations

from types import SimpleNamespace

import pytest

import precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer as module
from precios_supermercados.authenticated_provenance_plan import AuthenticatedCatalogProvenancePlan
from precios_supermercados.cloudflare_observability_verifier import (
    CloudflareObservabilityVerifierClient,
    CloudflareObservabilityVerifierError,
)
from precios_supermercados.cloudflare_trace_evidence import PlatformReconciledEdgePage
from precios_supermercados.edge_provenance_plan import DerivedCatalogProvenancePlan
from precios_supermercados.edge_provenance_run import (
    EdgeProvenanceRunManifest,
    ExpectedProvenancePage,
)
from precios_supermercados.scrapers.la_colonia_verified_catalog_transport import (
    VerifiedCatalogCollection,
    VerifiedCatalogEdgeCollector,
    VerifiedCatalogPageObservation,
)

RUN = "32550000000:1"
AUTH = "authorization-catalog-finalizer"
COMMIT = "a" * 40
RELEASE = "release-catalog-finalizer-001"
CODE_SHA = "d" * 64
KEY_ID = "cloudflare-ed25519-finalizer-v1"


class _NoopTransport:
    def post_json(self, path, *, bearer_token, payload):
        raise AssertionError("el test no debe ejecutar el transporte real del verifier")


def _verifier() -> CloudflareObservabilityVerifierClient:
    return CloudflareObservabilityVerifierClient("a" * 32, _NoopTransport())


def _plan() -> AuthenticatedCatalogProvenancePlan:
    pages = (
        ExpectedProvenancePage(
            traversal_role="primary",
            traversal_id=f"{RUN}:primary",
            partition_id="root",
            order_by="OrderByNameASC",
            from_index=0,
            to_index=49,
            request_digest="1" * 64,
        ),
        ExpectedProvenancePage(
            traversal_role="primary",
            traversal_id=f"{RUN}:primary",
            partition_id="root",
            order_by="OrderByNameASC",
            from_index=50,
            to_index=99,
            request_digest="2" * 64,
        ),
        ExpectedProvenancePage(
            traversal_role="reconciliation",
            traversal_id=f"{RUN}:reconciliation",
            partition_id="root",
            order_by="OrderByNameDESC",
            from_index=0,
            to_index=49,
            request_digest="3" * 64,
        ),
        ExpectedProvenancePage(
            traversal_role="reconciliation",
            traversal_id=f"{RUN}:reconciliation",
            partition_id="root",
            order_by="OrderByNameDESC",
            from_index=50,
            to_index=99,
            request_digest="4" * 64,
        ),
    )
    derived = DerivedCatalogProvenancePlan(
        run_id=RUN,
        tree_digest="3" * 64,
        page_size=50,
        primary_traversal_id=f"{RUN}:primary",
        reconciliation_traversal_id=f"{RUN}:reconciliation",
        primary_order_by="OrderByNameASC",
        reconciliation_order_by="OrderByNameDESC",
        pages=pages,
    )
    plan = object.__new__(AuthenticatedCatalogProvenancePlan)
    object.__setattr__(plan, "discovery_digest", "4" * 64)
    object.__setattr__(plan, "run_id", RUN)
    object.__setattr__(plan, "authorization_id", AUTH)
    object.__setattr__(plan, "approved_commit_sha", COMMIT)
    object.__setattr__(plan, "collector_release_id", RELEASE)
    object.__setattr__(plan, "collector_code_sha256", CODE_SHA)
    object.__setattr__(plan, "collector_signing_key_id", KEY_ID)
    object.__setattr__(plan, "plan", derived)
    object.__setattr__(plan, "discovery", None)
    object.__setattr__(plan, "schema_version", "1")
    object.__setattr__(plan, "production_authority", False)
    return plan


def _observation(expected: ExpectedProvenancePage, ordinal: int) -> VerifiedCatalogPageObservation:
    page = SimpleNamespace(
        cryptographic_signature_verified=True,
        production_authority=False,
        marker=f"crypto-page-{ordinal}",
    )
    observation = object.__new__(VerifiedCatalogPageObservation)
    object.__setattr__(observation, "expected", expected)
    object.__setattr__(observation, "page", page)
    object.__setattr__(observation, "raw_evidence", object())
    object.__setattr__(observation, "production_authority", False)
    return observation


def _collector(*, complete: bool = True) -> VerifiedCatalogEdgeCollector:
    plan = _plan()
    observations = [_observation(page, index) for index, page in enumerate(plan.pages)]
    if not complete:
        observations.pop()
    collector = object.__new__(VerifiedCatalogEdgeCollector)
    collector._plan = plan
    collector._observations = observations
    collector._next_index = len(observations)
    return collector


def _collection(plan: AuthenticatedCatalogProvenancePlan) -> VerifiedCatalogCollection:
    value = object.__new__(VerifiedCatalogCollection)
    object.__setattr__(value, "plan_digest", plan.digest)
    object.__setattr__(value, "discovery_digest", plan.discovery_digest)
    object.__setattr__(value, "primary", object())
    object.__setattr__(value, "reconciliation", object())
    object.__setattr__(value, "observations", tuple())
    object.__setattr__(value, "production_authority", False)
    return value


def _reconciled(
    marker: object,
    *,
    physical_evidence_id: str | None = None,
    fetch_span_id: str | None = None,
) -> PlatformReconciledEdgePage:
    marker_name = getattr(marker, "marker", f"page-{id(marker)}")
    trace_evidence = SimpleNamespace(
        physical_evidence_id=physical_evidence_id or f"physical-{marker_name}",
        fetch_span_id=fetch_span_id or f"fetch-{marker_name}",
    )
    value = object.__new__(PlatformReconciledEdgePage)
    object.__setattr__(value, "page", marker)
    object.__setattr__(value, "trace_evidence", trace_evidence)
    object.__setattr__(value, "platform_evidence_reconciled", True)
    object.__setattr__(value, "production_authority", False)
    return value


def _manifest(count: int) -> EdgeProvenanceRunManifest:
    value = object.__new__(EdgeProvenanceRunManifest)
    object.__setattr__(value, "pages", tuple(object() for _ in range(count)))
    object.__setattr__(value, "production_authority", False)
    return value


def _patch_collection(monkeypatch, collector: VerifiedCatalogEdgeCollector) -> VerifiedCatalogCollection:
    result = _collection(collector.authenticated_plan)
    monkeypatch.setattr(
        VerifiedCatalogEdgeCollector,
        "build_collection",
        lambda self: result,
    )
    return result


def test_reconcilia_todas_las_paginas_en_orden_y_cierra_manifest_autenticado(monkeypatch) -> None:
    collector = _collector()
    collection = _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    calls: list[tuple[object, str]] = []

    def fake_reconcile(self, page, *, bearer_token):
        calls.append((page, bearer_token))
        return _reconciled(page)

    monkeypatch.setattr(CloudflareObservabilityVerifierClient, "reconcile_page", fake_reconcile)
    captured: dict[str, object] = {}
    manifest = _manifest(collector.authenticated_plan.request_count)

    def fake_manifest_builder(*, authenticated_plan, reconciled_pages):
        captured["authenticated_plan"] = authenticated_plan
        captured["reconciled_pages"] = reconciled_pages
        return manifest

    monkeypatch.setattr(module, "build_authenticated_edge_provenance_run_manifest", fake_manifest_builder)
    token_calls = 0

    def token_provider() -> str:
        nonlocal token_calls
        token_calls += 1
        return "observability-token"

    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=token_provider,
    )
    result = finalizer.finalize(collector)

    assert result.collection is collection
    assert result.manifest is manifest
    assert result.production_authority is False
    assert tuple(page.page for page in result.reconciled_pages) == tuple(
        observation.page for observation in collector.observations
    )
    assert captured["authenticated_plan"] is collector.authenticated_plan
    assert captured["reconciled_pages"] == result.reconciled_pages
    assert [page for page, _token in calls] == [
        observation.page for observation in collector.observations
    ]
    assert {token for _page, token in calls} == {"observability-token"}
    assert token_calls == 1
    assert finalizer.finalized is True


def test_segunda_finalizacion_del_mismo_collector_es_idempotente_sin_nuevas_consultas(monkeypatch) -> None:
    collector = _collector()
    _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    reconcile_calls = 0

    def fake_reconcile(self, page, *, bearer_token):
        nonlocal reconcile_calls
        reconcile_calls += 1
        return _reconciled(page)

    monkeypatch.setattr(CloudflareObservabilityVerifierClient, "reconcile_page", fake_reconcile)
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: _manifest(collector.authenticated_plan.request_count),
    )
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )

    first = finalizer.finalize(collector)
    second = finalizer.finalize(collector)
    assert second is first
    assert reconcile_calls == collector.authenticated_plan.request_count


def test_finalizer_rechaza_otro_collector_despues_de_quedar_ligado(monkeypatch) -> None:
    first_collector = _collector()
    second_collector = _collector()
    _patch_collection(monkeypatch, first_collector)
    verifier = _verifier()
    monkeypatch.setattr(
        CloudflareObservabilityVerifierClient,
        "reconcile_page",
        lambda self, page, *, bearer_token: _reconciled(page),
    )
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: _manifest(first_collector.authenticated_plan.request_count),
    )
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )
    finalizer.finalize(first_collector)

    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(second_collector)
    assert captured.value.code == "finalizer_already_bound_to_other_collector"


def test_collector_incompleto_falla_antes_de_token_y_observability(monkeypatch) -> None:
    collector = _collector(complete=False)
    verifier = _verifier()
    token_calls = 0

    def token_provider() -> str:
        nonlocal token_calls
        token_calls += 1
        return "observability-token"

    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=token_provider,
    )
    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(collector)
    assert captured.value.code == "verified_catalog_collector_incomplete"
    assert token_calls == 0


def test_fallo_observability_en_primera_pagina_corta_sin_consultar_las_siguientes(monkeypatch) -> None:
    collector = _collector()
    _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    calls = 0

    def fail_first(self, page, *, bearer_token):
        nonlocal calls
        calls += 1
        raise CloudflareObservabilityVerifierError("matching_trace_missing")

    monkeypatch.setattr(CloudflareObservabilityVerifierClient, "reconcile_page", fail_first)
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )

    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(collector)
    assert captured.value.code == "catalog_page_0_observability_matching_trace_missing"
    assert calls == 1
    assert finalizer.finalized is False


def test_physical_evidence_reutilizado_corta_antes_de_paginas_posteriores(monkeypatch) -> None:
    collector = _collector()
    _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    calls: list[object] = []

    def fake_reconcile(self, page, *, bearer_token):
        calls.append(page)
        ordinal = len(calls) - 1
        return _reconciled(
            page,
            physical_evidence_id="physical-reused" if ordinal < 2 else f"physical-{ordinal}",
            fetch_span_id=f"fetch-{ordinal}",
        )

    monkeypatch.setattr(CloudflareObservabilityVerifierClient, "reconcile_page", fake_reconcile)
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: pytest.fail("el manifest no debe construirse después de detectar reuse"),
    )
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )

    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(collector)
    assert captured.value.code == "physical_evidence_reused"
    assert calls == [
        collector.observations[0].page,
        collector.observations[1].page,
    ]
    assert len(calls) < collector.authenticated_plan.request_count
    assert finalizer.finalized is False


def test_fetch_span_reutilizado_corta_antes_de_paginas_posteriores(monkeypatch) -> None:
    collector = _collector()
    _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    calls: list[object] = []

    def fake_reconcile(self, page, *, bearer_token):
        calls.append(page)
        ordinal = len(calls) - 1
        return _reconciled(
            page,
            physical_evidence_id=f"physical-{ordinal}",
            fetch_span_id="fetch-reused" if ordinal < 2 else f"fetch-{ordinal}",
        )

    monkeypatch.setattr(CloudflareObservabilityVerifierClient, "reconcile_page", fake_reconcile)
    monkeypatch.setattr(
        module,
        "build_authenticated_edge_provenance_run_manifest",
        lambda **_: pytest.fail("el manifest no debe construirse después de detectar reuse"),
    )
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )

    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(collector)
    assert captured.value.code == "physical_fetch_span_reused"
    assert calls == [
        collector.observations[0].page,
        collector.observations[1].page,
    ]
    assert len(calls) < collector.authenticated_plan.request_count
    assert finalizer.finalized is False


def test_manifest_rechazado_no_se_convierte_en_resultado_final(monkeypatch) -> None:
    collector = _collector()
    _patch_collection(monkeypatch, collector)
    verifier = _verifier()
    monkeypatch.setattr(
        CloudflareObservabilityVerifierClient,
        "reconcile_page",
        lambda self, page, *, bearer_token: _reconciled(page),
    )

    def fail_manifest(**_):
        raise module.AuthenticatedProvenanceRunError("run_manifest_receipt_reused")

    monkeypatch.setattr(module, "build_authenticated_edge_provenance_run_manifest", fail_manifest)
    finalizer = module.VerifiedCatalogProvenanceFinalizer(
        verifier,
        bearer_token_provider=lambda: "observability-token",
    )
    with pytest.raises(module.VerifiedCatalogFinalizationError) as captured:
        finalizer.finalize(collector)
    assert captured.value.code == "catalog_run_manifest_run_manifest_receipt_reused"
    assert finalizer.finalized is False
