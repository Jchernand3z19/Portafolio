"""Transporte secuencial de catálogo ligado al plan autenticado canónico.

La API no recibe URL, página, facet, order, IDs de request ni nonces. Todo se
deriva del ``AuthenticatedCatalogProvenancePlan`` y se vuelve a verificar contra
su ``VerifiedStructuralDiscovery``. El único input efímero externo es el bearer
token que autoriza cada llamada al gateway.

Esta capa no reintenta, no consulta Observability y no concede autoridad
productiva. Conserva las páginas Ed25519 verificadas para la reconciliación física
posterior.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from typing import NoReturn

from precios_supermercados.authenticated_provenance_plan import (
    AuthenticatedCatalogProvenancePlan,
)
from precios_supermercados.canonical_authenticated_provenance_plan import (
    CANONICAL_CATALOG_PAGE_SIZE,
    CANONICAL_CATALOG_REQUEST_LIMIT,
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
from precios_supermercados.edge_gateway_client import EdgeExecutionRequest, EdgeRequestContext
from precios_supermercados.edge_provenance import canonical_json_bytes
from precios_supermercados.edge_provenance_run import ExpectedProvenancePage
from precios_supermercados.la_colonia_edge_request import validate_la_colonia_edge_request
from precios_supermercados.scrapers.la_colonia_catalog_coverage import PartitionSpec
from precios_supermercados.scrapers.la_colonia_graphql import build_product_search_url

_REQUEST_ID_DOMAIN = b"precios-sps/catalog-request-id/v1\0"
_RESERVATION_ID_DOMAIN = b"precios-sps/catalog-reservation-id/v1\0"
_NONCE_DOMAIN = b"precios-sps/catalog-nonce/v1\0"


class VerifiedCatalogEdgeTransportError(RuntimeError):
    """El plan o una página edge no cumple la frontera canónica."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise VerifiedCatalogEdgeTransportError(code, message)


def _bearer(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 20_000
        or any(character.isspace() for character in value)
    ):
        _fail("catalog_bearer_token_invalid")
    return value


def _derived_identity(
    domain: bytes,
    plan_digest: str,
    expected: ExpectedProvenancePage,
    *,
    prefix: str,
) -> str:
    digest = hashlib.sha256(
        domain
        + canonical_json_bytes(
            {
                "expected": expected.canonical_dict(),
                "plan_digest": plan_digest,
            }
        )
    ).hexdigest()
    return f"{prefix}-{digest}"


