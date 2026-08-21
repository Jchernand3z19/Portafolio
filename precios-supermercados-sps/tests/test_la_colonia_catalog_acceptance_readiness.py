from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import precios_supermercados.scrapers.la_colonia_catalog_acceptance_readiness as module
from precios_supermercados.canonical_authenticated_provenance_plan import (
    CANONICAL_CATALOG_REQUEST_LIMIT,
)
from precios_supermercados.scrapers.la_colonia_catalog_coverage import CatalogCoverageReport
from precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer import (
    VerifiedCatalogProvenanceRun,
)
from precios_supermercados.structural_discovery_manifest import VerifiedStructuralDiscovery

RUN = "32560000000:1"
AUTH = "authorization-catalog-readiness"
COMMIT = "a" * 40
RELEASE = "release-catalog-readiness-001"
CODE_SHA = "d" * 64
KEY_ID = "cloudflare-ed25519-readiness-v1"
DISCOVERY_DIGEST = "1" * 64
PLAN_DIGEST = "2" * 64
MANIFEST_DIGEST = "3" * 64
TREE_DIGEST = "4" * 64
PRIMARY_ID = f"{RUN}:primary"
RECONCILIATION_ID = f"{RUN}:reconciliation"
TRUST_GATE = "trusted_collector_provenance_unavailable"
AUTHORITY_BLOCKER = "production_authority_not_established"


def _discovery() -> VerifiedStructuralDiscovery:
    value = object.__new__(VerifiedStructuralDiscovery)
    object.__setattr__(value, "run_id", RUN)
    object.__setattr__(value, "authorization_id", AUTH)
    object.__setattr__(value, "approved_commit_sha", COMMIT)
    object.__setattr__(value, "tree_digest", TREE_DIGEST)
    object.__setattr__(value, "structure", object())
    object.__setattr__(value, "production_authority", False)
    return value


def _plan():
    pages = (
        SimpleNamespace(identity=("primary", PRIMARY_ID, "root", "OrderByNameASC", 0, 49, "5" * 64)),
        SimpleNamespace(identity=("reconciliation", RECONCILIATION_ID, "root", "OrderByNameDESC", 0, 49, "6" * 64)),
    )
    return SimpleNamespace(
        digest=PLAN_DIGEST,
        discovery_digest=DISCOVERY_DIGEST,
        run_id=RUN,
        authorization_id=AUTH,
        approved_commit_sha=COMMIT,
        collector_release_id=RELEASE,
        collector_code_sha256=CODE_SHA,
        collector_signing_key_id=KEY_ID,
        request_count=len(pages),
        pages=pages,
        plan=SimpleNamespace(
            primary_traversal_id=PRIMARY_ID,
            reconciliation_traversal_id=RECONCILIATION_ID,
            primary_order_by="OrderByNameASC",
            reconciliation_order_by="OrderByNameDESC",
        ),
    )


def _coverage(*reasons: str) -> CatalogCoverageReport:
    values = tuple(reasons)
    return CatalogCoverageReport(
        partitions_discovered=1,
        partitions_attempted=1,
        partitions_completed=1 if values == (TRUST_GATE,) else 0,
        pages_expected=1,
        pages_attempted=2,
        pages_completed=1 if values == (TRUST_GATE,) else 0,
        products_reported=1,
        products_received=1,
        products_unique=1,
        duplicate_occurrences=0,
        repeated_page_sets=0,
        unexpected_overlaps=0,
        missing_coverage_events=len(values),
        total_changes=0,
        uncategorized_products=0,
        request_limit=CANONICAL_CATALOG_REQUEST_LIMIT,
        coverage_demonstrated=False,
        coverage_reason=";".join(values),
        accepted=False,
        run_id=RUN,
        tree_digest=TREE_DIGEST,
        primary_plan_digest="7" * 64,
        reconciliation_plan_digest="8" * 64,
        _reasons=values,
    )


def _provenance(plan=None) -> VerifiedCatalogProvenanceRun:
    plan = plan or _plan()
    primary = SimpleNamespace(
        run_id=RUN,
        tree_digest=TREE_DIGEST,
        traversal_id=PRIMARY_ID,
        order_by="OrderByNameASC",
    )
    reconciliation = SimpleNamespace(
        run_id=RUN,
        tree_digest=TREE_DIGEST,
        traversal_id=RECONCILIATION_ID,
        order_by="OrderByNameDESC",
    )
    collection = SimpleNamespace(
        plan_digest=PLAN_DIGEST,
        discovery_digest=DISCOVERY_DIGEST,
        primary=primary,
        reconciliation=reconciliation,
        production_authority=False,
    )
    manifest = SimpleNamespace(
        run_id=RUN,
        authorization_id=AUTH,
        approved_commit_sha=COMMIT,
        collector_release_id=RELEASE,
        collector_code_sha256=CODE_SHA,
        collector_signing_key_id=KEY_ID,
        primary_traversal_id=PRIMARY_ID,
        reconciliation_traversal_id=RECONCILIATION_ID,
        primary_order_by="OrderByNameASC",
        reconciliation_order_by="OrderByNameDESC",
        request_count=plan.request_count,
        pages=tuple(SimpleNamespace(expected=page) for page in plan.pages),
        digest=MANIFEST_DIGEST,
        production_authority=False,
    )
    value = object.__new__(VerifiedCatalogProvenanceRun)
    object.__setattr__(value, "collection", collection)
    object.__setattr__(value, "reconciled_pages", tuple(object() for _ in plan.pages))
    object.__setattr__(value, "manifest", manifest)
    object.__setattr__(value, "production_authority", False)
    return value


