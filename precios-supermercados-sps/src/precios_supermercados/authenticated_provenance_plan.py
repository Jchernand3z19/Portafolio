"""Plan de catálogo ligado al facet discovery autenticado.

La API canónica de esta capa ya no recibe directamente un
``StructuralDiscoveryReport`` aportado por el caller. Parte de un
``VerifiedStructuralDiscovery`` y deriva de nuevo el plan exacto de páginas,
conservando el digest de la evidencia estructural que lo originó.

Sigue siendo una composición offline: ``production_authority`` es siempre
``False`` y no sustituye la verificación productiva del collector.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import NoReturn

from precios_supermercados.edge_provenance import canonical_json_bytes
from precios_supermercados.edge_provenance_plan import (
    DerivedCatalogProvenancePlan,
    DerivedProvenancePlanError,
    derive_catalog_provenance_plan,
)
from precios_supermercados.structural_discovery_manifest import (
    VerifiedStructuralDiscovery,
)

AUTHENTICATED_PROVENANCE_PLAN_SCHEMA_VERSION = "1"
_AUTHENTICATED_PLAN_DOMAIN = b"precios-sps/authenticated-provenance-plan/v1\0"
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class AuthenticatedProvenancePlanError(ValueError):
    """El plan no está ligado de forma coherente al discovery verificado."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise AuthenticatedProvenancePlanError(code, message)


def _text(value: object, code: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(character.isspace() for character in value)
    ):
        _fail(code)
    return value


def _sha1(value: object, code: str) -> str:
    text = _text(value, code, maximum=40)
    if not _SHA1.fullmatch(text):
        _fail(code)
    return text


def _sha256(value: object, code: str) -> str:
    text = _text(value, code, maximum=64)
    if not _SHA256.fullmatch(text):
        _fail(code)
    return text


@dataclass(frozen=True, slots=True)
class AuthenticatedCatalogProvenancePlan:
    """Plan exacto cuya raíz de confianza offline es un discovery autenticado."""

    discovery_digest: str
    run_id: str
    authorization_id: str
    approved_commit_sha: str
    collector_release_id: str
    collector_code_sha256: str
    collector_signing_key_id: str
    plan: DerivedCatalogProvenancePlan
    discovery: VerifiedStructuralDiscovery = field(repr=False, compare=False)
    schema_version: str = AUTHENTICATED_PROVENANCE_PLAN_SCHEMA_VERSION
    production_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != AUTHENTICATED_PROVENANCE_PLAN_SCHEMA_VERSION:
            _fail("authenticated_plan_schema_version_invalid")
        object.__setattr__(
            self,
            "discovery_digest",
            _sha256(self.discovery_digest, "authenticated_plan_discovery_digest_invalid"),
        )
        object.__setattr__(self, "run_id", _text(self.run_id, "authenticated_plan_run_id_invalid"))
        object.__setattr__(
            self,
            "authorization_id",
            _text(self.authorization_id, "authenticated_plan_authorization_id_invalid"),
        )
        object.__setattr__(
            self,
            "approved_commit_sha",
            _sha1(self.approved_commit_sha, "authenticated_plan_commit_sha_invalid"),
        )
        object.__setattr__(
            self,
            "collector_release_id",
            _text(self.collector_release_id, "authenticated_plan_collector_release_id_invalid"),
        )
        object.__setattr__(
            self,
            "collector_code_sha256",
            _sha256(
                self.collector_code_sha256,
                "authenticated_plan_collector_code_sha256_invalid",
            ),
        )
        object.__setattr__(
            self,
            "collector_signing_key_id",
            _text(
                self.collector_signing_key_id,
                "authenticated_plan_collector_signing_key_id_invalid",
            ),
        )
        if not isinstance(self.discovery, VerifiedStructuralDiscovery):
            _fail("authenticated_plan_discovery_invalid")
        if self.discovery.production_authority is not False:
            _fail("authenticated_plan_discovery_authority_invalid")
        if not isinstance(self.plan, DerivedCatalogProvenancePlan):
            _fail("authenticated_plan_derived_plan_invalid")
        if self.plan.production_authority is not False:
            _fail("authenticated_plan_derived_authority_invalid")

        if self.discovery.digest != self.discovery_digest:
            _fail("authenticated_plan_discovery_digest_mismatch")
        if self.discovery.run_id != self.run_id:
            _fail("authenticated_plan_run_id_mismatch")
        if self.discovery.authorization_id != self.authorization_id:
            _fail("authenticated_plan_authorization_id_mismatch")
        if self.discovery.approved_commit_sha != self.approved_commit_sha:
            _fail("authenticated_plan_commit_sha_mismatch")
        if self.discovery.collector_release_id != self.collector_release_id:
            _fail("authenticated_plan_collector_release_id_mismatch")
        if self.discovery.collector_code_sha256 != self.collector_code_sha256:
            _fail("authenticated_plan_collector_code_sha256_mismatch")
        if self.discovery.collector_signing_key_id != self.collector_signing_key_id:
            _fail("authenticated_plan_collector_signing_key_id_mismatch")
        if self.plan.run_id != self.discovery.run_id:
            _fail("authenticated_plan_derived_run_id_mismatch")
        if self.plan.tree_digest != self.discovery.tree_digest:
            _fail("authenticated_plan_tree_digest_mismatch")
        if self.production_authority is not False:
            _fail("authenticated_plan_production_authority_forbidden")

    @property
    def request_count(self) -> int:
        return self.plan.request_count

    @property
    def pages(self):
        return self.plan.pages

    @property
    def primary_pages(self):
        return self.plan.primary_pages

    @property
    def reconciliation_pages(self):
        return self.plan.reconciliation_pages

    def canonical_dict(self) -> dict[str, object]:
        return {
            "approved_commit_sha": self.approved_commit_sha,
            "authorization_id": self.authorization_id,
            "collector_code_sha256": self.collector_code_sha256,
            "collector_release_id": self.collector_release_id,
            "collector_signing_key_id": self.collector_signing_key_id,
            "derived_plan_digest": self.plan.digest,
            "discovery_digest": self.discovery_digest,
            "plan": self.plan.canonical_dict(),
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            _AUTHENTICATED_PLAN_DOMAIN + canonical_json_bytes(self.canonical_dict())
        ).hexdigest()


