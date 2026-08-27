"""Política productiva de autoridad comercial para La Colonia SPS.

Esta es la única capa que puede transformar una atestación comercial Ed25519 en
una aceptación de catálogo para La Colonia. Exige simultáneamente:

- readiness técnica completa del catálogo;
- provenance física cerrada del mismo plan;
- atestación firmada por el keyring comercial confiable del deployment;
- binding exacto de supermercado, ubicación, run, autorización y digests;
- decisión posterior a la evidencia física que pretende aceptar.

El caller no puede inyectar un keyring. No hace red, no crea recursos cloud y no
habilita extracción futura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import NoReturn, Sequence

from precios_supermercados.commercial_authority import (
    CryptographicallyVerifiedCommercialAuthority,
    SignedCommercialAuthorityAttestation,
)
from precios_supermercados.commercial_authority_trust import (
    load_productive_commercial_authority_verifier,
)
from precios_supermercados.commercial_persistence_batch import (
    PreparedCommercialPersistence,
    _prepare_verified_archived_run_persistence,
)
from precios_supermercados.commercial_run_evidence import derive_bound_run_evidence_id
from precios_supermercados.commercial_state import (
    CommercialRunDecision,
    InMemoryCommercialState,
)
from precios_supermercados.locations import (
    DEFAULT_LOCATION_CATALOG,
    LA_COLONIA_SPS,
    LA_COLONIA_SUPERMARKET,
    LocationCatalog,
)
from precios_supermercados.models import ValidatedOffer
from precios_supermercados.scrapers.la_colonia_catalog_acceptance_readiness import (
    VerifiedCatalogAcceptanceReadiness,
)
from precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer import (
    VerifiedCatalogProvenanceRun,
)
from precios_supermercados.tabular_records import QualityEventRecord

_POLICY_VERIFICATION_SEAL = object()


class LaColoniaCommercialAuthorityError(ValueError):
    """La evidencia no puede promover este catálogo a autoridad comercial."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise LaColoniaCommercialAuthorityError(code, message)


@dataclass(frozen=True, slots=True)
class VerifiedLaColoniaCommercialAuthority:
    """Capability sellada de aceptación ligada a una atestación verificada."""

    cryptographic_authority: CryptographicallyVerifiedCommercialAuthority
    discovery_digest: str
    authenticated_plan_digest: str
    provenance_manifest_digest: str
    _policy_seal: object = field(repr=False, compare=False)
    production_authority: bool = True
    catalog_accepted: bool = True

    def __post_init__(self) -> None:
        if self._policy_seal is not _POLICY_VERIFICATION_SEAL:
            _fail("commercial_authority_unsealed")
        if not isinstance(
            self.cryptographic_authority,
            CryptographicallyVerifiedCommercialAuthority,
        ):
            _fail("commercial_authority_crypto_invalid")
        claims = self.cryptographic_authority.attestation.claims
        if claims.supermarket_id != LA_COLONIA_SUPERMARKET.supermarket_id:
            _fail("commercial_authority_supermarket_mismatch")
        if claims.location_id != LA_COLONIA_SPS.location_id:
            _fail("commercial_authority_location_mismatch")
        if self.discovery_digest != claims.discovery_digest:
            _fail("commercial_authority_discovery_digest_mismatch")
        if self.authenticated_plan_digest != claims.authenticated_plan_digest:
            _fail("commercial_authority_plan_digest_mismatch")
        if self.provenance_manifest_digest != claims.provenance_manifest_digest:
            _fail("commercial_authority_manifest_digest_mismatch")
        if self.production_authority is not True or self.catalog_accepted is not True:
            _fail("commercial_authority_promotion_invalid")

    @property
    def authority_evidence_id(self) -> str:
        return self.cryptographic_authority.authority_evidence_id

    @property
    def scrape_run_id(self) -> str:
        return self.cryptographic_authority.attestation.claims.scrape_run_id

    @property
    def commercial_decision(self) -> CommercialRunDecision:
        claims = self.cryptographic_authority.attestation.claims
        return CommercialRunDecision(
            scrape_run_id=claims.scrape_run_id,
            run_status=claims.run_status,
            catalog_accepted=True,
            decided_at_utc=claims.decided_at_utc,
        )


