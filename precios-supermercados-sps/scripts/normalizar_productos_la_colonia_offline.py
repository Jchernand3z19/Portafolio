#!/usr/bin/env python3
"""Genera la dimensión offline de productos de La Colonia desde un CSV sanitizado."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from precios_supermercados.la_colonia_product_normalization import (  # noqa: E402
    OUTPUT_COLUMNS,
    load_override_registry,
    normalize_catalog_rows,
)

DEFAULT_REGISTRY = (
    PROJECT_ROOT
    / "config"
    / "supermercados"
    / "la-colonia-product-normalization-overrides"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()

    with args.input_csv.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = tuple(csv.DictReader(handle))
    registry = load_override_registry(args.registry)
    normalized = normalize_catalog_rows(source_rows, registry=registry)

    unresolved = [
        row for row in normalized if row["normalization_status"] != "ready"
    ]
    if unresolved:
        print(
            f"normalization_not_ready={len(unresolved)}; "
            f"first_source_key={unresolved[0]['source_key']}",
            file=sys.stderr,
        )
        return 2

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized)

    print(f"products={len(normalized)} pending=0 output={args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
