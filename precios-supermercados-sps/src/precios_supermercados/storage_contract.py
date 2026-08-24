"""Contrato físico de almacenamiento para la fase actual.

El modelo lógico puede contener capacidades que todavía no justifican una
materialización durable. Esta frontera separa deliberadamente ambas cosas para
no convertir diseño futuro en tablas físicas prematuras.

Google Sheets es el backend temporal de la fase actual. Sólo se materializan
entidades con un grain/lifecycle/consumidor distinto que ya existe hoy. Las
estructuras de identidad canónica cross-source permanecen disponibles como
contratos lógicos hasta que una segunda fuente o un consumidor real requiera
resolver equivalencias entre productos.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .tabular_persistence import (
    CFG_LOCATIONS,
    CFG_SUPERMARKETS,
    DIM_PRODUCTS,
    FACT_OFFER_HISTORY,
    FACT_OFFERS_CURRENT,
    FACT_QUALITY_EVENTS,
    FACT_SCRAPE_RUNS,
    MAP_SOURCE_PRODUCTS,
    TableSpec,
)


ACTIVE_STORAGE_TABLE_SPECS: Mapping[str, TableSpec] = MappingProxyType(
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

DEFERRED_STORAGE_TABLE_SPECS: Mapping[str, TableSpec] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            DIM_PRODUCTS,
            MAP_SOURCE_PRODUCTS,
        )
    }
)

ACTIVE_STORAGE_TABLE_NAMES = tuple(ACTIVE_STORAGE_TABLE_SPECS)
DEFERRED_STORAGE_TABLE_NAMES = tuple(DEFERRED_STORAGE_TABLE_SPECS)


def is_active_storage_table(table_name: str) -> bool:
    return table_name in ACTIVE_STORAGE_TABLE_SPECS


def is_deferred_storage_table(table_name: str) -> bool:
    return table_name in DEFERRED_STORAGE_TABLE_SPECS
