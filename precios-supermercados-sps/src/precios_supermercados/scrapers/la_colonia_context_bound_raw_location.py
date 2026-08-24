"""Promoción evidence-bound de ``RawProduct`` al contexto comercial SPS.

La extracción histórica de La Colonia produce deliberadamente
``la_colonia_online / UNKNOWN``. Este módulo es la única frontera que puede
materializar esos mismos SKU como ``la_colonia_sps / CONFIRMED`` y sólo lo hace
cuando la página que los contiene ya fue verificada criptográficamente por la
ruta de catálogo context-bound v3.

No realiza red, no persiste, no concede ``catalog_accepted`` ni
``production_authority`` y no habilita extracción. La evidencia pública conserva
únicamente hashes/fingerprints sanitizados; el valor raw del contexto de ubicación
no se copia al resultado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import NoReturn

from precios_supermercados.catalog_context_provenance import (
    CATALOG_CONTEXT_RECEIPT_SCHEMA_VERSION,
    ContextBoundEdgeReceiptPayload,
)
from precios_supermercados.enums import LocationStatus
from precios_supermercados.locations import (
    LA_COLONIA_ONLINE_SOURCE_CONTEXT,
    LA_COLONIA_SPS,
)
from precios_supermercados.models import RawProduct
from precios_supermercados.scrapers.base import ScraperError
from precios_supermercados.scrapers.la_colonia import LaColoniaExtractor
from precios_supermercados.scrapers.la_colonia_context_bound_catalog_transport import (
    ContextBoundVerifiedCatalogCollection,
    ContextBoundVerifiedCatalogPageObservation,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ContextBoundRawLocationError(RuntimeError):
    """La evidencia no permite atribuir los productos a SPS."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise ContextBoundRawLocationError(code, message)


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(code)
    return value


def _sanitized_location_evidence(
    observation: ContextBoundVerifiedCatalogPageObservation,
) -> str:
    page = observation.page
    receipt = page.verified_receipt
    receipt_digest = _sha256(
        receipt.receipt_digest,
        "raw_location_receipt_digest_invalid",
    )
    worker_evidence_id = _sha256(
        page.worker_evidence_id,
        "raw_location_worker_evidence_id_invalid",
    )
    context_fingerprint = _sha256(
        observation.context_fingerprint,
        "raw_location_context_fingerprint_invalid",
    )
    wire_fingerprint = _sha256(
        observation.wire_request_fingerprint,
        "raw_location_wire_fingerprint_invalid",
    )
    return (
        "catalog_context_v3:"
        f"receipt_sha256={receipt_digest};"
        f"worker_evidence_sha256={worker_evidence_id};"
        f"context_sha256={context_fingerprint};"
        f"wire_sha256={wire_fingerprint}"
    )


@dataclass(frozen=True, slots=True)
class ContextBoundSpsRawPage:
    """SKU materializados desde una página context-bound, sin autoridad comercial."""

    run_id: str
    traversal_role: str
    partition_id: str
    source_url: str
    location_id: str
    context_fingerprint: str
    wire_request_fingerprint: str
    receipt_digest: str
    worker_evidence_id: str
    products: tuple[RawProduct, ...]
    production_authority: bool = False
    catalog_accepted: bool = False
    extraction_enabled: bool = False

    def __post_init__(self) -> None:
        if self.location_id != LA_COLONIA_SPS.location_id:
            _fail("raw_location_page_location_invalid")
        if self.traversal_role not in {"primary", "reconciliation"}:
            _fail("raw_location_page_traversal_role_invalid")
        if not self.run_id or not self.partition_id or not self.source_url:
            _fail("raw_location_page_identity_invalid")
        _sha256(self.context_fingerprint, "raw_location_page_context_invalid")
        _sha256(self.wire_request_fingerprint, "raw_location_page_wire_invalid")
        _sha256(self.receipt_digest, "raw_location_page_receipt_invalid")
        _sha256(self.worker_evidence_id, "raw_location_page_worker_evidence_invalid")
        if not self.products:
            _fail("raw_location_page_products_empty")
        for raw in self.products:
            if not isinstance(raw, RawProduct):
                _fail("raw_location_page_product_invalid")
            if raw.supermarket_id != LA_COLONIA_SPS.supermarket_id:
                _fail("raw_location_page_supermarket_mismatch")
            if raw.location_id != self.location_id:
                _fail("raw_location_page_product_location_mismatch")
            if raw.location_status is not LocationStatus.CONFIRMED:
                _fail("raw_location_page_product_status_invalid")
            if raw.location_confidence != Decimal("1"):
                _fail("raw_location_page_product_confidence_invalid")
            if raw.scrape_run_id != self.run_id or raw.source_url != self.source_url:
                _fail("raw_location_page_product_lineage_mismatch")
        if (
            self.production_authority is not False
            or self.catalog_accepted is not False
            or self.extraction_enabled is not False
        ):
            _fail("raw_location_page_authority_forbidden")


