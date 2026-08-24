"""Finaliza físicamente un catálogo obligatoriamente ligado al contexto SPS.

Esta ruta es deliberadamente separada del finalizador legacy. Consume sólo
``ContextBoundVerifiedCatalogEdgeCollector`` y conserva la cadena v3 de contexto
hasta el manifest run-level. Las páginas reconciliadas de Observability se usan
únicamente de forma transitoria: el resultado público retiene el manifest
sanitizado y nunca conserva ``fetch_url`` ni el valor raw de ubicación.

El placement ``header`` puede reconciliarse con el contrato de tracing actual
porque el URL físico coincide con el request base y el header sensible ya queda
atestiguado por el receipt v3. ``query`` falla antes de consultar Cloudflare: el
contrato legacy de tracing serializa el URL físico y no existe todavía una forma
redactada que preserve esa evidencia sin exponer el valor raw.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn

from precios_supermercados.authenticated_provenance_run import (
    AuthenticatedProvenanceRunError,
    build_authenticated_edge_provenance_run_manifest,
)
from precios_supermercados.catalog_context_provenance import (
    CATALOG_CONTEXT_RECEIPT_SCHEMA_VERSION,
    ContextBoundEdgeReceiptPayload,
)
from precios_supermercados.cloudflare_observability_verifier import (
    CloudflareObservabilityVerifierClient,
    CloudflareObservabilityVerifierError,
)
from precios_supermercados.cloudflare_trace_evidence import PlatformReconciledEdgePage
from precios_supermercados.edge_provenance_run import EdgeProvenanceRunManifest
from precios_supermercados.scrapers.la_colonia_context_bound_catalog_transport import (
    ContextBoundVerifiedCatalogCollection,
    ContextBoundVerifiedCatalogEdgeCollector,
    ContextBoundVerifiedCatalogPageObservation,
    ContextBoundVerifiedCatalogTransportError,
)
from precios_supermercados.scrapers.la_colonia_sps_facet_context import (
    RequestContextPlacement,
)


class ContextBoundCatalogFinalizationError(RuntimeError):
    """El catálogo SPS no puede cerrar su provenance física de forma segura."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise ContextBoundCatalogFinalizationError(code, message)


def _bearer(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 20_000
        or any(character.isspace() for character in value)
    ):
        _fail("observability_bearer_token_invalid")
    return value


@dataclass(frozen=True, slots=True)
class ContextBoundCatalogProvenanceRun:
    """Collection SPS + manifest físico, sin retener trazas con material raw."""

    collection: ContextBoundVerifiedCatalogCollection
    manifest: EdgeProvenanceRunManifest
    structural_context_plan_digest: str
    location_id: str
    context_fingerprint: str
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.collection, ContextBoundVerifiedCatalogCollection):
            _fail("catalog_context_collection_invalid")
        if not isinstance(self.manifest, EdgeProvenanceRunManifest):
            _fail("catalog_context_provenance_manifest_invalid")
        if self.structural_context_plan_digest != self.collection.structural_context_plan_digest:
            _fail("catalog_context_structural_plan_digest_mismatch")
        if self.location_id != self.collection.location_id:
            _fail("catalog_context_location_id_mismatch")
        if self.context_fingerprint != self.collection.context_fingerprint:
            _fail("catalog_context_fingerprint_mismatch")
        if self.manifest.production_authority is not False:
            _fail("catalog_context_manifest_authority_forbidden")
        if self.manifest.request_count != len(self.collection.observations):
            _fail("catalog_context_manifest_request_count_mismatch")
        if self.collection.production_authority is not False:
            _fail("catalog_context_collection_authority_forbidden")
        if self.production_authority is not False:
            _fail("catalog_context_provenance_authority_forbidden")


