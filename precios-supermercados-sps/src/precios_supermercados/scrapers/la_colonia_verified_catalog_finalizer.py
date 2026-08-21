"""Finalización física del catálogo recolectado por el gateway edge.

La colección criptográfica y la evidencia de plataforma se mantienen separadas.
Esta capa sólo cierra un run cuando TODAS las páginas del plan canónico ya fueron
recolectadas, cada una reconcilia con Workers Observability y el manifest run-level
resultante coincide exactamente con el plan autenticado.

No implementa red, no hace polling/retry implícito y no concede
``production_authority``. La ausencia temporal de telemetría falla cerrado; una
capa operativa posterior puede decidir cuándo volver a intentar explícitamente.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn

from precios_supermercados.authenticated_provenance_run import (
    AuthenticatedProvenanceRunError,
    build_authenticated_edge_provenance_run_manifest,
)
from precios_supermercados.cloudflare_observability_verifier import (
    CloudflareObservabilityVerifierClient,
    CloudflareObservabilityVerifierError,
)
from precios_supermercados.cloudflare_trace_evidence import PlatformReconciledEdgePage
from precios_supermercados.edge_provenance_run import EdgeProvenanceRunManifest
from precios_supermercados.scrapers.la_colonia_verified_catalog_transport import (
    VerifiedCatalogCollection,
    VerifiedCatalogEdgeCollector,
)


class VerifiedCatalogPhysicalFinalizationError(RuntimeError):
    """El catálogo no puede convertirse en un run físicamente reconciliado."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise VerifiedCatalogPhysicalFinalizationError(code, message)


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
class PhysicallyReconciledCatalogCollection:
    """Colección completa, páginas de plataforma y manifest exacto del run."""

    collection: VerifiedCatalogCollection
    reconciled_pages: tuple[PlatformReconciledEdgePage, ...]
    run_manifest: EdgeProvenanceRunManifest
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.collection, VerifiedCatalogCollection):
            _fail("physical_collection_invalid")
        if self.collection.production_authority is not False:
            _fail("physical_collection_authority_invalid")
        if not self.reconciled_pages or any(
            not isinstance(page, PlatformReconciledEdgePage)
            for page in self.reconciled_pages
        ):
            _fail("physical_reconciled_pages_invalid")
        if not isinstance(self.run_manifest, EdgeProvenanceRunManifest):
            _fail("physical_run_manifest_invalid")
        if self.run_manifest.production_authority is not False:
            _fail("physical_run_manifest_authority_invalid")
        if len(self.reconciled_pages) != len(self.collection.observations):
            _fail("physical_reconciled_page_count_mismatch")
        if self.run_manifest.request_count != len(self.reconciled_pages):
            _fail("physical_manifest_request_count_mismatch")

        observed_pages = tuple(item.page for item in self.collection.observations)
        if tuple(item.page for item in self.reconciled_pages) != observed_pages:
            _fail("physical_reconciled_page_order_mismatch")

        physical_ids = tuple(item.physical_evidence_id for item in self.reconciled_pages)
        fetch_spans = tuple(item.trace_evidence.fetch_span_id for item in self.reconciled_pages)
        if len(set(physical_ids)) != len(physical_ids):
            _fail("physical_evidence_reused")
        if len(set(fetch_spans)) != len(fetch_spans):
            _fail("physical_fetch_span_reused")
        if self.production_authority is not False:
            _fail("physical_collection_production_authority_forbidden")


class VerifiedCatalogPhysicalFinalizer:
    """Reconcilia secuencialmente cada página ya recolectada con Observability."""

    def __init__(
        self,
        verifier_client: CloudflareObservabilityVerifierClient,
        *,
        bearer_token_provider: Callable[[], str],
    ) -> None:
        if not isinstance(verifier_client, CloudflareObservabilityVerifierClient):
            _fail("observability_verifier_client_invalid")
        if not callable(bearer_token_provider):
            _fail("observability_bearer_token_provider_invalid")
        self._verifier_client = verifier_client
        self._bearer_token_provider = bearer_token_provider
        self._finalized_collector_id: int | None = None
        self._result: PhysicallyReconciledCatalogCollection | None = None

    @property
    def account_id(self) -> str:
        return self._verifier_client.account_id

    @property
    def finalized(self) -> bool:
        return self._result is not None

    def finalize(
        self,
        collector: VerifiedCatalogEdgeCollector,
    ) -> PhysicallyReconciledCatalogCollection:
        """Cierra un único collector completo; no consulta páginas futuras tras fallo."""

        collector_id = id(collector)
        if self._result is not None:
            if self._finalized_collector_id != collector_id:
                _fail("finalizer_already_bound_to_other_collector")
            return self._result

        if not isinstance(collector, VerifiedCatalogEdgeCollector):
            _fail("verified_catalog_collector_invalid")
        if not collector.complete:
            _fail("verified_catalog_collector_incomplete")

        collection = collector.build_collection()
        plan = collector.authenticated_plan
        if collection.plan_digest != plan.digest:
            _fail("physical_collection_plan_digest_mismatch")
        if collection.discovery_digest != plan.discovery_digest:
            _fail("physical_collection_discovery_digest_mismatch")
        if len(collection.observations) != plan.request_count:
            _fail("physical_collection_page_count_mismatch")
        expected_identities = tuple(page.identity for page in plan.pages)
        observed_identities = tuple(item.expected.identity for item in collection.observations)
        if observed_identities != expected_identities:
            _fail("physical_collection_plan_order_mismatch")

        try:
            token = _bearer(self._bearer_token_provider())
        except VerifiedCatalogPhysicalFinalizationError:
            raise
        except Exception as exc:
            raise VerifiedCatalogPhysicalFinalizationError(
                "observability_bearer_token_provider_failed"
            ) from exc

        reconciled: list[PlatformReconciledEdgePage] = []
        physical_ids: set[str] = set()
        fetch_spans: set[str] = set()
        for index, observation in enumerate(collection.observations):
            try:
                page = self._verifier_client.reconcile_page(
                    observation.page,
                    bearer_token=token,
                )
            except CloudflareObservabilityVerifierError as exc:
                raise VerifiedCatalogPhysicalFinalizationError(
                    f"page_{index}_observability_{exc.code}"
                ) from exc
            if page.page is not observation.page:
                _fail(f"page_{index}_reconciled_page_identity_mismatch")
            if page.production_authority is not False:
                _fail(f"page_{index}_reconciled_authority_forbidden")
            if page.physical_evidence_id in physical_ids:
                _fail("physical_evidence_reused")
            fetch_span_id = page.trace_evidence.fetch_span_id
            if fetch_span_id in fetch_spans:
                _fail("physical_fetch_span_reused")
            physical_ids.add(page.physical_evidence_id)
            fetch_spans.add(fetch_span_id)
            reconciled.append(page)

        try:
            manifest = build_authenticated_edge_provenance_run_manifest(
                authenticated_plan=plan,
                reconciled_pages=tuple(reconciled),
            )
        except AuthenticatedProvenanceRunError as exc:
            raise VerifiedCatalogPhysicalFinalizationError(
                f"run_manifest_{exc.code}"
            ) from exc

        result = PhysicallyReconciledCatalogCollection(
            collection=collection,
            reconciled_pages=tuple(reconciled),
            run_manifest=manifest,
        )
        self._finalized_collector_id = collector_id
        self._result = result
        return result
