"""Contrato offline y sanitizado de cobertura para el catálogo de La Colonia.

Este módulo no realiza solicitudes HTTP, no modifica el runner normal y no
persiste datos comerciales. Las identidades de producto se mantienen únicamente
en memoria para demostrar cobertura, detectar repeticiones y reconciliar
particiones u órdenes de búsqueda.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from .la_colonia_graphql import ALLOWED_ORDER_BY, MAX_CATALOG_PAGE_SIZE

COVERAGE_SCHEMA_VERSION = "1.0.0"
DEFAULT_MAX_COVERAGE_REQUESTS = 500
_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "productId",
        "product_id",
        "itemId",
        "item_id",
        "sku",
        "ean",
        "productName",
        "product_name",
        "brand",
        "price",
        "url",
        "source_key",
        "source_key_hash",
        "product_key",
        "product_keys",
    }
)


@dataclass(frozen=True, slots=True)
class PartitionSpec:
    """Partición lógica cerrada, normalmente una categoría hoja."""

    name: str
    facet_key: str
    facet_value: str
    expected_products: int
    leaf: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name no puede estar vacío")
        if not self.facet_key.strip() or not self.facet_value.strip():
            raise ValueError("facet_key y facet_value no pueden estar vacíos")
        if self.expected_products < 0:
            raise ValueError("expected_products no puede ser negativo")
        if not self.facet_key.startswith("category-"):
            raise ValueError("La partición debe usar una facet de categoría")


@dataclass(frozen=True, slots=True)
class CoveragePageObservation:
    """Respuesta agregada; las identidades privadas nunca se serializan."""

    partition: str
    order_by: str
    from_index: int
    to_index: int
    records_filtered: int
    products_received: int
    products_expected: int
    complete: bool
    membership_valid: bool
    sequence_signature: str
    set_signature: str
    quality_events: tuple[str, ...] = ()
    _product_keys: tuple[str, ...] = field(default=(), repr=False, compare=False)

    @property
    def width(self) -> int:
        return self.to_index - self.from_index + 1


@dataclass(frozen=True, slots=True)
class PartitionCoverageResult:
    """Cobertura demostrada o rechazada para una partición."""

    partition: str
    pages_expected: int
    pages_attempted: int
    pages_completed: int
    products_reported: int
    products_received: int
    products_unique: int
    duplicate_occurrences: int
    repeated_page_sets: int
    unexpected_overlaps: int
    missing_coverage_events: int
    total_changes: int
    orderings_attempted: int
    orderings_reconciled: bool
    coverage_demonstrated: bool
    coverage_reason: str
    _product_keys: tuple[str, ...] = field(default=(), repr=False, compare=False)
    _reasons: tuple[str, ...] = field(default=(), repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class CatalogCoverageReport:
    """Resumen agregado sin productos, categorías ni identificadores."""

    partitions_discovered: int
    partitions_attempted: int
    partitions_completed: int
    pages_expected: int
    pages_attempted: int
    pages_completed: int
    products_reported: int
    products_received: int
    products_unique: int
    duplicate_occurrences: int
    repeated_page_sets: int
    unexpected_overlaps: int
    missing_coverage_events: int
    total_changes: int
    uncategorized_products: int
    request_limit: int
    coverage_demonstrated: bool
    coverage_reason: str
    accepted: bool
    _reasons: tuple[str, ...] = field(default=(), repr=False, compare=False)

    def sanitized_summary(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("_reasons", None)
        value = {"schema_version": COVERAGE_SCHEMA_VERSION, **value}
        validate_sanitized_coverage_summary(value)
        return value


def observe_coverage_page(
    *,
    partition: str,
    order_by: str,
    from_index: int,
    to_index: int,
    records_filtered: int,
    product_keys: Sequence[str],
    membership_valid: bool = True,
) -> CoveragePageObservation:
    """Crea una observación offline a partir de identidades privadas."""

    if not partition.strip():
        raise ValueError("partition no puede estar vacía")
    if order_by not in ALLOWED_ORDER_BY:
        raise ValueError(f"order_by no permitido: {order_by}")
    if from_index < 0 or to_index < from_index:
        raise ValueError("Rango de página inválido")
    width = to_index - from_index + 1
    if width > MAX_CATALOG_PAGE_SIZE:
        raise ValueError(
            f"La página no puede superar {MAX_CATALOG_PAGE_SIZE} posiciones"
        )
    if records_filtered < 0:
        raise ValueError("records_filtered no puede ser negativo")

    keys = tuple(str(key).strip() for key in product_keys)
    if any(not key for key in keys):
        raise ValueError("Las identidades privadas no pueden estar vacías")
    expected = min(width, max(records_filtered - from_index, 0))
    events: list[str] = []
    if len(keys) < expected:
        events.append("partial_page")
    elif len(keys) > expected:
        events.append("more_products_than_expected")
    if len(set(keys)) != len(keys):
        events.append("duplicate_within_page")
    if not membership_valid:
        events.append("partition_membership_invalid")

    return CoveragePageObservation(
        partition=partition,
        order_by=order_by,
        from_index=from_index,
        to_index=to_index,
        records_filtered=records_filtered,
        products_received=len(keys),
        products_expected=expected,
        complete=len(keys) == expected,
        membership_valid=membership_valid,
        sequence_signature=_signature(keys),
        set_signature=_signature(sorted(set(keys))),
        quality_events=tuple(events),
        _product_keys=keys,
    )


def evaluate_partition_coverage(
    partition: PartitionSpec,
    observations: Sequence[CoveragePageObservation],
    *,
    primary_order_by: str = "OrderByNameASC",
) -> PartitionCoverageResult:
    """Evalúa una partición y reconcilia órdenes adicionales si existen."""

    values = tuple(observations)
    if not values:
        return PartitionCoverageResult(
            partition=partition.name,
            pages_expected=0,
            pages_attempted=0,
            pages_completed=0,
            products_reported=partition.expected_products,
            products_received=0,
            products_unique=0,
            duplicate_occurrences=0,
            repeated_page_sets=0,
            unexpected_overlaps=0,
            missing_coverage_events=1,
            total_changes=0,
            orderings_attempted=0,
            orderings_reconciled=False,
            coverage_demonstrated=False,
            coverage_reason="partition_not_attempted",
            _reasons=("partition_not_attempted",),
        )
    if primary_order_by not in ALLOWED_ORDER_BY:
        raise ValueError("primary_order_by no permitido")
    if any(item.partition != partition.name for item in values):
        raise ValueError("Todas las observaciones deben pertenecer a la partición")

    grouped: dict[str, list[CoveragePageObservation]] = {}
    for item in values:
        grouped.setdefault(item.order_by, []).append(item)
    if primary_order_by not in grouped:
        raise ValueError("Falta el order_by primario")

    traversals = {
        order_by: _evaluate_traversal(partition, pages)
        for order_by, pages in grouped.items()
    }
    primary = traversals[primary_order_by]
    reasons: list[str] = []
    for traversal in traversals.values():
        _extend_unique(reasons, traversal.reasons)

    reconciled = True
    for order_by, traversal in traversals.items():
        if order_by == primary_order_by:
            continue
        if not traversal.coverage_demonstrated:
            reconciled = False
            _append_unique(reasons, "order_reconciliation_incomplete")
        elif traversal.product_keys != primary.product_keys:
            reconciled = False
            _append_unique(reasons, "order_reconciliation_failed")

    coverage_demonstrated = primary.coverage_demonstrated and reconciled
    if len(traversals) == 1:
        reconciled = True
    reason = "coverage_demonstrated" if coverage_demonstrated else ";".join(reasons)

    return PartitionCoverageResult(
        partition=partition.name,
        pages_expected=sum(item.pages_expected for item in traversals.values()),
        pages_attempted=sum(item.pages_attempted for item in traversals.values()),
        pages_completed=sum(item.pages_completed for item in traversals.values()),
        products_reported=primary.products_reported,
        products_received=sum(item.products_received for item in traversals.values()),
        products_unique=len(primary.product_keys),
        duplicate_occurrences=sum(
            item.duplicate_occurrences for item in traversals.values()
        ),
        repeated_page_sets=sum(item.repeated_page_sets for item in traversals.values()),
        unexpected_overlaps=sum(
            item.unexpected_overlaps for item in traversals.values()
        ),
        missing_coverage_events=len(reasons),
        total_changes=sum(item.total_changes for item in traversals.values()),
        orderings_attempted=len(traversals),
        orderings_reconciled=reconciled,
        coverage_demonstrated=coverage_demonstrated,
        coverage_reason=reason or "coverage_not_demonstrated",
        _product_keys=tuple(sorted(primary.product_keys)),
        _reasons=tuple(reasons),
    )


def evaluate_catalog_coverage(
    partitions: Sequence[PartitionCoverageResult],
    *,
    partitions_discovered: int,
    products_reported: int,
    uncategorized_products: int = 0,
    request_limit: int = DEFAULT_MAX_COVERAGE_REQUESTS,
) -> CatalogCoverageReport:
    """Evalúa la unión global sin asumir que deduplicar demuestra completitud."""

    if partitions_discovered < 0 or products_reported < 0:
        raise ValueError("Los totales globales no pueden ser negativos")
    if uncategorized_products < 0:
        raise ValueError("uncategorized_products no puede ser negativo")
    if request_limit <= 0:
        raise ValueError("request_limit debe ser mayor que cero")

    values = tuple(partitions)
    reasons: list[str] = []
    if partitions_discovered != len(values):
        _append_unique(reasons, "partition_count_mismatch")
    if any(not item.coverage_demonstrated for item in values):
        _append_unique(reasons, "partitions_incomplete")
    if uncategorized_products:
        _append_unique(reasons, "uncategorized_products_present")

    canonical_occurrences = sum(len(item._product_keys) for item in values)
    unique_keys = {key for item in values for key in item._product_keys}
    cross_partition_duplicates = canonical_occurrences - len(unique_keys)
    if len(unique_keys) < products_reported:
        _append_unique(reasons, "global_union_below_reported_total")
    elif len(unique_keys) > products_reported:
        _append_unique(reasons, "global_union_above_reported_total")

    pages_attempted = sum(item.pages_attempted for item in values)
    if pages_attempted > request_limit:
        _append_unique(reasons, "request_limit_exceeded")

    _extend_unique(
        reasons,
        reason
        for item in values
        for reason in item._reasons
        if reason not in {"coverage_demonstrated"}
    )
    coverage_demonstrated = not reasons
    return CatalogCoverageReport(
        partitions_discovered=partitions_discovered,
        partitions_attempted=len(values),
        partitions_completed=sum(item.coverage_demonstrated for item in values),
        pages_expected=sum(item.pages_expected for item in values),
        pages_attempted=pages_attempted,
        pages_completed=sum(item.pages_completed for item in values),
        products_reported=products_reported,
        products_received=sum(item.products_received for item in values),
        products_unique=len(unique_keys),
        duplicate_occurrences=(
            sum(item.duplicate_occurrences for item in values)
            + cross_partition_duplicates
        ),
        repeated_page_sets=sum(item.repeated_page_sets for item in values),
        unexpected_overlaps=sum(item.unexpected_overlaps for item in values),
        missing_coverage_events=len(reasons),
        total_changes=sum(item.total_changes for item in values),
        uncategorized_products=uncategorized_products,
        request_limit=request_limit,
        coverage_demonstrated=coverage_demonstrated,
        coverage_reason=(
            "coverage_demonstrated" if coverage_demonstrated else ";".join(reasons)
        ),
        accepted=coverage_demonstrated,
        _reasons=tuple(reasons),
    )


def validate_sanitized_coverage_summary(value: Any) -> None:
    """Impide publicar identificadores o datos comerciales."""

    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in _FORBIDDEN_PUBLIC_KEYS:
                raise ValueError(f"Campo no permitido en resumen sanitizado: {key}")
            validate_sanitized_coverage_summary(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            validate_sanitized_coverage_summary(nested)


@dataclass(frozen=True, slots=True)
class _TraversalResult:
    pages_expected: int
    pages_attempted: int
    pages_completed: int
    products_reported: int
    products_received: int
    duplicate_occurrences: int
    repeated_page_sets: int
    unexpected_overlaps: int
    total_changes: int
    coverage_demonstrated: bool
    reasons: tuple[str, ...]
    product_keys: frozenset[str]


def _evaluate_traversal(
    partition: PartitionSpec,
    pages: Sequence[CoveragePageObservation],
) -> _TraversalResult:
    ordered = tuple(sorted(pages, key=lambda item: (item.from_index, item.to_index)))
    reasons: list[str] = []
    totals = [item.records_filtered for item in ordered]
    total_changes = sum(left != right for left, right in zip(totals, totals[1:]))
    if total_changes:
        _append_unique(reasons, "partition_total_changed")
    total = totals[0]
    if total != partition.expected_products:
        _append_unique(reasons, "partition_total_differs_from_discovery")

    pages_completed = 0
    all_keys: list[str] = []
    positions: set[int] = set()
    for item in ordered:
        all_keys.extend(item._product_keys)
        positions.update(
            range(
                max(item.from_index, 0),
                min(item.to_index, max(total - 1, -1)) + 1,
            )
        )
        if item.complete and item.membership_valid and not item.quality_events:
            pages_completed += 1
        _extend_unique(reasons, item.quality_events)

    repeated_page_sets = 0
    unexpected_overlaps = 0
    for index, left in enumerate(ordered):
        left_keys = set(left._product_keys)
        for right in ordered[index + 1 :]:
            if (
                left.set_signature == right.set_signature
                and (left.from_index, left.to_index)
                != (right.from_index, right.to_index)
            ):
                repeated_page_sets += 1
            expected_overlap = _expected_overlap(left, right)
            observed_overlap = len(left_keys.intersection(right._product_keys))
            if expected_overlap != observed_overlap:
                unexpected_overlaps += 1

    if repeated_page_sets:
        _append_unique(reasons, "repeated_page_set")
    if unexpected_overlaps:
        _append_unique(reasons, "unexpected_overlap")
    if len(positions) != total:
        _append_unique(reasons, "logical_positions_not_fully_covered")

    unique_keys = frozenset(all_keys)
    if len(unique_keys) < total:
        _append_unique(reasons, "unique_products_below_partition_total")
    elif len(unique_keys) > total:
        _append_unique(reasons, "unique_products_above_partition_total")

    duplicate_occurrences = len(all_keys) - len(unique_keys)
    coverage_demonstrated = not reasons
    return _TraversalResult(
        pages_expected=len(ordered),
        pages_attempted=len(ordered),
        pages_completed=pages_completed,
        products_reported=total,
        products_received=len(all_keys),
        duplicate_occurrences=duplicate_occurrences,
        repeated_page_sets=repeated_page_sets,
        unexpected_overlaps=unexpected_overlaps,
        total_changes=total_changes,
        coverage_demonstrated=coverage_demonstrated,
        reasons=tuple(reasons),
        product_keys=unique_keys,
    )


def _expected_overlap(
    left: CoveragePageObservation,
    right: CoveragePageObservation,
) -> int:
    start = max(left.from_index, right.from_index)
    end = min(left.to_index, right.to_index)
    return max(end - start + 1, 0)


def _signature(values: Sequence[str]) -> str:
    encoded = json.dumps(list(values), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _extend_unique(values: list[str], additions: Sequence[str] | Any) -> None:
    for value in additions:
        _append_unique(values, str(value))
