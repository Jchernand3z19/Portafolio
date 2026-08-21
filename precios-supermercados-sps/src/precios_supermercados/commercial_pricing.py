"""Derivaciones comerciales puras sobre current/history aceptados.

``reported_regular_price`` nunca participa en el cálculo de reducción real: es
sólo un valor reportado por la fuente. La referencia válida es el
``current_price`` del periodo histórico aceptado inmediatamente anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from .commercial_state import CurrentCommercialOffer, OfferHistoryPeriod


class CommercialPricingError(ValueError):
    """Current/history no reconcilian y no permiten derivar un ahorro seguro."""


@dataclass(frozen=True, slots=True)
class RealPriceReduction:
    """Comparación del precio actual contra el estado aceptado anterior."""

    offer_id: str
    current_price: Decimal | None
    previous_accepted_price: Decimal | None
    reduction_amount: Decimal | None
    reduction_ratio: Decimal | None
    is_real_reduction: bool
    current_observed_at_utc: datetime
    previous_observed_at_utc: datetime | None
    current_scrape_run_id: str
    previous_scrape_run_id: str | None


def evaluate_real_price_reduction(
    current: CurrentCommercialOffer | None,
    history: Sequence[OfferHistoryPeriod],
) -> RealPriceReduction | None:
    """Calcula ahorro real sin usar el precio regular reportado por la fuente.

    El último periodo debe ser el periodo abierto del ``current`` suministrado.
    Si existe un periodo previo, su ``current_price`` es la única referencia
    histórica. Sin ambos precios no se inventa una reducción. Una subida o un
    precio igual producen reducción 0.
    """

    if current is None:
        if history:
            raise CommercialPricingError("existe histórico sin current asociado")
        return None
    if not history:
        raise CommercialPricingError("current no tiene periodo histórico abierto")

    offer = current.validated_offer.offer
    open_period = history[-1]
    if open_period.offer_id != offer.offer_id:
        raise CommercialPricingError("current e histórico pertenecen a offer_id distintos")
    if open_period.valid_to_utc is not None:
        raise CommercialPricingError("el último periodo histórico no está abierto")
    if open_period.state_hash != current.validated_offer.state_hash:
        raise CommercialPricingError("current y periodo abierto tienen state_hash distinto")
    if open_period.last_observed_at_utc != current.last_observed_at_utc:
        raise CommercialPricingError("current e histórico discrepan en última observación")

    previous_period = history[-2] if len(history) >= 2 else None
    if previous_period is not None:
        if previous_period.offer_id != offer.offer_id:
            raise CommercialPricingError("el periodo previo pertenece a otro offer_id")
        if previous_period.valid_to_utc != open_period.valid_from_utc:
            raise CommercialPricingError("los periodos históricos no son contiguos")

    current_price = offer.current_price
    previous_price = (
        previous_period.validated_offer.offer.current_price
        if previous_period is not None
        else None
    )

    reduction_amount: Decimal | None = None
    reduction_ratio: Decimal | None = None
    is_real_reduction = False
    if current_price is not None and previous_price is not None:
        reduction_amount = max(previous_price - current_price, Decimal("0"))
        reduction_ratio = reduction_amount / previous_price
        is_real_reduction = reduction_amount > 0

    return RealPriceReduction(
        offer_id=offer.offer_id,
        current_price=current_price,
        previous_accepted_price=previous_price,
        reduction_amount=reduction_amount,
        reduction_ratio=reduction_ratio,
        is_real_reduction=is_real_reduction,
        current_observed_at_utc=current.last_observed_at_utc,
        previous_observed_at_utc=(
            previous_period.last_observed_at_utc
            if previous_period is not None
            else None
        ),
        current_scrape_run_id=current.last_scrape_run_id,
        previous_scrape_run_id=(
            previous_period.last_confirmed_by_scrape_run_id
            if previous_period is not None
            else None
        ),
    )
