"""Proyección y adapter SQLite/Turso para el estado comercial durable.

El motor ``commercial_state`` conserva la autoridad de transición. Esta capa:

- materializa ``current`` en cada oferta observada para conservar ``last_seen``;
- inserta histórico sólo al abrir/cerrar un periodo real, no por confirmaciones;
- registra cada run terminal;
- hace replay exacto como no-op y rechaza replay divergente;
- funciona offline con ``sqlite3`` y remotamente con ``turso_serverless``.

No concede autoridad live ni descarga fuentes externas.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

from .commercial_persistence_batch import PreparedCommercialPersistence
from .identifiers import (
    canonicalize_gtin,
    generate_gtin_product_id,
    generate_pending_product_id,
)
from .tabular_persistence import (
    CFG_LOCATIONS,
    CFG_SUPERMARKETS,
    FACT_OFFER_HISTORY,
    FACT_OFFERS_CURRENT,
    FACT_QUALITY_EVENTS,
    FACT_SCRAPE_RUNS,
)
from .tabular_rehydration import RehydratedCommercialSnapshot, rehydrate_commercial_snapshot
from .turso_contract import (
    CURRENT_SCHEMA_VERSION,
    LOCATIONS,
    NORMALIZATION_OVERRIDES,
    OFFER_HISTORY,
    OFFERS_CURRENT,
    PRODUCTS,
    QUALITY_EVENTS,
    SCHEMA_VERSION_TABLE,
    SCRAPE_RUNS,
    SOURCE_PRODUCTS,
    SUPERMARKETS,
    TURSO_MIGRATIONS,
    TURSO_SCHEMA_META_SQL,
    TURSO_TABLE_BY_NAME,
    TURSO_TABLE_NAMES,
    TursoTableSpec,
)


class TursoPersistenceError(ValueError):
    """Un plan o write violaría el contrato Turso."""


class TursoReplayConflict(TursoPersistenceError):
    """Un scrape_run_id existente reapareció con otro fingerprint."""


class TursoWriteConflict(TursoPersistenceError):
    """Una llave estable reapareció con contenido incompatible."""


class TursoConnectionPort(Protocol):
    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Any: ...

    def commit(self) -> Any: ...

    def rollback(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class TursoWritePlan:
    scrape_run_id: str
    run_fingerprint: str
    rows: Mapping[str, tuple[Mapping[str, Any], ...]]

    def __post_init__(self) -> None:
        if not isinstance(self.scrape_run_id, str) or not self.scrape_run_id.strip():
            raise TursoPersistenceError("scrape_run_id_invalid")
        if len(self.run_fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in self.run_fingerprint
        ):
            raise TursoPersistenceError("run_fingerprint_invalid")
        if set(self.rows) != set(TURSO_TABLE_NAMES):
            raise TursoPersistenceError("plan_tables_mismatch")

        normalized: dict[str, tuple[Mapping[str, Any], ...]] = {}
        for table_name in TURSO_TABLE_NAMES:
            spec = TURSO_TABLE_BY_NAME[table_name]
            values = self.rows[table_name]
            if not isinstance(values, tuple):
                raise TursoPersistenceError(f"plan_rows_not_tuple:{table_name}")
            deduped: dict[tuple[Any, ...], Mapping[str, Any]] = {}
            ordered: list[Mapping[str, Any]] = []
            for source_row in values:
                if not isinstance(source_row, Mapping):
                    raise TursoPersistenceError(f"plan_row_not_mapping:{table_name}")
                if set(source_row) != set(spec.columns):
                    raise TursoPersistenceError(f"row_schema_mismatch:{table_name}")
                row = {name: _db_scalar(source_row[name]) for name in spec.columns}
                key = _primary_key(spec, row)
                previous = deduped.get(key)
                if previous is not None:
                    if dict(previous) != row:
                        raise TursoPersistenceError(
                            f"logical_key_duplicate_divergent:{table_name}"
                        )
                    continue
                closed = MappingProxyType(row)
                deduped[key] = closed
                ordered.append(closed)
            normalized[table_name] = tuple(ordered)

        runs = normalized[SCRAPE_RUNS.name]
        if len(runs) != 1:
            raise TursoPersistenceError("exactly_one_scrape_run_required")
        if runs[0]["scrape_run_id"] != self.scrape_run_id:
            raise TursoPersistenceError("scrape_run_identity_mismatch")
        if runs[0]["run_fingerprint"] != self.run_fingerprint:
            raise TursoPersistenceError("scrape_run_fingerprint_mismatch")
        object.__setattr__(self, "rows", MappingProxyType(normalized))
        if _plan_fingerprint(self.rows) != self.run_fingerprint:
            raise TursoPersistenceError("run_fingerprint_content_mismatch")

    @property
    def row_counts(self) -> Mapping[str, int]:
        return MappingProxyType({name: len(rows) for name, rows in self.rows.items()})


@dataclass(frozen=True, slots=True)
class TursoApplyResult:
    created: int
    updated: int
    replayed: int
    history_confirmations_skipped: int
    exact_run_replay: bool
    table_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_counts", MappingProxyType(dict(self.table_counts)))


@dataclass(frozen=True, slots=True)
class TursoReadBack:
    current_rows: tuple[Mapping[str, Any], ...]
    history_rows: tuple[Mapping[str, Any], ...]
    runs: tuple[Mapping[str, Any], ...]
    quality_events: tuple[Mapping[str, Any], ...]
    source_products: tuple[Mapping[str, Any], ...]

    def rehydrate(self) -> RehydratedCommercialSnapshot:
        """Vuelve al contrato lógico current/history, incluida confirmación abierta."""

        current = [
            _logical_offer_row(row, FACT_OFFERS_CURRENT.columns)
            for row in self.current_rows
        ]
        by_offer = {row["offer_id"]: row for row in current}
        history: list[dict[str, Any]] = []
        for physical in self.history_rows:
            row = _logical_offer_row(physical, FACT_OFFER_HISTORY.columns)
            if row["valid_to_utc"] is None:
                live = by_offer.get(row["offer_id"])
                if live is None:
                    raise TursoPersistenceError("open_history_without_current")
                # Confirmaciones no reescriben history físicamente. Current es la
                # evidencia durable de la última observación del periodo abierto.
                row["last_confirmed_by_scrape_run_id"] = live["last_scrape_run_id"]
                row["last_observed_at_utc"] = live["last_observed_at_utc"]
            history.append(row)
        return rehydrate_commercial_snapshot(current, history)


@dataclass(slots=True)
class _MutationCounters:
    created: int = 0
    updated: int = 0
    replayed: int = 0
    history_confirmations_skipped: int = 0


def _db_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise TursoPersistenceError("decimal_not_finite")
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise TursoPersistenceError("datetime_timezone_missing")
        if value.utcoffset().total_seconds() != 0:
            raise TursoPersistenceError("datetime_not_utc")
        return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    raise TursoPersistenceError(f"unsupported_db_scalar:{type(value).__name__}")


def _primary_key(spec: TursoTableSpec, row: Mapping[str, Any]) -> tuple[Any, ...]:
    key = tuple(row[name] for name in spec.primary_key)
    if any(value is None or (isinstance(value, str) and not value.strip()) for value in key):
        raise TursoPersistenceError(f"primary_key_empty:{spec.name}")
    return key


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, bytes):
        return value.hex()
    return _db_scalar(value)


def _plan_fingerprint(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    payload: dict[str, list[dict[str, Any]]] = {}
    for table_name in sorted(rows):
        values = []
        for source in rows[table_name]:
            row = {key: _canonical(source[key]) for key in sorted(source)}
            if table_name == SCRAPE_RUNS.name:
                row.pop("run_fingerprint", None)
            values.append(row)
        payload[table_name] = values
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _optional_count(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TursoPersistenceError(f"{field_name}_invalid")
    return value


def _optional_coverage(value: Decimal | int | float | str | None) -> str | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TursoPersistenceError("catalog_product_coverage_invalid") from exc
    if not result.is_finite() or result < 0 or result > 1:
        raise TursoPersistenceError("catalog_product_coverage_invalid")
    return format(result.normalize(), "f")


def _minor_units(value: Any, *, currency: str, field_name: str) -> int | None:
    if value is None:
        return None
    if currency != "HNL":
        raise TursoPersistenceError(f"unsupported_currency_minor_units:{currency}")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TursoPersistenceError(f"{field_name}_invalid") from exc
    if not decimal.is_finite() or decimal < 0:
        raise TursoPersistenceError(f"{field_name}_invalid")
    scaled = decimal * Decimal(100)
    integral = scaled.to_integral_value()
    if scaled != integral:
        raise TursoPersistenceError(f"{field_name}_subcent_precision")
    return int(integral)


def _mapping(row: Mapping[str, Any]) -> tuple[str, str, str | None, str | None, str]:
    product_id = str(row["product_id"])
    source_product_id = str(row["source_product_id"])
    gtin = canonicalize_gtin(row.get("barcode"))
    if product_id.startswith("prod_pending_"):
        if product_id != generate_pending_product_id(source_product_id):
            raise TursoPersistenceError("pending_product_identity_mismatch")
        return "pending", "pending", "pending_product_mapping", None, "pending"
    if product_id.startswith("prod_gtin_"):
        if gtin is None or product_id != generate_gtin_product_id(gtin):
            raise TursoPersistenceError("gtin_product_identity_mismatch")
        return "mapped", "gtin", None, gtin, "gtin"
    return "mapped", "explicit", None, gtin, "explicit"


def _product_and_source_rows(current_rows: Sequence[Mapping[str, Any]]) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    products: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for row in current_rows:
        mapping_status, mapping_method, review_reason, canonical_gtin, identity_kind = _mapping(row)
        product = {
            "product_id": row["product_id"],
            "canonical_gtin": canonical_gtin,
            "identity_kind": identity_kind,
        }
        previous = products.get(str(row["product_id"]))
        if previous is not None and previous != product:
            raise TursoPersistenceError("canonical_product_identity_conflict")
        products[str(row["product_id"])] = product
        sources.append(
            {
                "source_product_id": row["source_product_id"],
                "supermarket_id": row["supermarket_id"],
                "source_key_type": row["source_key_type"],
                "source_key": row["source_key"],
                "source_sku": row["source_sku"],
                "source_name": row["source_name"],
                "source_brand": row["source_brand"],
                "source_presentation": row["source_presentation"],
                "barcode": row["barcode"],
                "product_url": row["product_url"],
                "image_url": row["image_url"],
                "product_id": row["product_id"],
                "mapping_status": mapping_status,
                "mapping_method": mapping_method,
                "review_reason": review_reason,
                "normalized_name": row["normalized_name"],
                "normalized_brand": row["normalized_brand"],
                "category": row["category"],
                "subcategory": row["subcategory"],
                "variant": row["variant"],
                "unit_count": row["unit_count"],
                "content_per_unit": row["content_per_unit"],
                "measurement_unit": row["measurement_unit"],
                "total_content": row["total_content"],
                "review_status": row["review_status"],
                "last_observed_at_utc": row["last_observed_at_utc"],
                "last_scrape_run_id": row["last_scrape_run_id"],
            }
        )
    return tuple(products[key] for key in sorted(products)), tuple(sources)


def _physical_offer_row(row: Mapping[str, Any], *, history: bool) -> dict[str, Any]:
    spec = OFFER_HISTORY if history else OFFERS_CURRENT
    logical_columns = FACT_OFFER_HISTORY.columns if history else FACT_OFFERS_CURRENT.columns
    values = {name: row[name] for name in logical_columns}
    currency = str(row["currency"])
    values.update(
        {
            "current_price_minor": _minor_units(
                row["current_price"], currency=currency, field_name="current_price"
            ),
            "reported_regular_price_minor": _minor_units(
                row["reported_regular_price"],
                currency=currency,
                field_name="reported_regular_price",
            ),
            # El snapshot aceptado actual no preserva estas evidencias. Unknown
            # permanece unknown y los campos quedan NULL hasta una observación
            # futura que los demuestre.
            "seller_id": None,
            "available_quantity_observed": None,
            "availability_evidence": None,
            "quantity_is_exact": 0,
        }
    )
    if set(values) != set(spec.columns):
        raise TursoPersistenceError(f"offer_projection_schema_mismatch:{spec.name}")
    return values


def _override_rows(values: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TursoPersistenceError("normalization_overrides_invalid")
    result: list[dict[str, Any]] = []
    for source in values:
        if not isinstance(source, Mapping) or set(source) != set(NORMALIZATION_OVERRIDES.columns):
            raise TursoPersistenceError("normalization_override_schema_mismatch")
        row = {name: source[name] for name in NORMALIZATION_OVERRIDES.columns}
        if type(row["active"]) is not bool:
            raise TursoPersistenceError("normalization_override_active_invalid")
        result.append(row)
    return tuple(result)


def build_turso_write_plan(
    prepared: PreparedCommercialPersistence,
    *,
    normalization_overrides: Sequence[Mapping[str, Any]] = (),
    catalog_products_reported: int | None = None,
    unique_products_extracted: int | None = None,
    skus_extracted: int | None = None,
    skus_with_price: int | None = None,
    catalog_product_coverage: Decimal | int | float | str | None = None,
) -> TursoWritePlan:
    """Proyecta un run ya validado al contrato operativo Turso sin I/O."""

    if not isinstance(prepared, PreparedCommercialPersistence):
        raise TursoPersistenceError("prepared_persistence_invalid")
    batch = prepared.batch.rows
    current_rows = tuple(batch.get(FACT_OFFERS_CURRENT.name, ()))
    history_rows = tuple(batch.get(FACT_OFFER_HISTORY.name, ()))
    accepted = prepared.apply_result.commercial_update_allowed
    if not accepted and (current_rows or history_rows):
        raise TursoPersistenceError("rejected_run_contains_commercial_rows")

    catalog_products_reported = _optional_count(catalog_products_reported, "catalog_products_reported")
    unique_products_extracted = _optional_count(unique_products_extracted, "unique_products_extracted")
    skus_extracted = _optional_count(skus_extracted, "skus_extracted")
    skus_with_price = _optional_count(skus_with_price, "skus_with_price")
    if skus_extracted is not None and skus_with_price is not None and skus_with_price > skus_extracted:
        raise TursoPersistenceError("skus_with_price_exceeds_skus_extracted")
    coverage = _optional_coverage(catalog_product_coverage)

    supermarkets = tuple(
        {
            "supermarket_id": row["supermarket_id"],
            "supermarket_name": row["supermarket_name"],
            "country_code": row["country_code"],
            "location_selection_mode": row["location_selection_mode"],
            "is_active": row["is_active"],
        }
        for row in batch[CFG_SUPERMARKETS.name]
    )
    locations = tuple(
        {
            "location_id": row["location_id"],
            "supermarket_id": row["supermarket_id"],
            "city_id": row["city_id"],
            "city_name": row["city_name"],
            "granularity": row["granularity"],
            "source_location_key": row["source_location_key"],
            "is_available": row["is_available"],
            "in_scope": row["in_scope"],
            "extraction_enabled": row["extraction_enabled"],
            "technical_binding_confirmed": row["technical_binding_confirmed"],
            "evidence": row["evidence"],
        }
        for row in batch[CFG_LOCATIONS.name]
    )

    products, source_products = _product_and_source_rows(current_rows) if accepted else ((), ())
    current = tuple(_physical_offer_row(row, history=False) for row in current_rows) if accepted else ()
    history = tuple(_physical_offer_row(row, history=True) for row in history_rows) if accepted else ()

    source_by_offer = {row["offer_id"]: row["source_product_id"] for row in current_rows}
    quality = tuple(
        {
            "quality_event_id": row["quality_event_id"],
            "scrape_run_id": row["scrape_run_id"],
            "supermarket_id": row["supermarket_id"],
            "location_id": row["location_id"],
            "offer_id": row["offer_id"],
            "source_product_id": source_by_offer.get(row["offer_id"]),
            "category": row["category"],
            "severity": row["severity"],
            "event_code": row["event_code"],
            "observed_at_utc": row["observed_at_utc"],
        }
        for row in batch[FACT_QUALITY_EVENTS.name]
    )

    run = batch[FACT_SCRAPE_RUNS.name]
    if len(run) != 1:
        raise TursoPersistenceError("exactly_one_tabular_run_required")
    run_source = run[0]
    run_base = {
        "scrape_run_id": run_source["scrape_run_id"],
        "run_fingerprint": "",
        "supermarket_id": run_source["supermarket_id"],
        "location_id": run_source["location_id"],
        "run_status": run_source["run_status"],
        "catalog_accepted": run_source["catalog_accepted"],
        "commercial_update_allowed": prepared.apply_result.commercial_update_allowed,
        "started_at_utc": run_source["started_at_utc"],
        "finished_at_utc": run_source["finished_at_utc"],
        "products_observed": run_source["products_observed"],
        "offers_observed": run_source["offers_observed"],
        "current_created": run_source["current_created"],
        "current_changed": run_source["current_changed"],
        "current_confirmed": run_source["current_confirmed"],
        "offers_ignored": run_source["offers_ignored"],
        "quality_event_count": run_source["quality_event_count"],
        "run_evidence_id": run_source["run_evidence_id"],
        "catalog_products_reported": catalog_products_reported,
        "unique_products_extracted": unique_products_extracted,
        "skus_extracted": skus_extracted,
        "skus_with_price": skus_with_price,
        "catalog_product_coverage": coverage,
    }

    rows: dict[str, tuple[Mapping[str, Any], ...]] = {
        SUPERMARKETS.name: supermarkets,
        LOCATIONS.name: locations,
        PRODUCTS.name: products,
        SOURCE_PRODUCTS.name: source_products,
        OFFERS_CURRENT.name: current,
        OFFER_HISTORY.name: history,
        SCRAPE_RUNS.name: (run_base,),
        QUALITY_EVENTS.name: quality,
        NORMALIZATION_OVERRIDES.name: _override_rows(normalization_overrides),
    }
    fingerprint = _plan_fingerprint(rows)
    run_base = dict(run_base)
    run_base["run_fingerprint"] = fingerprint
    rows[SCRAPE_RUNS.name] = (run_base,)
    return TursoWritePlan(
        scrape_run_id=str(run_base["scrape_run_id"]),
        run_fingerprint=fingerprint,
        rows=rows,
    )


def _cursor_mapping(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return dict(row)
    description = getattr(cursor, "description", None)
    if not description:
        raise TursoPersistenceError("cursor_description_missing")
    names = [item[0] for item in description]
    return dict(zip(names, row))


def _fetch_one(connection: TursoConnectionPort, sql: str, parameters: Sequence[Any] = ()) -> dict[str, Any] | None:
    cursor = connection.execute(sql, parameters)
    return _cursor_mapping(cursor, cursor.fetchone())


def _fetch_all(connection: TursoConnectionPort, sql: str, parameters: Sequence[Any] = ()) -> tuple[dict[str, Any], ...]:
    cursor = connection.execute(sql, parameters)
    return tuple(_cursor_mapping(cursor, row) or {} for row in cursor.fetchall())


def _where_primary_key(spec: TursoTableSpec) -> str:
    return " AND ".join(f'"{name}" = ?' for name in spec.primary_key)


def _select_existing(connection: TursoConnectionPort, spec: TursoTableSpec, row: Mapping[str, Any]) -> dict[str, Any] | None:
    columns = ", ".join(f'"{name}"' for name in spec.columns)
    key = _primary_key(spec, row)
    return _fetch_one(
        connection,
        f'SELECT {columns} FROM "{spec.name}" WHERE {_where_primary_key(spec)}',
        key,
    )


def _insert(connection: TursoConnectionPort, spec: TursoTableSpec, row: Mapping[str, Any]) -> None:
    columns = ", ".join(f'"{name}"' for name in spec.columns)
    placeholders = ", ".join("?" for _ in spec.columns)
    connection.execute(
        f'INSERT INTO "{spec.name}" ({columns}) VALUES ({placeholders})',
        tuple(row[name] for name in spec.columns),
    )


def _update(connection: TursoConnectionPort, spec: TursoTableSpec, row: Mapping[str, Any]) -> None:
    mutable = tuple(name for name in spec.columns if name not in spec.primary_key)
    assignments = ", ".join(f'"{name}" = ?' for name in mutable)
    connection.execute(
        f'UPDATE "{spec.name}" SET {assignments} WHERE {_where_primary_key(spec)}',
        tuple(row[name] for name in mutable) + _primary_key(spec, row),
    )


def _rows_equal(left: Mapping[str, Any], right: Mapping[str, Any], columns: Sequence[str]) -> bool:
    return all(left.get(name) == right.get(name) for name in columns)


def _stable_field_check(spec: TursoTableSpec, existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> None:
    stable: tuple[str, ...] = ()
    if spec is PRODUCTS:
        stable = PRODUCTS.columns
    elif spec is SOURCE_PRODUCTS:
        stable = ("source_product_id", "supermarket_id", "source_key_type", "source_key")
    elif spec is NORMALIZATION_OVERRIDES:
        stable = (
            "override_id",
            "supermarket_id",
            "source_product_id",
            "source_signature",
            "field_name",
            "source_value",
            "override_value",
        )
    if stable and not _rows_equal(existing, incoming, stable):
        raise TursoWriteConflict(f"stable_fields_changed:{spec.name}")


def _apply_mutable(
    connection: TursoConnectionPort,
    spec: TursoTableSpec,
    rows: Sequence[Mapping[str, Any]],
    counters: _MutationCounters,
) -> None:
    for row in rows:
        existing = _select_existing(connection, spec, row)
        if existing is None:
            _insert(connection, spec, row)
            counters.created += 1
            continue
        if _rows_equal(existing, row, spec.columns):
            counters.replayed += 1
            continue
        _stable_field_check(spec, existing, row)
        _update(connection, spec, row)
        counters.updated += 1


def _apply_immutable(
    connection: TursoConnectionPort,
    spec: TursoTableSpec,
    rows: Sequence[Mapping[str, Any]],
    counters: _MutationCounters,
) -> None:
    for row in rows:
        existing = _select_existing(connection, spec, row)
        if existing is None:
            _insert(connection, spec, row)
            counters.created += 1
        elif _rows_equal(existing, row, spec.columns):
            counters.replayed += 1
        else:
            raise TursoWriteConflict(f"immutable_row_conflict:{spec.name}")


def _history_confirmation_only(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> bool:
    if existing.get("valid_to_utc") is not None or incoming.get("valid_to_utc") is not None:
        return False
    ignored = {"last_confirmed_by_scrape_run_id", "last_observed_at_utc"}
    return all(
        existing.get(name) == incoming.get(name)
        for name in OFFER_HISTORY.columns
        if name not in ignored
    )


def _apply_history(
    connection: TursoConnectionPort,
    rows: Sequence[Mapping[str, Any]],
    counters: _MutationCounters,
) -> None:
    spec = OFFER_HISTORY
    for row in rows:
        existing = _select_existing(connection, spec, row)
        if existing is None:
            _insert(connection, spec, row)
            counters.created += 1
            continue
        if _rows_equal(existing, row, spec.columns):
            counters.replayed += 1
            continue
        if _history_confirmation_only(existing, row):
            counters.history_confirmations_skipped += 1
            continue
        # El único update válido de un periodo existente es cerrar el periodo
        # que estaba abierto. Un periodo ya cerrado es inmutable.
        if existing.get("valid_to_utc") is None and row.get("valid_to_utc") is not None:
            if existing.get("state_hash") != row.get("state_hash"):
                raise TursoWriteConflict("history_state_changed_while_closing")
            _update(connection, spec, row)
            counters.updated += 1
            continue
        raise TursoWriteConflict("history_period_divergent")


def _schema_version(connection: TursoConnectionPort) -> int:
    row = _fetch_one(
        connection,
        f'SELECT version FROM "{SCHEMA_VERSION_TABLE}" WHERE singleton = 1',
    )
    if row is None:
        raise TursoPersistenceError("schema_version_row_missing")
    value = row.get("version")
    if isinstance(value, bool) or not isinstance(value, int):
        raise TursoPersistenceError("schema_version_invalid")
    return value


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TursoAdapter:
    """Adapter DB-API compatible con sqlite3 y ``turso_serverless``."""

    def __init__(self, connection: TursoConnectionPort) -> None:
        if connection is None or not hasattr(connection, "execute"):
            raise TursoPersistenceError("connection_invalid")
        self._connection = connection

    def bootstrap(self) -> int:
        """Aplica migraciones incrementales y deja foreign keys activas."""

        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute(TURSO_SCHEMA_META_SQL)
            self._connection.execute(
                f'INSERT OR IGNORE INTO "{SCHEMA_VERSION_TABLE}" '
                "(singleton, version, applied_at_utc) VALUES (1, 0, ?)",
                (_utc_now_text(),),
            )
            self._connection.commit()
            current = _schema_version(self._connection)
            if current > CURRENT_SCHEMA_VERSION:
                raise TursoPersistenceError("database_schema_newer_than_application")
            for version in range(current + 1, CURRENT_SCHEMA_VERSION + 1):
                statements = TURSO_MIGRATIONS.get(version)
                if statements is None:
                    raise TursoPersistenceError(f"migration_missing:{version}")
                self._connection.execute("BEGIN")
                try:
                    for statement in statements:
                        self._connection.execute(statement)
                    self._connection.execute(
                        f'UPDATE "{SCHEMA_VERSION_TABLE}" SET version = ?, applied_at_utc = ? '
                        "WHERE singleton = 1",
                        (version, _utc_now_text()),
                    )
                    self._connection.commit()
                except Exception:
                    self._connection.rollback()
                    raise
            self._connection.execute("PRAGMA foreign_keys = ON")
            return _schema_version(self._connection)
        except TursoPersistenceError:
            raise
        except Exception as exc:
            raise TursoPersistenceError("bootstrap_failed") from exc

    def apply(self, plan: TursoWritePlan) -> TursoApplyResult:
        if not isinstance(plan, TursoWritePlan):
            raise TursoPersistenceError("write_plan_invalid")
        if _schema_version(self._connection) != CURRENT_SCHEMA_VERSION:
            raise TursoPersistenceError("schema_not_bootstrapped")

        existing_run = _fetch_one(
            self._connection,
            'SELECT run_fingerprint FROM "scrape_runs" WHERE scrape_run_id = ?',
            (plan.scrape_run_id,),
        )
        if existing_run is not None:
            if existing_run.get("run_fingerprint") != plan.run_fingerprint:
                raise TursoReplayConflict("scrape_run_fingerprint_conflict")
            return TursoApplyResult(
                created=0,
                updated=0,
                replayed=1,
                history_confirmations_skipped=0,
                exact_run_replay=True,
                table_counts=MappingProxyType({name: 0 for name in TURSO_TABLE_NAMES}),
            )

        run = plan.rows[SCRAPE_RUNS.name][0]
        if run["commercial_update_allowed"] and not run["run_evidence_id"]:
            raise TursoPersistenceError("commercial_write_requires_run_evidence")

        counters = _MutationCounters()
        table_counts = {name: len(plan.rows[name]) for name in TURSO_TABLE_NAMES}
        try:
            self._connection.execute("BEGIN")
            _apply_mutable(self._connection, SUPERMARKETS, plan.rows[SUPERMARKETS.name], counters)
            _apply_mutable(self._connection, LOCATIONS, plan.rows[LOCATIONS.name], counters)
            _apply_immutable(self._connection, SCRAPE_RUNS, plan.rows[SCRAPE_RUNS.name], counters)
            _apply_mutable(self._connection, PRODUCTS, plan.rows[PRODUCTS.name], counters)
            _apply_mutable(self._connection, SOURCE_PRODUCTS, plan.rows[SOURCE_PRODUCTS.name], counters)
            _apply_mutable(self._connection, OFFERS_CURRENT, plan.rows[OFFERS_CURRENT.name], counters)
            _apply_history(self._connection, plan.rows[OFFER_HISTORY.name], counters)
            _apply_immutable(self._connection, QUALITY_EVENTS, plan.rows[QUALITY_EVENTS.name], counters)
            _apply_mutable(
                self._connection,
                NORMALIZATION_OVERRIDES,
                plan.rows[NORMALIZATION_OVERRIDES.name],
                counters,
            )
            self._connection.commit()
        except (TursoPersistenceError, TursoWriteConflict):
            self._connection.rollback()
            raise
        except Exception as exc:
            self._connection.rollback()
            raise TursoPersistenceError("transaction_failed") from exc

        return TursoApplyResult(
            created=counters.created,
            updated=counters.updated,
            replayed=counters.replayed,
            history_confirmations_skipped=counters.history_confirmations_skipped,
            exact_run_replay=False,
            table_counts=MappingProxyType(table_counts),
        )

    def read_back(self, *, supermarket_id: str, location_id: str) -> TursoReadBack:
        if not supermarket_id or not location_id:
            raise TursoPersistenceError("read_back_scope_invalid")
        current = _fetch_all(
            self._connection,
            'SELECT * FROM "offers_current" WHERE supermarket_id = ? AND location_id = ? ORDER BY offer_id',
            (supermarket_id, location_id),
        )
        history = _fetch_all(
            self._connection,
            'SELECT * FROM "offer_history" WHERE supermarket_id = ? AND location_id = ? '
            "ORDER BY offer_id, valid_from_utc",
            (supermarket_id, location_id),
        )
        runs = _fetch_all(
            self._connection,
            'SELECT * FROM "scrape_runs" WHERE supermarket_id = ? AND location_id = ? '
            "ORDER BY started_at_utc",
            (supermarket_id, location_id),
        )
        quality = _fetch_all(
            self._connection,
            'SELECT * FROM "quality_events" WHERE supermarket_id = ? AND location_id = ? '
            "ORDER BY observed_at_utc, quality_event_id",
            (supermarket_id, location_id),
        )
        sources = _fetch_all(
            self._connection,
            'SELECT * FROM "source_products" WHERE supermarket_id = ? ORDER BY source_product_id',
            (supermarket_id,),
        )
        return TursoReadBack(
            current_rows=tuple(MappingProxyType(row) for row in current),
            history_rows=tuple(MappingProxyType(row) for row in history),
            runs=tuple(MappingProxyType(row) for row in runs),
            quality_events=tuple(MappingProxyType(row) for row in quality),
            source_products=tuple(MappingProxyType(row) for row in sources),
        )

    def explain_query_plan(self, sql: str, parameters: Sequence[Any] = ()) -> tuple[str, ...]:
        if not isinstance(sql, str) or not sql.strip():
            raise TursoPersistenceError("explain_sql_invalid")
        cursor = self._connection.execute("EXPLAIN QUERY PLAN " + sql, parameters)
        rows = cursor.fetchall()
        return tuple(str(row[-1]) for row in rows)


def _logical_offer_row(row: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    result = {name: row[name] for name in columns}
    if "is_promotion" in result:
        value = result["is_promotion"]
        if value not in (0, 1, False, True):
            raise TursoPersistenceError("stored_boolean_invalid:is_promotion")
        result["is_promotion"] = bool(value)
    return result


def connect_turso_remote(database_url: str, auth_token: str) -> TursoConnectionPort:
    """Abre Turso Cloud sólo cuando el caller ya posee credenciales explícitas."""

    if not isinstance(database_url, str) or not database_url.strip():
        raise TursoPersistenceError("turso_database_url_missing")
    if not isinstance(auth_token, str) or not auth_token.strip():
        raise TursoPersistenceError("turso_auth_token_missing")
    try:
        import turso_serverless  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TursoPersistenceError("turso_serverless_not_installed") from exc
    try:
        return turso_serverless.connect(
            database_url.strip(),
            auth_token=auth_token.strip(),
        )
    except Exception as exc:
        raise TursoPersistenceError("turso_connection_failed") from exc


def connect_turso_from_env(environ: Mapping[str, str] | None = None) -> TursoConnectionPort:
    values = os.environ if environ is None else environ
    return connect_turso_remote(
        values.get("TURSO_DATABASE_URL", ""),
        values.get("TURSO_AUTH_TOKEN", ""),
    )