@dataclass(frozen=True, slots=True)
class ContextBoundSpsRawCatalog:
    """Vista primary completa de SKU SPS, todavía no aceptada ni persistible."""

    run_id: str
    plan_digest: str
    discovery_digest: str
    structural_context_plan_digest: str
    location_id: str
    context_fingerprint: str
    pages: tuple[ContextBoundSpsRawPage, ...]
    product_count: int
    production_authority: bool = False
    catalog_accepted: bool = False
    extraction_enabled: bool = False

    def __post_init__(self) -> None:
        if self.location_id != LA_COLONIA_SPS.location_id:
            _fail("raw_location_catalog_location_invalid")
        for digest, code in (
            (self.plan_digest, "raw_location_catalog_plan_digest_invalid"),
            (self.discovery_digest, "raw_location_catalog_discovery_digest_invalid"),
            (
                self.structural_context_plan_digest,
                "raw_location_catalog_structural_plan_digest_invalid",
            ),
            (self.context_fingerprint, "raw_location_catalog_context_invalid"),
        ):
            _sha256(digest, code)
        if not self.run_id or not self.pages:
            _fail("raw_location_catalog_identity_invalid")
        if any(page.traversal_role != "primary" for page in self.pages):
            _fail("raw_location_catalog_non_primary_page")
        if any(page.run_id != self.run_id for page in self.pages):
            _fail("raw_location_catalog_run_mismatch")
        if any(page.context_fingerprint != self.context_fingerprint for page in self.pages):
            _fail("raw_location_catalog_context_changed")
        if self.product_count != sum(len(page.products) for page in self.pages):
            _fail("raw_location_catalog_product_count_mismatch")
        if (
            self.production_authority is not False
            or self.catalog_accepted is not False
            or self.extraction_enabled is not False
        ):
            _fail("raw_location_catalog_authority_forbidden")


