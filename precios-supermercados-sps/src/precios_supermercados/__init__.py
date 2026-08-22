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
from .locations import (
    DEFAULT_LOCATION_CATALOG,
    LA_COLONIA_SPS,
    LA_COLONIA_TGU,
    LocationCatalog,
    LocationConfig,
    LocationConfigError,
    LocationGranularity,
    LocationSelectionMode,
    SupermarketConfig,
    build_location_catalog,
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
    "LocationConfigError",
    "LocationGranularity",
    "LocationSelectionMode",
    "SupermarketConfig",
    "LocationConfig",
    "LocationCatalog",
    "DEFAULT_LOCATION_CATALOG",
    "LA_COLONIA_SPS",
    "LA_COLONIA_TGU",
    "build_location_catalog",
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
