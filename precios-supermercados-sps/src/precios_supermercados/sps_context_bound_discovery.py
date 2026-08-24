"""Prueba offline de que un discovery estructural proviene del contexto SPS firmado.

``VerifiedStructuralDiscovery`` conserva la estructura y la evidencia física
reconciliada, pero históricamente no serializa los campos de ubicación del receipt
estructural v2. Esta capa no reinterpreta el manifest ni confía en un booleano del
caller: vuelve a ligar sus dos records a las observaciones criptográficas exactas
y al ``SpsStructuralFacetPlan`` que produjo los requests context-bound.

El resultado no contiene el ``regionId`` raw ni concede autoridad productiva. El
plan privado se conserva sólo para que una capa de transporte posterior pueda
derivar material de request sin volver a pedir al caller datos de ubicación.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NoReturn

from precios_supermercados.edge_structural_observation import (
    CryptographicallyVerifiedStructuralObservation,
)
from precios_supermercados.scrapers.la_colonia_sps_facet_context import (
    ConfirmedSpsFacetBinding,
    RequestContextPlacement,
    SpsFacetContextError,
    confirmed_sps_facet_binding,
)
from precios_supermercados.scrapers.la_colonia_sps_structural_plan import (
    SpsStructuralFacetPlan,
)
from precios_supermercados.structural_discovery_manifest import (
    StructuralObservationRecord,
    VerifiedStructuralDiscovery,
)


class SpsContextBoundDiscoveryError(ValueError):
    """La evidencia estructural no demuestra de forma cerrada el contexto SPS."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise SpsContextBoundDiscoveryError(code, message)


@dataclass(frozen=True, slots=True)
class VerifiedSpsStructuralContext:
    """Manifest estructural enlazado a dos receipts contextuales v2 de SPS."""

    discovery: VerifiedStructuralDiscovery
    location_id: str
    binding_source_key: str
    binding_evidence: str
    context_fingerprint: str
    context_placement: RequestContextPlacement
    context_wire_key: str
    context_value_path: tuple[str, ...]
    root_wire_request_fingerprint: str
    category_tree_wire_request_fingerprint: str
    _plan: SpsStructuralFacetPlan = field(repr=False, compare=False)
    production_authority: bool = False
    catalog_accepted: bool = False
    extraction_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.discovery, VerifiedStructuralDiscovery):
            _fail("structural_discovery_invalid")
        if not isinstance(self._plan, SpsStructuralFacetPlan):
            _fail("sps_structural_plan_invalid")
        if self.location_id != "la_colonia_sps":
            _fail("sps_location_id_invalid")
        if self.location_id != self._plan.location_id:
            _fail("sps_plan_location_mismatch")
        if self.binding_source_key != self._plan.binding_source_key:
            _fail("sps_plan_binding_source_mismatch")
        if self.binding_evidence != self._plan.binding_evidence:
            _fail("sps_plan_binding_evidence_mismatch")
        if self.context_fingerprint != self._plan.context_fingerprint:
            _fail("sps_plan_context_fingerprint_mismatch")
        if self.context_placement is not self._plan.placement:
            _fail("sps_plan_context_placement_mismatch")
        if self.context_wire_key != self._plan.wire_key:
            _fail("sps_plan_context_wire_key_mismatch")
        if self.context_value_path != self._plan.value_path:
            _fail("sps_plan_context_value_path_mismatch")
        if self.root_wire_request_fingerprint != self._plan.requests[0].wire_request_fingerprint:
            _fail("sps_plan_root_wire_fingerprint_mismatch")
        if (
            self.category_tree_wire_request_fingerprint
            != self._plan.requests[1].wire_request_fingerprint
        ):
            _fail("sps_plan_tree_wire_fingerprint_mismatch")
        if self.production_authority is not False:
            _fail("sps_context_authority_forbidden")
        if self.catalog_accepted is not False:
            _fail("sps_context_catalog_acceptance_forbidden")
        if self.extraction_enabled is not False:
            _fail("sps_context_extraction_forbidden")

    @property
    def plan_digest(self) -> str:
        return self._plan.digest

    @property
    def discovery_digest(self) -> str:
        return self.discovery.digest

    def public_dict(self) -> dict[str, object]:
        return {
            "binding_evidence": self.binding_evidence,
            "binding_source_key": self.binding_source_key,
            "catalog_accepted": False,
            "category_tree_wire_request_fingerprint": self.category_tree_wire_request_fingerprint,
            "context_fingerprint": self.context_fingerprint,
            "context_placement": self.context_placement.value,
            "context_value_path": list(self.context_value_path),
            "context_wire_key": self.context_wire_key,
            "discovery_digest": self.discovery_digest,
            "extraction_enabled": False,
            "location_id": self.location_id,
            "plan_digest": self.plan_digest,
            "production_authority": False,
            "raw_values_exposed": False,
            "root_wire_request_fingerprint": self.root_wire_request_fingerprint,
        }

    def _private_plan_for_transport(self) -> SpsStructuralFacetPlan:
        """Sólo para módulos de transporte auditados; nunca serializa el raw value."""

        return self._plan


