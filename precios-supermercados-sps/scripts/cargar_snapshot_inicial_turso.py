#!/usr/bin/env python3
"""Materializa o carga el snapshot inicial aprobado de La Colonia para Turso.

El comando no descarga el catálogo ni habilita tráfico live. El archivo recibido se
valida por digest, metadata y conteos dentro de ``la_colonia_initial_snapshot``.
Por defecto conecta a Turso con ``TURSO_DATABASE_URL`` y ``TURSO_AUTH_TOKEN``.
Con ``--sqlite-output`` crea primero una base SQLite local verificable, apta para
la importación inicial mediante la interfaz de Turso sin miles de escrituras HTTP.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from precios_supermercados.la_colonia_initial_snapshot import (
    LA_COLONIA_INITIAL_SNAPSHOT_LOCATION_ID,
    LA_COLONIA_INITIAL_SNAPSHOT_RUN_ID,
    apply_la_colonia_initial_snapshot_turso,
)
from precios_supermercados.turso_persistence import connect_turso_from_env


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materializa o carga el snapshot inicial aprobado de La Colonia para Turso",
    )
    parser.add_argument(
        "--snapshot-json",
        required=True,
        type=Path,
        help="Ruta al full-catalog.json aprobado",
    )
    parser.add_argument(
        "--sqlite-output",
        type=Path,
        help="Crea una base SQLite local nueva en vez de conectar a Turso Cloud",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Confirma explícitamente la escritura durable",
    )
    return parser


def _local_connection(path: Path) -> sqlite3.Connection:
    target = path.expanduser().resolve()
    if target.exists():
        raise SystemExit(f"sqlite_output_already_exists:{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(target)


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if not args.apply:
        parser.error("la escritura requiere --apply")

    connection = (
        _local_connection(args.sqlite_output)
        if args.sqlite_output is not None
        else connect_turso_from_env()
    )
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
                "storage": "sqlite" if args.sqlite_output is not None else "turso",
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