def _prepare(monkeypatch, *, reasons=(TRUST_GATE,)):
    discovery = _discovery()
    plan = _plan()
    provenance = _provenance(plan)
    object.__setattr__(discovery, "digest", DISCOVERY_DIGEST)
    monkeypatch.setattr(
        module,
        "derive_canonical_authenticated_catalog_plan",
        lambda value: plan,
    )
    captured: dict[str, object] = {}

    def evaluate(structure, primary, reconciliation, *, request_limit):
        captured["structure"] = structure
        captured["primary"] = primary
        captured["reconciliation"] = reconciliation
        captured["request_limit"] = request_limit
        return _coverage(*reasons)

    monkeypatch.setattr(module, "_evaluate_canonical_catalog_coverage", evaluate)
    return discovery, provenance, plan, captured


def test_unico_blocker_trusted_collector_separa_completitud_de_aceptacion(monkeypatch) -> None:
    discovery, provenance, plan, captured = _prepare(monkeypatch)

    result = module.assess_verified_catalog_acceptance_readiness(
        discovery=discovery,
        provenance=provenance,
    )

    assert result.technical_catalog_complete is True
    assert result.ready_for_productive_authority_evidence is True
    assert result.catalog_accepted is False
    assert result.production_authority is False
    assert result.blockers == (TRUST_GATE, AUTHORITY_BLOCKER)
    assert result.discovery_digest == DISCOVERY_DIGEST
    assert result.authenticated_plan_digest == plan.digest
    assert result.provenance_manifest_digest == MANIFEST_DIGEST
    assert result.coverage.accepted is False
    assert captured["request_limit"] == CANONICAL_CATALOG_REQUEST_LIMIT
    assert captured["structure"] is discovery.structure


def test_fallo_real_de_coverage_impide_readiness_productiva(monkeypatch) -> None:
    discovery, provenance, _plan_value, _captured = _prepare(
        monkeypatch,
        reasons=(TRUST_GATE, "global_reconciliation_mismatch"),
    )
    result = module.assess_verified_catalog_acceptance_readiness(
        discovery=discovery,
        provenance=provenance,
    )

    assert result.technical_catalog_complete is False
    assert result.ready_for_productive_authority_evidence is False
    assert result.catalog_accepted is False
    assert result.blockers == (
        "global_reconciliation_mismatch",
        TRUST_GATE,
        AUTHORITY_BLOCKER,
    )


def test_collection_no_puede_pertenecer_a_otro_plan(monkeypatch) -> None:
    discovery, provenance, _plan_value, _captured = _prepare(monkeypatch)
    provenance.collection.plan_digest = "9" * 64

    with pytest.raises(module.CatalogAcceptanceReadinessError) as captured:
        module.assess_verified_catalog_acceptance_readiness(
            discovery=discovery,
            provenance=provenance,
        )
    assert captured.value.code == "readiness_collection_plan_digest_mismatch"


def test_manifest_no_puede_sustituir_una_pagina_del_plan(monkeypatch) -> None:
    discovery, provenance, _plan_value, _captured = _prepare(monkeypatch)
    forged = SimpleNamespace(identity=("primary", PRIMARY_ID, "root", "OrderByNameASC", 50, 99, "0" * 64))
    provenance.manifest.pages = (
        SimpleNamespace(expected=forged),
        provenance.manifest.pages[1],
    )

    with pytest.raises(module.CatalogAcceptanceReadinessError) as captured:
        module.assess_verified_catalog_acceptance_readiness(
            discovery=discovery,
            provenance=provenance,
        )
    assert captured.value.code == "readiness_manifest_page_set_mismatch"


def test_provenance_con_authoridad_fabricada_se_rechaza(monkeypatch) -> None:
    discovery, provenance, _plan_value, _captured = _prepare(monkeypatch)
    object.__setattr__(provenance, "production_authority", True)

    with pytest.raises(module.CatalogAcceptanceReadinessError) as captured:
        module.assess_verified_catalog_acceptance_readiness(
            discovery=discovery,
            provenance=provenance,
        )
    assert captured.value.code == "readiness_provenance_authority_forbidden"


def test_resultado_no_permite_catalog_accepted_true() -> None:
    with pytest.raises(module.CatalogAcceptanceReadinessError) as captured:
        module.VerifiedCatalogAcceptanceReadiness(
            coverage=_coverage(TRUST_GATE),
            discovery_digest=DISCOVERY_DIGEST,
            authenticated_plan_digest=PLAN_DIGEST,
            provenance_manifest_digest=MANIFEST_DIGEST,
            technical_catalog_complete=True,
            ready_for_productive_authority_evidence=True,
            catalog_accepted=True,
            blockers=(TRUST_GATE, AUTHORITY_BLOCKER),
        )
    assert captured.value.code == "readiness_catalog_acceptance_forbidden"


def test_api_no_expone_overrides_de_authority_ni_request_limit() -> None:
    parameters = inspect.signature(
        module.assess_verified_catalog_acceptance_readiness
    ).parameters
    assert tuple(parameters) == ("discovery", "provenance")
    assert "catalog_accepted" not in parameters
    assert "production_authority" not in parameters
    assert "request_limit" not in parameters
