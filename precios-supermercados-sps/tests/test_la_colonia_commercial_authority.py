from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from precios_supermercados.bigquery_adapter import BigQueryAdapter, FakeBigQueryClient
from precios_supermercados.bigquery_persistence import build_bigquery_write_plan
from precios_supermercados.commercial_authority import (
    CommercialAuthorityClaims,
    CommercialAuthorityError,
    Ed25519CommercialAuthorityVerifier,
    SignedCommercialAuthorityAttestation,
    commercial_authority_signing_bytes,
)
from precios_supermercados.commercial_state import InMemoryCommercialState
from precios_supermercados.enums import (
    AvailabilityStatus,
    LocationStatus,
    RunStatus,
    SourceKeyType,
)
from precios_supermercados.identifiers import (
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
)
from precios_supermercados.locations import DEFAULT_LOCATION_CATALOG, LA_COLONIA_SPS
from precios_supermercados.models import NormalizedOffer, ValidatedOffer
from precios_supermercados.scrapers.la_colonia_catalog_acceptance_readiness import (
    VerifiedCatalogAcceptanceReadiness,
)
from precios_supermercados.scrapers.la_colonia_catalog_coverage import CatalogCoverageReport
from precios_supermercados.scrapers.la_colonia_commercial_authority import (
    LaColoniaCommercialAuthorityError,
    prepare_la_colonia_authoritative_run_persistence,
    verify_la_colonia_commercial_authority,
)
from precios_supermercados.scrapers.la_colonia_verified_catalog_finalizer import (
    VerifiedCatalogProvenanceRun,
)

RUN = "32922877781:15"
AUTH = "authorization-full-catalog-2026-08-25"
DISCOVERY_DIGEST = "1" * 64
PLAN_DIGEST = "2" * 64
MANIFEST_DIGEST = "3" * 64
TREE_DIGEST = "4" * 64
TRUST_GATE = "trusted_collector_provenance_unavailable"
AUTHORITY_BLOCKER = "production_authority_not_established"
BASE = datetime(2026, 8, 25, 21, 15, tzinfo=timezone.utc)


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _key_material():
    private = Ed25519PrivateKey.generate()
    der = private.public_key().public_bytes(
        Encoding.DER,
        PublicFormat.SubjectPublicKeyInfo,
    )
    return private, _b64url(der)


def _coverage(*reasons: str) -> CatalogCoverageReport:
    return CatalogCoverageReport(
        partitions_discovered=62,
        partitions_attempted=62,
        partitions_completed=62 if reasons == (TRUST_GATE,) else 61,
        pages_expected=252,
        pages_attempted=252,
        pages_completed=252 if reasons == (TRUST_GATE,) else 251,
        products_reported=9437,
        products_received=9439,
        products_unique=9437,
        duplicate_occurrences=2,
        repeated_page_sets=0,
        unexpected_overlaps=0,
        missing_coverage_events=0 if reasons == (TRUST_GATE,) else 1,
        total_changes=0,
        uncategorized_products=0,
        request_limit=50,
        coverage_demonstrated=False,
        coverage_reason=";".join(reasons),
        accepted=False,
        run_id=RUN,
        tree_digest=TREE_DIGEST,
        primary_plan_digest="5" * 64,
        reconciliation_plan_digest="6" * 64,
        _reasons=tuple(reasons),
    )


def _readiness(*, complete: bool = True) -> VerifiedCatalogAcceptanceReadiness:
    reasons = (TRUST_GATE,) if complete else (TRUST_GATE, "missing_partition")
    blockers = (
        (TRUST_GATE, AUTHORITY_BLOCKER)
        if complete
        else ("missing_partition", TRUST_GATE, AUTHORITY_BLOCKER)
    )
    return VerifiedCatalogAcceptanceReadiness(
        coverage=_coverage(*reasons),
        discovery_digest=DISCOVERY_DIGEST,
        authenticated_plan_digest=PLAN_DIGEST,
        provenance_manifest_digest=MANIFEST_DIGEST,
        technical_catalog_complete=complete,
        ready_for_productive_authority_evidence=complete,
        catalog_accepted=False,
        blockers=blockers,
    )


def _provenance() -> VerifiedCatalogProvenanceRun:
    manifest = SimpleNamespace(
        run_id=RUN,
        authorization_id=AUTH,
        digest=MANIFEST_DIGEST,
        latest_response_completed_at_utc=BASE,
        production_authority=False,
    )
    value = object.__new__(VerifiedCatalogProvenanceRun)
    object.__setattr__(value, "collection", SimpleNamespace(production_authority=False))
    object.__setattr__(value, "reconciled_pages", (object(),))
    object.__setattr__(value, "manifest", manifest)
    object.__setattr__(value, "production_authority", False)
    return value