def derive_authenticated_catalog_provenance_plan(
    discovery: VerifiedStructuralDiscovery,
    *,
    page_size: int,
    primary_traversal_id: str,
    reconciliation_traversal_id: str,
    primary_order_by: str,
    reconciliation_order_by: str,
) -> AuthenticatedCatalogProvenancePlan:
    """Deriva páginas únicamente desde la estructura contenida en el manifest."""

    if not isinstance(discovery, VerifiedStructuralDiscovery):
        _fail("authenticated_plan_discovery_invalid")
    if discovery.production_authority is not False:
        _fail("authenticated_plan_discovery_authority_invalid")
    if not discovery.structure.valid:
        _fail("authenticated_plan_structure_not_valid")
    if discovery.structure.run_id != discovery.run_id:
        _fail("authenticated_plan_structure_run_id_mismatch")
    if discovery.structure.tree_digest != discovery.tree_digest:
        _fail("authenticated_plan_structure_digest_mismatch")

    try:
        plan = derive_catalog_provenance_plan(
            discovery.structure,
            page_size=page_size,
            primary_traversal_id=primary_traversal_id,
            reconciliation_traversal_id=reconciliation_traversal_id,
            primary_order_by=primary_order_by,
            reconciliation_order_by=reconciliation_order_by,
        )
    except DerivedProvenancePlanError as exc:
        raise AuthenticatedProvenancePlanError(f"derived_{exc.code}") from exc

    return AuthenticatedCatalogProvenancePlan(
        discovery_digest=discovery.digest,
        run_id=discovery.run_id,
        authorization_id=discovery.authorization_id,
        approved_commit_sha=discovery.approved_commit_sha,
        collector_release_id=discovery.collector_release_id,
        collector_code_sha256=discovery.collector_code_sha256,
        collector_signing_key_id=discovery.collector_signing_key_id,
        plan=plan,
        discovery=discovery,
    )
