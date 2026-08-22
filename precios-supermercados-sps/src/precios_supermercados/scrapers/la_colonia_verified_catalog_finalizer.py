"""Finalización física run-level del catálogo autenticado de La Colonia.

Compone piezas ya cerradas sin abrir una segunda ruta de confianza:

1. ``VerifiedCatalogEdgeCollector`` debe haber completado el plan canónico exacto;
2. cada página criptográficamente verificada se reconcilia una vez contra
   Workers Observability;
3. el conjunto reconciliado completo se entrega al manifest autenticado
   run-level existente, que vuelve a exigir páginas exactas y evidencia física
   única.

No implementa HTTP, no reintenta, no persiste bearer tokens y no concede
``production_authority``.
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
    VerifiedCatalogPageObservation,
    VerifiedCatalogTransportError,
)


class VerifiedCatalogFinalizationError(RuntimeError):
    """El catálogo no puede convertirse en un run de provenance física cerrado."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise VerifiedCatalogFinalizationError(code, message)


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
class VerifiedCatalogProvenanceRun:
    """Catálogo recolectado + evidencia física cerrada del mismo plan."""

    collection: VerifiedCatalogCollection
    reconciled_pages: tuple[PlatformReconciledEdgePage, ...]
    manifest: EdgeProvenanceRunManifest
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.collection, VerifiedCatalogCollection):
            _fail("catalog_collection_invalid")
        if not self.reconciled_pages or any(
            not isinstance(page, PlatformReconciledEdgePage)
            for page in self.reconciled_pages
        ):
            _fail("catalog_reconciled_pages_invalid")
        if not isinstance(self.manifest, EdgeProvenanceRunManifest):
            _fail("catalog_provenance_manifest_invalid")
        if self.manifest.production_authority is not False:
            _fail("catalog_provenance_manifest_authority_forbidden")
        if self.manifest.request_count != len(self.reconciled_pages):
            _fail("catalog_provenance_request_count_mismatch")
        if self.production_authority is not False:
            _fail("catalog_provenance_authority_forbidden")


class VerifiedCatalogProvenanceFinalizer:
    """Finalizador one-shot lógico para un collector de catálogo completo."""

    def __init__(
        self,
        verifier_client: CloudflareObservabilityVerifierClient,
        *,
        bearer_token_provider: Callable[[], str],
    ) -> None:
        if not isinstance(verifier_client, CloudflareObservabilityVerifierClient):
            _fail("catalog_observability_verifier_client_invalid")
        if not callable(bearer_token_provider):
            _fail("observability_bearer_token_provider_invalid")
        self._verifier_client = verifier_client
        self._bearer_token_provider = bearer_token_provider
        self._finalized_collector_id: int | None = None
        self._result: VerifiedCatalogProvenanceRun | None = None

    @property
    def account_id(self) -> str:
        return self._verifier_client.account_id

    @property
    def finalized(self) -> bool:
        return self._result is not None

    def _snapshot(
        self,
        collector: VerifiedCatalogEdgeCollector,
    ) -> tuple[VerifiedCatalogCollection, tuple[VerifiedCatalogPageObservation, ...]]:
        if not isinstance(collector, VerifiedCatalogEdgeCollector):
            _fail("verified_catalog_collector_invalid")
        if not collector.complete:
            _fail("verified_catalog_collector_incomplete")

        observations = collector.observations
        plan = collector.authenticated_plan
        if len(observations) != plan.request_count:
            _fail("verified_catalog_observation_count_mismatch")
        if any(
            not isinstance(observation, VerifiedCatalogPageObservation)
            for observation in observations
        ):
            _fail("verified_catalog_observation_invalid")
        expected = tuple(page.identity for page in plan.pages)
        observed = tuple(observation.expected.identity for observation in observations)
        if observed != expected:
            _fail("verified_catalog_observation_order_mismatch")
        for observation in observations:
            if observation.page.cryptographic_signature_verified is not True:
                _fail("verified_catalog_observation_signature_unverified")
            if observation.page.production_authority is not False:
                _fail("verified_catalog_observation_authority_forbidden")
            if observation.production_authority is not False:
                _fail("verified_catalog_observation_authority_forbidden")

        try:
            collection = collector.build_collection()
        except VerifiedCatalogTransportError as exc:
            raise VerifiedCatalogFinalizationError(
                f"catalog_collection_{exc.code}"
            ) from exc
        if collection.plan_digest != plan.digest:
            _fail("catalog_collection_plan_digest_mismatch")
        if collection.discovery_digest != plan.discovery_digest:
            _fail("catalog_collection_discovery_digest_mismatch")
        return collection, observations

    def finalize(
        self,
        collector: VerifiedCatalogEdgeCollector,
    ) -> VerifiedCatalogProvenanceRun:
        """Reconcilia páginas en orden y cierra el manifest autenticado completo.

        Una segunda llamada con el mismo collector devuelve el resultado cacheado
        sin volver a consultar Observability. Un collector distinto se rechaza.
        """

        collector_id = id(collector)
        if self._result is not None:
            if self._finalized_collector_id != collector_id:
                _fail("finalizer_already_bound_to_other_collector")
            return self._result

        collection, observations = self._snapshot(collector)
        try:
            token = _bearer(self._bearer_token_provider())
        except VerifiedCatalogFinalizationError:
            raise
        except Exception as exc:
            raise VerifiedCatalogFinalizationError(
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
                raise VerifiedCatalogFinalizationError(
                    f"catalog_page_{ordinal}_observability_{exc.code}"
                ) from exc
            if not isinstance(page, PlatformReconciledEdgePage):
                _fail("catalog_observability_result_invalid")
            # El verifier de plataforma no puede sustituir la página que se le
            # entregó por otra página válida. La identidad de objeto preserva la
            # cadena exacta crypto/body → trace para este ordinal del plan.
            if page.page is not observation.page:
                _fail("catalog_observability_page_identity_mismatch")
            if page.platform_evidence_reconciled is not True:
                _fail("catalog_observability_result_unreconciled")
            if page.production_authority is not False:
                _fail("catalog_observability_authority_forbidden")

            physical_evidence_id = page.physical_evidence_id
            if physical_evidence_id in physical_evidence_ids:
                _fail("physical_evidence_reused")
            fetch_span_id = page.trace_evidence.fetch_span_id
            if fetch_span_id in fetch_span_ids:
                _fail("physical_fetch_span_reused")
            physical_evidence_ids.add(physical_evidence_id)
            fetch_span_ids.add(fetch_span_id)
            reconciled.append(page)

        try:
            manifest = build_authenticated_edge_provenance_run_manifest(
                authenticated_plan=collector.authenticated_plan,
                reconciled_pages=tuple(reconciled),
            )
        except AuthenticatedProvenanceRunError as exc:
            raise VerifiedCatalogFinalizationError(
                f"catalog_run_manifest_{exc.code}"
            ) from exc

        result = VerifiedCatalogProvenanceRun(
            collection=collection,
            reconciled_pages=tuple(reconciled),
            manifest=manifest,
        )
        self._finalized_collector_id = collector_id
        self._result = result
        return result
