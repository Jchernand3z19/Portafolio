from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


colonial = _load("obtener_catalogo_colonial_operativo")
walmart = _load("obtener_catalogo_walmart_operativo")
pricesmart = _load("obtener_catalogo_pricesmart_operativo")


def test_walmart_operational_contract_reuses_proven_store_binding() -> None:
    seller = "walmarthnwm947"
    assert walmart.region_id(seller) == base64.b64encode(("SW#" + seller).encode()).decode()
    assert walmart.SALES_CHANNEL == "1"
    assert walmart.PAGE_SIZE == 100
    assert walmart.CATEGORY2_PARTITIONS == {"articulos-para-el-hogar", "ropa-y-zapateria"}
    assert walmart.MAX_REQUESTS_HARD == 700


def test_pricesmart_operational_contract_is_bounded_to_two_accepted_clubs() -> None:
    assert pricesmart.category_url("G10D03", "Alimentos") == (
        "https://www.pricesmart.com/es-hn/categoria/Alimentos-G10D03/G10D03"
    )
    assert len(pricesmart.ROOTS) == 26
    assert {key for key, _ in pricesmart.ROOTS} >= {"U11D13", "J10D44", "G10D03"}
    sps_fields = pricesmart.fields_for_club("6603")
    assert "price_HN_6603" in sps_fields
    assert "availability_HN_6603" in sps_fields
    assert "_HN_6604" not in sps_fields
    assert pricesmart.MAX_REQUESTS_HARD == 80


@pytest.mark.parametrize(
    ("module", "argv"),
    [
        (colonial, ["prog", "--output", "out"]),
        (
            walmart,
            ["prog", "--output-directory", "out", "--raw-directory", "raw", "--evidence-output", "evidence.json"],
        ),
        (
            pricesmart,
            ["prog", "--output-directory", "out", "--raw-directory", "raw", "--evidence-output", "evidence.json"],
        ),
    ],
)
def test_operational_full_catalog_entrypoints_fail_closed_without_both_fuses(monkeypatch, module, argv) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit, match="explicit_live_full_catalog_authorization_required"):
        module.main()
