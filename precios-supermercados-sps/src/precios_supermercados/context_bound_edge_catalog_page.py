"""Frontera de página para el gateway de catálogo ligado a SPS.

Convierte únicamente un ``ContextBoundCatalogExecutionRequest`` ejecutado por
``CatalogContextGatewayClient`` en la misma ``ValidatedEdgeCatalogPage`` que
consume el verifier criptográfico existente. Esto permite reutilizar la
validación estricta del body sin volver a abrir la ruta legacy ``/v1/execute``.

El contexto raw de ubicación permanece encapsulado en el request privado y no se
copia a la página resultante. La capa no verifica la firma por sí sola y nunca
concede autoridad productiva.
"""

from __future__ import annotations

from typing import NoReturn

from precios_supermercados.catalog_context_gateway_client import (
    CatalogContextGatewayClient,
    CatalogContextGatewayClientError,
    ContextBoundCatalogExecutionRequest,
)
from precios_supermercados.edge_catalog_page import ValidatedEdgeCatalogPage
from precios_supermercados.edge_gateway_client import (
    EdgeGatewayDenied,
    EdgeGatewayEvidence,
    EdgeGatewayWait,
)
from precios_supermercados.la_colonia_edge_body import (
    LaColoniaEdgeBodyError,
    validate_la_colonia_edge_body,
)


class ContextBoundEdgeCatalogPageError(RuntimeError):
    """La ejecución context-bound no produjo una página validada."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise ContextBoundEdgeCatalogPageError(code, message)


class ContextBoundEdgeCatalogPageFetcher:
    """Adapta ``/v1/catalog-execute`` a una página GraphQL validada."""

    def __init__(self, client: CatalogContextGatewayClient) -> None:
        if not isinstance(client, CatalogContextGatewayClient):
            _fail("catalog_context_gateway_client_invalid")
        self._client = client

    def fetch(
        self,
        request: ContextBoundCatalogExecutionRequest,
        *,
        bearer_token: str,
    ) -> ValidatedEdgeCatalogPage:
        if not isinstance(request, ContextBoundCatalogExecutionRequest):
            _fail("catalog_context_execution_request_invalid")

        try:
            result = self._client.execute(request, bearer_token=bearer_token)
        except CatalogContextGatewayClientError as exc:
            raise ContextBoundEdgeCatalogPageError(
                f"catalog_context_gateway_{exc.code}"
            ) from exc

        if isinstance(result, EdgeGatewayWait):
            _fail(
                "catalog_context_gateway_wait",
                f"gateway WAIT: {result.reason}; not_before_ms={result.not_before_ms}",
            )
        if isinstance(result, EdgeGatewayDenied):
            _fail(
                "catalog_context_gateway_denied",
                f"gateway DENY: {result.reason}",
            )
        if not isinstance(result, EdgeGatewayEvidence):
            _fail("catalog_context_gateway_result_invalid")

        validated_request = request.validated_origin
        if validated_request.canonical_request_sha256 != request.context.request_digest:
            _fail("catalog_context_request_digest_mismatch")

        try:
            validated_body = validate_la_colonia_edge_body(
                result.raw_body,
                validated_request,
            )
        except LaColoniaEdgeBodyError as exc:
            raise ContextBoundEdgeCatalogPageError(
                f"catalog_context_body_{exc.code}"
            ) from exc

        return ValidatedEdgeCatalogPage(
            request=validated_request,
            evidence=result,
            body=validated_body,
        )