def _record_matches_observation(
    record: StructuralObservationRecord,
    observation: CryptographicallyVerifiedStructuralObservation,
    *,
    code_prefix: str,
) -> None:
    if not isinstance(record, StructuralObservationRecord):
        _fail(f"{code_prefix}_record_invalid")
    if not isinstance(observation, CryptographicallyVerifiedStructuralObservation):
        _fail(f"{code_prefix}_observation_invalid")
    if observation.cryptographic_signature_verified is not True:
        _fail(f"{code_prefix}_signature_unverified")
    if observation.production_authority is not False:
        _fail(f"{code_prefix}_authority_forbidden")

    verified = observation.verified_receipt
    payload = verified.receipt.payload
    pairs = (
        (record.request_kind, payload.request_kind, "request_kind"),
        (record.request_digest, payload.request_digest, "request_digest"),
        (record.request_id, payload.request_id, "request_id"),
        (record.reservation_id, payload.reservation_id, "reservation_id"),
        (record.nonce, payload.nonce, "nonce"),
        (record.receipt_digest, verified.receipt_digest, "receipt_digest"),
        (
            record.public_key_spki_sha256,
            verified.public_key_spki_sha256,
            "public_key_spki_sha256",
        ),
        (record.raw_response_sha256, payload.raw_response_sha256, "raw_response_sha256"),
        (record.response_body_bytes, payload.response_body_bytes, "response_body_bytes"),
        (
            record.physical_started_at_utc,
            payload.physical_started_at_utc,
            "physical_started_at_utc",
        ),
        (
            record.response_completed_at_utc,
            payload.response_completed_at_utc,
            "response_completed_at_utc",
        ),
    )
    for expected, actual, label in pairs:
        if expected != actual:
            _fail(f"{code_prefix}_{label}_mismatch")


def _require_manifest_run_context(
    discovery: VerifiedStructuralDiscovery,
    observation: CryptographicallyVerifiedStructuralObservation,
    *,
    code_prefix: str,
) -> None:
    payload = observation.verified_receipt.receipt.payload
    pairs = (
        (discovery.run_id, payload.run_id, "run_id"),
        (discovery.authorization_id, payload.authorization_id, "authorization_id"),
        (
            discovery.approved_commit_sha,
            payload.approved_commit_sha,
            "approved_commit_sha",
        ),
        (discovery.github_repository, payload.github_repository, "github_repository"),
        (
            discovery.github_repository_id,
            payload.github_repository_id,
            "github_repository_id",
        ),
        (discovery.github_ref, payload.github_ref, "github_ref"),
        (
            discovery.github_workflow_ref,
            payload.github_workflow_ref,
            "github_workflow_ref",
        ),
        (
            discovery.github_environment,
            payload.github_environment,
            "github_environment",
        ),
        (discovery.github_run_id, payload.github_run_id, "github_run_id"),
        (
            discovery.github_run_attempt,
            payload.github_run_attempt,
            "github_run_attempt",
        ),
        (discovery.oidc_subject, payload.oidc_subject, "oidc_subject"),
        (
            discovery.collector_provider,
            payload.collector_provider,
            "collector_provider",
        ),
        (
            discovery.collector_principal,
            payload.collector_principal,
            "collector_principal",
        ),
        (
            discovery.collector_release_id,
            payload.collector_release_id,
            "collector_release_id",
        ),
        (
            discovery.collector_code_sha256,
            payload.collector_code_sha256,
            "collector_code_sha256",
        ),
        (
            discovery.collector_signing_key_id,
            payload.signing_key_id,
            "signing_key_id",
        ),
    )
    for expected, actual, label in pairs:
        if expected != actual:
            _fail(f"{code_prefix}_{label}_mismatch")


