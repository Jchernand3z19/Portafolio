"""CLI cerrada para observación del binding de ubicación de La Colonia.

No expone flags para cambiar target, política de red, allow-list ni fuse live.
Puede usar el mecanismo histórico por authorization-id o la autorización permanente
pública read-only vigente desde 2026-08-23T21:02:02Z.
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
        description="Observación cerrada del binding de ubicación de La Colonia",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--authorization-id",
        help="ID histórico de autorización live versionado y activo",
    )
    mode.add_argument(
        "--standing-public-read-only",
        action="store_true",
        help="Usa la autorización permanente para observación pública read-only",
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
        standing_public_read_only=bool(args.standing_public_read_only),
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
