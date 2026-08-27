"""Contrato físico activo de almacenamiento.

Turso es el backend persistente activo. El motor tabular ``current + history``
continúa siendo la frontera backend-neutral de transición/rehidratación y ahora se
materializa en SQL operativo en vez de snapshots analíticos diarios.

BigQuery y Google Sheets se conservan como implementaciones legadas/verificadas,
pero ninguna define el backend activo ni debe recibir nuevas escrituras por
accidente.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .bigquery_contract import BIGQUERY_TABLE_SPECS, BigQueryTableSpec
from .tabular_persistence import (
    CFG_LOCATIONS,
    CFG_SUPERMARKETS,
    DIM_PRODUCTS,
    FACT_OFFER_HISTORY,
    FACT_OFFERS_CURRENT,
    FACT_QUALITY_EVENTS,
    FACT_SCRAPE_RUNS,
    MAP_SOURCE_PRODUCTS,
    TABLE_SPECS as LEGACY_TABLE_SPECS,
    TableSpec,
)
from .turso_contract import TURSO_TABLE_SPECS, TursoTableSpec


ACTIVE_STORAGE_BACKEND = "turso"
ACTIVE_STORAGE_TABLE_SPECS: Mapping[str, TursoTableSpec] = MappingProxyType(
    {spec.name: spec for spec in TURSO_TABLE_SPECS}
)
ACTIVE_STORAGE_TABLE_NAMES = tuple(ACTIVE_STORAGE_TABLE_SPECS)

# BigQuery quedó completamente validado offline antes del cambio de backend. Se
# conserva como adapter futuro/legado, no como ruta productiva activa.
LEGACY_BIGQUERY_TABLE_SPECS: Mapping[str, BigQueryTableSpec] = MappingProxyType(
    {spec.name: spec for spec in BIGQUERY_TABLE_SPECS}
)
LEGACY_BIGQUERY_TABLE_NAMES = tuple(LEGACY_BIGQUERY_TABLE_SPECS)

# Contrato lógico backend-neutral. No es un segundo backend activo.
LEGACY_TABULAR_TABLE_SPECS: Mapping[str, TableSpec] = MappingProxyType(
    dict(LEGACY_TABLE_SPECS)
)
LEGACY_TABULAR_TABLE_NAMES = tuple(LEGACY_TABULAR_TABLE_SPECS)

# Superficie exacta que el backend Sheets retirado administraba.
LEGACY_SHEETS_MANAGED_TABLE_SPECS: Mapping[str, TableSpec] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            CFG_SUPERMARKETS,
            CFG_LOCATIONS,
            FACT_OFFERS_CURRENT,
            FACT_OFFER_HISTORY,
            FACT_SCRAPE_RUNS,
            FACT_QUALITY_EVENTS,
        )
    }
)
LEGACY_SHEETS_MANAGED_TABLE_NAMES = tuple(LEGACY_SHEETS_MANAGED_TABLE_SPECS)
LEGACY_SHEETS_DEFERRED_TABLE_NAMES = (
    DIM_PRODUCTS.name,
    MAP_SOURCE_PRODUCTS.name,
)


def is_active_storage_table(table_name: str) -> bool:
    return table_name in ACTIVE_STORAGE_TABLE_SPECS


def is_legacy_bigquery_table(table_name: str) -> bool:
    return table_name in LEGACY_BIGQUERY_TABLE_SPECS


def is_legacy_tabular_table(table_name: str) -> bool:
    return table_name in LEGACY_TABULAR_TABLE_SPECS


def is_legacy_sheets_managed_table(table_name: str) -> bool:
    return table_name in LEGACY_SHEETS_MANAGED_TABLE_SPECS
