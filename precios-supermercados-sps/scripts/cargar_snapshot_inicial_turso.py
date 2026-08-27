#!/usr/bin/env python3
"""Carga durable del snapshot inicial aprobado de La Colonia en Turso.

El comando no descarga el catálogo ni habilita tráfico live. El archivo recibido se
valida por digest, metadata y conteos dentro de ``la_colonia_initial_snapshot``.
Las credenciales Turso se leen exclusivamente de ``TURSO_DATABASE_URL`` y
``TURSO_AUTH_TOKEN``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from precios_supermercados.la_colonia_initial_snapshot import (
    LA_COLONIA_INITIAL_SNAPSHOT_LOCATION_ID,
    LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID,
    apply_la_colonia_initial_snapshot_turso,
)
from precios_supermercados.turso_persistence import connect_turso_from_env


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Carga el snapshot inicial aprobado de La Colonia en Turso",
    )
    parser.add_argument(
        "--snapshot-json",
        required=True,
        type=Path,
        help="Ruta al full-catalog.json aprobado",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Confirma explícitamente la escritura durable",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if not args.apply:
        parser.error("la escritura requiere --apply")

    connection = connect_turso_from_env()
    try:
        result = apply_la_colonia_initial_snapshot_turso(
            args.snapshot_json,
            connection=connection,
        )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    print(
        json.dumps(
            {
                "scrape_run_id": LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID,
                "location_id": LA_COLONIA_INITIAL_SNAPSHOT_LOCATION_ID,
                "created": result.created,
                "updated": result.updated,
                "replayed": result.replayed,
                "history_confirmations_skipped": result.history_confirmations_skipped,
                "exact_run_replay": result.exact_run_replay,
                "table_counts": dict(result.table_counts),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
