"""Contrato físico activo de almacenamiento.

BigQuery es el único backend productivo objetivo. El contrato tabular histórico
(current + period history) continúa existiendo como motor/backend-neutral de
transición y rehidratación, pero ya no se presenta como contrato físico activo ni
como Google Sheets.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .bigquery_contract import BIGQUERY_TABLE_SPECS, BigQueryTableSpec
from .tabular_persistence import TABLE_SPECS as LEGACY_TABLE_SPECS, TableSpec


ACTIVE_STORAGE_BACKEND = "bigquery"
ACTIVE_STORAGE_TABLE_SPECS: Mapping[str, BigQueryTableSpec] = MappingProxyType(
    {spec.name: spec for spec in BIGQUERY_TABLE_SPECS}
)
ACTIVE_STORAGE_TABLE_NAMES = tuple(ACTIVE_STORAGE_TABLE_SPECS)

# Evidencia/compatibilidad del motor backend-neutral anterior. No es un segundo
# backend activo y no debe utilizarse para habilitar nuevas escrituras Sheets.
LEGACY_TABULAR_TABLE_SPECS: Mapping[str, TableSpec] = MappingProxyType(
    dict(LEGACY_TABLE_SPECS)
)
LEGACY_TABULAR_TABLE_NAMES = tuple(LEGACY_TABULAR_TABLE_SPECS)


def is_active_storage_table(table_name: str) -> bool:
    return table_name in ACTIVE_STORAGE_TABLE_SPECS


def is_legacy_tabular_table(table_name: str) -> bool:
    return table_name in LEGACY_TABULAR_TABLE_SPECS
