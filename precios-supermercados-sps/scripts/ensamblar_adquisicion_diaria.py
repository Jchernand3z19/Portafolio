#!/usr/bin/env python3
"""Ensambla los handoffs de adquisición más recientes de cada supermercado.

Cada job de adquisición publica un árbol `<retailer>/<run_attempt>/run-artifacts`.
Al reintentar sólo jobs fallidos pueden coexistir intentos distintos dentro del
mismo workflow run. Este ensamblador elige de forma determinista el intento
exitoso más alto de cada retailer y reconstruye un único `run-artifacts/` para
la validación y persistencia existentes.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


EXPECTED = {
    "la_colonia": (
        "sps/full-catalog.json",
        "tgu/full-catalog.json",
    ),
    "los_andes": (
        "los-andes/full-catalog.json",
    ),
    "paiz": (
        "paiz/snapshot-paiz-multiplaza.json",
        "paiz/snapshot-paiz-proceres.json",
    ),
    "colonial": (
        "colonial/full-catalog.json",
    ),
    "walmart": (
        "walmart/snapshot-walmart-sps.json",
        "walmart/snapshot-walmart-tgu-ffaa.json",
        "walmart/snapshot-walmart-tgu-el-sauce.json",
    ),
    "pricesmart": (
        "pricesmart/snapshot-pricesmart-sps.json",
        "pricesmart/snapshot-pricesmart-tgu.json",
    ),
}

OWNED_TOP_LEVEL = {
    "la_colonia": {"sps", "tgu"},
    "los_andes": {"los-andes"},
    "paiz": {"paiz"},
    "colonial": {"colonial"},
    "walmart": {"walmart"},
    "pricesmart": {"pricesmart"},
}


class AssemblyError(RuntimeError):
    pass


def _attempts(root: Path, retailer: str) -> list[tuple[int, Path]]:
    base = root / retailer
    if not base.is_dir():
        return []
    result: list[tuple[int, Path]] = []
    for child in base.iterdir():
        if child.is_symlink() or not child.is_dir() or not child.name.isdigit():
            continue
        attempt = int(child.name)
        if attempt < 1:
            continue
        artifacts = child / "run-artifacts"
        if artifacts.is_dir() and not artifacts.is_symlink():
            result.append((attempt, artifacts))
    return sorted(result)


def _complete(path: Path, required: tuple[str, ...]) -> bool:
    return all((path / relative).is_file() and not (path / relative).is_symlink() for relative in required)


def select_handoffs(root: Path) -> dict[str, tuple[int, Path]]:
    selected: dict[str, tuple[int, Path]] = {}
    for retailer, required in EXPECTED.items():
        valid = [(attempt, path) for attempt, path in _attempts(root, retailer) if _complete(path, required)]
        if not valid:
            raise AssemblyError(f"accepted_retailer_handoff_missing:{retailer}")
        selected[retailer] = valid[-1]
    return selected


def assemble(root: Path, output: Path) -> dict[str, object]:
    selected = select_handoffs(root)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for retailer, (attempt, source) in selected.items():
        allowed = OWNED_TOP_LEVEL[retailer]
        actual = {child.name for child in source.iterdir() if child.is_dir() and not child.is_symlink()}
        unexpected = actual - allowed
        if unexpected:
            raise AssemblyError(f"retailer_handoff_unexpected_directory:{retailer}:{sorted(unexpected)}")
        for top_level in sorted(allowed):
            item = source / top_level
            if not item.is_dir() or item.is_symlink():
                raise AssemblyError(f"retailer_handoff_directory_missing:{retailer}:{top_level}")
            destination = output / top_level
            if destination.exists():
                raise AssemblyError(f"retailer_handoff_collision:{top_level}")
            shutil.copytree(item, destination, symlinks=False)
    for retailer, required in EXPECTED.items():
        for relative in required:
            if not (output / relative).is_file():
                raise AssemblyError(f"assembled_required_file_missing:{retailer}:{relative}")
    return {
        "schema": "precios-sps-daily-acquisition-assembly/v1",
        "retailers": {
            retailer: {"run_attempt": attempt, "required_files": list(EXPECTED[retailer])}
            for retailer, (attempt, _) in sorted(selected.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = assemble(args.input, args.output)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssemblyError as exc:
        raise SystemExit(str(exc)) from exc