def verify_la_colonia_commercial_authority(
    *,
    readiness: VerifiedCatalogAcceptanceReadiness,
    provenance: VerifiedCatalogProvenanceRun,
    attestation: SignedCommercialAuthorityAttestation,
) -> VerifiedLaColoniaCommercialAuthority:
    """Reconcilia firma comercial confiable con el run técnico exacto.

    El keyring se carga sólo desde la trust config productiva; no forma parte de
    los argumentos y no puede ser elegido por el caller de esta función.
    """

    if not isinstance(readiness, VerifiedCatalogAcceptanceReadiness):
        _fail("commercial_authority_readiness_invalid")
    if not isinstance(provenance, VerifiedCatalogProvenanceRun):
        _fail("commercial_authority_provenance_invalid")
    if not isinstance(attestation, SignedCommercialAuthorityAttestation):
        _fail("commercial_authority_attestation_invalid")
    if readiness.technical_catalog_complete is not True:
        _fail("commercial_authority_technical_catalog_incomplete")
    if readiness.ready_for_productive_authority_evidence is not True:
        _fail("commercial_authority_readiness_not_ready")
    if readiness.catalog_accepted is not False or readiness.production_authority is not False:
        _fail("commercial_authority_readiness_already_promoted")
    if provenance.production_authority is not False:
        _fail("commercial_authority_provenance_prepromoted")
    if readiness.provenance_manifest_digest != provenance.manifest.digest:
        _fail("commercial_authority_readiness_manifest_mismatch")

    verifier = load_productive_commercial_authority_verifier()
    cryptographic = verifier.verify(attestation)
    claims = cryptographic.attestation.claims
    expected = {
        "supermarket_id": LA_COLONIA_SUPERMARKET.supermarket_id,
        "location_id": LA_COLONIA_SPS.location_id,
        "scrape_run_id": provenance.manifest.run_id,
        "source_authorization_id": provenance.manifest.authorization_id,
        "discovery_digest": readiness.discovery_digest,
        "authenticated_plan_digest": readiness.authenticated_plan_digest,
        "provenance_manifest_digest": readiness.provenance_manifest_digest,
    }
    for field_name, expected_value in expected.items():
        if getattr(claims, field_name) != expected_value:
            _fail(f"commercial_authority_{field_name}_mismatch")
    if claims.decided_at_utc < provenance.manifest.latest_response_completed_at_utc:
        _fail("commercial_authority_decision_predates_evidence")

    return VerifiedLaColoniaCommercialAuthority(
        cryptographic_authority=cryptographic,
        discovery_digest=readiness.discovery_digest,
        authenticated_plan_digest=readiness.authenticated_plan_digest,
        provenance_manifest_digest=readiness.provenance_manifest_digest,
        _policy_seal=_POLICY_VERIFICATION_SEAL,
    )


def prepare_la_colonia_authoritative_run_persistence(
    state: InMemoryCommercialState,
    authority: VerifiedLaColoniaCommercialAuthority,
    offers: Sequence[ValidatedOffer],
    *,
    started_at_utc: datetime,
    finished_at_utc: datetime,
    products_observed: int,
    offers_observed: int,
    quality_events: Sequence[QualityEventRecord] = (),
    catalog: LocationCatalog = DEFAULT_LOCATION_CATALOG,
) -> PreparedCommercialPersistence:
    """Prepara un run comercial sin aceptar bools ni evidence IDs del caller.

    El ``run_evidence_id`` se deriva internamente de la atestación productiva y
    del payload completo. Así un mismo authority evidence no puede reutilizarse
    con otras ofertas, métricas o eventos. La capability privada de snapshot se
    cruza sólo después de validar esta autoridad tipada y sellada.
    """

    if not isinstance(authority, VerifiedLaColoniaCommercialAuthority):
        _fail("verified_commercial_authority_required")
    if authority._policy_seal is not _POLICY_VERIFICATION_SEAL:
        _fail("verified_commercial_authority_unsealed")
    decision = authority.commercial_decision
    run_evidence_id = derive_bound_run_evidence_id(
        authority_evidence_id=authority.authority_evidence_id,
        decision=decision,
        offers=offers,
        supermarket_id=LA_COLONIA_SUPERMARKET.supermarket_id,
        location_id=LA_COLONIA_SPS.location_id,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        products_observed=products_observed,
        offers_observed=offers_observed,
        quality_events=quality_events,
    )
    return _prepare_verified_archived_run_persistence(
        state,
        decision,
        offers,
        supermarket_id=LA_COLONIA_SUPERMARKET.supermarket_id,
        location_id=LA_COLONIA_SPS.location_id,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        products_observed=products_observed,
        offers_observed=offers_observed,
        quality_events=quality_events,
        run_evidence_id=run_evidence_id,
        catalog=catalog,
    )
