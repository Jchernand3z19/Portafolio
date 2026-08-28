from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import obtener_catalogo_sps_la_colonia_operativo_v2 as operational_v2  # noqa: E402
from precios_supermercados.enums import AvailabilityStatus  # noqa: E402


def test_zero_quantity_with_price_is_out_of_stock() -> None:
    status, evidence = operational_v2._operational_availability(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (Decimal("0"),),
    )

    assert status is AvailabilityStatus.OUT_OF_STOCK
    assert evidence == "available_quantity_zero"


def test_positive_quantity_is_in_stock() -> None:
    status, evidence = operational_v2._operational_availability(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (Decimal("3"),),
    )

    assert status is AvailabilityStatus.IN_STOCK
    assert evidence == "available_quantity_positive"


def test_positive_price_without_quantity_remains_in_stock() -> None:
    status, evidence = operational_v2._operational_availability(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (),
    )

    assert status is AvailabilityStatus.IN_STOCK
    assert evidence == "price_positive_without_quantity"


def test_missing_seller_remains_unknown() -> None:
    status, evidence = operational_v2._operational_availability(
        None,
        (),
        (),
    )

    assert status is AvailabilityStatus.UNKNOWN
    assert evidence == "seller_absent"
