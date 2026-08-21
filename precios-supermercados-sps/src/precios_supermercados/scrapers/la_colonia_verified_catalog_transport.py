"""Colección edge del catálogo derivada del discovery estructural verificado.

El caller no aporta URLs, particiones, rangos, page size, órdenes ni traversal
IDs. La capa recibe un ``VerifiedStructuralDiscovery``, deriva internamente el
plan canónico y ejecuta exactamente sus páginas en orden.

Cada respuesta sólo puede alimentar cobertura después de validación estricta
del body y verificación Ed25519. La evidencia GraphQL inmutable se convierte a
estructuras JSON ordinarias únicamente después de esas verificaciones para
interoperar con el parser de cobertura existente.

Sigue siendo una composición offline: el transporte productivo se inyecta, no
consulta Observability y ``production_authority`` permanece siempre ``False``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn, Protocol

from precios_supermercados.authenticated_provenance_plan import (
    AuthenticatedCatalogProvenancePlan,
)
from precios_supermercados.canonical_authenticated_provenance_plan import (
    CanonicalAuthenticatedProvenancePlanError,
    derive_canonical_authenticated_catalog_plan,
)
from precios_supermercados.edge_catalog_page import (
    EdgeCatalogPageError,
    EdgeCatalogPageFetcher,
)
from precios_supermercados.edge_crypto_page import (
    CryptographicallyVerifiedEdgeCatalogPage,
    EdgeCatalogPageCryptoVerifier,
    EdgeCryptoPageError,
)
from precios_supermercados.edge_gateway_client import (
    EdgeExecutionRequest,
    EdgeGatewayClient,
    EdgeRequestContext,
)
from precios_supermercados.edge_provenance_run import ExpectedProvenancePage
from precios_supermercados.la_colonia_edge_request import (
    ValidatedLaColoniaEdgeRequest,
    validate_la_colonia_edge_request,
)
from precios_supermercados.scrapers.la_colonia_catalog_coverage import (
    RawPageEvidence,
    TraversalEvidence,
    build_traversal_evidence,
    raw_page_evidence_from_response,
)
from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url
from precios_supermercados.structural_discovery_manifest import VerifiedStructuralDiscovery


class VerifiedCatalogTransportError(RuntimeError):
    """La página no puede incorporarse a la colección autenticada."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise VerifiedCatalogTransportError(code, message)


class CatalogContextProvider(Protocol):
    def __call__(
        self,
        expected: ExpectedProvenancePage,
        validated_request: ValidatedLaColoniaEdgeRequest,
    ) -> EdgeRequestContext: ...


class BearerTokenProvider(Protocol):
    def __call__(self) -> str: ...


def _verified_payload_as_json(value: Any) -> Any:
    """Copia estructuras frozen a JSON mutable después de crypto/body verify."""

    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("catalog_verified_payload_key_invalid")
            result[key] = _verified_payload_as_json(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_verified_payload_as_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    _fail("catalog_verified_payload_value_invalid")


@dataclass(frozen=True, slots=True)
class VerifiedCatalogPageObservation:
    """Página íntegra y evidencia cruda derivada de esa misma página."""

    expected: ExpectedProvenancePage
    page: CryptographicallyVerifiedEdgeCatalogPage
    raw_evidence: RawPageEvidence
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.expected, ExpectedProvenancePage):
            _fail("catalog_observation_expected_invalid")
        if not isinstance(self.page, CryptographicallyVerifiedEdgeCatalogPage):
            _fail("catalog_observation_page_invalid")
        if not isinstance(self.raw_evidence, RawPageEvidence):
            _fail("catalog_observation_raw_evidence_invalid")
        if self.page.cryptographic_signature_verified is not True:
            _fail("catalog_observation_signature_unverified")
        if self.page.production_authority is not False:
            _fail("catalog_observation_page_authority_forbidden")
        if self.production_authority is not False:
            _fail("catalog_observation_authority_forbidden")

        raw_identity = (
            self.raw_evidence.run_id,
            self.raw_evidence.traversal_id,
            self.raw_evidence.partition,
            self.raw_evidence.order_by,
            self.raw_evidence.from_index,
            self.raw_evidence.to_index,
        )
        expected_identity = (
            self.page.verified_receipt.receipt.payload.run_id,
            self.expected.traversal_id,
            self.expected.partition_id,
            self.expected.order_by,
            self.expected.from_index,
            self.expected.to_index,
        )
        if raw_identity != expected_identity:
            _fail("catalog_observation_raw_evidence_mismatch")


