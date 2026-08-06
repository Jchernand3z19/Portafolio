"""Contrato y análisis offline del descubrimiento de facets de La Colonia.

El módulo no realiza HTTP, no conoce GitHub Actions y no publica nombres ni
valores de categorías. El transporte futuro recibirá únicamente dos solicitudes
lógicas predeterminadas del plan ``catalog_categories_v1``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .la_colonia_catalog_coverage import PartitionSpec
from .la_colonia_catalog_partitions import (
    DEFAULT_MAX_PARTITIONS,
    PartitionRequestPlan,
    estimate_partition_request_plan,
)

FACET_DISCOVERY_SCHEMA_VERSION = "1.0.0"
FACET_DISCOVERY_REQUEST_ID = "la-colonia-facet-discovery-001"
FACET_DISCOVERY_MODE = "facet_discovery"
FACET_DISCOVERY_PLAN_NAME = "catalog_categories_v1"
FACET_DISCOVERY_DELAY_SECONDS = 1.5
FACET_DISCOVERY_PAGE_SIZE = 50
FACET_DISCOVERY_REQUEST_LIMIT = 500
FACET_DISCOVERY_MAX_REQUESTS = 2
FACET_DISCOVERY_CONCURRENCY = 1
FACET_DISCOVERY_MAX_CATEGORY_LEVEL = 8
FACET_DISCOVERY_RECOVERY_REQUESTS = 4
FACET_DISCOVERY_MAX_RECOVERY_PARTITIONS = 5
FACET_DISCOVERY_MAX_RECONCILIATION_PARTITIONS = 2
FACET_DISCOVERY_MAX_ARTIFACT_BYTES = 64 * 1024

_ALLOWED_COMMAND_FIELDS = frozenset(
    {
        "request_id",
        "supermarket",
        "mode",
        "discovery_plan",
        "delay_seconds",
        "allow_full",
    }
)
_CATEGORY_KEY_RE = re.compile(r"category-(\d+)\Z")
_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "url",
        "query",
        "selectedFacets",
        "selected_facets",
        "facet_value",
        "facet_values",
        "category_name",
        "category_value",
        "productId",
        "product_id",
        "itemId",
        "item_id",
        "sku",
        "ean",
        "brand",
        "price",
        "payload",
        "products",
    }
)


class FacetDiscoveryError(ValueError):
    """Error cerrado y clasificable del análisis de facets."""


class InvalidFacetQuantitiesError(FacetDiscoveryError):
    pass


class IncompleteFacetTreeError(FacetDiscoveryError):
    pass


class InvalidFacetStructureError(FacetDiscoveryError):
    pass


class FacetPartitionLimitError(FacetDiscoveryError):
    pass


@dataclass(frozen=True, slots=True)
class FacetDiscoveryCommand:
    request_id: str
    supermarket: str
    mode: str
    discovery_plan: str
    delay_seconds: float
    allow_full: bool


@dataclass(frozen=True, slots=True)
class FacetDiscoveryRequest:
    """Solicitud lógica predeterminada; no contiene URL ni query arbitraria."""

    name: str
    sequence: int
    response_kind: str


@dataclass(frozen=True, slots=True)
class FacetDiscoveryPlan:
    name: str
    requests: tuple[FacetDiscoveryRequest, ...]
    page_size: int = FACET_DISCOVERY_PAGE_SIZE
    request_limit: int = FACET_DISCOVERY_REQUEST_LIMIT
    max_requests: int = FACET_DISCOVERY_MAX_REQUESTS
    max_category_level: int = FACET_DISCOVERY_MAX_CATEGORY_LEVEL
    max_partitions: int = DEFAULT_MAX_PARTITIONS

    def __post_init__(self) -> None:
        if self.name != FACET_DISCOVERY_PLAN_NAME:
            raise ValueError("Plan de facets no autorizado")
        if self.requests != (
            FacetDiscoveryRequest("root_total", 1, "root_total"),
            FacetDiscoveryRequest("category_tree", 2, "category_tree"),
        ):
            raise ValueError("El plan debe contener las dos solicitudes cerradas")
        if self.max_requests != len(self.requests):
            raise ValueError("max_requests debe coincidir con el plan cerrado")
        if self.page_size != 50 or self.request_limit != 500:
            raise ValueError("Los límites del plan no pueden modificarse")


CATALOG_CATEGORIES_V1 = FacetDiscoveryPlan(
    name=FACET_DISCOVERY_PLAN_NAME,
    requests=(
        FacetDiscoveryRequest("root_total", 1, "root_total"),
        FacetDiscoveryRequest("category_tree", 2, "category_tree"),
    ),
)


@dataclass(frozen=True, slots=True)
class FacetLeafPartition:
    """Hoja privada; la ruta real nunca se serializa."""

    name: str
    quantity: int
    level: int
    _path: tuple[tuple[str, str], ...] = field(repr=False, compare=False)

    def budget_spec(self) -> PartitionSpec:
        key, value = self._path[-1]
        return PartitionSpec(
            name=self.name,
            facet_key=key,
            facet_value=value,
            expected_products=self.quantity,
            leaf=True,
        )


@dataclass(frozen=True, slots=True)
class FacetTreeAnalysis:
    root_total: int
    sampling: bool
    facet_levels_detected: tuple[str, ...]
    facet_values_count: Mapping[str, int]
    leaf_partitions: tuple[FacetLeafPartition, ...]
    leaf_partitions_count: int
    positive_leaf_partitions: int
    zero_quantity_partitions: int
    leaf_quantity_sum: int
    quality_events: tuple[str, ...]

    def budget_specs(self) -> tuple[PartitionSpec, ...]:
        return tuple(item.budget_spec() for item in self.leaf_partitions)


@dataclass(frozen=True, slots=True)
class FacetBudget:
    primary_requests: int
    probe_requests: int
    recovery_reserve: int
    reconciliation_requests: int
    total_estimated_requests: int
    request_limit: int
    within_request_limit: bool


def parse_facet_discovery_command(value: Mapping[str, Any]) -> FacetDiscoveryCommand:
    """Valida el contrato exacto; cualquier campo adicional queda rechazado."""

    if not isinstance(value, Mapping):
        raise ValueError("El contrato facet_discovery debe ser un objeto")
    keys = set(value)
    missing = _ALLOWED_COMMAND_FIELDS - keys
    extra = keys - _ALLOWED_COMMAND_FIELDS
    if missing:
        raise ValueError(f"Faltan campos requeridos: {sorted(missing)}")
    if extra:
        raise ValueError(f"El contrato contiene campos no permitidos: {sorted(extra)}")

    request_id = value["request_id"]
    supermarket = value["supermarket"]
    mode = value["mode"]
    discovery_plan = value["discovery_plan"]
    delay = value["delay_seconds"]
    allow_full = value["allow_full"]

    if request_id != FACET_DISCOVERY_REQUEST_ID:
        raise ValueError("request_id no autorizado")
    if supermarket != "la_colonia":
        raise ValueError("supermarket no autorizado")
    if mode != FACET_DISCOVERY_MODE:
        raise ValueError("mode no autorizado")
    if discovery_plan != FACET_DISCOVERY_PLAN_NAME:
        raise ValueError("discovery_plan no autorizado")
    if isinstance(delay, bool) or not isinstance(delay, (int, float)):
        raise ValueError("delay_seconds debe ser numérico")
    if float(delay) != FACET_DISCOVERY_DELAY_SECONDS:
        raise ValueError("delay_seconds debe ser exactamente 1.5")
    if allow_full is not False:
        raise ValueError("allow_full debe ser false")

    return FacetDiscoveryCommand(
        request_id=request_id,
        supermarket=supermarket,
        mode=mode,
        discovery_plan=discovery_plan,
        delay_seconds=float(delay),
        allow_full=False,
    )


def get_facet_discovery_plan(name: str) -> FacetDiscoveryPlan:
    if name != FACET_DISCOVERY_PLAN_NAME:
        raise ValueError("Plan de facets desconocido")
    return CATALOG_CATEGORIES_V1


def read_root_total(payload: Mapping[str, Any]) -> int:
    if not isinstance(payload, Mapping):
        raise InvalidFacetStructureError("La respuesta raíz debe ser un objeto")
    value = payload.get("recordsFiltered")
    if isinstance(value, bool):
        raise InvalidFacetQuantitiesError("recordsFiltered debe ser entero")
    try:
        total = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidFacetQuantitiesError("recordsFiltered debe ser entero") from exc
    if total < 0:
        raise InvalidFacetQuantitiesError("recordsFiltered no puede ser negativo")
    return total


def analyze_category_facets(
    payload: Mapping[str, Any],
    *,
    root_total: int,
    max_category_level: int = FACET_DISCOVERY_MAX_CATEGORY_LEVEL,
    max_partitions: int = DEFAULT_MAX_PARTITIONS,
) -> FacetTreeAnalysis:
    """Identifica las hojas más específicas de un fixture normalizado."""

    if root_total < 0:
        raise InvalidFacetQuantitiesError("root_total no puede ser negativo")
    if not isinstance(payload, Mapping):
        raise InvalidFacetStructureError("La respuesta de facets debe ser un objeto")

    response_total = read_root_total(payload)
    if response_total != root_total:
        raise InvalidFacetStructureError("El total cambió durante facet discovery")

    sampling = payload.get("sampling")
    if not isinstance(sampling, bool):
        raise InvalidFacetStructureError("sampling debe ser booleano")
    if sampling:
        return FacetTreeAnalysis(
            root_total=root_total,
            sampling=True,
            facet_levels_detected=(),
            facet_values_count={},
            leaf_partitions=(),
            leaf_partitions_count=0,
            positive_leaf_partitions=0,
            zero_quantity_partitions=0,
            leaf_quantity_sum=0,
            quality_events=("sampling_detected",),
        )

    facets = payload.get("facets")
    if not isinstance(facets, Sequence) or isinstance(facets, (str, bytes)):
        raise InvalidFacetStructureError("facets debe ser una secuencia")

    counts: dict[int, int] = {}
    leaves: list[tuple[int, int, tuple[tuple[str, str], ...]]] = []
    seen_paths: dict[tuple[tuple[str, str], ...], int] = {}
    events: list[str] = []

    category_facets = 0
    for facet in facets:
        if not isinstance(facet, Mapping):
            raise InvalidFacetStructureError("Cada facet debe ser un objeto")
        facet_type = str(facet.get("type") or "").strip().upper()
        if facet_type not in {"CATEGORYTREE", "CATEGORY"}:
            continue
        category_facets += 1
        values = facet.get("values")
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise InvalidFacetStructureError("facet.values debe ser una secuencia")
        _collect_nodes(
            values,
            parent_level=None,
            parent_path=(),
            parent_quantity=None,
            max_category_level=max_category_level,
            counts=counts,
            leaves=leaves,
            seen_paths=seen_paths,
        )

    if category_facets == 0:
        raise IncompleteFacetTreeError("No se devolvieron facets de categoría")

    positive = [item for item in leaves if item[1] > 0]
    zero_leaves = sum(item[1] == 0 for item in leaves)
    if len(positive) > max_partitions:
        raise FacetPartitionLimitError("La cantidad de hojas supera el límite")
    if not positive:
        raise IncompleteFacetTreeError("No existen particiones hoja positivas")

    leaf_quantity_sum = sum(quantity for _, quantity, _ in positive)
    if leaf_quantity_sum < root_total:
        raise IncompleteFacetTreeError(
            "La suma de hojas positivas no cubre el total raíz"
        )
    if leaf_quantity_sum > root_total:
        events.append("leaf_quantities_exceed_root_total")

    ordered = sorted(positive, key=lambda item: item[2])
    partitions = tuple(
        FacetLeafPartition(
            name=f"partition-{index:04d}",
            quantity=quantity,
            level=level,
            _path=path,
        )
        for index, (level, quantity, path) in enumerate(ordered, start=1)
    )
    level_names = tuple(f"category-{level}" for level in sorted(counts))
    counts_by_name = {f"category-{level}": counts[level] for level in sorted(counts)}
    return FacetTreeAnalysis(
        root_total=root_total,
        sampling=False,
        facet_levels_detected=level_names,
        facet_values_count=counts_by_name,
        leaf_partitions=partitions,
        leaf_partitions_count=len(leaves),
        positive_leaf_partitions=len(partitions),
        zero_quantity_partitions=zero_leaves,
        leaf_quantity_sum=leaf_quantity_sum,
        quality_events=tuple(events),
    )


def estimate_facet_discovery_budget(
    analysis: FacetTreeAnalysis,
    *,
    plan: FacetDiscoveryPlan = CATALOG_CATEGORIES_V1,
) -> FacetBudget:
    if analysis.sampling:
        return FacetBudget(0, 0, 0, 0, 0, plan.request_limit, False)
    request_plan: PartitionRequestPlan = estimate_partition_request_plan(
        analysis.budget_specs(),
        page_size=plan.page_size,
        include_boundary_probes=True,
        recovery_windows_per_partition=FACET_DISCOVERY_RECOVERY_REQUESTS,
        max_recovery_partitions=FACET_DISCOVERY_MAX_RECOVERY_PARTITIONS,
        reconcile_with_second_order=True,
        max_reconciliation_partitions=(
            FACET_DISCOVERY_MAX_RECONCILIATION_PARTITIONS
        ),
        request_limit=plan.request_limit,
    )
    return FacetBudget(
        primary_requests=request_plan.primary_requests,
        probe_requests=request_plan.probe_requests,
        recovery_reserve=request_plan.recovery_reserve,
        reconciliation_requests=request_plan.reconciliation_requests,
        total_estimated_requests=request_plan.requests_planned,
        request_limit=request_plan.request_limit,
        within_request_limit=request_plan.within_limit,
    )


def validate_sanitized_facet_summary(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in _FORBIDDEN_PUBLIC_KEYS:
                raise ValueError(f"Campo no permitido en resumen sanitizado: {key}")
            validate_sanitized_facet_summary(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            validate_sanitized_facet_summary(nested)


def serialize_sanitized_facet_summary(
    summary: Mapping[str, Any],
    *,
    max_bytes: int = FACET_DISCOVERY_MAX_ARTIFACT_BYTES,
) -> bytes:
    if max_bytes <= 0:
        raise ValueError("max_bytes debe ser mayor que cero")
    validate_sanitized_facet_summary(summary)
    encoded = json.dumps(
        summary, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError("El artefacto facet_discovery supera 64 KiB")
    return encoded


def _collect_nodes(
    values: Sequence[Any],
    *,
    parent_level: int | None,
    parent_path: tuple[tuple[str, str], ...],
    parent_quantity: int | None,
    max_category_level: int,
    counts: dict[int, int],
    leaves: list[tuple[int, int, tuple[tuple[str, str], ...]]],
    seen_paths: dict[tuple[tuple[str, str], ...], int],
) -> None:
    for node in values:
        if not isinstance(node, Mapping):
            raise InvalidFacetStructureError("Cada valor de facet debe ser objeto")
        key = str(node.get("key") or "").strip()
        value = str(node.get("value") or "").strip()
        match = _CATEGORY_KEY_RE.fullmatch(key)
        if not match or not value:
            raise InvalidFacetStructureError("Nivel o valor de categoría inválido")
        level = int(match.group(1))
        if not 1 <= level <= max_category_level:
            raise InvalidFacetStructureError("Nivel de categoría no permitido")
        expected_level = 1 if parent_level is None else parent_level + 1
        if level != expected_level:
            raise IncompleteFacetTreeError("La jerarquía de categorías tiene saltos")

        quantity_value = node.get("quantity")
        if isinstance(quantity_value, bool):
            raise InvalidFacetQuantitiesError("quantity debe ser entero")
        try:
            quantity = int(quantity_value)
        except (TypeError, ValueError) as exc:
            raise InvalidFacetQuantitiesError("quantity debe ser entero") from exc
        if quantity < 0:
            raise InvalidFacetQuantitiesError("quantity no puede ser negativo")
        if parent_quantity is not None and quantity > parent_quantity:
            raise InvalidFacetQuantitiesError(
                "Una categoría hija no puede exceder a su padre"
            )

        path = (*parent_path, (key, value))
        previous = seen_paths.get(path)
        if previous is not None:
            if previous != quantity:
                raise InvalidFacetQuantitiesError(
                    "La misma ruta tiene cantidades incompatibles"
                )
            continue
        seen_paths[path] = quantity
        counts[level] = counts.get(level, 0) + 1

        if "children" not in node:
            raise IncompleteFacetTreeError(
                "Cada nodo debe declarar children para distinguir hoja de corte"
            )
        children = node.get("children")
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise InvalidFacetStructureError("children debe ser una secuencia")
        if children:
            _collect_nodes(
                children,
                parent_level=level,
                parent_path=path,
                parent_quantity=quantity,
                max_category_level=max_category_level,
                counts=counts,
                leaves=leaves,
                seen_paths=seen_paths,
            )
        else:
            leaves.append((level, quantity, path))