def materialize_context_bound_sps_raw_page(
    observation: ContextBoundVerifiedCatalogPageObservation,
) -> ContextBoundSpsRawPage:
    """Parsea una página ya verificada y liga sus SKU a SPS sin hacer red."""

    if not isinstance(observation, ContextBoundVerifiedCatalogPageObservation):
        _fail("context_bound_catalog_observation_required")
    page = observation.page
    if page.cryptographic_signature_verified is not True:
        _fail("raw_location_signature_unverified")
    if page.production_authority is not False or observation.production_authority is not False:
        _fail("raw_location_input_authority_forbidden")

    verified_receipt = page.verified_receipt
    if verified_receipt.cryptographic_signature_verified is not True:
        _fail("raw_location_receipt_signature_unverified")
    if verified_receipt.production_authority is not False:
        _fail("raw_location_receipt_authority_forbidden")
    payload = verified_receipt.receipt.payload
    if not isinstance(payload, ContextBoundEdgeReceiptPayload):
        _fail("raw_location_receipt_downgrade")
    if (
        payload.schema_version != CATALOG_CONTEXT_RECEIPT_SCHEMA_VERSION
        or payload.location_context_bound is not True
    ):
        _fail("raw_location_receipt_schema_invalid")
    if observation.location_id != LA_COLONIA_SPS.location_id:
        _fail("raw_location_observation_location_invalid")
    if payload.location_id != LA_COLONIA_SPS.location_id:
        _fail("raw_location_receipt_location_invalid")
    if LA_COLONIA_SPS.source_location_key is None or LA_COLONIA_SPS.evidence is None:
        _fail("raw_location_canonical_binding_incomplete")
    if payload.binding_source_key != LA_COLONIA_SPS.source_location_key:
        _fail("raw_location_binding_source_mismatch")
    if payload.binding_evidence != LA_COLONIA_SPS.evidence:
        _fail("raw_location_binding_evidence_mismatch")
    if payload.context_fingerprint != observation.context_fingerprint:
        _fail("raw_location_context_fingerprint_mismatch")
    if payload.wire_request_fingerprint != observation.wire_request_fingerprint:
        _fail("raw_location_wire_fingerprint_mismatch")
    if payload.run_id != observation.raw_evidence.run_id:
        _fail("raw_location_run_id_mismatch")
    if payload.traversal_role != observation.expected.traversal_role:
        _fail("raw_location_traversal_role_mismatch")
    if payload.partition_id != observation.expected.partition_id:
        _fail("raw_location_partition_mismatch")

    try:
        parsed = LaColoniaExtractor(
            clock=lambda: payload.response_completed_at_utc,
        ).parse_payload(
            page.payload,
            scrape_run_id=payload.run_id,
            source_url=page.source_url,
            page_size=page.page_size,
        )
    except (ScraperError, ValueError, TypeError) as exc:
        raise ContextBoundRawLocationError("raw_location_page_parse_rejected") from exc

    metrics = parsed.metrics
    if parsed.accepted is not True:
        _fail("raw_location_page_parser_not_accepted")
    if parsed.source_url != page.source_url:
        _fail("raw_location_page_source_url_mismatch")
    if metrics.products_returned != len(observation.raw_evidence.products):
        _fail("raw_location_product_evidence_count_mismatch")
    expected_item_ids = tuple(
        item_id
        for product in observation.raw_evidence.products
        for item_id in product.item_ids
    )
    if not expected_item_ids or any(not item_id for item_id in expected_item_ids):
        _fail("raw_location_item_evidence_incomplete")
    if metrics.skus_returned != len(expected_item_ids):
        _fail("raw_location_sku_returned_count_mismatch")
    if metrics.skus_extracted != len(expected_item_ids):
        _fail("raw_location_sku_extracted_count_mismatch")
    if metrics.duplicate_skus != 0:
        _fail("raw_location_duplicate_skus")

    parsed_item_ids = tuple(raw.raw_values.get("item_id") for raw in parsed.products)
    if any(not isinstance(item_id, str) or not item_id for item_id in parsed_item_ids):
        _fail("raw_location_parsed_item_identity_missing")
    if parsed_item_ids != expected_item_ids:
        _fail("raw_location_item_identity_mismatch")

    evidence = _sanitized_location_evidence(observation)
    promoted: list[RawProduct] = []
    for raw in parsed.products:
        if raw.supermarket_id != LA_COLONIA_ONLINE_SOURCE_CONTEXT.supermarket_id:
            _fail("raw_location_source_supermarket_mismatch")
        if raw.location_id != LA_COLONIA_ONLINE_SOURCE_CONTEXT.location_id:
            _fail("raw_location_source_context_mismatch")
        if raw.location_status is not LocationStatus.UNKNOWN:
            _fail("raw_location_source_status_mismatch")
        if raw.location_evidence != LA_COLONIA_ONLINE_SOURCE_CONTEXT.evidence:
            _fail("raw_location_source_evidence_mismatch")
        if raw.location_confidence is not None:
            _fail("raw_location_source_confidence_forbidden")
        if raw.scrape_run_id != payload.run_id or raw.source_url != page.source_url:
            _fail("raw_location_source_lineage_mismatch")
        if raw.observed_at_utc != payload.response_completed_at_utc:
            _fail("raw_location_source_observed_at_mismatch")
        promoted.append(
            replace(
                raw,
                location_id=LA_COLONIA_SPS.location_id,
                location_status=LocationStatus.CONFIRMED,
                location_evidence=evidence,
                location_confidence=Decimal("1"),
            )
        )

    return ContextBoundSpsRawPage(
        run_id=payload.run_id,
        traversal_role=observation.expected.traversal_role,
        partition_id=observation.expected.partition_id,
        source_url=page.source_url,
        location_id=LA_COLONIA_SPS.location_id,
        context_fingerprint=observation.context_fingerprint,
        wire_request_fingerprint=observation.wire_request_fingerprint,
        receipt_digest=verified_receipt.receipt_digest,
        worker_evidence_id=page.worker_evidence_id,
        products=tuple(promoted),
    )


def materialize_context_bound_sps_primary_catalog(
    collection: ContextBoundVerifiedCatalogCollection,
) -> ContextBoundSpsRawCatalog:
    """Materializa sólo primary y exige correspondencia exacta con su collection."""

    if not isinstance(collection, ContextBoundVerifiedCatalogCollection):
        _fail("context_bound_catalog_collection_required")
    if collection.production_authority is not False:
        _fail("raw_location_collection_authority_forbidden")
    if collection.location_id != LA_COLONIA_SPS.location_id:
        _fail("raw_location_collection_location_invalid")

    primary_observations = tuple(
        observation
        for observation in collection.observations
        if observation.expected.traversal_role == "primary"
    )
    if not primary_observations:
        _fail("raw_location_primary_observations_missing")
    if tuple(item.raw_evidence for item in primary_observations) != collection.primary.pages:
        _fail("raw_location_primary_evidence_mismatch")

    pages = tuple(
        materialize_context_bound_sps_raw_page(observation)
        for observation in primary_observations
    )
    seen_source_identities: set[tuple[str, str]] = set()
    for page in pages:
        for raw in page.products:
            identity = (raw.source_key_type.value, raw.source_key)
            if identity in seen_source_identities:
                _fail("raw_location_primary_source_identity_duplicate")
            seen_source_identities.add(identity)

    return ContextBoundSpsRawCatalog(
        run_id=collection.primary.run_id,
        plan_digest=collection.plan_digest,
        discovery_digest=collection.discovery_digest,
        structural_context_plan_digest=collection.structural_context_plan_digest,
        location_id=collection.location_id,
        context_fingerprint=collection.context_fingerprint,
        pages=pages,
        product_count=sum(len(page.products) for page in pages),
    )