def _claims(*, key_id: str, decided_at: datetime | None = None, **overrides):
    values = {
        "supermarket_id": "la_colonia",
        "location_id": "la_colonia_sps",
        "scrape_run_id": RUN,
        "source_authorization_id": AUTH,
        "run_status": RunStatus.SUCCESS,
        "decided_at_utc": decided_at or BASE + timedelta(minutes=1),
        "discovery_digest": DISCOVERY_DIGEST,
        "authenticated_plan_digest": PLAN_DIGEST,
        "provenance_manifest_digest": MANIFEST_DIGEST,
        "signing_key_id": key_id,
    }
    values.update(overrides)
    return CommercialAuthorityClaims(**values)


def _signed(private, claims: CommercialAuthorityClaims):
    signature = private.sign(commercial_authority_signing_bytes(claims))
    return SignedCommercialAuthorityAttestation(
        claims=claims,
        signature_b64url=_b64url(signature),
    )


def _verified_authority():
    private, public_spki = _key_material()
    verifier = Ed25519CommercialAuthorityVerifier({"commercial-authority-v1": public_spki})
    attestation = _signed(private, _claims(key_id="commercial-authority-v1"))
    return verify_la_colonia_commercial_authority(
        readiness=_readiness(),
        provenance=_provenance(),
        attestation=attestation,
        verifier=verifier,
    )


def _offer() -> ValidatedOffer:
    source_key = "sku:authority:001"
    source_product_id = generate_source_product_id(
        "la_colonia",
        SourceKeyType.SKU,
        source_key,
    )
    offer_id = generate_offer_id(
        "la_colonia",
        "la_colonia_sps",
        source_product_id,
    )
    offer = NormalizedOffer(
        supermarket_id="la_colonia",
        location_id="la_colonia_sps",
        source_product_id=source_product_id,
        source_key_type=SourceKeyType.SKU,
        source_key=source_key,
        product_id="prod_authority_001",
        offer_id=offer_id,
        source_name="Producto prueba autoridad",
        product_url="https://example.invalid/producto-autoridad",
        normalized_name="Producto prueba autoridad",
        currency="HNL",
        is_promotion=False,
        availability=AvailabilityStatus.IN_STOCK,
        location_status=LocationStatus.CONFIRMED,
        location_evidence=LA_COLONIA_SPS.evidence,
        location_confidence=Decimal("1"),
        observed_at_utc=BASE,
        scrape_run_id=RUN,
        extractor_version="authority-test",
        schema_version="1",
        source_url="https://example.invalid/graphql",
        normalized_brand="Marca",
        category="Categoria",
        subcategory="Subcategoria",
        variant="Base",
        unit_count=1,
        content_per_unit=Decimal("1000"),
        measurement_unit="g",
        total_content=Decimal("1000"),
        current_price=Decimal("30.00"),
        source_sku="AUTH-001",
        source_brand="Marca",
        source_presentation="1 kg",
        source_category="Categoria",
    )
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=BASE,
    )


def test_crypto_verifier_accepts_only_signature_from_trusted_authority_key() -> None:
    private, public_spki = _key_material()
    claims = _claims(key_id="commercial-authority-v1")
    attestation = _signed(private, claims)
    verifier = Ed25519CommercialAuthorityVerifier({"commercial-authority-v1": public_spki})

    verified = verifier.verify(attestation)

    assert verified.cryptographic_signature_verified is True
    assert verified.production_authority is False
    assert verified.catalog_accepted is False
    assert verified.authority_evidence_id.startswith("caev1_")

    forged = SignedCommercialAuthorityAttestation(
        claims=_claims(
            key_id="commercial-authority-v1",
            location_id="la_colonia_tgu",
        ),
        signature_b64url=attestation.signature_b64url,
    )
    with pytest.raises(CommercialAuthorityError, match="authority_signature_invalid"):
        verifier.verify(forged)


def test_policy_promotes_only_exact_signed_readiness_binding() -> None:
    authority = _verified_authority()

    assert authority.production_authority is True
    assert authority.catalog_accepted is True
    assert authority.scrape_run_id == RUN
    decision = authority.commercial_decision
    assert decision.catalog_accepted is True
    assert decision.commercial_update_allowed is True
    assert decision.run_status is RunStatus.SUCCESS


def test_policy_rejects_valid_signature_bound_to_wrong_location() -> None:
    private, public_spki = _key_material()
    verifier = Ed25519CommercialAuthorityVerifier({"commercial-authority-v1": public_spki})
    attestation = _signed(
        private,
        _claims(
            key_id="commercial-authority-v1",
            location_id="la_colonia_tgu",
        ),
    )

    with pytest.raises(
        LaColoniaCommercialAuthorityError,
        match="commercial_authority_location_id_mismatch",
    ):
        verify_la_colonia_commercial_authority(
            readiness=_readiness(),
            provenance=_provenance(),
            attestation=attestation,
            verifier=verifier,
        )


