#!/usr/bin/env python3
"""Carga una sola vez el snapshot inicial aprobado de La Colonia en BigQuery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from google.cloud import bigquery  # noqa: E402

from precios_supermercados.google_bigquery_client import (  # noqa: E402
    GoogleCloudBigQueryClient,
)
from precios_supermercados.la_colonia_initial_snapshot import (  # noqa: E402
    apply_la_colonia_initial_snapshot_bigquery,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Confirma que se desea ejecutar bootstrap y escritura BigQuery.",
    )
    args = parser.parse_args(argv)

    if not args.apply:
        parser.error("la escritura requiere --apply")
    if not args.project_id.strip():
        parser.error("--project-id no puede estar vacío")
    if not args.dataset_id.strip():
        parser.error("--dataset-id no puede estar vacío")

    sdk_client = bigquery.Client(project=args.project_id.strip())
    result = apply_la_colonia_initial_snapshot_bigquery(
        args.snapshot_json,
        client=GoogleCloudBigQueryClient(sdk_client),
        dataset_id=args.dataset_id.strip(),
    )
    print(
        json.dumps(
            {
                "scrape_run_id": result.scrape_run_id,
                "created": result.created,
                "updated": result.updated,
                "replayed_rows": result.replayed_rows,
                "exact_run_replay": result.exact_run_replay,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
