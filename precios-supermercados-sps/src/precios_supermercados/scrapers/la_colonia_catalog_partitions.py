"""Planificación offline de particiones de catálogo mediante facets de categoría.

El módulo recibe fixtures equivalentes a una respuesta de facets ya obtenida. No
realiza HTTP y no publica nombres, valores ni identificadores de categorías.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .la_colonia_catalog_coverage import PartitionSpec
from .la_colonia_graphql import MAX_CATALOG_PAGE_SIZE

DEFAULT_MAX_PARTITIONS = 250
DEFAULT_MAX_PARTITION_REQUESTS = 500


@dataclass(frozen=True, slots=True)
class PartitionRequestPlan:
    partitions: tuple[PartitionSpec, ...]
    primary_requests: int
    probe_requests: int
    recovery_reserve: int
    reconciliation_requests: int
    requests_planned: int
    request_limit: int
    within_limit: bool


def discover_leaf_category_partitions(
    facets: Sequence[Mapping[str, Any]],
    *,
    sampling: bool = False,
    max_partitions: int = DEFAULT_MAX_PARTITIONS,
) -> tuple[PartitionSpec, ...]:
    """Extrae categorías hoja con cantidad positiva de un fixture de facets."""

    if sampling:
        raise ValueError("Facets muestreadas no demuestran todas las particiones")
    if max_partitions <= 0:
        raise ValueError("max_partitions debe ser mayor que cero")

    leaves: dict[tuple[str, str], int] = {}
    for facet in facets:
        if not isinstance(facet, Mapping):
            raise ValueError("Cada facet debe ser un objeto")
        values = facet.get("values", ())
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ValueError("facet.values debe ser una secuencia")
        _collect_leaf_values(values, leaves)

    ordered = sorted(leaves.items())
    if len(ordered) > max_partitions:
        raise ValueError("La cantidad de particiones supera el límite permitido")

    return tuple(
        PartitionSpec(
            name=f"partition-{index:04d}",
            facet_key=key,
            facet_value=value,
            expected_products=quantity,
            leaf=True,
        )
        for index, ((key, value), quantity) in enumerate(ordered, start=1)
    )


def estimate_partition_request_plan(
    partitions: Sequence[PartitionSpec],
    *,
    page_size: int,
    include_boundary_probes: bool = False,
    recovery_windows_per_partition: int = 0,
    max_recovery_partitions: int | None = None,
    reconcile_with_second_order: bool = False,
    max_reconciliation_partitions: int | None = None,
    request_limit: int = DEFAULT_MAX_PARTITION_REQUESTS,
) -> PartitionRequestPlan:
    """Calcula un límite previo sin realizar solicitudes.

    Los defaults conservan el comportamiento histórico. Cuando se activan sondas,
    se reserva una por cada frontera interna. La recuperación y reconciliación
    pueden limitarse a un número cerrado de particiones anómalas.
    """

    values = tuple(partitions)
    if not 1 <= page_size <= MAX_CATALOG_PAGE_SIZE:
        raise ValueError(
            f"page_size debe estar entre 1 y {MAX_CATALOG_PAGE_SIZE}"
        )
    if recovery_windows_per_partition < 0:
        raise ValueError("recovery_windows_per_partition no puede ser negativo")
    if max_recovery_partitions is not None and max_recovery_partitions < 0:
        raise ValueError("max_recovery_partitions no puede ser negativo")
    if (
        max_reconciliation_partitions is not None
        and max_reconciliation_partitions < 0
    ):
        raise ValueError("max_reconciliation_partitions no puede ser negativo")
    if request_limit <= 0:
        raise ValueError("request_limit debe ser mayor que cero")

    page_counts = [
        math.ceil(partition.expected_products / page_size)
        if partition.expected_products
        else 0
        for partition in values
    ]
    primary = sum(page_counts)
    probes = (
        sum(max(pages - 1, 0) for pages in page_counts)
        if include_boundary_probes
        else 0
    )

    recovery_partition_count = len(values)
    if max_recovery_partitions is not None:
        recovery_partition_count = min(
            recovery_partition_count, max_recovery_partitions
        )
    recovery = recovery_partition_count * recovery_windows_per_partition

    reconciliation = 0
    if reconcile_with_second_order:
        ordered_pages = sorted(page_counts, reverse=True)
        if max_reconciliation_partitions is not None:
            ordered_pages = ordered_pages[:max_reconciliation_partitions]
        reconciliation = sum(ordered_pages)

    planned = primary + probes + recovery + reconciliation
    return PartitionRequestPlan(
        partitions=values,
        primary_requests=primary,
        probe_requests=probes,
        recovery_reserve=recovery,
        reconciliation_requests=reconciliation,
        requests_planned=planned,
        request_limit=request_limit,
        within_limit=planned <= request_limit,
    )


def _collect_leaf_values(
    values: Sequence[Any],
    leaves: dict[tuple[str, str], int],
) -> None:
    for entry in values:
        if not isinstance(entry, Mapping):
            raise ValueError("Cada valor de facet debe ser un objeto")
        children = entry.get("children", ())
        if children is None:
            children = ()
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise ValueError("children debe ser una secuencia")
        if children:
            _collect_leaf_values(children, leaves)
            continue

        key = str(entry.get("key") or "").strip()
        value = str(entry.get("value") or "").strip()
        if not key.startswith("category-") or not value:
            continue
        try:
            quantity = int(entry.get("quantity", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("quantity debe ser un entero") from exc
        if quantity < 0:
            raise ValueError("quantity no puede ser negativo")
        if quantity == 0:
            continue

        identity = (key, value)
        previous = leaves.get(identity)
        if previous is not None and previous != quantity:
            raise ValueError("La misma categoría hoja tiene cantidades incompatibles")
        leaves[identity] = quantity