class ContextBoundCatalogProvenanceFinalizer:
    """Finalizador one-shot del collector v3 ligado a SPS."""

    def __init__(
        self,
        verifier_client: CloudflareObservabilityVerifierClient,
        *,
        bearer_token_provider: Callable[[], str],
    ) -> None:
        if not isinstance(verifier_client, CloudflareObservabilityVerifierClient):
            _fail("catalog_context_observability_verifier_client_invalid")
        if not callable(bearer_token_provider):
            _fail("observability_bearer_token_provider_invalid")
        self._verifier_client = verifier_client
        self._bearer_token_provider = bearer_token_provider
        self._finalized_collector_id: int | None = None
        self._result: ContextBoundCatalogProvenanceRun | None = None

    @property
    def account_id(self) -> str:
        return self._verifier_client.account_id

    @property
    def finalized(self) -> bool:
        return self._result is not None

    def _snapshot(
        self,
        collector: ContextBoundVerifiedCatalogEdgeCollector,
    ) -> tuple[
        ContextBoundVerifiedCatalogCollection,
        tuple[ContextBoundVerifiedCatalogPageObservation, ...],
    ]:
        if not isinstance(collector, ContextBoundVerifiedCatalogEdgeCollector):
            _fail("context_bound_catalog_collector_invalid")
        if not collector.complete:
            _fail("context_bound_catalog_collector_incomplete")

        observations = collector.observations
        plan = collector.authenticated_plan
        sps_context = collector.sps_context
        if len(observations) != plan.request_count:
            _fail("context_bound_catalog_observation_count_mismatch")
        if any(
            not isinstance(item, ContextBoundVerifiedCatalogPageObservation)
            for item in observations
        ):
            _fail("context_bound_catalog_observation_invalid")
        expected = tuple(page.identity for page in plan.pages)
        observed = tuple(item.expected.identity for item in observations)
        if observed != expected:
            _fail("context_bound_catalog_observation_order_mismatch")

        seen_wire_fingerprints: set[str] = set()
        for item in observations:
            page = item.page
            if page.cryptographic_signature_verified is not True:
                _fail("context_bound_catalog_observation_signature_unverified")
            if page.production_authority is not False or item.production_authority is not False:
                _fail("context_bound_catalog_observation_authority_forbidden")
            payload = page.verified_receipt.receipt.payload
            if not isinstance(payload, ContextBoundEdgeReceiptPayload):
                _fail("context_bound_catalog_receipt_downgrade")
            if (
                payload.schema_version != CATALOG_CONTEXT_RECEIPT_SCHEMA_VERSION
                or payload.location_context_bound is not True
            ):
                _fail("context_bound_catalog_receipt_schema_invalid")
            if item.location_id != sps_context.location_id or payload.location_id != sps_context.location_id:
                _fail("context_bound_catalog_location_changed")
            if (
                item.context_fingerprint != sps_context.context_fingerprint
                or payload.context_fingerprint != sps_context.context_fingerprint
            ):
                _fail("context_bound_catalog_context_changed")
            if item.wire_request_fingerprint != payload.wire_request_fingerprint:
                _fail("context_bound_catalog_wire_fingerprint_mismatch")
            if item.wire_request_fingerprint in seen_wire_fingerprints:
                _fail("context_bound_catalog_wire_fingerprint_reused")
            seen_wire_fingerprints.add(item.wire_request_fingerprint)

        try:
            collection = collector.build_collection()
        except ContextBoundVerifiedCatalogTransportError as exc:
            raise ContextBoundCatalogFinalizationError(
                f"catalog_context_collection_{exc.code}"
            ) from exc
        if collection.plan_digest != plan.digest:
            _fail("catalog_context_collection_plan_digest_mismatch")
        if collection.discovery_digest != plan.discovery_digest:
            _fail("catalog_context_collection_discovery_digest_mismatch")
        if collection.structural_context_plan_digest != sps_context.plan_digest:
            _fail("catalog_context_collection_structural_plan_digest_mismatch")
        if collection.location_id != sps_context.location_id:
            _fail("catalog_context_collection_location_mismatch")
        if collection.context_fingerprint != sps_context.context_fingerprint:
            _fail("catalog_context_collection_fingerprint_mismatch")
        return collection, observations

    def finalize(
        self,
        collector: ContextBoundVerifiedCatalogEdgeCollector,
    ) -> ContextBoundCatalogProvenanceRun:
        """Reconcilia físicamente el catálogo sin persistir la traza raw.

        El tracing actual sólo es seguro para ``header``. Si el contexto SPS
        probado fuese ``query`` se corta antes de obtener el bearer token y antes
        de consultar Observability.
        """

        collector_id = id(collector)
        if self._result is not None:
            if self._finalized_collector_id != collector_id:
                _fail("finalizer_already_bound_to_other_collector")
            return self._result

        collection, observations = self._snapshot(collector)
        if collector.sps_context.context_placement is not RequestContextPlacement.HEADER:
            _fail("catalog_context_query_observability_redaction_required")

        try:
            token = _bearer(self._bearer_token_provider())
        except ContextBoundCatalogFinalizationError:
            raise
        except Exception as exc:
            raise ContextBoundCatalogFinalizationError(
                "observability_bearer_token_provider_failed"
            ) from exc

        reconciled: list[PlatformReconciledEdgePage] = []
        physical_evidence_ids: set[str] = set()
        fetch_span_ids: set[str] = set()
        for ordinal, observation in enumerate(observations):
            try:
                page = self._verifier_client.reconcile_page(
                    observation.page,
                    bearer_token=token,
                )
            except CloudflareObservabilityVerifierError as exc:
                raise ContextBoundCatalogFinalizationError(
                    f"catalog_context_page_{ordinal}_observability_{exc.code}"
                ) from exc
            if not isinstance(page, PlatformReconciledEdgePage):
                _fail("catalog_context_observability_result_invalid")
            if page.page is not observation.page:
                _fail("catalog_context_observability_page_identity_mismatch")
            if page.platform_evidence_reconciled is not True:
                _fail("catalog_context_observability_result_unreconciled")
            if page.production_authority is not False:
                _fail("catalog_context_observability_authority_forbidden")
            # Con placement header, el URL trazado debe seguir siendo exactamente
            # el request base; así ningún valor raw de ubicación entra al objeto
            # que alimenta el manifest.
            if page.trace_evidence.fetch_url != observation.page.source_url:
                _fail("catalog_context_observability_fetch_url_mismatch")

            physical_id = page.physical_evidence_id
            if physical_id in physical_evidence_ids:
                _fail("catalog_context_physical_evidence_reused")
            fetch_span_id = page.trace_evidence.fetch_span_id
            if fetch_span_id in fetch_span_ids:
                _fail("catalog_context_fetch_span_reused")
            physical_evidence_ids.add(physical_id)
            fetch_span_ids.add(fetch_span_id)
            reconciled.append(page)

        try:
            manifest = build_authenticated_edge_provenance_run_manifest(
                authenticated_plan=collector.authenticated_plan,
                reconciled_pages=tuple(reconciled),
            )
        except AuthenticatedProvenanceRunError as exc:
            raise ContextBoundCatalogFinalizationError(
                f"catalog_context_run_manifest_{exc.code}"
            ) from exc

        result = ContextBoundCatalogProvenanceRun(
            collection=collection,
            manifest=manifest,
            structural_context_plan_digest=collector.sps_context.plan_digest,
            location_id=collector.sps_context.location_id,
            context_fingerprint=collector.sps_context.context_fingerprint,
        )
        self._finalized_collector_id = collector_id
        self._result = result
        return result
