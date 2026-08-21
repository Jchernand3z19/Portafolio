"""Transporte verificado para ``FacetDiscoveryRuntime`` sobre el gateway edge.

Esta capa no implementa HTTP ni genera autoridad live. Convierte las dos
solicitudes lógicas cerradas (`root_total`, `category_tree`) en requests edge
canónicos, exige un contexto suministrado explícitamente por el caller y sólo
devuelve el payload normalizado después de verificar Ed25519 + bytes + GraphQL.

No hay retries ocultos: WAIT, DENY, error de transporte, firma o body detienen
el runtime de facet discovery mediante una excepción clasificable.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import NoReturn, Protocol

from precios_supermercados.edge_structural_gateway_client import (
    StructuralEdgeExecutionRequest,
    StructuralEdgeGatewayClient,
    StructuralEdgeGatewayDenied,
    StructuralEdgeGatewayEvidence,
    StructuralEdgeGatewayWait,
    StructuralEdgeRequestContext,
)
from precios_supermercados.edge_structural_observation import (
    CryptographicallyVerifiedStructuralObservation,
    EdgeStructuralObservationError,
    EdgeStructuralObservationVerifier,
)
from precios_supermercados.la_colonia_edge_structural_request import (
    ValidatedLaColoniaStructuralRequest,
    build_structural_discovery_url,
    validate_la_colonia_structural_request,
)
from precios_supermercados.scrapers.la_colonia_facet_discovery import (
    FacetDiscoveryRequest,
)

_EXPECTED_REQUESTS = (
    FacetDiscoveryRequest("root_total", 1, "root_total"),
    FacetDiscoveryRequest("category_tree", 2, "category_tree"),
)


class VerifiedFacetDiscoveryTransportError(RuntimeError):
    """La observación estructural no puede entregarse al analizador de facets."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise VerifiedFacetDiscoveryTransportError(code, message)


class StructuralContextProvider(Protocol):
    def __call__(
        self,
        logical_request: FacetDiscoveryRequest,
        validated_request: ValidatedLaColoniaStructuralRequest,
    ) -> StructuralEdgeRequestContext: ...


class BearerTokenProvider(Protocol):
    def __call__(self) -> str: ...


class VerifiedFacetDiscoveryEdgeTransport:
    """Adapter stateful de exactamente dos requests lógicos a evidencia edge."""

    def __init__(
        self,
        client: StructuralEdgeGatewayClient,
        verifier: EdgeStructuralObservationVerifier,
        *,
        context_provider: StructuralContextProvider,
        bearer_token_provider: BearerTokenProvider,
    ) -> None:
        if not isinstance(client, StructuralEdgeGatewayClient):
            _fail("structural_gateway_client_invalid")
        if not isinstance(verifier, EdgeStructuralObservationVerifier):
            _fail("structural_observation_verifier_invalid")
        if not callable(context_provider):
            _fail("structural_context_provider_invalid")
        if not callable(bearer_token_provider):
            _fail("bearer_token_provider_invalid")
        self._client = client
        self._verifier = verifier
        self._context_provider = context_provider
        self._bearer_token_provider = bearer_token_provider
        self._next_sequence = 1
        self._observations: dict[str, CryptographicallyVerifiedStructuralObservation] = {}
        self._execution_fence: tuple[str, str, str] | None = None
        self._signed_fence: tuple[object, ...] | None = None

    @property
    def requests_completed(self) -> int:
        return len(self._observations)

    @property
    def observations(self) -> Mapping[str, CryptographicallyVerifiedStructuralObservation]:
        """Snapshot de sólo lectura; útil para reconciliación física posterior."""

        return MappingProxyType(dict(self._observations))

    @property
    def complete(self) -> bool:
        return set(self._observations) == {"root_total", "category_tree"}

    @staticmethod
    def _receipt_fence(
        observation: CryptographicallyVerifiedStructuralObservation,
    ) -> tuple[object, ...]:
        payload = observation.verified_receipt.receipt.payload
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
        )

    def __call__(self, logical_request: FacetDiscoveryRequest) -> Mapping[str, object]:
        if not isinstance(logical_request, FacetDiscoveryRequest):
            _fail("facet_logical_request_invalid")
        if self._next_sequence > len(_EXPECTED_REQUESTS):
            _fail("facet_request_count_exceeded")
        expected = _EXPECTED_REQUESTS[self._next_sequence - 1]
        if logical_request != expected:
            _fail("facet_request_sequence_invalid")
        if logical_request.name in self._observations:
            _fail("facet_request_duplicate")

        source_url = build_structural_discovery_url(logical_request.name)
        validated = validate_la_colonia_structural_request(source_url)
        try:
            context = self._context_provider(logical_request, validated)
        except VerifiedFacetDiscoveryTransportError:
            raise
        except Exception as exc:
            raise VerifiedFacetDiscoveryTransportError("structural_context_provider_failed") from exc
        if not isinstance(context, StructuralEdgeRequestContext):
            _fail("structural_context_invalid")
        if context.request_kind != logical_request.name:
            _fail("structural_context_request_kind_mismatch")
        if context.request_digest != validated.canonical_request_sha256:
            _fail("structural_context_request_digest_mismatch")

        fence = (context.authorization_id, context.run_id, context.approved_commit_sha)
        if self._execution_fence is None:
            self._execution_fence = fence
        elif self._execution_fence != fence:
            _fail("structural_execution_context_changed")

        try:
            token = self._bearer_token_provider()
        except Exception as exc:
            raise VerifiedFacetDiscoveryTransportError("bearer_token_provider_failed") from exc
        if not isinstance(token, str) or not token or token.strip() != token:
            _fail("bearer_token_invalid")

        execution = StructuralEdgeExecutionRequest(
            origin_url=validated.source_url,
            context=context,
        )
        try:
            result = self._client.execute(execution, bearer_token=token)
        except Exception as exc:
            raise VerifiedFacetDiscoveryTransportError("structural_gateway_execution_failed") from exc

        if isinstance(result, StructuralEdgeGatewayWait):
            _fail(f"structural_gateway_wait_{result.reason}")
        if isinstance(result, StructuralEdgeGatewayDenied):
            _fail(f"structural_gateway_denied_{result.reason}")
        if not isinstance(result, StructuralEdgeGatewayEvidence):
            _fail("structural_gateway_result_invalid")

        try:
            observation = self._verifier.verify(
                source_url=execution.origin_url,
                raw_body=result.raw_body,
                signed_receipt=result.receipt,
            )
        except EdgeStructuralObservationError as exc:
            raise VerifiedFacetDiscoveryTransportError(
                f"structural_observation_{exc.code}"
            ) from exc
        if observation.request_kind != logical_request.name:
            _fail("verified_observation_request_kind_mismatch")
        if observation.verified_receipt.receipt.digest != result.worker_evidence_id:
            _fail("verified_observation_worker_evidence_mismatch")
        if observation.production_authority is not False:
            _fail("verified_observation_authority_forbidden")

        signed_fence = self._receipt_fence(observation)
        if self._signed_fence is None:
            self._signed_fence = signed_fence
        elif self._signed_fence != signed_fence:
            _fail("structural_signed_execution_context_changed")

        self._observations[logical_request.name] = observation
        self._next_sequence += 1
        return observation.normalized_payload
