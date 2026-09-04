#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

# Archivo temporal: este commit fuerza la auditoría final sobre el código corregido.
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "precios_supermercados" / "product_homologation.py"
TESTS = ROOT / "tests" / "test_product_homologation.py"


def replace_once(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return False
    if text.count(old) != 1:
        raise SystemExit(f"replacement_contract_failed:{path}:{text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def main() -> None:
    changed = False
    changed |= replace_once(
        SOURCE,
        '    if _AMBIGUOUS_PACK_RE.search(value):\n        return None, True\n',
        '    pack_scan_value = re.sub(\n'
        '        r"(?i)\\b(?:doy|tetra)\\s+pack\\b",\n'
        '        "",\n'
        '        value,\n'
        '    )\n'
        '    if _AMBIGUOUS_PACK_RE.search(pack_scan_value):\n'
        '        return None, True\n',
    )

    marker = '''def test_single_unit_never_matches_multipack_candidate() -> None:\n'''
    addition = '''def test_packaging_words_doy_pack_and_tetra_pack_are_not_multipacks() -> None:\n    doy, doy_status = resolve_presentation(\n        product(\n            "a",\n            "la_colonia",\n            "Mayonesa Hellmanns Doy Pack 380 Gr",\n            presentation="380 Gr",\n        )\n    )\n    tetra, tetra_status = resolve_presentation(\n        product(\n            "b",\n            "la_colonia",\n            "Jugo Del Monte Néctar De Pera Tetra Pack 200 Ml",\n            presentation="200 Ml",\n        )\n    )\n\n    assert doy is not None and doy.total_base == Decimal("380")\n    assert doy_status == "confirmed"\n    assert tetra is not None and tetra.total_base == Decimal("200")\n    assert tetra_status == "confirmed"\n\n\n'''
    test_text = TESTS.read_text(encoding="utf-8")
    if addition not in test_text:
        if test_text.count(marker) != 1:
            raise SystemExit(f"test_marker_contract_failed:{test_text.count(marker)}")
        TESTS.write_text(test_text.replace(marker, addition + marker, 1), encoding="utf-8")
        changed = True

    print("PATCH_CHANGED=" + ("1" if changed else "0"))


if __name__ == "__main__":
    main()
