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
from .identifiers import generate_state_hash


class CommercialPricingError(ValueError):
    """Current/history no reconcilian y no permiten derivar un ahorro seguro."""


@dataclass(frozen=True, slots=True)
class RealPriceReduction:
    """Comparación del precio actual contra el estado aceptado anterior."""

    offer_id: str
    currency: str
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

    ``history`` debe ser una cadena íntegra y ordenada de periodos aceptados, con
    exactamente un periodo abierto al final y reconciliado con ``current``. Si
    existe un periodo previo, su ``current_price`` es la única referencia. Sin
    ambos precios no se inventa una reducción. Una subida o igualdad produce 0.
    """

    if current is None:
        if history:
            raise CommercialPricingError("existe histórico sin current asociado")
        return None
    if not history:
        raise CommercialPricingError("current no tiene periodo histórico abierto")

    validated = current.validated_offer
    offer = validated.offer
    if generate_state_hash(offer) != validated.state_hash:
        raise CommercialPricingError("current contiene state_hash inválido")

    _validate_history_chain(offer.offer_id, offer.currency, history)
    open_period = history[-1]

    if open_period.state_hash != validated.state_hash:
        raise CommercialPricingError("current y periodo abierto tienen state_hash distinto")
    if open_period.valid_from_utc != current.first_observed_at_utc:
        raise CommercialPricingError("current e histórico discrepan en apertura")
    if open_period.last_observed_at_utc != current.last_observed_at_utc:
        raise CommercialPricingError("current e histórico discrepan en última observación")
    if open_period.last_confirmed_by_scrape_run_id != current.last_scrape_run_id:
        raise CommercialPricingError("current e histórico discrepan en última ejecución")

    previous_period = history[-2] if len(history) >= 2 else None
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
        currency=offer.currency,
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


def _validate_history_chain(
    offer_id: str,
    currency: str,
    history: Sequence[OfferHistoryPeriod],
) -> None:
    open_count = 0
    previous: OfferHistoryPeriod | None = None
    for index, period in enumerate(history):
        validated = period.validated_offer
        period_offer = validated.offer
        if period.offer_id != offer_id or period_offer.offer_id != period.offer_id:
            raise CommercialPricingError("current e histórico pertenecen a offer_id distintos")
        if period_offer.currency != currency:
            raise CommercialPricingError("current e histórico usan monedas distintas")
        if validated.state_hash != period.state_hash:
            raise CommercialPricingError("periodo y ValidatedOffer tienen state_hash distinto")
        if generate_state_hash(period_offer) != period.state_hash:
            raise CommercialPricingError("periodo histórico contiene state_hash inválido")

        if period.valid_to_utc is None:
            open_count += 1
            if index != len(history) - 1:
                raise CommercialPricingError("existe un periodo histórico abierto intermedio")
        elif period.valid_to_utc <= period.valid_from_utc:
            raise CommercialPricingError("periodo histórico con intervalo no positivo")

        if period.last_observed_at_utc < period.valid_from_utc:
            raise CommercialPricingError("periodo histórico con última observación inválida")
        if period.valid_to_utc is not None and period.last_observed_at_utc > period.valid_to_utc:
            raise CommercialPricingError("periodo histórico observado después de su cierre")

        if previous is not None and previous.valid_to_utc != period.valid_from_utc:
            raise CommercialPricingError("los periodos históricos no son contiguos")
        previous = period

    if open_count != 1 or history[-1].valid_to_utc is not None:
        raise CommercialPricingError("el último periodo histórico no está abierto")