class VerifiedCatalogEdgeTransport:
    """Ejecuta, en orden, exactamente las páginas del plan canónico autenticado."""

    def __init__(
        self,
        plan: AuthenticatedCatalogProvenancePlan,
        fetcher: EdgeCatalogPageFetcher,
        crypto_verifier: EdgeCatalogPageCryptoVerifier,
        *,
        bearer_token_provider: Callable[[], str],
    ) -> None:
        if not isinstance(plan, AuthenticatedCatalogProvenancePlan):
            _fail("catalog_plan_invalid")
        if not isinstance(fetcher, EdgeCatalogPageFetcher):
            _fail("catalog_fetcher_invalid")
        if not isinstance(crypto_verifier, EdgeCatalogPageCryptoVerifier):
            _fail("catalog_crypto_verifier_invalid")
        if not callable(bearer_token_provider):
            _fail("catalog_bearer_token_provider_invalid")

        canonical = derive_canonical_authenticated_catalog_plan(plan.discovery)
        if canonical.digest != plan.digest or canonical.plan.digest != plan.plan.digest:
            _fail("catalog_plan_not_canonical")
        if plan.request_count > CANONICAL_CATALOG_REQUEST_LIMIT:
            _fail("catalog_plan_request_limit_exceeded")
        if plan.plan.page_size != CANONICAL_CATALOG_PAGE_SIZE:
            _fail("catalog_plan_page_size_mismatch")

        partitions: dict[str, PartitionSpec] = {}
        for partition in plan.discovery.structure.valid_leaves:
            if partition.name in partitions:
                _fail("catalog_partition_name_duplicate")
            partitions[partition.name] = partition
        if not partitions:
            _fail("catalog_partitions_empty")

        self._plan = plan
        self._fetcher = fetcher
        self._crypto_verifier = crypto_verifier
        self._bearer_token_provider = bearer_token_provider
        self._partitions = partitions
        self._next_index = 0
        self._pages: list[CryptographicallyVerifiedEdgeCatalogPage] = []
        self._signed_fence: tuple[object, ...] | None = None

    @property
    def plan(self) -> AuthenticatedCatalogProvenancePlan:
        return self._plan

    @property
    def total_pages(self) -> int:
        return len(self._plan.pages)

    @property
    def completed_pages(self) -> int:
        return len(self._pages)

    @property
    def complete(self) -> bool:
        return self._next_index == self.total_pages and len(self._pages) == self.total_pages

    @property
    def pages(self) -> tuple[CryptographicallyVerifiedEdgeCatalogPage, ...]:
        return tuple(self._pages)

    @property
    def next_expected(self) -> ExpectedProvenancePage | None:
        if self._next_index >= self.total_pages:
            return None
        return self._plan.pages[self._next_index]

    def _source_url(self, expected: ExpectedProvenancePage) -> str:
        partition = self._partitions.get(expected.partition_id)
        if partition is None:
            _fail("catalog_expected_partition_missing")
        if partition.expected_products <= 0:
            _fail("catalog_expected_partition_not_positive")
        if expected.from_index % CANONICAL_CATALOG_PAGE_SIZE != 0:
            _fail("catalog_expected_page_boundary_invalid")
        if expected.to_index != expected.from_index + CANONICAL_CATALOG_PAGE_SIZE - 1:
            _fail("catalog_expected_page_width_invalid")
        page_number = expected.from_index // CANONICAL_CATALOG_PAGE_SIZE + 1
        source_url = build_product_search_url(
            page=page_number,
            page_size=CANONICAL_CATALOG_PAGE_SIZE,
            query=partition.facet_value,
            category_map=partition.facet_key,
            order_by=expected.order_by,
        )
        validated = validate_la_colonia_edge_request(source_url)
        if validated.canonical_request_sha256 != expected.request_digest:
            _fail("catalog_expected_request_digest_mismatch")
        if validated.from_index != expected.from_index or validated.to_index != expected.to_index:
            _fail("catalog_expected_request_range_mismatch")
        if validated.order_by != expected.order_by:
            _fail("catalog_expected_request_order_mismatch")
        return validated.source_url

    def _execution(self, expected: ExpectedProvenancePage) -> EdgeExecutionRequest:
        plan_digest = self._plan.digest
        context = EdgeRequestContext(
            authorization_id=self._plan.authorization_id,
            run_id=self._plan.run_id,
            approved_commit_sha=self._plan.approved_commit_sha,
            reservation_id=_derived_identity(
                _RESERVATION_ID_DOMAIN,
                plan_digest,
                expected,
                prefix="reservation",
            ),
            request_id=_derived_identity(
                _REQUEST_ID_DOMAIN,
                plan_digest,
                expected,
                prefix="request",
            ),
            request_digest=expected.request_digest,
            nonce=_derived_identity(
                _NONCE_DOMAIN,
                plan_digest,
                expected,
                prefix="nonce",
            ),
            traversal_role=expected.traversal_role,
            traversal_id=expected.traversal_id,
            partition_id=expected.partition_id,
        )
        return EdgeExecutionRequest(
            origin_url=self._source_url(expected),
            context=context,
        )

    def _expected_fence(self) -> tuple[object, ...]:
        discovery = self._plan.discovery
        if discovery.root_total.public_key_spki_sha256 != discovery.category_tree.public_key_spki_sha256:
            _fail("catalog_discovery_public_key_mismatch")
        return (
            discovery.run_id,
            discovery.authorization_id,
            discovery.approved_commit_sha,
            discovery.github_repository,
            discovery.github_repository_id,
            discovery.github_ref,
            discovery.github_workflow_ref,
            discovery.github_environment,
            discovery.github_run_id,
            discovery.github_run_attempt,
            discovery.oidc_subject,
            discovery.collector_provider,
            discovery.collector_principal,
            discovery.collector_release_id,
            discovery.collector_code_sha256,
            discovery.collector_signing_key_id,
            discovery.root_total.public_key_spki_sha256,
        )

    @staticmethod
    def _page_fence(page: CryptographicallyVerifiedEdgeCatalogPage) -> tuple[object, ...]:
        payload = page.verified_receipt.receipt.payload
        return (
            payload.run_id,
            payload.authorization_id,
            payload.approved_commit_sha,
            payload.github_repository,
            payload.github_repository_id,
            payload.github_ref,
            payload.github_workflow_ref,
            payload.github_environment,
            payload.github_run_id,
            payload.github_run_attempt,
            payload.oidc_subject,
            payload.collector_provider,
            payload.collector_principal,
            payload.collector_release_id,
            payload.collector_code_sha256,
            payload.signing_key_id,
            page.verified_receipt.public_key_spki_sha256,
        )

    @staticmethod
    def _match_expected(
        page: CryptographicallyVerifiedEdgeCatalogPage,
        expected: ExpectedProvenancePage,
        execution: EdgeExecutionRequest,
    ) -> None:
        payload = page.verified_receipt.receipt.payload
        if payload.request_id != execution.context.request_id:
            _fail("catalog_receipt_request_id_mismatch")
        if payload.reservation_id != execution.context.reservation_id:
            _fail("catalog_receipt_reservation_id_mismatch")
        if payload.nonce != execution.context.nonce:
            _fail("catalog_receipt_nonce_mismatch")
        if payload.request_digest != expected.request_digest:
            _fail("catalog_receipt_request_digest_mismatch")
        if payload.traversal_role != expected.traversal_role:
            _fail("catalog_receipt_traversal_role_mismatch")
        if payload.traversal_id != expected.traversal_id:
            _fail("catalog_receipt_traversal_id_mismatch")
        if payload.partition_id != expected.partition_id:
            _fail("catalog_receipt_partition_id_mismatch")
        if payload.order_by != expected.order_by:
            _fail("catalog_receipt_order_mismatch")
        if payload.from_index != expected.from_index or payload.to_index != expected.to_index:
            _fail("catalog_receipt_range_mismatch")
        if page.request.canonical_request_sha256 != expected.request_digest:
            _fail("catalog_page_request_digest_mismatch")
        if page.production_authority is not False:
            _fail("catalog_page_authority_forbidden")

    def execute_next(self) -> CryptographicallyVerifiedEdgeCatalogPage:
        """Ejecuta una sola página; WAIT/DENY/error no avanza el cursor."""
        expected = self.next_expected
        if expected is None:
            _fail("catalog_plan_already_complete")
        execution = self._execution(expected)
        try:
            token = _bearer(self._bearer_token_provider())
        except VerifiedCatalogEdgeTransportError:
            raise
        except Exception as exc:
            raise VerifiedCatalogEdgeTransportError(
                "catalog_bearer_token_provider_failed"
            ) from exc

        try:
            validated = self._fetcher.fetch(execution, bearer_token=token)
        except EdgeCatalogPageError as exc:
            raise VerifiedCatalogEdgeTransportError(f"catalog_fetch_{exc.code}") from exc
        try:
            page = self._crypto_verifier.verify(validated)
        except EdgeCryptoPageError as exc:
            raise VerifiedCatalogEdgeTransportError(f"catalog_crypto_{exc.code}") from exc

        self._match_expected(page, expected, execution)
        expected_fence = self._expected_fence()
        page_fence = self._page_fence(page)
        if page_fence != expected_fence:
            _fail("catalog_signed_fence_mismatch")
        if self._signed_fence is None:
            self._signed_fence = page_fence
        elif self._signed_fence != page_fence:
            _fail("catalog_signed_fence_changed")

        self._pages.append(page)
        self._next_index += 1
        return page