def test_policy_rejects_authority_decision_that_predates_physical_evidence() -> None:
    private, public_spki = _key_material()
    verifier = Ed25519CommercialAuthorityVerifier({"commercial-authority-v1": public_spki})
    attestation = _signed(
        private,
        _claims(
            key_id="commercial-authority-v1",
            decided_at=BASE - timedelta(seconds=1),
        ),
    )

    with pytest.raises(
        LaColoniaCommercialAuthorityError,
        match="commercial_authority_decision_predates_evidence",
    ):
        verify_la_colonia_commercial_authority(
            readiness=_readiness(),
            provenance=_provenance(),
            attestation=attestation,
            verifier=verifier,
        )


def test_policy_rejects_technical_incompleteness_even_with_valid_signature() -> None:
    private, public_spki = _key_material()
    verifier = Ed25519CommercialAuthorityVerifier({"commercial-authority-v1": public_spki})
    attestation = _signed(private, _claims(key_id="commercial-authority-v1"))

    with pytest.raises(
        LaColoniaCommercialAuthorityError,
        match="commercial_authority_technical_catalog_incomplete",
    ):
        verify_la_colonia_commercial_authority(
            readiness=_readiness(complete=False),
            provenance=_provenance(),
            attestation=attestation,
            verifier=verifier,
        )


def test_authoritative_snapshot_can_persist_while_future_extraction_stays_disabled() -> None:
    assert DEFAULT_LOCATION_CATALOG.extraction_block_reason("la_colonia_sps") == "extraction_disabled"
    authority = _verified_authority()
    state = InMemoryCommercialState()
    offer = _offer()

    prepared = prepare_la_colonia_authoritative_run_persistence(
        state,
        authority,
        (offer,),
        started_at_utc=BASE - timedelta(minutes=10),
        finished_at_utc=BASE,
        products_observed=1,
        offers_observed=1,
    )

    assert prepared.run_record.catalog_accepted is True
    assert prepared.run_record.run_evidence_id is not None
    assert prepared.run_record.run_evidence_id.startswith("crev1_")
    assert prepared.apply_result.commercial_update_allowed is True
    assert prepared.table_row_counts["fact_offers_current"] == 1
    assert prepared.table_row_counts["fact_offer_history"] == 1
    config_rows = prepared.batch.rows["cfg_locations"]
    by_id = {row["location_id"]: row for row in config_rows}
    assert by_id["la_colonia_sps"]["extraction_enabled"] is False
    assert DEFAULT_LOCATION_CATALOG.extraction_block_reason("la_colonia_sps") == "extraction_disabled"


def test_authority_path_reaches_bigquery_and_exact_replay_without_enabling_live() -> None:
    authority = _verified_authority()
    prepared = prepare_la_colonia_authoritative_run_persistence(
        InMemoryCommercialState(),
        authority,
        (_offer(),),
        started_at_utc=BASE - timedelta(minutes=10),
        finished_at_utc=BASE,
        products_observed=1,
        offers_observed=1,
    )
    plan = build_bigquery_write_plan(prepared)
    client = FakeBigQueryClient()
    adapter = BigQueryAdapter(client, dataset_id="precios_authority_test")
    adapter.bootstrap()

    first = adapter.apply(plan)
    snapshot = adapter.read_back(
        supermarket_id="la_colonia",
        location_id="la_colonia_sps",
    )
    locations = client.read_rows("precios_authority_test", "locations")
    sps = next(row for row in locations if row["location_id"] == "la_colonia_sps")

    assert first.exact_run_replay is False
    assert len(snapshot.products) == 1
    assert len(snapshot.latest_prices) == 1
    assert len(snapshot.latest_inventory) == 1
    assert len(snapshot.runs) == 1
    assert snapshot.runs[0]["catalog_accepted"] is True
    assert snapshot.runs[0]["run_evidence_id"].startswith("crev1_")
    assert sps["extraction_enabled"] is False

    replay = adapter.apply(plan)
    replay_snapshot = adapter.read_back(
        supermarket_id="la_colonia",
        location_id="la_colonia_sps",
    )
    assert replay.exact_run_replay is True
    assert len(replay_snapshot.products) == 1
    assert len(replay_snapshot.latest_prices) == 1
    assert len(replay_snapshot.latest_inventory) == 1
    assert len(replay_snapshot.runs) == 1
    assert DEFAULT_LOCATION_CATALOG.extraction_block_reason("la_colonia_sps") == "extraction_disabled"
