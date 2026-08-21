"""Orquestación offline-first del discovery estructural autenticado.

La capa une tres piezas ya cerradas de forma independiente:

1. ``FacetDiscoveryRuntime`` sobre un transporte edge que sólo expone payloads
   después de verificar Ed25519 + bytes + GraphQL;
2. Workers Observability para demostrar un child ``fetch`` físico por cada
   observación root/tree;
3. ``build_verified_structural_discovery`` para derivar el universo estructural
   privado que alimentará el plan exacto del catálogo.

No implementa HTTP, no hace retry, no persiste tokens y nunca convierte este
resultado en autoridad productiva por sí solo.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, NoReturn, Protocol

from precios_supermercados.cloudflare_structural_trace_evidence import (
    PlatformReconciledStructuralObservation,
)
from precios_supermercados.edge_structural_observation import (
    CryptographicallyVerifiedStructuralObservation,
)
from precios_supermercados.scrapers.la_colonia_facet_discovery_runtime import (
    FacetDiscoveryExecutionResult,
    FacetDiscoveryRuntime,
)
from precios_supermercados.scrapers.la_colonia_verified_facet_transport import (
    VerifiedFacetDiscoveryEdgeTransport,
)
from precios_supermercados.structural_discovery_manifest import (
    StructuralDiscoveryManifestError,
    VerifiedStructuralDiscovery,
    build_verified_structural_discovery,
)


class StructuralDiscoveryCoordinatorError(RuntimeError):
    """La ejecución no puede producir un manifest estructural verificado."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise StructuralDiscoveryCoordinatorError(code, message)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _token(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 20_000
        or any(character.isspace() for character in value)
    ):
        _fail("observability_bearer_token_invalid")
    return value


class StructuralObservabilityVerifier(Protocol):
    def reconcile_observation(
        self,
        observation: CryptographicallyVerifiedStructuralObservation,
        *,
        bearer_token: str,
    ) -> PlatformReconciledStructuralObservation: ...


class ObservabilityBearerTokenProvider(Protocol):
    def __call__(self) -> str: ...


@dataclass(frozen=True, slots=True)
class VerifiedStructuralDiscoveryExecution:
    facet_summary: Mapping[str, object]
    discovery: VerifiedStructuralDiscovery
    root_platform_evidence_id: str
    tree_platform_evidence_id: str
    production_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.facet_summary, Mapping):
            _fail("facet_summary_invalid")
        object.__setattr__(self, "facet_summary", _deep_freeze(self.facet_summary))
        if not isinstance(self.discovery, VerifiedStructuralDiscovery):
            _fail("verified_structural_discovery_invalid")
        if self.discovery.production_authority is not False:
            _fail("verified_structural_discovery_authority_invalid")
        for name in ("root_platform_evidence_id", "tree_platform_evidence_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                _fail(f"{name}_invalid")
            try:
                int(value, 16)
            except ValueError as exc:
                raise StructuralDiscoveryCoordinatorError(f"{name}_invalid") from exc
        if self.root_platform_evidence_id == self.tree_platform_evidence_id:
            _fail("structural_platform_evidence_reused")
        if self.facet_summary.get("discovery_outcome") != "within_budget":
            _fail("facet_summary_not_accepted")
        if self.facet_summary.get("root_total") != self.discovery.structure.root_total:
            _fail("facet_summary_root_total_mismatch")
        if self.facet_summary.get("leaf_partitions_count") != self.discovery.leaf_partitions_count:
            _fail("facet_summary_leaf_count_mismatch")
        if (
            self.facet_summary.get("positive_leaf_partitions")
            != self.discovery.positive_leaf_partitions
        ):
            _fail("facet_summary_positive_leaf_count_mismatch")
        if self.production_authority is not False:
            _fail("production_authority_forbidden")


class VerifiedStructuralDiscoveryCoordinator:
    """One-shot: facet runtime -> physical traces -> structural manifest."""

    def __init__(
        self,
        facet_transport: VerifiedFacetDiscoveryEdgeTransport,
        observability_verifier: StructuralObservabilityVerifier,
        *,
        observability_bearer_token_provider: ObservabilityBearerTokenProvider,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(facet_transport, VerifiedFacetDiscoveryEdgeTransport):
            _fail("verified_facet_transport_invalid")
        if not callable(getattr(observability_verifier, "reconcile_observation", None)):
            _fail("structural_observability_verifier_invalid")
        if not callable(observability_bearer_token_provider):
            _fail("observability_token_provider_invalid")
        if not callable(sleeper):
            _fail("sleeper_invalid")
        if clock is not None and not callable(clock):
            _fail("clock_invalid")
        self._facet_transport = facet_transport
        self._observability_verifier = observability_verifier
        self._token_provider = observability_bearer_token_provider
        self._sleeper = sleeper
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._used = False

    def run(
        self,
        command: Mapping[str, object],
    ) -> VerifiedStructuralDiscoveryExecution:
        if self._used:
            _fail("coordinator_already_used")
        self._used = True
        if self._facet_transport.requests_completed != 0:
            _fail("facet_transport_not_fresh")

        runtime = FacetDiscoveryRuntime(
            self._facet_transport,
            sleeper=self._sleeper,
            clock=self._clock,
            max_retries=0,
            max_requests=2,
        )
        result: FacetDiscoveryExecutionResult = runtime.run(command)
        if not result.accepted:
            reason = result.summary.get("stop_reason") or result.summary.get(
                "discovery_outcome",
                "unknown",
            )
            _fail(f"facet_discovery_{reason}")
        if not self._facet_transport.complete:
            _fail("facet_transport_incomplete")
        observations = self._facet_transport.observations
        if set(observations) != {"root_total", "category_tree"}:
            _fail("structural_observation_set_invalid")

        reconciled: dict[str, PlatformReconciledStructuralObservation] = {}
        for kind in ("root_total", "category_tree"):
            observation = observations[kind]
            if not isinstance(observation, CryptographicallyVerifiedStructuralObservation):
                _fail(f"{kind}_observation_invalid")
            try:
                token = _token(self._token_provider())
            except StructuralDiscoveryCoordinatorError:
                raise
            except Exception as exc:
                raise StructuralDiscoveryCoordinatorError(
                    "observability_token_provider_failed"
                ) from exc
            try:
                platform = self._observability_verifier.reconcile_observation(
                    observation,
                    bearer_token=token,
                )
            except Exception as exc:
                raise StructuralDiscoveryCoordinatorError(
                    f"{kind}_observability_reconciliation_failed"
                ) from exc
            if not isinstance(platform, PlatformReconciledStructuralObservation):
                _fail(f"{kind}_platform_observation_invalid")
            if platform.observation is not observation:
                _fail(f"{kind}_platform_observation_identity_mismatch")
            if platform.platform_evidence_reconciled is not True:
                _fail(f"{kind}_platform_evidence_unreconciled")
            if platform.production_authority is not False:
                _fail(f"{kind}_platform_authority_forbidden")
            reconciled[kind] = platform

        try:
            discovery = build_verified_structural_discovery(
                root_total=reconciled["root_total"],
                category_tree=reconciled["category_tree"],
            )
        except StructuralDiscoveryManifestError as exc:
            raise StructuralDiscoveryCoordinatorError(
                f"structural_manifest_{exc.code}"
            ) from exc

        return VerifiedStructuralDiscoveryExecution(
            facet_summary=result.summary,
            discovery=discovery,
            root_platform_evidence_id=reconciled[
                "root_total"
            ].trace_evidence.physical_evidence_id,
            tree_platform_evidence_id=reconciled[
                "category_tree"
            ].trace_evidence.physical_evidence_id,
        )
