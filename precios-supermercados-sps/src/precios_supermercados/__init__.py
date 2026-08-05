"""Fundación común del proyecto Precios de Supermercados de SPS."""

from .enums import (
    AvailabilityStatus,
    ChangeType,
    LocationStatus,
    QualityEventCategory,
    QualityEventSeverity,
    ReviewStatus,
    RunStatus,
    SourceKeyType,
)
from .identifiers import (
    canonicalize_text,
    canonicalize_url,
    generate_offer_id,
    generate_source_product_id,
    generate_state_hash,
    select_source_key,
)
from .models import NormalizedOffer, RawProduct, ValidatedOffer

__all__ = [
    "AvailabilityStatus",
    "ChangeType",
    "LocationStatus",
    "QualityEventCategory",
    "QualityEventSeverity",
    "ReviewStatus",
    "RunStatus",
    "SourceKeyType",
    "RawProduct",
    "NormalizedOffer",
    "ValidatedOffer",
    "canonicalize_text",
    "canonicalize_url",
    "select_source_key",
    "generate_source_product_id",
    "generate_offer_id",
    "generate_state_hash",
]