def _require_signed_location(
    observation: CryptographicallyVerifiedStructuralObservation,
    plan: SpsStructuralFacetPlan,
    *,
    request_index: int,
    code_prefix: str,
) -> None:
    payload = observation.verified_receipt.receipt.payload
    if payload.location_context_bound is not True:
        _fail(f"{code_prefix}_location_context_downgrade")
    plan_request = plan.requests[request_index]
    expected = (
        (payload.location_id, plan.location_id, "location_id"),
        (payload.binding_source_key, plan.binding_source_key, "binding_source_key"),
        (payload.binding_evidence, plan.binding_evidence, "binding_evidence"),
        (payload.context_fingerprint, plan.context_fingerprint, "context_fingerprint"),
        (payload.context_placement, plan.placement.value, "context_placement"),
        (payload.context_wire_key, plan.wire_key, "context_wire_key"),
        (payload.context_value_path, plan.value_path, "context_value_path"),
        (
            payload.wire_request_fingerprint,
            plan_request.wire_request_fingerprint,
            "wire_request_fingerprint",
        ),
        (
            payload.request_digest,
            plan_request.canonical_request_digest,
            "canonical_request_digest",
        ),
    )
    for actual, wanted, label in expected:
        if actual != wanted:
            _fail(f"{code_prefix}_{label}_mismatch")


def bind_verified_structural_discovery_to_sps(
    discovery: VerifiedStructuralDiscovery,
    observations: Mapping[str, CryptographicallyVerifiedStructuralObservation],
    plan: SpsStructuralFacetPlan,
    *,
    binding: ConfirmedSpsFacetBinding | None = None,
) -> VerifiedSpsStructuralContext:
    """Re-liga manifest + receipts + plan sin aceptar claims caller-controlled."""

    if not isinstance(discovery, VerifiedStructuralDiscovery):
        _fail("structural_discovery_invalid")
    if not isinstance(plan, SpsStructuralFacetPlan):
        _fail("sps_structural_plan_invalid")
    if not isinstance(observations, Mapping) or set(observations) != {
        "root_total",
        "category_tree",
    }:
        _fail("structural_observations_incomplete")
    if discovery.production_authority is not False:
        _fail("structural_discovery_authority_forbidden")

    try:
        effective_binding = binding or confirmed_sps_facet_binding()
    except SpsFacetContextError as exc:
        raise SpsContextBoundDiscoveryError("confirmed_sps_binding_invalid") from exc
    if not isinstance(effective_binding, ConfirmedSpsFacetBinding):
        _fail("confirmed_sps_binding_invalid")
    if (
        plan.location_id != effective_binding.location_id
        or plan.binding_source_key != effective_binding.source_key
        or plan.binding_evidence != effective_binding.evidence
        or plan.context_fingerprint != effective_binding.expected_fingerprint
    ):
        _fail("sps_structural_plan_binding_mismatch")

    root = observations["root_total"]
    tree = observations["category_tree"]
    _record_matches_observation(discovery.root_total, root, code_prefix="root_total")
    _record_matches_observation(discovery.category_tree, tree, code_prefix="category_tree")
    _require_manifest_run_context(discovery, root, code_prefix="root_total")
    _require_manifest_run_context(discovery, tree, code_prefix="category_tree")
    _require_signed_location(root, plan, request_index=0, code_prefix="root_total")
    _require_signed_location(tree, plan, request_index=1, code_prefix="category_tree")

    if root.verified_receipt.public_key_spki_sha256 != tree.verified_receipt.public_key_spki_sha256:
        _fail("structural_context_public_key_changed")

    return VerifiedSpsStructuralContext(
        discovery=discovery,
        location_id=plan.location_id,
        binding_source_key=plan.binding_source_key,
        binding_evidence=plan.binding_evidence,
        context_fingerprint=plan.context_fingerprint,
        context_placement=plan.placement,
        context_wire_key=plan.wire_key,
        context_value_path=plan.value_path,
        root_wire_request_fingerprint=plan.requests[0].wire_request_fingerprint,
        category_tree_wire_request_fingerprint=plan.requests[1].wire_request_fingerprint,
        _plan=plan,
    )
