"""Pipeline común RawProduct -> NormalizedOffer -> ValidatedOffer.

La capa es deliberadamente backend-neutral: no concede aceptación de catálogo, no
resuelve una ciudad comercial y no persiste. El ``location_id`` del RawProduct se
preserva hasta que exista un binding técnico explícito; por tanto un contexto
fuente como ``la_colonia_online`` no se convierte por inferencia en SPS.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .enums import AvailabilityStatus, LocationStatus
from .identifiers import (
    canonicalize_gtin,
    canonicalize_text,
    generate_gtin_product_id,
    generate_offer_id,
    generate_pending_product_id,
    generate_source_product_id,
    generate_state_hash,
)
from .locations import LocationConfigError, validate_source_location_context
from .models import NormalizedOffer, RawProduct, ValidatedOffer


class OfferNormalizationError(ValueError):
    """La evidencia raw no puede transformarse sin inventar información."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


ProductIdResolver = Callable[[RawProduct, str], str | None]


@dataclass(frozen=True, slots=True)
class PresentationComponents:
    """Componentes de presentación sólo cuando la fuente los permite demostrar."""

    unit_count: int | None = None
    content_per_unit: Decimal | None = None
    measurement_unit: str | None = None
    total_content: Decimal | None = None


_UNIT_ALIASES = {
    "lb": "lb",
    "lbs": "lb",
    "libra": "lb",
    "libras": "lb",
    "kg": "kg",
    "g": "g",
    "gr": "g",
    "gramo": "g",
    "gramos": "g",
    "ml": "ml",
    "l": "l",
    "lt": "l",
    "litro": "l",
    "litros": "l",
    "oz": "oz",
    "un": "unit",
    "und": "unit",
    "uds": "unit",
    "unidad": "unit",
    "unidades": "unit",
    "ft": "ft",
}
_MULTIPACK_RE = re.compile(
    r"^\s*(?P<count>\d+)\s*[x×]\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zÁÉÍÓÚáéíóú]+)\s*$",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(
    r"^\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zÁÉÍÓÚáéíóú]+)\s*$",
    re.IGNORECASE,
)
_WEIGHT_RE = re.compile(
    r"^\s*x\s*(?P<unit>[A-Za-zÁÉÍÓÚáéíóú]+)\s*$",
    re.IGNORECASE,
)
_UNIT_ONLY_RE = re.compile(r"^\s*(?:un|und|uds|unidad|unidades)\s*$", re.IGNORECASE)


def _decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise OfferNormalizationError(f"{field_name}_invalid")
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise OfferNormalizationError(f"{field_name}_invalid") from exc
    if not result.is_finite() or result <= 0:
        raise OfferNormalizationError(f"{field_name}_invalid")
    return result


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _unit(value: str | None) -> str | None:
    if value is None:
        return None
    return _UNIT_ALIASES.get(value.strip().casefold())


def parse_presentation(raw: RawProduct) -> PresentationComponents:
    """Interpreta únicamente patrones explícitos; lo ambiguo queda pendiente.

    Para productos vendidos por peso, ``measurement_unit`` + ``unit_multiplier``
    de la fuente constituyen evidencia suficiente. Para productos empacados se
    usa la presentación visible. Un simple ``measurementUnit='un'`` no se toma
    como contenido cuando la presentación falta.
    """

    values = raw.raw_values
    weighted = values.get("weighted_product") is True
    source_unit = _unit(_text(values.get("measurement_unit")))
    multiplier = _decimal(values.get("unit_multiplier"), "unit_multiplier")

    if weighted and source_unit is not None and multiplier is not None:
        return PresentationComponents(
            unit_count=1,
            content_per_unit=multiplier,
            measurement_unit=source_unit,
            total_content=multiplier,
        )

    presentation = _text(raw.source_presentation)
    if presentation is None:
        return PresentationComponents()

    if _UNIT_ONLY_RE.fullmatch(presentation):
        return PresentationComponents(
            unit_count=1,
            content_per_unit=Decimal("1"),
            measurement_unit="unit",
            total_content=Decimal("1"),
        )

    match = _MULTIPACK_RE.fullmatch(presentation)
    if match is not None:
        unit = _unit(match.group("unit"))
        if unit is None:
            return PresentationComponents()
        count = int(match.group("count"))
        amount = _decimal(match.group("amount"), "presentation_amount")
        assert amount is not None
        if count <= 0:
            return PresentationComponents()
        return PresentationComponents(
            unit_count=count,
            content_per_unit=amount,
            measurement_unit=unit,
            total_content=amount * count,
        )

    match = _SINGLE_RE.fullmatch(presentation)
    if match is not None:
        unit = _unit(match.group("unit"))
        amount = _decimal(match.group("amount"), "presentation_amount")
        if unit is None or amount is None:
            return PresentationComponents()
        if unit == "unit":
            count = int(amount) if amount == amount.to_integral_value() else 0
            if count <= 0:
                return PresentationComponents()
            return PresentationComponents(
                unit_count=count,
                content_per_unit=Decimal("1"),
                measurement_unit="unit",
                total_content=Decimal(count),
            )
        return PresentationComponents(
            unit_count=1,
            content_per_unit=amount,
            measurement_unit=unit,
            total_content=amount,
        )

    match = _WEIGHT_RE.fullmatch(presentation)
    if match is not None:
        unit = _unit(match.group("unit"))
        if unit is not None and multiplier is not None:
            return PresentationComponents(
                unit_count=1,
                content_per_unit=multiplier,
                measurement_unit=unit,
                total_content=multiplier,
            )

    return PresentationComponents()


def _availability(values: Mapping[str, Any]) -> AvailabilityStatus:
    value = values.get("availability")
    if value is None:
        raise OfferNormalizationError("availability_missing")
    try:
        return value if isinstance(value, AvailabilityStatus) else AvailabilityStatus(value)
    except (TypeError, ValueError) as exc:
        raise OfferNormalizationError("availability_invalid") from exc


def _promotion(values: Mapping[str, Any]) -> bool:
    value = values.get("is_promotion")
    if not isinstance(value, bool):
        raise OfferNormalizationError("is_promotion_invalid")
    return value


def _default_product_id(raw: RawProduct, source_product_id: str) -> str:
    gtin = canonicalize_gtin(_text(raw.raw_values.get("ean")))
    if gtin is not None:
        return generate_gtin_product_id(gtin)
    return generate_pending_product_id(source_product_id)


def normalize_raw_product(
    raw: RawProduct,
    *,
    currency: str,
    product_id_resolver: ProductIdResolver | None = None,
) -> NormalizedOffer:
    """Normaliza una observación sin cambiar su contexto de ubicación raw."""

    if not isinstance(raw, RawProduct):
        raise OfferNormalizationError("raw_product_invalid")
    try:
        validate_source_location_context(
            supermarket_id=raw.supermarket_id,
            location_id=raw.location_id,
            location_status=raw.location_status,
            location_evidence=raw.location_evidence,
            location_confidence=raw.location_confidence,
        )
    except LocationConfigError as exc:
        raise OfferNormalizationError(str(exc)) from exc

    source_product_id = generate_source_product_id(
        raw.supermarket_id,
        raw.source_key_type,
        raw.source_key,
    )
    if product_id_resolver is None:
        product_id = _default_product_id(raw, source_product_id)
    else:
        product_id = product_id_resolver(raw, source_product_id)
        if product_id is None:
            product_id = generate_pending_product_id(source_product_id)
    if not isinstance(product_id, str) or not product_id.strip():
        raise OfferNormalizationError("product_id_invalid")

    offer_id = generate_offer_id(
        raw.supermarket_id,
        raw.location_id,
        source_product_id,
    )
    normalized_name = canonicalize_text(raw.source_name)
    if normalized_name is None:
        raise OfferNormalizationError("normalized_name_missing")

    values = raw.raw_values
    presentation = parse_presentation(raw)
    current_price = _decimal(values.get("current_price"), "current_price")
    reported_regular_price = _decimal(
        values.get("reported_regular_price"),
        "reported_regular_price",
    )
    availability = _availability(values)
    if availability is AvailabilityStatus.IN_STOCK and current_price is None:
        raise OfferNormalizationError("in_stock_current_price_missing")

    barcode = _text(values.get("ean"))
    category = _text(raw.source_category)
    subcategory = _text(values.get("subcategory"))

    return NormalizedOffer(
        supermarket_id=raw.supermarket_id,
        location_id=raw.location_id,
        source_product_id=source_product_id,
        source_key_type=raw.source_key_type,
        source_key=raw.source_key,
        product_id=product_id,
        offer_id=offer_id,
        source_name=raw.source_name,
        product_url=raw.product_url,
        normalized_name=normalized_name,
        normalized_brand=_text(raw.source_brand),
        category=category,
        subcategory=subcategory,
        variant=None,
        unit_count=presentation.unit_count,
        content_per_unit=presentation.content_per_unit,
        measurement_unit=presentation.measurement_unit,
        total_content=presentation.total_content,
        currency=currency,
        current_price=current_price,
        is_promotion=_promotion(values),
        availability=availability,
        location_status=raw.location_status,
        observed_at_utc=raw.observed_at_utc,
        scrape_run_id=raw.scrape_run_id,
        extractor_version=raw.extractor_version,
        schema_version=raw.schema_version,
        source_url=raw.source_url,
        source_sku=raw.source_sku,
        source_brand=raw.source_brand,
        source_presentation=raw.source_presentation,
        source_category=raw.source_category,
        image_url=raw.image_url,
        barcode=barcode,
        reported_regular_price=reported_regular_price,
        unit_price=None,
        unit_price_basis=None,
        location_evidence=raw.location_evidence,
        location_confidence=raw.location_confidence,
        raw_values=raw.raw_values,
    )


def validate_normalized_offer(
    offer: NormalizedOffer,
    *,
    validated_at_utc: datetime,
    quality_events: Sequence[str] = (),
) -> ValidatedOffer:
    """Sella hash y eventos explícitos después de crear la oferta común."""

    if not isinstance(offer, NormalizedOffer):
        raise OfferNormalizationError("normalized_offer_invalid")
    supplied = list(quality_events)
    if offer.product_id.startswith("prod_pending_"):
        supplied.append("pending_product_mapping")
    if offer.location_status is LocationStatus.UNKNOWN:
        supplied.append("pending_location_binding")
    return ValidatedOffer(
        offer=offer,
        state_hash=generate_state_hash(offer),
        validated_at_utc=validated_at_utc,
        quality_events=tuple(dict.fromkeys(supplied)),
    )


def normalize_and_validate_raw_products(
    raw_products: Sequence[RawProduct],
    *,
    currency: str,
    validated_at_utc: datetime,
    product_id_resolver: ProductIdResolver | None = None,
    quality_events: Sequence[str] = (),
) -> tuple[ValidatedOffer, ...]:
    """Ejecuta la frontera común para un batch ya extraído y completo."""

    if isinstance(raw_products, (str, bytes)) or not isinstance(raw_products, Sequence):
        raise OfferNormalizationError("raw_products_sequence_invalid")
    return tuple(
        validate_normalized_offer(
            normalize_raw_product(
                raw,
                currency=currency,
                product_id_resolver=product_id_resolver,
            ),
            validated_at_utc=validated_at_utc,
            quality_events=quality_events,
        )
        for raw in raw_products
    )
