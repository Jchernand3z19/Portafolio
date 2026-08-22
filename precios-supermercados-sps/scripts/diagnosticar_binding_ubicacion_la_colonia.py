"""CLI cerrada para la radiografía live de binding de ubicación de La Colonia.

No expone flags para cambiar target, política de red, allow-list ni fuse live.
Esos controles permanecen versionados en
``diagnostics.la_colonia_location_binding_capture`` y sólo pueden cambiarse por
un PR explícito y revisado.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from precios_supermercados.diagnostics.la_colonia_location_binding_capture import (
    run_capture,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Radiografía cerrada del binding de ubicación de La Colonia",
    )
    parser.add_argument(
        "--authorization-id",
        required=True,
        help="ID de autorización live previamente versionado y activo",
    )
    parser.add_argument(
        "--output-path",
        default="precios-supermercados-sps/diagnostic-artifacts/location-binding-radiography.json",
        help="Ruta local para el artefacto sanitizado",
    )
    return parser


def _summary(result: object) -> dict[str, object]:
    public = result.public_dict()  # type: ignore[attr-defined]
    binding = public.get("binding_report")
    binding = binding if isinstance(binding, dict) else {}
    return {
        "mode": public.get("mode"),
        "stop_reason": public.get("stop_reason"),
        "available_city_count": len(public.get("available_cities") or []),
        "available_store_count": len(public.get("available_stores") or []),
        "store_selection_observed": public.get("store_selection_observed"),
        "granularity_candidate": binding.get("granularity_candidate"),
        "confidence": binding.get("confidence"),
        "technical_binding_observed": binding.get("technical_binding_observed"),
        "production_authority": False,
        "catalog_accepted": False,
        "extraction_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_capture(
        authorization_id=args.authorization_id,
        output_path=Path(args.output_path),
    )
    print(json.dumps(_summary(result), ensure_ascii=False, sort_keys=True))

    if result.stop_reason is not None:
        return 3
    binding = result.binding_report or {}
    if binding.get("granularity_candidate") == "unknown":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
