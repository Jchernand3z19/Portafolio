from __future__ import annotations

from types import SimpleNamespace

import pytest

import precios_supermercados.authenticated_provenance_run as module
from precios_supermercados.authenticated_provenance_plan import AuthenticatedCatalogProvenancePlan
from precios_supermercados.edge_provenance_plan import DerivedCatalogProvenancePlan
from precios_supermercados.edge_provenance_run import ExpectedProvenancePage

RUN = "32529000000:1"
AUTH = "authorization-authenticated-run"
COMMIT = "a" * 40
RELEASE = "release-authenticated-run-001"
CODE_SHA = "d" * 64
KEY_ID = "cloudflare-ed25519-v1"


def _plan() -> AuthenticatedCatalogProvenancePlan:
    pages = (
        ExpectedProvenancePage(
            traversal_role="primary",
            traversal_id="primary-auth",
            partition_id="root",
            order_by="OrderByNameASC",
            from_index=0,
            to_index=49,
            request_digest="1" * 64,
        ),
        ExpectedProvenancePage(
            traversal_role="reconciliation",
            traversal_id="reconciliation-auth",
            partition_id="root",
            order_by="OrderByPriceDESC",
            from_index=0,
            to_index=49,
            request_digest="2" * 64,
        ),
    )
    derived = DerivedCatalogProvenancePlan(
        run_id=RUN,
        tree_digest="3" * 64,
        page_size=50,
        primary_traversal_id="primary-auth",
        reconciliation_traversal_id="reconciliation-auth",
        primary_order_by="OrderByNameASC",
        reconciliation_order_by="OrderByPriceDESC",
        pages=pages,
    )

    # La unidad bajo prueba sólo acepta una instancia ya autenticada. Construimos
    # una instancia mínima sin repetir aquí toda la cadena estructural, cubierta
    # exhaustivamente por test_authenticated_provenance_plan.py.
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


def _manifest(plan: AuthenticatedCatalogProvenancePlan, **overrides: object):
    values = {
        "run_id": plan.run_id,
        "authorization_id": plan.authorization_id,
        "approved_commit_sha": plan.approved_commit_sha,
        "collector_release_id": plan.collector_release_id,
        "collector_code_sha256": plan.collector_code_sha256,
        "collector_signing_key_id": plan.collector_signing_key_id,
        "primary_traversal_id": plan.plan.primary_traversal_id,
        "reconciliation_traversal_id": plan.plan.reconciliation_traversal_id,
        "primary_order_by": plan.plan.primary_order_by,
        "reconciliation_order_by": plan.plan.reconciliation_order_by,
        "request_count": plan.request_count,
        "pages": tuple(SimpleNamespace(expected=page) for page in plan.pages),
        "production_authority": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_deriva_expected_pages_exclusivamente_del_plan_autenticado(monkeypatch) -> None:
    plan = _plan()
    captured: dict[str, object] = {}
    manifest = _manifest(plan)

    def fake_builder(*, expected_pages, reconciled_pages):
        captured["expected_pages"] = expected_pages
        captured["reconciled_pages"] = reconciled_pages
        return manifest

    monkeypatch.setattr(module, "build_edge_provenance_run_manifest", fake_builder)
    marker = object()
    result = module.build_authenticated_edge_provenance_run_manifest(
        authenticated_plan=plan,
        reconciled_pages=[marker],  # type: ignore[list-item]
    )

    assert result is manifest
    assert captured["expected_pages"] is plan.pages
    assert captured["reconciled_pages"] == [marker]


def test_rechaza_contexto_del_manifest_que_no_coincide_con_discovery(monkeypatch) -> None:
    plan = _plan()
    monkeypatch.setattr(
        module,
        "build_edge_provenance_run_manifest",
        lambda **_: _manifest(plan, authorization_id="authorization-other"),
    )

    with pytest.raises(module.AuthenticatedProvenanceRunError) as captured:
        module.build_authenticated_edge_provenance_run_manifest(
            authenticated_plan=plan,
            reconciled_pages=[],
        )
    assert captured.value.code == "run_manifest_authorization_id_mismatch"


def test_rechaza_manifest_con_plan_observado_distinto(monkeypatch) -> None:
    plan = _plan()
    forged = ExpectedProvenancePage(
        traversal_role="primary",
        traversal_id="primary-auth",
        partition_id="root",
        order_by="OrderByNameASC",
        from_index=50,
        to_index=99,
        request_digest="5" * 64,
    )
    monkeypatch.setattr(
        module,
        "build_edge_provenance_run_manifest",
        lambda **_: _manifest(
            plan,
            pages=(SimpleNamespace(expected=forged), *tuple(SimpleNamespace(expected=p) for p in plan.pages[1:])),
        ),
    )

    with pytest.raises(module.AuthenticatedProvenanceRunError) as captured:
        module.build_authenticated_edge_provenance_run_manifest(
            authenticated_plan=plan,
            reconciled_pages=[],
        )
    assert captured.value.code == "run_manifest_expected_pages_mismatch"


def test_rechaza_objeto_que_no_es_plan_autenticado() -> None:
    with pytest.raises(module.AuthenticatedProvenanceRunError) as captured:
        module.build_authenticated_edge_provenance_run_manifest(
            authenticated_plan=object(),  # type: ignore[arg-type]
            reconciled_pages=[],
        )
    assert captured.value.code == "authenticated_plan_invalid"