@dataclass(frozen=True, slots=True)
class VerifiedCatalogCollection:
    """Primary + reconciliation completos de un plan canónico autenticado."""

    plan_digest: str
    discovery_digest: str
    primary: TraversalEvidence
    reconciliation: TraversalEvidence
    observations: tuple[VerifiedCatalogPageObservation, ...]
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.primary, TraversalEvidence):
            _fail("catalog_collection_primary_invalid")
        if not isinstance(self.reconciliation, TraversalEvidence):
            _fail("catalog_collection_reconciliation_invalid")
        if not self.observations or any(
            not isinstance(item, VerifiedCatalogPageObservation)
            for item in self.observations
        ):
            _fail("catalog_collection_observations_invalid")
        if self.primary.run_id != self.reconciliation.run_id:
            _fail("catalog_collection_run_id_mismatch")
        if self.primary.tree_digest != self.reconciliation.tree_digest:
            _fail("catalog_collection_tree_digest_mismatch")
        if self.primary.traversal_id == self.reconciliation.traversal_id:
            _fail("catalog_collection_traversal_ids_not_distinct")
        if self.primary.order_by == self.reconciliation.order_by:
            _fail("catalog_collection_orders_not_distinct")
        if self.production_authority is not False:
            _fail("catalog_collection_authority_forbidden")


