"""Derivaciones comerciales puras sobre current/history aceptados.

``reported_regular_price`` nunca participa en el cálculo de reducción real: es
sólo un valor reportado por la fuente. La referencia válida es el
``current_price`` del periodo histórico aceptado inmediatamente anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .commercial_state import InMemoryCommercialState


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
    state: InMemoryCommercialState,
    offer_id: str,
) -> RealPriceReduction | None:
    """Calcula ahorro real sin usar el precio regular reportado por la fuente.

    El periodo abierto representa el estado actual. Si existe un periodo previo,
    su ``current_price`` es la única referencia histórica. Sin ambos precios no
    se inventa una reducción. Una subida o un precio igual producen reducción 0.
    """

    current = state.current(offer_id)
    if current is None:
        return None

    history = state.history(offer_id)
    previous_period = history[-2] if len(history) >= 2 else None
    current_price = current.validated_offer.offer.current_price
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
        offer_id=offer_id,
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
