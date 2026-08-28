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


def test_positive_quantity_preserves_base_in_stock_semantics() -> None:
    expected = operational_v2.BASE_AVAILABILITY(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (Decimal("3"),),
    )
    observed = operational_v2._operational_availability(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (Decimal("3"),),
    )

    assert observed == expected
    assert observed[0] is AvailabilityStatus.IN_STOCK


def test_missing_quantity_preserves_base_unknown_semantics() -> None:
    expected = operational_v2.BASE_AVAILABILITY(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (),
    )
    observed = operational_v2._operational_availability(
        Decimal("25.00"),
        ({"sellerId": "1"},),
        (),
    )

    assert observed == expected
    assert observed[0] is AvailabilityStatus.UNKNOWN


def test_missing_seller_preserves_base_unknown_semantics() -> None:
    expected = operational_v2.BASE_AVAILABILITY(None, (), ())
    observed = operational_v2._operational_availability(None, (), ())

    assert observed == expected
    assert observed[0] is AvailabilityStatus.UNKNOWN