class VerifiedCatalogEdgeCollector:
    """Ejecuta sólo la siguiente página del plan canónico derivado internamente."""

    def __init__(
        self,
        client: EdgeGatewayClient,
        crypto_verifier: EdgeCatalogPageCryptoVerifier,
        discovery: VerifiedStructuralDiscovery,
        *,
        context_provider: CatalogContextProvider,
        bearer_token_provider: BearerTokenProvider,
    ) -> None:
        if not isinstance(client, EdgeGatewayClient):
            _fail("catalog_gateway_client_invalid")
        if not isinstance(crypto_verifier, EdgeCatalogPageCryptoVerifier):
            _fail("catalog_crypto_verifier_invalid")
        if not isinstance(discovery, VerifiedStructuralDiscovery):
            _fail("catalog_discovery_invalid")
        if discovery.production_authority is not False:
            _fail("catalog_discovery_authority_invalid")
        if not callable(context_provider):
            _fail("catalog_context_provider_invalid")
        if not callable(bearer_token_provider):
            _fail("catalog_bearer_token_provider_invalid")

        try:
            plan = derive_canonical_authenticated_catalog_plan(discovery)
        except CanonicalAuthenticatedProvenancePlanError as exc:
            raise VerifiedCatalogTransportError(f"catalog_plan_{exc.code}") from exc
        if plan.discovery is not discovery:
            _fail("catalog_plan_discovery_identity_mismatch")

        leaves = discovery.structure.valid_leaves
        leaf_by_name = {leaf.name: leaf for leaf in leaves}
        if len(leaf_by_name) != len(leaves):
            _fail("catalog_partition_names_not_unique")
        expected_partitions = {page.partition_id for page in plan.pages}
        if expected_partitions != set(leaf_by_name):
            _fail("catalog_plan_partition_set_mismatch")

        self._fetcher = EdgeCatalogPageFetcher(client)
        self._crypto_verifier = crypto_verifier
        self._plan = plan
        self._context_provider = context_provider
        self._bearer_token_provider = bearer_token_provider
        self._leaf_by_name = leaf_by_name
        self._next_index = 0
        self._observations: list[VerifiedCatalogPageObservation] = []
        self._seen_request_ids: set[str] = set()
        self._seen_reservation_ids: set[str] = set()
        self._seen_nonces: set[str] = set()
        self._seen_receipt_digests: set[str] = set()
        self._seen_worker_evidence_ids: set[str] = set()

    @property
    def authenticated_plan(self) -> AuthenticatedCatalogProvenancePlan:
        return self._plan

    @property
    def requests_completed(self) -> int:
        return len(self._observations)

    @property
    def requests_expected(self) -> int:
        return self._plan.request_count

    @property
    def complete(self) -> bool:
        return self.requests_completed == self.requests_expected

    @property
    def observations(self) -> tuple[VerifiedCatalogPageObservation, ...]:
        return tuple(self._observations)

    @property
    def next_expected(self) -> ExpectedProvenancePage | None:
        if self.complete:
            return None
        return self._plan.pages[self._next_index]

    def _validated_request_for(
        self,
        expected: ExpectedProvenancePage,
    ) -> ValidatedLaColoniaEdgeRequest:
        leaf = self._leaf_by_name.get(expected.partition_id)
        if leaf is None:
            _fail("catalog_expected_partition_unknown")
        page_size = self._plan.plan.page_size
        if expected.from_index % page_size != 0:
            _fail("catalog_expected_range_not_page_aligned")
        page_number = expected.from_index // page_size + 1
        source_url = build_product_search_url(
            page=page_number,
            page_size=page_size,
            query=leaf.facet_value,
            category_map=leaf.facet_key,
            order_by=expected.order_by,
        )
        validated = validate_la_colonia_edge_request(source_url)
        if validated.selected_facets != ((leaf.facet_key, leaf.facet_value),):
            _fail("catalog_expected_partition_request_mismatch")
        if (
            validated.from_index != expected.from_index
            or validated.to_index != expected.to_index
            or validated.order_by != expected.order_by
            or validated.canonical_request_sha256 != expected.request_digest
        ):
            _fail("catalog_expected_request_mismatch")
        return validated

    def _context_for(
        self,
        expected: ExpectedProvenancePage,
        validated: ValidatedLaColoniaEdgeRequest,
    ) -> EdgeRequestContext:
        try:
            context = self._context_provider(expected, validated)
        except VerifiedCatalogTransportError:
            raise
        except Exception as exc:
            raise VerifiedCatalogTransportError("catalog_context_provider_failed") from exc
        if not isinstance(context, EdgeRequestContext):
            _fail("catalog_request_context_invalid")

        expected_values = {
            "authorization_id": self._plan.authorization_id,
            "run_id": self._plan.run_id,
            "approved_commit_sha": self._plan.approved_commit_sha,
            "request_digest": expected.request_digest,
            "traversal_role": expected.traversal_role,
            "traversal_id": expected.traversal_id,
            "partition_id": expected.partition_id,
        }
        for name, value in expected_values.items():
            if getattr(context, name) != value:
                _fail(f"catalog_request_context_{name}_mismatch")
        if context.request_digest != validated.canonical_request_sha256:
            _fail("catalog_request_context_digest_mismatch")
        return context

    def _token(self) -> str:
        try:
            token = self._bearer_token_provider()
        except Exception as exc:
            raise VerifiedCatalogTransportError("catalog_bearer_token_provider_failed") from exc
        if (
            not isinstance(token, str)
            or not token
            or token.strip() != token
            or any(character.isspace() for character in token)
        ):
            _fail("catalog_bearer_token_invalid")
        return token

    def _assert_receipt_bindings(
        self,
        observation: CryptographicallyVerifiedEdgeCatalogPage,
        expected: ExpectedProvenancePage,
    ) -> None:
        payload = observation.verified_receipt.receipt.payload
        discovery = self._plan.discovery
        expected_values = {
            "run_id": self._plan.run_id,
            "authorization_id": self._plan.authorization_id,
            "approved_commit_sha": self._plan.approved_commit_sha,
            "request_digest": expected.request_digest,
            "traversal_role": expected.traversal_role,
            "traversal_id": expected.traversal_id,
            "partition_id": expected.partition_id,
            "order_by": expected.order_by,
            "from_index": expected.from_index,
            "to_index": expected.to_index,
            "github_repository": discovery.github_repository,
            "github_repository_id": discovery.github_repository_id,
            "github_ref": discovery.github_ref,
            "github_workflow_ref": discovery.github_workflow_ref,
            "github_environment": discovery.github_environment,
            "github_run_id": discovery.github_run_id,
            "github_run_attempt": discovery.github_run_attempt,
            "oidc_subject": discovery.oidc_subject,
            "collector_provider": discovery.collector_provider,
            "collector_principal": discovery.collector_principal,
            "collector_release_id": discovery.collector_release_id,
            "collector_code_sha256": discovery.collector_code_sha256,
            "signing_key_id": discovery.collector_signing_key_id,
        }
        for name, value in expected_values.items():
            if getattr(payload, name) != value:
                _fail(f"catalog_receipt_{name}_mismatch")

        expected_key_hash = discovery.root_total.public_key_spki_sha256
        if discovery.category_tree.public_key_spki_sha256 != expected_key_hash:
            _fail("catalog_discovery_public_key_mismatch")
        if observation.verified_receipt.public_key_spki_sha256 != expected_key_hash:
            _fail("catalog_receipt_public_key_mismatch")
        if observation.production_authority is not False:
            _fail("catalog_verified_page_authority_forbidden")

    def _unique_values(
        self,
        page: CryptographicallyVerifiedEdgeCatalogPage,
    ) -> tuple[tuple[str, set[str], str], ...]:
        payload = page.verified_receipt.receipt.payload
        return (
            (payload.request_id, self._seen_request_ids, "catalog_request_id_reused"),
            (
                payload.reservation_id,
                self._seen_reservation_ids,
                "catalog_reservation_id_reused",
            ),
            (payload.nonce, self._seen_nonces, "catalog_nonce_reused"),
            (
                page.verified_receipt.receipt_digest,
                self._seen_receipt_digests,
                "catalog_receipt_reused",
            ),
            (
                page.worker_evidence_id,
                self._seen_worker_evidence_ids,
                "catalog_worker_evidence_reused",
            ),
        )

    def _assert_not_reused(
        self,
        page: CryptographicallyVerifiedEdgeCatalogPage,
    ) -> tuple[tuple[str, set[str], str], ...]:
        values = self._unique_values(page)
        for value, seen, code in values:
            if value in seen:
                _fail(code)
        return values

    @staticmethod
    def _remember(values: tuple[tuple[str, set[str], str], ...]) -> None:
        for value, seen, _code in values:
            seen.add(value)

    def collect_next(self) -> VerifiedCatalogPageObservation:
        """Recolecta exactamente la siguiente página; WAIT/DENY no se reintentan."""

        expected = self.next_expected
        if expected is None:
            _fail("catalog_plan_already_complete")
        validated = self._validated_request_for(expected)
        context = self._context_for(expected, validated)
        execution = EdgeExecutionRequest(origin_url=validated.source_url, context=context)

        try:
            page = self._fetcher.fetch(execution, bearer_token=self._token())
        except EdgeCatalogPageError as exc:
            raise VerifiedCatalogTransportError(f"catalog_{exc.code}") from exc
        except Exception as exc:
            raise VerifiedCatalogTransportError("catalog_gateway_execution_failed") from exc

        try:
            verified = self._crypto_verifier.verify(page)
        except EdgeCryptoPageError as exc:
            raise VerifiedCatalogTransportError(f"catalog_crypto_{exc.code}") from exc
        self._assert_receipt_bindings(verified, expected)
        unique_values = self._assert_not_reused(verified)

        verified_payload = _verified_payload_as_json(verified.payload)
        if not isinstance(verified_payload, Mapping):
            _fail("catalog_verified_payload_not_object")
        try:
            raw_evidence = raw_page_evidence_from_response(
                run_id=self._plan.run_id,
                traversal_id=expected.traversal_id,
                partition=expected.partition_id,
                order_by=expected.order_by,
                from_index=expected.from_index,
                to_index=expected.to_index,
                response=verified_payload,
            )
        except (TypeError, ValueError) as exc:
            raise VerifiedCatalogTransportError("catalog_raw_evidence_invalid") from exc

        observation = VerifiedCatalogPageObservation(
            expected=expected,
            page=verified,
            raw_evidence=raw_evidence,
        )
        self._remember(unique_values)
        self._observations.append(observation)
        self._next_index += 1
        return observation

    def build_collection(self) -> VerifiedCatalogCollection:
        """Cierra ambos traversals sólo después de recolectar el plan completo."""

        if not self.complete:
            _fail("catalog_plan_incomplete")
        primary_pages = tuple(
            observation.raw_evidence
            for observation in self._observations
            if observation.expected.traversal_role == "primary"
        )
        reconciliation_pages = tuple(
            observation.raw_evidence
            for observation in self._observations
            if observation.expected.traversal_role == "reconciliation"
        )
        if len(primary_pages) != len(self._plan.primary_pages):
            _fail("catalog_primary_page_count_mismatch")
        if len(reconciliation_pages) != len(self._plan.reconciliation_pages):
            _fail("catalog_reconciliation_page_count_mismatch")

        primary = build_traversal_evidence(
            run_id=self._plan.run_id,
            traversal_id=self._plan.plan.primary_traversal_id,
            tree_digest=self._plan.plan.tree_digest,
            order_by=self._plan.plan.primary_order_by,
            pages=primary_pages,
        )
        reconciliation = build_traversal_evidence(
            run_id=self._plan.run_id,
            traversal_id=self._plan.plan.reconciliation_traversal_id,
            tree_digest=self._plan.plan.tree_digest,
            order_by=self._plan.plan.reconciliation_order_by,
            pages=reconciliation_pages,
        )
        return VerifiedCatalogCollection(
            plan_digest=self._plan.digest,
            discovery_digest=self._plan.discovery_digest,
            primary=primary,
            reconciliation=reconciliation,
            observations=tuple(self._observations),
        )

    def collect_all(self) -> VerifiedCatalogCollection:
        """Recorre el plan exacto secuencialmente; cualquier fallo detiene el run."""

        while not self.complete:
            self.collect_next()
        return self.build_collection()
